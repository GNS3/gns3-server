"""
Unit tests for packet filter validation.
"""

import pytest

from gns3server.utils.packet_filter_validation import (
    FilterValidationError,
    filter_inactive_filters,
    split_kernel_only_features,
    validate_all_filters,
    validate_filter_parameters,
)


class TestPacketFilterValidation:
    """Test packet filter parameter validation."""

    def test_frequency_drop_valid(self):
        """Test valid frequency drop parameters."""
        # Valid range: -1 to 32767
        validate_filter_parameters("frequency_drop", [-1])
        validate_filter_parameters("frequency_drop", [1])
        validate_filter_parameters("frequency_drop", [100])
        validate_filter_parameters("frequency_drop", [32767])

    def test_frequency_drop_invalid(self):
        """Test invalid frequency drop parameters."""
        # Too low
        with pytest.raises(FilterValidationError, match="between -1 and 32767"):
            validate_filter_parameters("frequency_drop", [-2])

        # Too high
        with pytest.raises(FilterValidationError, match="between -1 and 32767"):
            validate_filter_parameters("frequency_drop", [32768])

        # Wrong type
        with pytest.raises(FilterValidationError, match="must be an integer"):
            validate_filter_parameters("frequency_drop", ["invalid"])

    def test_packet_loss_valid(self):
        """Test valid packet loss parameters."""
        # Valid range: 0-100%
        validate_filter_parameters("packet_loss", [0])
        validate_filter_parameters("packet_loss", [50])
        validate_filter_parameters("packet_loss", [100])

    def test_packet_loss_invalid(self):
        """Test invalid packet loss parameters."""
        # Negative
        with pytest.raises(FilterValidationError, match="between 0 and 100"):
            validate_filter_parameters("packet_loss", [-1])

        # Over 100%
        with pytest.raises(FilterValidationError, match="between 0 and 100"):
            validate_filter_parameters("packet_loss", [101])

    def test_delay_valid(self):
        """Test valid delay parameters."""
        # Valid range: 1-32767ms latency, 0-32767ms jitter
        validate_filter_parameters("delay", [1, 0])
        validate_filter_parameters("delay", [100, 50])
        validate_filter_parameters("delay", [32767, 32767])

    def test_delay_invalid(self):
        """Test invalid delay parameters."""
        # Zero latency (ubridge rejects latency <= 0)
        with pytest.raises(FilterValidationError, match="between 1 and 32767"):
            validate_filter_parameters("delay", [0, 0])

        # Negative latency
        with pytest.raises(FilterValidationError, match="between 1 and 32767"):
            validate_filter_parameters("delay", [-1, 0])

        # Over max
        with pytest.raises(FilterValidationError, match="between 1 and 32767"):
            validate_filter_parameters("delay", [32768, 0])

        # Negative jitter
        with pytest.raises(FilterValidationError, match="between 0 and 32767"):
            validate_filter_parameters("delay", [100, -1])

    def test_corrupt_valid(self):
        """Test valid corrupt parameters."""
        # Valid range: 0-100%
        validate_filter_parameters("corrupt", [0])
        validate_filter_parameters("corrupt", [50])
        validate_filter_parameters("corrupt", [100])

    def test_corrupt_invalid(self):
        """Test invalid corrupt parameters."""
        # Over 100%
        with pytest.raises(FilterValidationError, match="between 0 and 100"):
            validate_filter_parameters("corrupt", [101])

    def test_bpf_valid(self):
        """Test valid BPF parameters."""
        validate_filter_parameters("bpf", ["tcp port 80"])
        validate_filter_parameters("bpf", ["tcp and not port 22"])
        validate_filter_parameters("bpf", [""])  # Empty is valid
        validate_filter_parameters("bpf", ["host 192.168.1.1 and port 443"])

    def test_bpf_multi_line_valid(self):
        """Test valid multi-line BPF expressions."""
        validate_filter_parameters("bpf", ["tcp port 80\nnot arp"])
        validate_filter_parameters("bpf", ["tcp and not port 22\nhost 192.168.1.1\nicmp"])

    def test_bpf_multi_line_invalid(self):
        """Test multi-line BPF with invalid line."""
        with pytest.raises(FilterValidationError) as excinfo:
            validate_filter_parameters("bpf", ["tcp port 80\ninvalid!!!"])
        err = str(excinfo.value).lower()
        assert "syntax error" in err

    def test_bpf_invalid(self):
        """Test invalid BPF parameters."""
        # Wrong type
        with pytest.raises(FilterValidationError, match="must be a string"):
            validate_filter_parameters("bpf", [123])

        # Invalid BPF syntax
        with pytest.raises(FilterValidationError) as excinfo:
            validate_filter_parameters("bpf", ["tcp port"])  # Missing port number
        assert "syntax error" in str(excinfo.value).lower()

    def test_parameter_count_mismatch(self):
        """Test wrong number of parameters."""
        # frequency_drop expects 1 parameter
        with pytest.raises(FilterValidationError, match="expects 1 parameter"):
            validate_filter_parameters("frequency_drop", [])

        with pytest.raises(FilterValidationError, match="expects 1 parameter"):
            validate_filter_parameters("frequency_drop", [1, 2])

        # delay takes 1 to 3 parameters (latency, optional jitter,
        # optional distribution) — latency alone is valid, a 4th is not
        validate_filter_parameters("delay", [100])
        with pytest.raises(FilterValidationError, match="expects 1 to 3 parameter"):
            validate_filter_parameters("delay", [100, 50, "normal", "extra"])

    def test_string_to_int_conversion(self):
        """Test string to integer conversion."""
        # Should work with string numbers
        validate_filter_parameters("frequency_drop", ["10"])
        validate_filter_parameters("packet_loss", ["50"])
        validate_filter_parameters("delay", ["100", "50"])

    def test_validate_all_filters(self):
        """Test validating multiple filters at once."""
        filters = {"frequency_drop": [10], "delay": [100, 50]}
        validate_all_filters(filters)  # Should not raise

    def test_validate_all_filters_with_invalid(self):
        """Test validate_all_filters with invalid filter."""
        filters = {
            "frequency_drop": [10],
            "packet_loss": [150],  # Invalid: over 100%
        }
        with pytest.raises(FilterValidationError):
            validate_all_filters(filters)

    def test_unknown_filter_type(self):
        """Test unknown filter type."""
        with pytest.raises(FilterValidationError, match="Unknown filter type"):
            validate_filter_parameters("unknown_filter", [1])


class TestFilterInactiveFilters:
    """Test filter_inactive_filters function for smart filter filtering logic."""

    def test_filter_inactive_delay_disabled(self):
        """Test delay [0, 0] is filtered out (user wants to disable delay)."""
        filters = {"delay": [0, 0]}
        result = filter_inactive_filters(filters)
        assert result == {}  # Should be filtered out

    def test_filter_inactive_delay_invalid_config(self):
        """Test delay [0, 100] is kept for validation (invalid config)."""
        filters = {"delay": [0, 100]}
        result = filter_inactive_filters(filters)
        assert result == {"delay": [0, 100]}  # Should be kept for validation error

    def test_filter_inactive_delay_normal_config(self):
        """Test delay [100, 20] is kept (normal configuration)."""
        filters = {"delay": [100, 20]}
        result = filter_inactive_filters(filters)
        assert result == {"delay": [100, 20]}  # Should be kept

    def test_filter_inactive_delay_zero_jitter(self):
        """Test delay [100, 0] is kept (normal config with zero jitter)."""
        filters = {"delay": [100, 0]}
        result = filter_inactive_filters(filters)
        assert result == {"delay": [100, 0]}  # Should be kept

    def test_filter_inactive_packet_loss_zero(self):
        """Test packet_loss [0] is filtered out (disabled)."""
        filters = {"packet_loss": [0]}
        result = filter_inactive_filters(filters)
        assert result == {}  # Should be filtered out

    def test_filter_inactive_packet_loss_active(self):
        """Test packet_loss [5] is kept (active)."""
        filters = {"packet_loss": [5]}
        result = filter_inactive_filters(filters)
        assert result == {"packet_loss": [5]}  # Should be kept

    def test_filter_inactive_corrupt_zero(self):
        """Test corrupt [0] is filtered out (disabled)."""
        filters = {"corrupt": [0]}
        result = filter_inactive_filters(filters)
        assert result == {}  # Should be filtered out

    def test_filter_inactive_corrupt_active(self):
        """Test corrupt [2] is kept (active)."""
        filters = {"corrupt": [2]}
        result = filter_inactive_filters(filters)
        assert result == {"corrupt": [2]}  # Should be kept

    def test_filter_inactive_frequency_drop_zero(self):
        """Test frequency_drop [0] is filtered out (disabled)."""
        filters = {"frequency_drop": [0]}
        result = filter_inactive_filters(filters)
        assert result == {}  # Should be filtered out

    def test_filter_inactive_frequency_drop_active(self):
        """Test frequency_drop [10] is kept (active)."""
        filters = {"frequency_drop": [10]}
        result = filter_inactive_filters(filters)
        assert result == {"frequency_drop": [10]}  # Should be kept

    def test_filter_inactive_bpf_empty(self):
        """Test BPF empty string is filtered out."""
        filters = {"bpf": [""]}
        result = filter_inactive_filters(filters)
        assert result == {}  # Should be filtered out

    def test_filter_inactive_bpf_active(self):
        """Test BPF with expression is kept."""
        filters = {"bpf": ["tcp port 80"]}
        result = filter_inactive_filters(filters)
        assert result == {"bpf": ["tcp port 80"]}  # Should be kept

    def test_filter_inactive_multiple_filters_mixed(self):
        """Test multiple filters with mixed active/inactive states."""
        filters = {
            "delay": [0, 0],  # Disabled: [0, 0]
            "packet_loss": [0],  # Disabled: 0%
            "corrupt": [2],  # Active: 2%
            "frequency_drop": [10],  # Active: every 10th packet
        }
        result = filter_inactive_filters(filters)
        assert result == {"corrupt": [2], "frequency_drop": [10]}

    def test_filter_inactive_empty_filters(self):
        """Test empty filters dictionary."""
        filters = {}
        result = filter_inactive_filters(filters)
        assert result == {}

    def test_filter_inactive_none_filters(self):
        """Test None filters."""
        result = filter_inactive_filters(None)
        assert result == {}


class TestNetemExtensionFilters:
    """P6a: the netem-extension filter types (rate, reorder, gemodel,
    duplicate, seed, limit) and the kernel-only parameter extensions."""

    def test_rate_valid(self):
        for value in ("512kbit", "10mbit", "1gbit", "64000bps", "8000kbps", "100mbps", "1544bit"):
            validate_filter_parameters("rate", [value])

    def test_rate_invalid(self):
        # bare number, unknown unit, float, over 100gbit
        for value in ("512", "512kbits", "0.5mbit", "101gbit", "", "mbit"):
            with pytest.raises(FilterValidationError, match="Rate"):
                validate_filter_parameters("rate", [value])

    def test_rate_rejects_non_string(self):
        with pytest.raises(FilterValidationError, match="must be a string"):
            validate_filter_parameters("rate", [512000])

    def test_reorder_valid(self):
        validate_filter_parameters("reorder", [25])
        validate_filter_parameters("reorder", [25, 50])
        validate_filter_parameters("reorder", [25, 50, 5])

    def test_reorder_invalid_ranges(self):
        with pytest.raises(FilterValidationError, match="Reorder"):
            validate_filter_parameters("reorder", [101])
        with pytest.raises(FilterValidationError, match="Gap"):
            validate_filter_parameters("reorder", [25, 0, 0])  # gap < 1
        with pytest.raises(FilterValidationError, match="Gap"):
            validate_filter_parameters("reorder", [25, 0, 1001])

    def test_reorder_requires_delay(self):
        with pytest.raises(FilterValidationError, match="reorder requires delay"):
            validate_all_filters({"reorder": [25]})
        # with delay present it passes
        validate_all_filters({"reorder": [25, 0, 5], "delay": [100, 10]})

    def test_gemodel_valid_and_exclusive(self):
        validate_filter_parameters("gemodel", [100])
        validate_filter_parameters("gemodel", [100, 0])
        validate_filter_parameters("gemodel", [100, 0, 30])
        with pytest.raises(FilterValidationError, match="mutually exclusive"):
            validate_all_filters({"gemodel": [100, 0, 30], "packet_loss": [10]})

    def test_gemodel_invalid_range(self):
        with pytest.raises(FilterValidationError, match="bad-state"):
            validate_filter_parameters("gemodel", [101, 0, 30])

    def test_duplicate_valid(self):
        validate_filter_parameters("duplicate", [10])
        validate_filter_parameters("duplicate", [10, 25])

    def test_seed_and_limit(self):
        validate_filter_parameters("seed", [42])
        validate_filter_parameters("seed", [4294967295])
        with pytest.raises(FilterValidationError, match="Seed"):
            validate_filter_parameters("seed", [4294967296])
        validate_filter_parameters("limit", [5000])
        with pytest.raises(FilterValidationError, match="Limit"):
            validate_filter_parameters("limit", [0])
        with pytest.raises(FilterValidationError, match="Limit"):
            validate_filter_parameters("limit", [1000001])

    def test_delay_distribution(self):
        for dist in ("uniform", "normal", "pareto", "paretonormal"):
            validate_filter_parameters("delay", [100, 20, dist])
        with pytest.raises(FilterValidationError, match="Distribution"):
            validate_filter_parameters("delay", [100, 20, "poisson"])
        # distribution without jitter does nothing -> rejected
        with pytest.raises(FilterValidationError, match="requires a Jitter"):
            validate_filter_parameters("delay", [100, 0, "normal"])
        # empty distribution = not set
        validate_filter_parameters("delay", [100, 20, ""])

    def test_packet_loss_correlation(self):
        validate_filter_parameters("packet_loss", [10])
        validate_filter_parameters("packet_loss", [10, 25])
        with pytest.raises(FilterValidationError, match="Correlation"):
            validate_filter_parameters("packet_loss", [10, 101])

    def test_kernel_only_features(self):
        clean, dropped = split_kernel_only_features(
            {
                "delay": [100, 20, "normal"],
                "packet_loss": [10, 25],
                "rate": ["512kbit"],
                "corrupt": [2],
            }
        )
        assert dropped == {"rate", "delay distribution", "packet_loss correlation"}
        assert clean == {"delay": [100, 20], "packet_loss": [10], "corrupt": [2]}

    def test_kernel_only_features_all_relay_safe(self):
        clean, dropped = split_kernel_only_features(
            {"delay": [100, 20, ""], "packet_loss": [10, 0], "corrupt": [2], "bpf": ["icmp"]}
        )
        assert dropped == set()
        # zero correlation and empty distribution are kept as-is (no-ops)
        assert clean == {"delay": [100, 20, ""], "packet_loss": [10, 0], "corrupt": [2], "bpf": ["icmp"]}

    def test_kernel_only_features_empty(self):
        assert split_kernel_only_features({}) == ({}, set())
        assert split_kernel_only_features(None) == ({}, set())

    def test_quota_valid_and_invalid(self):
        validate_filter_parameters("quota", [1000000, 100])
        validate_filter_parameters("quota", [1, 0])
        with pytest.raises(FilterValidationError, match="Quota"):
            validate_filter_parameters("quota", [0, 100])
        with pytest.raises(FilterValidationError, match="Chance"):
            validate_filter_parameters("quota", [1000, 101])
        with pytest.raises(FilterValidationError, match="expects 2 parameter"):
            validate_filter_parameters("quota", [1000])

    def test_quota_is_kernel_only(self):
        clean, dropped = split_kernel_only_features({"quota": [1000, 50], "frequency_drop": [7]})
        assert dropped == {"quota"}
        # frequency_drop runs on both datapaths (relay userspace filter /
        # eBPF every-Nth) and stays
        assert clean == {"frequency_drop": [7]}
