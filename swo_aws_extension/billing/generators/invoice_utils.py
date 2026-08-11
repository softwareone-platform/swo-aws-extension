MAX_INVOICE_ID_LENGTH = 20
_INVOICE_ID_SUFFIX_LENGTH = 4
_OVERFLOW_MARKER = ".."
_SUFFIX_PREFIX = "-"
_SEPARATOR = ","


def merge_invoice_ids(existing_id: str, new_id: str) -> str:
    """Merge invoice IDs keeping only the unique suffix (last 4 chars) of each.

    Each suffix is prefixed with ``-`` to signal truncation.
    The result must fit within MAX_INVOICE_ID_LENGTH characters.
    When it overflows, an ellipsis marker replaces the newest suffix.
    """
    if not new_id:
        return existing_id
    new_suffix = _SUFFIX_PREFIX + new_id[-_INVOICE_ID_SUFFIX_LENGTH:]
    if _SEPARATOR not in existing_id:
        existing_id = _SUFFIX_PREFIX + existing_id[-_INVOICE_ID_SUFFIX_LENGTH:]
    candidate = _SEPARATOR.join((existing_id, new_suffix))
    if len(candidate) <= MAX_INVOICE_ID_LENGTH:
        return candidate
    truncated = _SEPARATOR.join((existing_id, _OVERFLOW_MARKER))
    if len(truncated) <= MAX_INVOICE_ID_LENGTH:
        return truncated
    return existing_id
