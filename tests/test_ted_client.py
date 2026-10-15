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
    result = TedClient(session=session).search_all("FT = data", page_size=2, max_notices=5)

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


class IterationSession:
    headers = {}
    def __init__(self, fault=None):
        self.calls = []
        self.fault = fault

    def post(self, _url, *, json, timeout):
        self.calls.append(json)
        total = 15001
        if json["paginationMode"] == "PAGE_NUMBER":
            return FakeResponse({"notices": [{"publication-number": "1"}], "totalNoticeCount": total})
        offset = int(json.get("iterationNextToken", "0"))
        notices = [{"publication-number": str(i)} for i in range(offset, min(total, offset + json["limit"]))]
        token = str(offset + len(notices))
        if offset and self.fault == "repeat":
            token = json["iterationNextToken"]
        if offset and self.fault == "duplicate":
            notices[0] = {"publication-number": "0"}
        if offset and self.fault == "missing":
            token = None
        if offset and self.fault == "timeout":
            return FakeResponse({"notices": notices, "totalNoticeCount": total, "timedOut": True})
        return FakeResponse({"notices": notices, "totalNoticeCount": total, "iterationNextToken": token})


def test_iteration_retrieves_more_than_the_page_number_ceiling():
    session = IterationSession()
    result = TedClient(session=session).search_all("query")
    assert result["paginationMode"] == "ITERATION"
    assert result["isComplete"] and len(result["notices"]) == 15001
    assert len({n["publication-number"] for n in result["notices"]}) == 15001
    assert "iterationNextToken" not in result
    assert "iterationNextToken" not in session.calls[0]
    assert session.calls[1]["iterationNextToken"] == "250"


@pytest.mark.parametrize("fault", ["repeat", "duplicate", "missing", "timeout"])
def test_iteration_rejects_incomplete_or_corrupt_snapshots(fault):
    with pytest.raises(TedApiError):
        TedClient(session=IterationSession(fault)).search_all("query")


def test_limited_fetch_does_not_claim_complete_or_require_iteration():
    result = TedClient(session=IterationSession()).search_all("query", max_notices=1)
    assert not result["isComplete"]
    assert result["paginationMode"] == "PAGE_NUMBER"


def test_iteration_confirms_exhaustion_when_reported_count_exceeds_latest_rows():
    class LatestCountSession(IterationSession):
        def post(self, *args, **kwargs):
            result = super().post(*args, **kwargs)
            result._body["totalNoticeCount"] = 20000
            return result
    result = TedClient(session=LatestCountSession()).search_all("query")
    assert result["isComplete"]
    assert len(result["notices"]) == 15001
    assert result["totalNoticeCount"] == 20000


def test_iteration_rejects_an_unconfirmed_empty_page():
    class UnstableEnd(IterationSession):
        def __init__(self):
            super().__init__()
            self.empty_seen = False
        def post(self, *args, **kwargs):
            result = super().post(*args, **kwargs)
            if kwargs["json"].get("paginationMode") == "ITERATION" and not result._body["notices"]:
                if self.empty_seen:
                    result._body["notices"] = [{"publication-number": "99999"}]
                self.empty_seen = True
            return result
    with pytest.raises(TedApiError, match="could not be confirmed"):
        TedClient(session=UnstableEnd()).search_all("query")
