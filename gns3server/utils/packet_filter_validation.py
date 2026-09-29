"""
Packet filter parameter validation utilities.
"""

import logging
import re
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


class FilterValidationError(Exception):
    """Raised when packet filter parameters fail validation."""

    pass


# Every GNS3 filter type now has a kernel-datapath equivalent: delay /
# packet_loss / corrupt / the netem extensions run as one tc netem qdisc,
# bpf as cBPF match-drop classifiers, and frequency_drop as the eBPF
# stateful classifier's exact every-Nth mode (tc nth_drop — needs a uBridge
# reporting ebpf=1). No type is relay-only anymore; the controller-side
# kernel/relay choice is purely topological (same compute, docker/docker).
#
# Packet filters with no uBridge *relay* equivalent: the netem extensions
# plus the eBPF quota/window modes run on the kernel datapath only. The
# relay's packet-filter registry only knows frequency_drop / packet_loss /
# delay / corrupt / bpf / mark.
KERNEL_ONLY_FILTERS = frozenset({"rate", "reorder", "gemodel", "duplicate", "seed", "limit", "quota", "window_drop"})

# Jitter distributions embedded in the netem-extension uBridge (tc_netem_dist).
NETEM_DISTRIBUTIONS = ("uniform", "normal", "pareto", "paretonormal")

# Bandwidth values follow the tc netem grammar: integer + unit, capped at
# 100gbit (uBridge NETEM_RATE_MAX_BPS). bps-family units are bytes/s.
_RATE_RE = re.compile(r"^(\d+)(bit|kbit|mbit|gbit|bps|kbps|mbps)$", re.IGNORECASE)
_RATE_UNITS = {
    "bit": 1,
    "kbit": 1000,
    "mbit": 1000**2,
    "gbit": 1000**3,
    "bps": 8,
    "kbps": 8000,
    "mbps": 8000 * 1000,
}
_RATE_MAX_BITS = 100 * 1000**3


def validate_bpf_syntax(bpf_expression: str) -> Dict[str, Optional[str]]:
    """
    Validate BPF filter expression syntax using tcpdump.

    Uses `tcpdump -d` to compile the BPF expression into filter instructions.
    This calls pcap_compile() internally (same as ubridge) but does not
    capture traffic, so it returns immediately for both valid and invalid
    expressions.

    Args:
        bpf_expression: BPF filter expression to validate

    Returns:
        dict with 'valid' (bool) and 'error' (str or None) keys
    """
    try:
        result = subprocess.run(
            ["tcpdump", "-d", bpf_expression],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Extract meaningful error from tcpdump's stderr
            # Skip "Warning: assuming Ethernet" lines, keep only error lines
            error_lines = []
            for line in result.stderr.split("\n"):
                line = line.strip()
                if line and not line.startswith("Warning:"):
                    # Strip "tcpdump: " prefix
                    for prefix in ["tcpdump: "]:
                        if line.startswith(prefix):
                            line = line[len(prefix) :]
                    error_lines.append(line)
            error_msg = " ".join(error_lines) if error_lines else "Invalid BPF expression"
            log.warning("BPF syntax validation failed: %s", error_msg)
            return {"valid": False, "error": error_msg}

        log.info("BPF syntax validation passed")
        return {"valid": True, "error": None}

    except FileNotFoundError:
        log.warning("tcpdump not found, skipping BPF syntax validation. Install tcpdump to enable BPF validation.")
        return {"valid": True, "error": None}

    except Exception as e:
        log.error("Unexpected error during BPF validation: %s", e)
        return {"valid": False, "error": f"BPF validation error: {e!s}"}


def _validate_distribution_value(value: Any, name: str) -> str:
    """
    Validate a netem jitter distribution name (delay filter, 3rd parameter).
    Returns the normalized (lowercase) name; an empty value is treated as
    "not set" and returns "".
    """

    if not isinstance(value, str):
        raise FilterValidationError(f"{name} must be one of {', '.join(NETEM_DISTRIBUTIONS)} (or empty), got: {value}")
    value = value.strip().lower()
    if not value:
        return ""  # empty = not set
    if value not in NETEM_DISTRIBUTIONS:
        raise FilterValidationError(f"{name} must be one of {', '.join(NETEM_DISTRIBUTIONS)} (or empty), got: {value}")
    return value


def _validate_rate_value(value: Any, name: str) -> None:
    """
    Validate a tc-style bandwidth value (rate filter), e.g. "512kbit".
    """

    if not isinstance(value, str):
        raise FilterValidationError(f"{name} must be a string like '512kbit', got: {value}")
    match = _RATE_RE.match(value.strip())
    if not match:
        raise FilterValidationError(
            f"{name} must be an integer plus a unit (bit, kbit, mbit, gbit, bps, kbps, mbps), got: {value}"
        )
    if int(match.group(1)) * _RATE_UNITS[match.group(2).lower()] > _RATE_MAX_BITS:
        raise FilterValidationError(f"{name} exceeds the 100gbit maximum, got: {value}")


def _validate_int_parameter(filter_type: str, rules: dict, i: int, value: Any) -> None:
    """
    Integer parameter validation: type coercion plus range check.
    """

    try:
        if isinstance(value, str):
            value = value.strip()
            int_value = int(value)
        else:
            int_value = int(value)
    except (ValueError, TypeError):
        raise FilterValidationError(
            f"{filter_type} parameter {rules['names'][i]} must be an integer, got: {value}"
        )

    # Range validation
    min_val, max_val = rules["ranges"][i]
    if int_value < min_val or int_value > max_val:
        raise FilterValidationError(
            f"{filter_type} parameter {rules['names'][i]} must be between "
            f"{min_val} and {max_val} {rules['units'][i]}, got: {int_value}"
        )


def validate_filter_parameters(filter_type: str, values: List[Any]) -> None:
    """
    Validate packet filter parameters.

    Args:
        filter_type: Type of packet filter
        values: List of parameter values

    Raises:
        FilterValidationError: If parameters are invalid
    """

    # Define validation rules based on ubridge implementation. params_count is
    # (min, max): trailing parameters are optional (clients sending only the
    # first N fields keep working). String parameters are declared per index
    # in "string_params" with their own validators.
    VALIDATION_RULES: Dict[str, Dict[str, Any]] = {
        "frequency_drop": {
            "params_count": (1, 1),
            "ranges": [(-1, 32767)],  # min, max
            "names": ["Frequency"],
            "units": ["th packet"],
        },
        "packet_loss": {
            # 2nd parameter (loss correlation) needs the netem-extension
            # uBridge and only runs on the kernel datapath.
            "params_count": (1, 2),
            "ranges": [(0, 100), (0, 100)],
            "names": ["Chance", "Correlation"],
            "units": ["%", "%"],
        },
        "delay": {
            # 3rd parameter (jitter distribution) needs the netem-extension
            # uBridge and only runs on the kernel datapath.
            "params_count": (1, 3),
            "ranges": [(1, 32767), (0, 32767)],  # ubridge rejects latency <= 0
            "names": ["Latency", "Jitter", "Distribution"],
            "units": ["ms", "ms", ""],
            "string_params": {2: _validate_distribution_value},
        },
        "corrupt": {"params_count": (1, 1), "ranges": [(0, 100)], "names": ["Chance"], "units": ["%"]},
        "duplicate": {
            "params_count": (1, 2),
            "ranges": [(0, 100), (0, 100)],
            "names": ["Chance", "Correlation"],
            "units": ["%", "%"],
        },
        "rate": {"params_count": (1, 1), "ranges": [], "names": ["Rate"], "string_params": {0: _validate_rate_value}},
        "reorder": {
            "params_count": (1, 3),
            "ranges": [(0, 100), (0, 100), (1, 1000)],
            "names": ["Reorder", "Correlation", "Gap"],
            "units": ["%", "%", "packets"],
        },
        "gemodel": {
            # Gilbert-Elliot loss model, tc semantics: p = loss probability in
            # the bad state, r = loss probability in the good state, 1-h =
            # probability of moving from the good to the bad state.
            "params_count": (1, 3),
            "ranges": [(0, 100), (0, 100), (0, 100)],
            "names": ["p (bad-state loss)", "r (good-state loss)", "1-h (good-to-bad transition)"],
            "units": ["%", "%", "%"],
        },
        "seed": {"params_count": (1, 1), "ranges": [(0, 4294967295)], "names": ["Seed"], "units": [""]},
        "limit": {"params_count": (1, 1), "ranges": [(1, 1000000)], "names": ["Limit"], "units": ["packets"]},
        "quota": {
            # eBPF stateful classifier (uBridge tc quota_drop): after the byte
            # quota is consumed, each further packet drops with the given
            # chance (100 = hard cutoff). Kernel-datapath only.
            "params_count": (2, 2),
            "ranges": [(1, 10**15), (0, 100)],
            "names": ["Quota", "Chance"],
            "units": ["bytes", "%"],
        },
        "window_drop": {
            # eBPF stateful classifier (uBridge tc window_drop): packets drop
            # with the given chance inside [start, start+outage) measured from
            # the moment the filter is applied — a single outage, traffic
            # passes before AND after. A period makes the outage recur every
            # cycle (period >= outage); a jitter re-draws each cycle's outage
            # and period uniformly in nominal ± jitter (0 = the fixed
            # schedule). Kernel-datapath only.
            "params_count": (3, 5),
            "ranges": [(0, 10**12), (1, 10**12), (0, 100), (1, 10**12), (0, 10**9)],
            "names": ["Start", "Outage", "Chance", "Period", "Jitter"],
            "units": ["ms", "ms", "%", "ms", "ms"],
        },
        "bpf": {"params_count": (1, 1), "is_text": True, "names": ["Filters"]},
    }

    if filter_type not in VALIDATION_RULES:
        raise FilterValidationError(f"Unknown filter type: {filter_type}")

    rules = VALIDATION_RULES[filter_type]
    string_params = rules.get("string_params", {})

    # Check parameter count
    min_count, max_count = rules["params_count"]
    if not (min_count <= len(values) <= max_count):
        expected = str(min_count) if min_count == max_count else f"{min_count} to {max_count}"
        raise FilterValidationError(f"{filter_type} expects {expected} parameter(s), got {len(values)}")

    # Validate each parameter
    for i, value in enumerate(values):
        if rules.get("is_text"):
            # Text validation (BPF)
            if not isinstance(value, str):
                raise FilterValidationError(f"{filter_type} parameter {rules['names'][i]} must be a string")

            # Validate BPF syntax using tshark (same method as gns3_copilot)
            # The value may be a multi-line string; each line becomes a
            # separate ubridge filter. Validate each line individually.
            value = value.strip()
            if value:
                lines = value.split("\n")
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    bpf_result = validate_bpf_syntax(line)
                    if not bpf_result["valid"]:
                        raise FilterValidationError(
                            f"{filter_type} parameter {rules['names'][i]} line {line_num + 1} "
                            f"has invalid syntax: {bpf_result['error']}"
                        )
        elif i in string_params:
            string_params[i](value, f"{filter_type} parameter {rules['names'][i]}")
        else:
            _validate_int_parameter(filter_type, rules, i, value)

    if filter_type == "delay" and len(values) >= 3 and isinstance(values[2], str) and values[2].strip():
        # The distribution shapes the jitter draw — without jitter it does
        # nothing (the kernel silently stays uniform). values[1] has already
        # passed integer validation at this point.
        if int(values[1]) <= 0:
            raise FilterValidationError(
                "delay parameter Distribution requires a Jitter > 0 (the distribution shapes the jitter draw)"
            )


def filter_inactive_filters(filters: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
    """
    Filter out inactive packet filters before validation.

    This function implements smart filtering logic:
    - For most filters: value 0 means "disabled" and will be filtered out
    - For delay filter: check both latency and jitter to determine intent
      * delay: [0, 0] → User wants to disable delay completely, filter it out
      * delay: [0, X] where X > 0 → Invalid config (latency must be >= 1), keep for validation error
      * delay: [X, X] where X > 0 → Normal configuration, keep for validation

    Args:
        filters: Dictionary mapping filter types to their values

    Returns:
        Filtered dictionary with only active filters for validation
    """

    if not filters:
        return {}

    active_filters = {}
    for filter_type, values in filters.items():
        if not values:
            continue

        # Normalize values (strip strings, convert to int)
        normalized_values: List[Any] = []
        for value in values:
            if isinstance(value, str):
                normalized_values.append(value.strip("\n "))
            else:
                normalized_values.append(int(value))
        values = normalized_values

        # Skip empty filters after normalization
        if len(values) == 0:
            continue

        # Special handling for delay filter - check both latency and jitter
        if filter_type == "delay":
            if len(values) >= 1 and values[0] == 0:  # latency = 0
                if len(values) >= 2 and values[1] == 0:  # jitter = 0 too
                    # User intentionally disabling delay completely: [0, 0]
                    log.debug(f"Filter {filter_type} with values {values} skipped (disabled)")
                    continue  # Skip this filter silently
                else:
                    # Invalid config: latency=0 but jitter>0, keep for validation error
                    log.debug(f"Filter {filter_type} with values {values} kept for validation (invalid config)")
                    active_filters[filter_type] = values
            else:
                # latency>0, normal configuration
                active_filters[filter_type] = values
        # window_drop's first parameter is a start offset: 0 means "the
        # outage starts now", not "disabled" — the filter is active whenever
        # present (an outage of 0 is rejected by validation, so there is no
        # natural zero-value encoding for "off").
        elif filter_type == "window_drop":
            active_filters[filter_type] = values
        # For other filters, skip if first value is 0 or empty string (means "disabled")
        elif values[0] != 0 and values[0] != "":
            active_filters[filter_type] = values
        else:
            # Filters like packet_loss=0, corrupt=0, frequency_drop=0 are intentionally disabled
            log.debug(f"Filter {filter_type} with values {values} skipped (disabled)")

    return active_filters


def split_kernel_only_features(filters: Dict[str, List[Any]]) -> Tuple[Dict[str, List[Any]], Set[str]]:
    """
    Split a filter set into what the uBridge *relay* can run and what needs
    the kernel datapath (tc netem on the veth host end).

    Kernel-only are the whole types in KERNEL_ONLY_FILTERS plus two
    parameters: the delay jitter distribution (3rd) and the packet_loss
    correlation (2nd) — the relay's delay/packet_loss filters take no such
    argument.

    :returns: (relay-safe filters copy, names of the dropped features)
    """

    dropped: Set[str] = set()
    clean: Dict[str, List[Any]] = {}
    for filter_type, values in (filters or {}).items():
        if filter_type in KERNEL_ONLY_FILTERS:
            dropped.add(filter_type)
            continue
        # tolerate the legacy bare-value shape ({"packet_loss": 10})
        if isinstance(values, (list, tuple)):
            values = list(values)
        else:
            values = [values] if values else []
        if filter_type == "delay" and len(values) >= 3 and str(values[2]).strip():
            dropped.add("delay distribution")
            values = values[:2]
        elif filter_type == "packet_loss" and len(values) >= 2:
            try:
                correl = int(values[1])
            except (ValueError, TypeError):
                correl = 0
            if correl:
                dropped.add("packet_loss correlation")
                values = values[:1]
        clean[filter_type] = values
    return clean, dropped


def kernel_only_features(filters: Dict[str, List[Any]]) -> Set[str]:
    """
    Names of the features in *filters* that only run on the kernel datapath
    (see split_kernel_only_features).
    """

    return split_kernel_only_features(filters)[1]


def validate_all_filters(filters: Dict[str, List[Any]]) -> None:
    """
    Validate all packet filters, including cross-filter dependencies that
    mirror the tc netem grammar (reorder requires delay; gemodel and
    packet_loss both translate to the netem loss keyword and are mutually
    exclusive) and the eBPF window grammar (period >= outage).

    Args:
        filters: Dictionary mapping filter types to their values

    Raises:
        FilterValidationError: If any filter is invalid
    """

    if not filters:
        return

    for filter_type, values in filters.items():
        if not values:
            continue

        validate_filter_parameters(filter_type, values)

    if "reorder" in filters and "delay" not in filters:
        raise FilterValidationError("reorder requires delay")
    if "gemodel" in filters and "packet_loss" in filters:
        raise FilterValidationError("gemodel and packet_loss are mutually exclusive (both map to the netem loss keyword)")
    window = filters.get("window_drop")
    if window and len(window) >= 4 and int(window[3]) < int(window[1]):
        raise FilterValidationError("window_drop period must be greater than or equal to the outage length")
