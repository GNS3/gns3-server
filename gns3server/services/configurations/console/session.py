"""One console session (a capture or a startup replay): login, prompts, commands. Runs as a subprocess.

``session_runner`` starts ``python -m ...console.session`` for every session. The request arrives as JSON on stdin
(so credentials never appear in a command line), is validated, and a ``ConsoleSession`` runs it against the
loopback bridge. The only thing written back is one length-prefixed JSON result; device and library diagnostics are
never emitted. A session that hangs or floods is killed by the runner without touching the compute's event loop.
"""

import base64
import codecs
import json
import logging
import sys
import time
from contextlib import contextmanager

from telnetlib3.telnetlib import Telnet

from gns3server.schemas.configurations import is_single_line, normalize_device_type

from ..shared.errors import CaptureFailure
from ..shared.failure_context import failure_context
from .platforms import get_platform, get_platforms
from .prompts import LOGIN_PROMPT, PASSWORD_PROMPT, PROMPT, last_line, prompt_tail
from .replay import restore_seconds

MAX_BYTES = 2 * 1024 * 1024  # The largest transcript a session reads (four times that for a replay).
STARTUP_APPLY_SECONDS = 590  # A boot-time apply waits for the guest's own boot as well.
CANCEL = "\x03"  # Ctrl-C: cancels a prompt that asks for a value a replay cannot give.


class ConsoleSession:
    def __init__(self, payload):
        self.payload = payload
        self.platform = get_platform(payload["device_type"])
        self.driver = self.platform.name
        self.setup_dialog = self.platform.setup_dialog() if self.platform.setup_dialog else None
        self.connection = Telnet()
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.received = 0
        self.progress = {}
        self.last_output = ""
        seconds = restore_seconds(payload["content"]) if "content" in payload else 25
        self.expires = time.monotonic() + (STARTUP_APPLY_SECONDS if payload.get("wait_ready") else seconds)

    def mark(self, phase, command=None, index=None, total=None):
        """Record the stage being run so a failure can say where it happened."""
        if "content" not in self.payload:
            return
        self.progress = {"phase": phase}
        if command is not None:
            self.progress["command"] = command
        if index is not None:
            self.progress["command_index"] = index
            if total is not None:
                self.progress["command_total"] = total

    def snapshot(self, *, soft=False):
        """Failure context (masked later by failure_context); empty outside restores."""
        if not self.progress:
            return {}
        context = dict(self.progress)
        if soft and not context.get("device_error") and self.last_output:
            context["device_error"] = self.last_output
        return context

    @contextmanager
    def reporting_progress(self):
        """Give a failure that carries no context the stage the session was in."""
        try:
            yield
        except CaptureFailure as error:
            if not error.context:
                error.context = self.snapshot()
            raise

    def failure(self, code):
        """A CaptureFailure for a response that was read but not accepted."""
        error = CaptureFailure(code)
        error.context = self.snapshot(soft=True)
        return error

    def read(self):
        if time.monotonic() >= self.expires:
            raise CaptureFailure("console_incomplete_output")
        data = self.connection.read_very_eager()
        self.received += len(data)
        if self.received > MAX_BYTES * (4 if "content" in self.payload else 1):
            raise CaptureFailure("console_output_limit")
        if not data:
            time.sleep(0.01)
        try:
            return self.decoder.decode(data)
        except UnicodeError:
            raise CaptureFailure("console_invalid_encoding") from None

    def send(self, command):
        self.connection.write((command + "\r").encode("utf-8"))

    def safe_tail(self, text):
        return prompt_tail(text, operational=self.platform.operational)

    def startup_prompt(self, tail, normalized):
        if "content" not in self.payload:
            return False, normalized
        if self.platform.boot_dialog(self, tail):
            return True, normalized
        leave = self.platform.startup_exit(tail) if not normalized else None
        if leave:
            self.send(leave)
            return True, True
        return False, normalized

    def enable_prompt(self, tail, enabling):
        if self.platform.strict_prompt:
            raise CaptureFailure("console_unsafe_mode")
        if tail.endswith("#"):
            return False
        if enabling:
            raise CaptureFailure("console_authentication_failed", console_reusable=True)
        if not self.platform.enable:
            raise CaptureFailure("console_not_ready")
        self.send("enable")
        return True

    def login(self):
        buffer = ""
        sent = set()
        enabling = False
        normalized_mode = False
        self.send("")
        while True:
            buffer += self.read()
            if self.setup_dialog:
                handled, command = self.setup_dialog.respond(buffer)
                if handled:
                    if command is not None:
                        self.send(command)
                        buffer = ""
                    continue
            transitioned, normalized_mode = self.startup_prompt(last_line(buffer), normalized_mode)
            if transitioned:
                buffer = ""
                continue
            tail = self.safe_tail(buffer)
            operational = self.platform.operational_prompt(tail)
            if operational:
                return operational
            if LOGIN_PROMPT.fullmatch(tail):
                self.credential("username", sent)
                buffer = ""
            elif PASSWORD_PROMPT.fullmatch(tail):
                self.credential("enable_secret" if enabling else "password", sent)
                buffer = ""
            elif PROMPT.fullmatch(tail):
                enabling = self.enable_prompt(tail, enabling)
                if not enabling:
                    return tail
                buffer = ""

    def credential(self, key, sent):
        value = self.payload[key]
        if key == "enable_secret" and not value and not self.platform.empty_enable:
            raise CaptureFailure("console_enable_secret_required", console_reusable=True)
        empty_allowed = (key == "enable_secret" and self.platform.empty_enable) or (
            key == "password" and self.platform.empty_password
        )
        if key in sent or (not value and not empty_allowed):
            raise CaptureFailure("console_authentication_failed", console_reusable=True)
        if key == "username":
            value += self.platform.username_suffix
        self.send(value)
        sent.add(key)

    def wait(
        self,
        predicate,
        *,
        echo=None,
        error_code="configuration_apply_failed",
        parser=None,
        pager=None,
        check_errors=True,
    ):
        """Consume one exchange, preserving framing and sharing error/echo handling."""
        buffer = ""
        quiet = 0
        while True:
            data = self.read()
            quiet = 0 if data else quiet + 1
            if pager is not None:
                advance = pager.feed(data)
                buffer = pager.buffer
                if advance:
                    self.connection.write(b" ")
                    continue
            else:
                buffer += data
            if parser is not None:
                content = parser(buffer)
                if content is not None:
                    return content
                continue
            response = self._without_echo(buffer, echo)
            if response is None:
                continue
            if check_errors and self.platform.has_error(response):
                error_line = self.platform.first_error_line(response)
                if self.platform.tolerates(error_line):
                    check_errors = False  # Already configured: read on to the prompt.
                else:
                    if self.progress:
                        self.progress["device_error"] = error_line
                    raise CaptureFailure(error_code)
            if predicate(response, last_line(response)):
                return buffer
            if self.stuck_at_input_prompt(response, quiet):
                self.connection.write(CANCEL.encode())
                if self.progress:
                    self.progress["device_error"] = f"{last_line(response).strip()} a value is required"
                raise CaptureFailure(error_code)

    @staticmethod
    def _without_echo(buffer, echo):
        """The reply to a command without its echo; None while the echo itself is still arriving."""
        if echo is None:
            return buffer
        normalized = buffer.replace("\r\n", "\n").replace("\r", "\n")
        expected = echo.replace("\r\n", "\n").replace("\r", "\n") + "\n"
        if expected.startswith(normalized):
            return None
        return normalized[len(expected) :] if normalized.startswith(expected) else buffer

    def execute(self, value, *, prompt=None, preparation=False):
        self.send(value)
        if self.progress:
            self.progress["command"] = value
            self.progress.pop("device_error", None)

        def predicate(text, tail):
            return self.safe_tail(text) == prompt if preparation else self.platform.command_prompt.fullmatch(tail)

        with self.reporting_progress():
            response = self.wait(
                predicate,
                echo=value,
                error_code="console_not_ready" if preparation else "configuration_apply_failed",
            )
        self.last_output = self.first_output_line(response, value)
        return response

    def stuck_at_input_prompt(self, response, quiet):
        """The device went quiet at a prompt that asks for a missing value (not a command prompt)."""
        pattern = self.platform.input_prompt
        if pattern is None or quiet < 20 or "content" not in self.payload:  # Only a replay sends commands.
            return False
        return pattern.fullmatch(last_line(response).strip()) is not None

    def first_output_line(self, response, value):
        """First device line after the echoed command, for diagnostics only."""
        if "content" not in self.payload:
            return ""
        lines = response.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for line in lines:
            line = line.strip()
            if line and line != value.strip() and not self.platform.command_prompt.fullmatch(line):
                return line
        return ""

    def capture(self, value, prompt):
        self.send(value)
        parser = self.platform.parser
        return self.wait(
            None,
            parser=lambda text: parser(text, prompt),
            pager=self.platform.pager() if self.platform.pager else None,
        )

    def collect(self):
        content = self.payload.get("content")
        if content is not None:
            self.platform.preflight(content)
        try:
            with self.reporting_progress():
                self.connection.open("127.0.0.1", self.payload["port"], timeout=5)
                self.mark("login")
                prompt = self.login()
                for position, value in enumerate(self.platform.commands, 1):
                    self.mark("prepare", value, position, len(self.platform.commands))
                    self.execute(value, prompt=prompt, preparation=True)
                self.mark("prepare")
                if content is not None:
                    self.platform.restore(self, content)
                    return b"applied\n"
                if self.payload.get("save") is True:
                    self.platform.save(self)
                value = self.platform.export_command(self, prompt, backup=self.payload.get("backup", False))
                return self.capture(value, prompt)
        finally:
            self.connection.close()


# ---- The subprocess entry point -----------------------------------------------------------------------------

REQUIRED_FIELDS = frozenset({"port", "username", "password", "enable_secret", "device_type"})
OPTIONAL_FIELDS = frozenset({"backup", "content", "wait_ready", "startup", "save"})
BOOLEAN_FIELDS = ("backup", "wait_ready", "startup", "save")
CREDENTIAL_FIELDS = ("username", "password", "enable_secret")
# JSON can represent one content byte as six ASCII bytes (e.g. DEL).
MAX_REQUEST_BYTES = 6 * MAX_BYTES + 16385


def validated(payload):
    """The request itself, or ValueError: exact field set, bounded text, no control characters."""
    if (
        not isinstance(payload, dict)
        or not REQUIRED_FIELDS <= set(payload)
        or set(payload) - REQUIRED_FIELDS - OPTIONAL_FIELDS
    ):
        raise ValueError
    if "content" in payload:
        content = payload["content"]
        if (
            not isinstance(content, str)
            or not 0 < len(content.encode()) <= MAX_BYTES
            or any(ord(c) < 32 and c not in "\r\n\t" for c in content)
        ):
            raise ValueError
    for key in BOOLEAN_FIELDS:
        if key in payload and type(payload[key]) is not bool:
            raise ValueError
    device_type = payload["device_type"]
    if not isinstance(device_type, str) or normalize_device_type(device_type) not in get_platforms():
        raise ValueError
    if type(payload["port"]) is not int or not 0 < payload["port"] <= 65535:
        raise ValueError
    for key in CREDENTIAL_FIELDS:
        value = payload[key]
        if not isinstance(value, str) or not is_single_line(value):
            raise ValueError
    return payload


def main():
    logging.disable(logging.CRITICAL)
    try:
        payload = validated(json.loads(sys.stdin.buffer.read(MAX_REQUEST_BYTES)))
        result: dict[str, object] = {
            "content_base64": base64.b64encode(ConsoleSession(payload).collect()).decode("ascii")
        }
    except ImportError:
        result = {"error": "console_driver_unavailable"}
    except CaptureFailure as error:
        result = {"error": str(error)}
        context = failure_context(error.context)
        if context:
            result["context"] = context
        if error.console_reusable:
            result["console_reusable"] = True
    except Exception:
        result = {"error": "console_capture_failed"}
    data = json.dumps(result).encode()
    sys.stdout.buffer.write(len(data).to_bytes(4, "big") + data)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
