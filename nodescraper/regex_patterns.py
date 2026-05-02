"""Common regex patterns and helpers for building analyzer error rules.

Keep these lightweight and dependency-free so other modules can import them
without circular imports.
"""
from typing import Iterable, List

COMMON_PATTERNS: dict[str, str] = {
    "ipv4": r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b",
    "mac": r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
    "uuid": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
    "iso8601_ts": r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b",
    "email": r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b",
}


def get_pattern(name: str) -> str:
    """Return the raw regex string for a named common pattern.

    Raises KeyError if the name is unknown.
    """
    return COMMON_PATTERNS[name]


def build_error_regex_dicts(
    names: Iterable[str],
    message_template: str = "{name} matched",
    event_category: str = "UNKNOWN",
    event_priority: str = "ERROR",
) -> List[dict]:
    """Create list of dicts compatible with RegexAnalyzer._convert_and_extend_error_regex.

    Each dict contains keys: 'regex' (string), 'message', 'event_category', 'event_priority'.
    The analyzer will compile the regex strings into patterns.
    """
    out: List[dict] = []
    for name in names:
        pat = COMMON_PATTERNS.get(name)
        if not pat:
            raise KeyError(f"Unknown pattern name: {name}")
        out.append(
            {
                "regex": pat,
                "message": message_template.format(name=name),
                "event_category": event_category,
                "event_priority": event_priority,
            }
        )
    return out


__all__ = ["COMMON_PATTERNS", "get_pattern", "build_error_regex_dicts"]
