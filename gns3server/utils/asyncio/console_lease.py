"""An exclusive, bounded view of an already connected console proxy."""

import asyncio
import contextlib


class ConsoleLeaseError(ConnectionError):
    """Stable reason codes only; never include terminal data."""


class ConsoleReadiness:
    """Bounded passive prompt observation; never reserves or writes the console."""

    def __init__(self):
        self.tail = b""
        self.changed = asyncio.Event()
        self.closed = False

    def feed_data(self, data):
        self.tail = (self.tail + data)[-2048:]
        self.changed.set()

    def clear(self):
        self.tail = b""

    def close(self):
        self.clear()
        self.closed = True
        self.changed.set()

    async def wait_for(self, predicate, wait_seconds, *, settle_seconds=0):
        """Wait until ``predicate(tail)`` holds and the stream has settled.

        The predicate must turn false again if boot output follows the prompt.
        """
        async with asyncio.timeout(wait_seconds):
            while True:
                if self.closed:
                    raise ConsoleLeaseError("console_unavailable")
                ready = predicate(self.tail.decode("utf-8", errors="ignore"))
                if ready and not settle_seconds:
                    return
                self.changed.clear()
                if ready:
                    # A serial read may end halfway through boot output at a
                    # string resembling a prompt. Require a quiet interval
                    # before letting automation reserve the interactive stream.
                    try:
                        await asyncio.wait_for(self.changed.wait(), settle_seconds)
                    except TimeoutError:
                        if not self.changed.is_set():
                            return
                else:
                    await self.changed.wait()


class ConsoleLease:
    def __init__(self, writer, max_bytes: int):
        self.reader = asyncio.StreamReader()
        self._writer = writer
        self._max_bytes = max_bytes
        self._received = 0
        self._closed = False
        self.error: ConsoleLeaseError | None = None
        self.written_bytes = 0
        self.probe_only = True

    def feed_data(self, data):
        if self._closed or self.error:
            return
        self._received += len(data)
        if self._received > self._max_bytes:
            self.error = ConsoleLeaseError("console_output_limit")
            self.reader.set_exception(self.error)
            return
        self.reader.feed_data(data)

    def write(self, data):
        if self._closed:
            raise ConsoleLeaseError("console_lease_closed")
        if self.error:
            raise self.error
        self._writer.write(data)
        self.written_bytes += len(data)
        if data.strip(b"\r\n"):
            self.probe_only = False

    async def drain(self):
        if self._closed:
            raise ConsoleLeaseError("console_lease_closed")
        if self.error:
            raise self.error
        await self._writer.drain()

    def close(self):
        # Never close the proxy's persistent connection to the guest and never
        # send exit/end/save commands as transport cleanup.
        self._closed = True
        self.reader.feed_eof()


class ConsoleLeaseMixin:
    """Exclusive console admission shared by the Telnet and SSH proxies.

    The host calls ``_init_console_lease()`` and provides ``_server``, ``_broadcast_task``, ``_writer``
    and ``_active_clients()`` (live client connections).
    """

    def _init_console_lease(self):
        self._protocol_clients = set()
        self._exclusive_console = None
        self._console_readiness = ConsoleReadiness()
        self._console_recovery_required = False

    @property
    def _console_reserved(self):
        """New clients and their input are refused: a lease owns the console, or it needs a restart."""
        return self._exclusive_console is not None or self._console_recovery_required

    def _active_clients(self):
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def lease_console(self, *, max_bytes=2 * 1024 * 1024):
        """Fail busy without disconnecting a client, including during negotiation.

        Admission and reservation contain no await, making them atomic on this
        event loop. New connections are refused at the listening proxy while a
        lease owns input and output.
        """
        if not 1 <= max_bytes <= 32 * 1024 * 1024:
            raise ValueError("Invalid console output limit")
        if self._console_recovery_required:
            raise ConsoleLeaseError("console_recovery_required")
        if self._server is None or self._broadcast_task is None or self._broadcast_task.done() or self._writer is None:
            raise ConsoleLeaseError("console_unavailable")
        if self._exclusive_console is not None or self._protocol_clients or self._active_clients():
            raise ConsoleLeaseError("console_busy")
        lease = ConsoleLease(self._writer, max_bytes)
        self._exclusive_console = lease
        self._console_readiness.clear()
        try:
            yield lease
            if lease.error is not None:
                raise lease.error
        finally:
            lease.close()
            self._exclusive_console = None
