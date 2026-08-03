import datetime as dt

MINIMUM_DAYS_MONTH = 28


def end_of_month(reference: dt.datetime) -> dt.datetime:
    """Return the last instant of the month of the given datetime (23:59:59.999).

    Args:
        reference: A datetime object within the target month.

    Returns:
        A datetime object at the end of the last day of the month.
    """
    first_day_next_month = (
        reference.replace(day=MINIMUM_DAYS_MONTH, hour=0, minute=0, second=0, microsecond=0)
        + dt.timedelta(days=4)
    ).replace(day=1)
    return first_day_next_month - dt.timedelta(milliseconds=1)


def to_utc(parsed: dt.datetime) -> dt.datetime:
    """Convert a datetime object to UTC timezone.

    Args:
        parsed: A datetime object to convert.

    Returns:
        A datetime object in UTC timezone.
    """
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def to_str(date_str: str) -> str:
    """Format a date string to a specific format in UTC timezone.

    Args:
        date_str: A date string in ISO format.

    Returns:
        A formatted date string in UTC timezone.
    """
    if not date_str:
        return ""
    parsed = to_utc(dt.datetime.fromisoformat(date_str))
    date_part = parsed.strftime("%Y-%m-%d %H:%M:%S.")
    ms = format(parsed.microsecond // 1000, "03d")
    return f"{date_part}{ms}"
