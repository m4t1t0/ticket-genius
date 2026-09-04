"""Cursor-based pagination utilities."""

import base64
import json
from uuid import UUID


def encode_cursor(last_seen_id: UUID, last_seen_sort_key: str) -> str:
    """
    Encode cursor as opaque base64 token.

    Args:
        last_seen_id: Last seen entity ID
        last_seen_sort_key: Sort key value (e.g., created_at ISO string)

    Returns:
        Base64 encoded cursor string
    """
    data = {"id": str(last_seen_id), "sort_key": last_seen_sort_key}
    json_str = json.dumps(data, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> tuple[UUID, str] | None:
    """
    Decode cursor from opaque base64 token.

    Args:
        cursor: Base64 encoded cursor string

    Returns:
        Tuple of (UUID, sort_key) or None if invalid
    """
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(json_str)
        return (UUID(data["id"]), data["sort_key"])
    except Exception:
        return None


def apply_cursor_filter(query, cursor: str | None, id_column, sort_column) -> tuple:
    """
    Apply cursor-based filtering to a SQLAlchemy query.

    Uses keyset pagination: WHERE (sort_key, id) < (cursor_sort_key, cursor_id)

    Args:
        query: SQLAlchemy query
        cursor: Opaque cursor string
        id_column: ID column (e.g., Order.order_id)
        sort_column: Sort column (e.g., Order.created_at)

    Returns:
        Tuple of (filtered_query, decoded_cursor_tuple_or_None)
    """
    if not cursor:
        return query, None

    decoded = decode_cursor(cursor)
    if not decoded:
        return query, None

    cursor_id, cursor_sort_key = decoded

    # Keyset pagination: (sort_key, id) < (cursor_sort_key, cursor_id)
    # For DESC ordering: WHERE (sort_key < cursor_sort_key)
    #                    OR (sort_key = cursor_sort_key AND id < cursor_id)
    from sqlalchemy import and_, or_

    query = query.filter(
        or_(
            sort_column < cursor_sort_key,
            and_(sort_column == cursor_sort_key, id_column < cursor_id),
        )
    )

    return query, decoded


def get_next_cursor(results: list, id_attr: str, sort_attr: str) -> str | None:
    """
    Generate next cursor from query results.

    Args:
        results: List of result objects
        id_attr: Name of ID attribute (e.g., 'order_id')
        sort_attr: Name of sort attribute (e.g., 'created_at')

    Returns:
        Next cursor string or None if no results
    """
    if not results:
        return None

    last = results[-1]
    last_id = getattr(last, id_attr)
    last_sort_key = getattr(last, sort_attr)

    # Convert datetime to ISO string if needed
    if hasattr(last_sort_key, "isoformat"):
        last_sort_key = last_sort_key.isoformat()

    return encode_cursor(last_id, last_sort_key)
