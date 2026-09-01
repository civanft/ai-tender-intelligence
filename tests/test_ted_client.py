import pytest

from tender_intelligence.config import load_taxonomy
from tender_intelligence.ted_client import TedClient, build_candidate_query


class FakeResponse:
    def __init__(self, body):
        self._body = body
        self.ok = True
        self.status_code = 200

    def json(self):
        return self._body


class PaginatedSession:
    def __init__(self):
        self.headers = {}
        self.pages = []

    def post(self, _url, *, json, timeout):
        del timeout
        self.pages.append(json["page"])
        page = json["page"]
        notices = {
            1: [{"publication-number": "1"}, {"publication-number": "2"}],
            2: [{"publication-number": "3"}, {"publication-number": "4"}],
            3: [{"publication-number": "5"}],
        }[page]
        return FakeResponse({"totalNoticeCount": 5, "notices": notices})


def test_candidate_query_contains_targets_and_sort():
    query = build_candidate_query(["FIN", "BEL", "ITA"], load_taxonomy())

    assert "buyer-country IN (BEL FIN ITA)" in query
    assert "classification-cpv" in query
    assert '"machine learning"' in query
    assert query.endswith("SORT BY publication-date DESC")


def test_candidate_query_rejects_invalid_country():
    with pytest.raises(ValueError, match="Invalid ISO"):
        build_candidate_query(["BEL OR OJ"], load_taxonomy())


def test_search_all_combines_every_page():
    session = PaginatedSession()
    result = TedClient(session=session).search_all("FT = data", page_size=2)

    assert [notice["publication-number"] for notice in result["notices"]] == [
        "1", "2", "3", "4", "5"
    ]
    assert result["fetchedPageCount"] == 3
    assert result["isComplete"] is True
    assert session.pages == [1, 2, 3]
