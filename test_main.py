import json
import pytest
from main import normalize_timestamp, process_line

class TestNormalizeTimestamp:
    def test_with_timezone_offset(self):
        result = normalize_timestamp("2021-01-01T12:00:00+02:00")
        assert result == "2021-01-01T10:00:00Z"

    def test_with_Z_suffix(self):
        result = normalize_timestamp("2021-01-01T12:00:00Z")
        assert result == "2021-01-01T12:00:00Z"

    def test_without_timezone_assumes_utc(self):
        result = normalize_timestamp("2021-01-01T12:00:00")
        assert result == "2021-01-01T12:00:00Z"

    def test_with_fractional_seconds_and_negative_offset(self):
        result = normalize_timestamp("2021-01-01T12:00:00.123456-05:00")
        assert result == "2021-01-01T17:00:00.123456Z"

    def test_invalid_timestamp_raises_valueerror(self):
        with pytest.raises(ValueError, match="Invalid ISO 8601 timestamp"):
            normalize_timestamp("not-a-timestamp")

    def test_edge_empty_string_raises(self):
        with pytest.raises(ValueError):
            normalize_timestamp("")

class TestProcessLine:
    def test_valid_unique_line(self):
        line = json.dumps({"timestamp": "2021-06-15T14:00:00+02:00", "msg": "hello"})
        result = process_line(line, 1, set())
        parsed = json.loads(result)
        assert parsed["timestamp"] == "2021-06-15T12:00:00Z"
        assert parsed["msg"] == "hello"

    def test_duplicate_timestamp_returns_none(self):
        seen = set()
        line = json.dumps({"timestamp": "2021-06-15T14:00:00+02:00"})
        first = process_line(line, 1, seen)
        assert first is not None
        second = process_line(line, 2, seen)
        assert second is None

    def test_invalid_json_returns_none_and_stderr(self, capsys):
        result = process_line("not json", 42, set())
        captured = capsys.readouterr()
        assert result is None
        assert "Line 42: invalid JSON" in captured.err

    def test_missing_timestamp_field_returns_none(self, capsys):
        line = json.dumps({"msg": "no ts"})
        result = process_line(line, 10, set())
        captured = capsys.readouterr()
        assert result is None
        assert "Line 10: missing 'timestamp' field" in captured.err

    def test_timestamp_not_string_returns_none(self, capsys):
        line = json.dumps({"timestamp": 12345})
        result = process_line(line, 3, set())
        captured = capsys.readouterr()
        assert result is None
        assert "Line 3: 'timestamp' is not a string" in captured.err

    def test_invalid_timestamp_value_returns_none(self, capsys):
        line = json.dumps({"timestamp": "bogus"})
        result = process_line(line, 5, set())
        captured = capsys.readouterr()
        assert result is None
        assert "Line 5: Invalid ISO 8601 timestamp" in captured.err

    def test_empty_line_returns_none(self):
        result = process_line("   ", 1, set())
        assert result is None

    def test_non_dict_top_level(self, capsys):
        line = json.dumps(["an", "array"])
        result = process_line(line, 8, set())
        captured = capsys.readouterr()
        assert result is None
        assert "Line 8: top-level JSON is not an object" in captured.err

    def test_deduplication_across_different_original_zones(self):
        seen = set()
        line1 = json.dumps({"timestamp": "2021-06-15T12:00:00Z"})
        line2 = json.dumps({"timestamp": "2021-06-15T14:00:00+02:00"})  # same UTC
        first = process_line(line1, 1, seen)
        assert first is not None
        second = process_line(line2, 2, seen)
        assert second is None  # duplicate after normalization

    def test_ensure_ascii_false_allows_unicode(self):
        line = json.dumps({"timestamp": "2021-01-01T00:00:00Z", "text": "élève"})
        result = process_line(line, 1, set())
        # Should contain the unescaped é
        assert "élève" in result