import sys
import json
from datetime import datetime, timezone
from typing import Optional

def normalize_timestamp(raw: str) -> str:
    """
    Parse an ISO 8601 timestamp string, convert it to UTC,
    and return an ISO 8601 string with the 'Z' suffix.
    Handles timezone offsets and the 'Z' suffix gracefully.
    """
    # Python < 3.11 datetime.fromisoformat does not accept 'Z';
    # we replace it with the equivalent '+00:00' before parsing.
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'

    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        # Re-raise for the caller to handle as a parsing failure.
        raise ValueError(f"Invalid ISO 8601 timestamp: {raw!r}")

    if dt.tzinfo is None:
        # Assume UTC if no timezone information is present.
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    iso = dt.isoformat()
    # Convert the 'UTC' representation from '+00:00' to 'Z'.
    if iso.endswith('+00:00'):
        iso = iso[:-6] + 'Z'
    return iso


def process_line(line: str, line_num: int, seen: set) -> Optional[str]:
    """
    Process a single JSON line.

    Returns a normalized JSON string if the line represents a new log entry
    (by timestamp deduplication), or None if the line should be skipped
    (invalid, duplicate, or missing timestamp).
    """
    stripped = line.strip()
    if not stripped:
        return None

    # 1. Parse JSON.
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as exc:
        print(f"Line {line_num}: invalid JSON ({exc})", file=sys.stderr)
        return None

    if not isinstance(obj, dict):
        print(f"Line {line_num}: top-level JSON is not an object", file=sys.stderr)
        return None

    # 2. Extract timestamp.
    timestamp = obj.get("timestamp")
    if timestamp is None:
        print(f"Line {line_num}: missing 'timestamp' field", file=sys.stderr)
        return None
    if not isinstance(timestamp, str):
        print(f"Line {line_num}: 'timestamp' is not a string", file=sys.stderr)
        return None

    # 3. Normalize timestamp.
    try:
        normalized_ts = normalize_timestamp(timestamp)
    except ValueError as exc:
        print(f"Line {line_num}: {exc}", file=sys.stderr)
        return None

    # 4. Deduplicate by normalized timestamp.
    if normalized_ts in seen:
        return None
    seen.add(normalized_ts)

    # 5. Update object and serialize.
    obj["timestamp"] = normalized_ts
    return json.dumps(obj, ensure_ascii=False)


def main():
    """
    Read line-delimited JSON log entries from stdin,
    normalize timestamps to UTC, deduplicate by timestamp,
    and write the cleaned entries to stdout.
    Malformed or duplicate lines are skipped with warnings to stderr.
    """
    seen_timestamps = set()
    line_num = 0

    for line in sys.stdin:
        line_num += 1
        result = process_line(line, line_num, seen_timestamps)
        if result is not None:
            print(result, flush=True)


if __name__ == '__main__':
    main()