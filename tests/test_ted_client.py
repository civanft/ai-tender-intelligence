import pytest

from tender_intelligence.config import load_taxonomy
from tender_intelligence.ted_client import TedApiError, TedClient, build_candidate_query


class FakeResponse:
    def __init__(self, body, *, ok=True, status_code=200):
        self._body = body
        self.ok = ok
        self.status_code = status_code

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


def test_search_rejects_more_notices_than_requested():
    class OversizedSession:
        headers = {}

        def post(self, _url, *, json, timeout):
            del timeout
            notices = [{"publication-number": str(index)} for index in range(json["limit"] + 1)]
            return FakeResponse({"totalNoticeCount": len(notices), "notices": notices})

    with pytest.raises(TedApiError, match="more notices than requested"):
        TedClient(session=OversizedSession()).search("FT = data", limit=2)


def test_query_validation_accepts_ted_null_total_count():
    class ValidationSession:
        headers = {}

        def post(self, _url, *, json, timeout):
            del json, timeout
            return FakeResponse({"totalNoticeCount": None, "notices": []})

    result = TedClient(session=ValidationSession()).validate_query("FT = data")

    assert result["totalNoticeCount"] == 0


def test_api_error_text_cannot_inject_new_log_lines():
    class ErrorSession:
        headers = {}

        def post(self, _url, *, json, timeout):
            del json, timeout
            return FakeResponse(
                {"message": "failed\n::warning:: forged"}, ok=False, status_code=400
            )

    with pytest.raises(TedApiError) as error:
        TedClient(session=ErrorSession()).search("FT = data")

    assert "\n" not in str(error.value)
    assert str(error.value).endswith("failed ::warning:: forged")
