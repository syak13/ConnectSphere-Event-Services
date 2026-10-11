from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (tzinfo stripped).

    Behaves like the old datetime.utcnow() without triggering its
    deprecation warning. Kept naive on purpose: the DB columns storing
    these values are plain DATETIME with no timezone component, so a
    tz-aware value here would just get silently stripped later anyway.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)