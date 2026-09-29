"""Unit tests for ``mlflow_oidc_auth.utils.pagination``."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mlflow_oidc_auth.utils.pagination import (
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    NO_PAGE,
    TOTAL_COUNT_HEADER,
    PageParams,
    PageQuery,
    paginate,
    paginate_with_headers,
    total_count_headers,
)


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/items")
    async def items(page: PageQuery = NO_PAGE):
        return {"limit": page.limit, "offset": page.offset, "search": page.search}

    return TestClient(app)


class TestPageParamsDependency:
    def test_defaults(self, client):
        assert client.get("/items").json() == {"limit": None, "offset": 0, "search": None}

    def test_values(self, client):
        assert client.get("/items", params={"limit": 5, "offset": 10, "search": "x"}).json() == {"limit": 5, "offset": 10, "search": "x"}

    @pytest.mark.parametrize("limit", [1, MAX_PAGE_SIZE])
    def test_limit_bounds_accepted(self, client, limit):
        assert client.get("/items", params={"limit": limit}).status_code == 200

    @pytest.mark.parametrize(
        "params",
        [
            {"limit": 0},
            {"limit": -1},
            {"limit": MAX_PAGE_SIZE + 1},
            {"limit": "ten"},
            {"offset": -1},
            {"offset": "x"},
            {"search": "a" * (MAX_SEARCH_LENGTH + 1)},
        ],
    )
    def test_out_of_range_rejected(self, client, params):
        assert client.get("/items", params=params).status_code == 422

    def test_empty_search_is_no_search(self, client):
        assert client.get("/items", params={"search": ""}).json()["search"] is None

    def test_direct_call_default_is_inactive(self):
        assert NO_PAGE.active is False
        assert PageParams(limit=1).active is True
        assert PageParams(search="a").active is True
        assert PageParams(offset=5).active is False


class TestPaginate:
    ITEMS = ["delta", "Alpha", "charlie", "bravo", "alpha2"]

    def test_no_params_returns_everything_in_original_order(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=NO_PAGE)
        assert page == self.ITEMS
        assert total == 5

    def test_offset_without_limit_is_ignored(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=PageParams(offset=3))
        assert page == self.ITEMS
        assert total == 5

    def test_sorted_case_insensitively_before_slicing(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=PageParams(limit=2))
        assert page == ["Alpha", "alpha2"]
        assert total == 5
        page, _ = paginate(self.ITEMS, key=lambda s: s, params=PageParams(limit=2, offset=2))
        assert page == ["bravo", "charlie"]

    def test_search_is_case_insensitive_substring(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=PageParams(search="ALP"))
        assert page == ["Alpha", "alpha2"]
        assert total == 2

    def test_search_then_slice(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=PageParams(search="a", limit=2, offset=1))
        assert total == 5
        assert page == ["alpha2", "bravo"]

    def test_slice_past_end_is_empty_with_total(self):
        page, total = paginate(self.ITEMS, key=lambda s: s, params=PageParams(limit=10, offset=100))
        assert page == []
        assert total == 5

    def test_ties_broken_by_id(self):
        rows = [{"n": "same", "id": 10}, {"n": "same", "id": 2}, {"n": "same", "id": 7}]
        page, _ = paginate(rows, key=lambda r: r["n"], params=PageParams(limit=3), tiebreak=lambda r: r["id"])
        assert [r["id"] for r in page] == [2, 7, 10]

    def test_numeric_string_ids_tie_break_numerically(self):
        rows = [{"n": "x", "id": "10"}, {"n": "x", "id": "9"}, {"n": "x", "id": "abc"}]
        page, _ = paginate(rows, key=lambda r: r["n"], params=PageParams(limit=3), tiebreak=lambda r: r["id"])
        assert [r["id"] for r in page] == ["9", "10", "abc"]

    def test_case_variants_have_stable_order(self):
        rows = ["b", "B", "a", "A"]
        first, _ = paginate(rows, key=lambda s: s, params=PageParams(limit=4))
        second, _ = paginate(list(reversed(rows)), key=lambda s: s, params=PageParams(limit=4))
        assert first == second == ["A", "a", "B", "b"]

    def test_none_key_sorts_first_and_does_not_match_search(self):
        rows = [{"n": None}, {"n": "a"}]
        page, _ = paginate(rows, key=lambda r: r["n"], params=PageParams(limit=5))
        assert page == [{"n": None}, {"n": "a"}]
        page, total = paginate(rows, key=lambda r: r["n"], params=PageParams(search="a"))
        assert page == [{"n": "a"}] and total == 1

    def test_accepts_iterators(self):
        page, total = paginate(iter(self.ITEMS), key=lambda s: s, params=PageParams(limit=1))
        assert page == ["Alpha"] and total == 5


class TestHeaders:
    def test_no_header_when_inactive(self):
        assert total_count_headers(5, NO_PAGE) == {}

    def test_header_when_limited(self):
        assert total_count_headers(5, PageParams(limit=1)) == {TOTAL_COUNT_HEADER: "5"}

    def test_header_when_searched(self):
        assert total_count_headers(2, PageParams(search="x")) == {TOTAL_COUNT_HEADER: "2"}

    def test_paginate_with_headers(self):
        page, headers = paginate_with_headers(["b", "a", "c"], key=lambda s: s, params=PageParams(limit=1, offset=1))
        assert page == ["b"]
        assert headers == {TOTAL_COUNT_HEADER: "3"}
