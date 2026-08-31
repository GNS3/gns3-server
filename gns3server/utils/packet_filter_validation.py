"""
Packet filter parameter validation utilities.
"""

import logging
import subprocess
from typing import Dict, List, Any, Optional

log = logging.getLogger(__name__)


class FilterValidationError(Exception):
    """Raised when packet filter parameters fail validation."""
    pass


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
                            line = line[len(prefix):]
                    error_lines.append(line)
            error_msg = " ".join(error_lines) if error_lines else "Invalid BPF expression"
            log.warning("BPF syntax validation failed: %s", error_msg)
            return {"valid": False, "error": error_msg}

        log.info("BPF syntax validation passed")
        return {"valid": True, "error": None}

    except FileNotFoundError:
        log.warning(
            "tcpdump not found, skipping BPF syntax validation. "
            "Install tcpdump to enable BPF validation."
        )
        return {"valid": True, "error": None}

    except Exception as e:
        log.error("Unexpected error during BPF validation: %s", e)
        return {"valid": False, "error": f"BPF validation error: {str(e)}"}


def validate_filter_parameters(filter_type: str, values: List[Any]) -> None:
    """
    Validate packet filter parameters.

    Args:
        filter_type: Type of packet filter
        values: List of parameter values

    Raises:
        FilterValidationError: If parameters are invalid
    """

    # Define validation rules based on ubridge implementation
    VALIDATION_RULES = {
        "frequency_drop": {
            "params_count": 1,
            "ranges": [(-1, 32767)],  # min, max
            "names": ["Frequency"],
            "units": ["th packet"]
        },
        "packet_loss": {
            "params_count": 1,
            "ranges": [(0, 100)],
            "names": ["Chance"],
            "units": ["%"]
        },
        "delay": {
            "params_count": 2,  # latency, jitter
            "ranges": [(1, 32767), (0, 32767)],  # ubridge rejects latency <= 0
            "names": ["Latency", "Jitter"],
            "units": ["ms", "ms"]
        },
        "corrupt": {
            "params_count": 1,
            "ranges": [(0, 100)],
            "names": ["Chance"],
            "units": ["%"]
        },
        "bpf": {
            "params_count": 1,
            "is_text": True,
            "names": ["Filters"]
        }
    }

    if filter_type not in VALIDATION_RULES:
        raise FilterValidationError(f"Unknown filter type: {filter_type}")

    rules = VALIDATION_RULES[filter_type]

    # Check parameter count
    if len(values) != rules["params_count"]:
        raise FilterValidationError(
            f"{filter_type} expects {rules['params_count']} parameter(s), got {len(values)}"
        )

    # Validate each parameter
    for i, value in enumerate(values):
        if rules.get("is_text"):
            # Text validation (BPF)
            if not isinstance(value, str):
                raise FilterValidationError(
                    f"{filter_type} parameter {rules['names'][i]} must be a string"
                )

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
        else:
            # Integer parameter validation
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
        if not values or (isinstance(values, list) and len(values) == 0):
            continue

        # Normalize values (strip strings, convert to int)
        normalized_values = []
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
        # For other filters, skip if first value is 0 or empty string (means "disabled")
        elif values[0] != 0 and values[0] != "":
            active_filters[filter_type] = values
        else:
            # Filters like packet_loss=0, corrupt=0, frequency_drop=0 are intentionally disabled
            log.debug(f"Filter {filter_type} with values {values} skipped (disabled)")

    return active_filters


def validate_all_filters(filters: Dict[str, List[Any]]) -> None:
    """
    Validate all packet filters.

    Args:
        filters: Dictionary mapping filter types to their values

    Raises:
        FilterValidationError: If any filter is invalid
    """

    if not filters:
        return

    for filter_type, values in filters.items():
        if not values or (isinstance(values, list) and len(values) == 0):
            continue

        validate_filter_parameters(filter_type, values)