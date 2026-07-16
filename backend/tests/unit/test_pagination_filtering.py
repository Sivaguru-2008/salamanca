from __future__ import annotations

import pytest
from app.core.errors import ValidationAppError
from app.core.filtering import FilterOperator, parse_filters, parse_sort
from app.core.pagination import Page, PageParams, decode_cursor, encode_cursor

ALLOWED = frozenset({"email", "role", "created_at"})


class TestCursor:
    def test_roundtrip(self) -> None:
        for offset in (0, 1, 20, 999_999):
            assert decode_cursor(encode_cursor(offset)) == offset

    def test_invalid_cursor_rejected(self) -> None:
        with pytest.raises(ValidationAppError):
            decode_cursor("!!!not-base64!!!")

    def test_negative_offset_rejected(self) -> None:
        import base64
        import json

        raw = base64.urlsafe_b64encode(json.dumps({"o": -5}).encode()).decode().rstrip("=")
        with pytest.raises(ValidationAppError):
            decode_cursor(raw)

    def test_non_numeric_offset_rejected(self) -> None:
        import base64
        import json

        raw = base64.urlsafe_b64encode(json.dumps({"o": "abc"}).encode()).decode().rstrip("=")
        with pytest.raises(ValidationAppError):
            decode_cursor(raw)


class TestPage:
    def test_next_cursor_present_when_more(self) -> None:
        params = PageParams(limit=10, offset=0)
        page = Page[int].build(list(range(10)), total=25, params=params)
        assert page.next_cursor is not None
        assert decode_cursor(page.next_cursor) == 10

    def test_next_cursor_absent_at_end(self) -> None:
        params = PageParams(limit=10, offset=20)
        page = Page[int].build([1, 2, 3], total=23, params=params)
        assert page.next_cursor is None

    def test_from_query(self) -> None:
        params = PageParams.from_query(limit=5, cursor=encode_cursor(15))
        assert params.limit == 5
        assert params.offset == 15


class TestFilters:
    def test_parse_valid(self) -> None:
        filters = parse_filters(["email:ilike:alice", "role:eq:owner"], ALLOWED)
        assert filters[0].operator is FilterOperator.ILIKE
        assert filters[1].value == "owner"

    def test_value_may_contain_colons(self) -> None:
        filters = parse_filters(["created_at:gte:2026-01-01T00:00:00Z"], ALLOWED)
        assert filters[0].value == "2026-01-01T00:00:00Z"

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationAppError):
            parse_filters(["hashed_password:eq:x"], ALLOWED)

    def test_unknown_operator_rejected(self) -> None:
        with pytest.raises(ValidationAppError):
            parse_filters(["email:regex:x"], ALLOWED)

    def test_malformed_rejected(self) -> None:
        with pytest.raises(ValidationAppError):
            parse_filters(["email"], ALLOWED)


class TestSort:
    def test_parse_multi(self) -> None:
        fields = parse_sort("-created_at,email", ALLOWED)
        assert fields[0].field == "created_at" and fields[0].descending
        assert fields[1].field == "email" and not fields[1].descending

    def test_default_applied(self) -> None:
        fields = parse_sort(None, ALLOWED, default="-created_at")
        assert fields[0].field == "created_at"

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationAppError):
            parse_sort("secret", ALLOWED)
