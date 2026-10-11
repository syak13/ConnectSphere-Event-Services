import re

_CONTAINS_WORD = re.compile(r"[A-Za-z]")


def validate_descriptive_text(value: str, label: str):
    """Raises ValueError unless value is non-blank and contains at least
    one real word (not just symbols, punctuation, or digits). Shared by
    clarification comments/responses and rejection/cancellation reasons,
    which all carry the same requirement."""
    if not value or not value.strip():
        raise ValueError(f"At least one {label} is required")
    if not _CONTAINS_WORD.search(value):
        raise ValueError(f"{label.capitalize()} must contain descriptive text, not just symbols or numbers")