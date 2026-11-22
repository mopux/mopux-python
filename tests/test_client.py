from __future__ import annotations

from urllib.parse import unquote

import httpx
import pytest

from mopux import (
    AsyncMopux,
    AuthenticationError,
    AuthorizationError,
    ClientError,
    InvalidInputError,
    MalformedResponseError,
    Mopux,
    MopuxConnectionError,
    NotFoundError,
    Page,
    RateLimitError,
    RetryPolicy,
    ServerError,
    UncertainWriteError,
    Upload,
    ValidationError,
)
from mopux.testing import MockApi


def client(api: MockApi, retry: RetryPolicy | None = None) -> Mopux:
    return Mopux("https://acme.mopux.test/api/v1/", "1|secret", http_client=api.client(), retry=retry)


class TestRequests:
    def test_sends_token_json_headers_and_user_agent_and_parses_models(self) -> None:
        api = MockApi().push(MockApi.json({"id": 12, "title": "Web", "unknown_field": "kept"}))
        project = client(api).projects.show(12)

        assert project.id == 12
        assert project.title == "Web"
        assert project.model_extra == {"unknown_field": "kept"}
        request = api.assert_sent("GET", "projects/12")
        assert request.url.host == "acme.mopux.test"
        assert request.headers["authorization"] == "Bearer 1|secret"
        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"].startswith("mopux-python/")

    def test_token_function_and_laravel_style_query(self) -> None:
        api = MockApi().push(MockApi.json([]))
        mopux = Mopux("https://acme.test", lambda: "from-vault", http_client=api.client())

        mopux.tasks.my(search="web", project_ids=[3, 4])

        request = api.assert_sent("GET", "tasks/my")
        assert request.headers["authorization"] == "Bearer from-vault"
        assert unquote(request.url.query.decode()) == "search=web&params[projects][]=3&params[projects][]=4"

    def test_booleans_as_one_and_zero(self) -> None:
        api = MockApi().push(MockApi.json({"id": 12, "task_groups": []}))
        client(api).projects.board(12, statuses=[0, 1])
        assert unquote(api.requests[0].url.query.decode()) == "archived=0&params[status][]=0&params[status][]=1"

    def test_none_clears_and_unset_is_not_sent(self) -> None:
        api = MockApi().push(MockApi.json({"id": 101}))
        client(api).tasks.update(101, description=None, assignees={"operation": "replace", "user_ids": []})
        assert api.requests[0].json == {"description": None, "assignees": {"operation": "replace", "user_ids": []}}

    def test_normalizes_hours_and_validates_before_sending(self) -> None:
        api = MockApi().always(MockApi.json({"id": 101}))
        mopux = client(api)

        mopux.tasks.update_hours(101, expected=90, inverted=None)
        assert api.requests[0].json == {"hours_expected": "01:30", "hours_inverted": None}

        with pytest.raises(InvalidInputError):
            mopux.tasks.update_hours(101, expected="1:75")
        with pytest.raises(InvalidInputError):
            mopux.tasks.update_status(101, -1)  # type: ignore[arg-type]
        with pytest.raises(InvalidInputError):
            mopux.tasks.update_start(101, "2026-02-30")
        with pytest.raises(InvalidInputError):
            mopux.projects.show(0)
        with pytest.raises(InvalidInputError):
            mopux.comments.create(101, "   ")
        with pytest.raises(InvalidInputError):
            mopux.tasks.update(101)
        assert len(api.requests) == 1

    def test_rejects_an_invalid_base_url(self) -> None:
        with pytest.raises(InvalidInputError):
            Mopux("acme.mopux.com")


class TestErrors:
    @pytest.mark.parametrize(
        ("status", "error_class"),
        [
            (401, AuthenticationError),
            (403, AuthorizationError),
            (404, NotFoundError),
            (409, ClientError),
            (422, ValidationError),
        ],
    )
    def test_maps_http_status(self, status: int, error_class: type[Exception]) -> None:
        api = MockApi().push(MockApi.error(status, "Nope"))
        with pytest.raises(error_class) as caught:
            client(api).projects.show(12)
        assert caught.value.status == status  # type: ignore[attr-defined]
        assert caught.value.path == "projects/12"  # type: ignore[attr-defined]

    def test_plan_restriction_and_field_errors(self) -> None:
        api = MockApi().push(
            MockApi.plan_restricted("api"), MockApi.validation({"title": ["The title field is required."]})
        )
        mopux = client(api)

        with pytest.raises(AuthorizationError) as plan:
            mopux.tasks.my()
        assert plan.value.is_plan_restriction()
        assert plan.value.plan_feature == "api"
        assert not plan.value.is_billing_blocked()

        with pytest.raises(ValidationError) as invalid:
            mopux.tasks.update_title(101, "x")
        assert invalid.value.errors == {"title": ["The title field is required."]}
        assert "The title field is required." in str(invalid.value)
        assert "(HTTP 422)" in str(invalid.value)

    def test_5xx_write_is_uncertain_and_never_retried(self) -> None:
        api = MockApi().always(MockApi.error(500, "Server Error."))
        with pytest.raises(UncertainWriteError, match="outcome is uncertain"):
            client(api).tasks.create(1, 2, "x")
        assert len(api.requests) == 1

    def test_write_is_not_retried_after_a_network_error(self) -> None:
        api = MockApi().always(MockApi.network_error())
        with pytest.raises(MopuxConnectionError) as caught:
            client(api).tasks.delete(101)
        assert caught.value.is_write_outcome_uncertain
        assert len(api.requests) == 1

    def test_rejects_a_body_that_is_not_the_envelope(self) -> None:
        api = MockApi().push(httpx.Response(200, text="<html>"), MockApi.json({"id": "not-a-number"}))
        with pytest.raises(MalformedResponseError):
            client(api).projects.show(1)
        with pytest.raises(MalformedResponseError, match="ProjectDetail"):
            client(api).projects.show(1)


class TestRetries:
    def test_retries_reads_after_5xx_and_network_errors(self, no_sleep: list[float]) -> None:
        api = MockApi().push(MockApi.error(503, "Unavailable"), MockApi.network_error(), MockApi.json({"id": 12}))
        assert client(api).projects.show(12).id == 12
        assert len(api.requests) == 3
        assert len(no_sleep) == 2
        assert no_sleep[0] >= 0.25 and no_sleep[1] >= 0.5

    def test_gives_up_after_max_retries(self) -> None:
        api = MockApi().always(MockApi.error(502, "Bad gateway"))
        with pytest.raises(ServerError):
            client(api, RetryPolicy(max_retries=1)).projects.show(1)
        assert len(api.requests) == 2

    def test_waits_retry_after_on_429_but_not_when_too_long(self, no_sleep: list[float]) -> None:
        api = MockApi().push(
            MockApi.error(429, "Too Many Attempts.", headers={"Retry-After": "3"}),
            MockApi.json({"id": 1}),
            MockApi.error(429, "Too Many Attempts.", headers={"Retry-After": "120"}),
        )
        mopux = client(api)
        mopux.tasks.update_title(1, "x")
        assert no_sleep == [3.0]
        with pytest.raises(RateLimitError) as caught:
            mopux.tasks.update_title(1, "y")
        assert caught.value.retry_after == 120


class TestPagination:
    def test_laravel_pagination_and_lazy_iteration(self) -> None:
        def page(items: list[int], current: int) -> httpx.Response:
            meta = {"current_page": current, "last_page": 2, "per_page": 2, "total": 3}
            return MockApi.json({"data": [{"id": i} for i in items], "links": {}, "meta": meta})

        api = MockApi().push(page([1, 2], 1), page([3], 2))
        assert [project.id for project in client(api).projects.iter(per_page=2)] == [1, 2, 3]
        assert [r.url.params["page"] for r in api.requests] == ["1", "2"]

    def test_plain_list_of_api_1_1_stops_at_a_short_page(self) -> None:
        api = MockApi().push(MockApi.json([{"id": 1}, {"id": 2}]), MockApi.json([{"id": 3}]))
        assert [comment.id for comment in client(api).comments.iter(101, per_page=2)] == [1, 2, 3]
        assert len(api.requests) == 2

    def test_page_fields_inside_the_object(self) -> None:
        api = MockApi().push(MockApi.json({"members": [{"id": 5}], "page": 1, "last_page": 3, "total": 51}))
        team = client(api).team.list(per_page=25)
        assert isinstance(team, Page)
        assert [member.id for member in team] == [5]
        assert team.total == 51
        assert team.next_page() == 2


class TestUploadsAndLogin:
    def test_comment_with_files_is_multipart_with_bracketed_names(self) -> None:
        api = MockApi().push(MockApi.json({"id": 9}))
        client(api).comments.create(
            101, "See attached", mentions=[5, 6], files=[Upload.from_bytes("hello", "notes.txt", "text/plain")]
        )
        request = api.assert_sent("POST", "tasks/101/comments")
        body = request.content.decode()
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert 'name="comment"' in body and "See attached" in body
        assert body.count('name="mentions[]"') == 2
        assert 'name="files[]"; filename="notes.txt"' in body and "hello" in body

    def test_login_returns_a_client_with_the_new_token(self) -> None:
        api = MockApi().push(
            MockApi.json({"token_type": "Bearer", "token": "7|new", "user": {"id": 1}}),
            MockApi.json({"user": {"id": 1, "name": "Ada"}}),
        )
        mopux = Mopux.login("https://acme.test", "ada@acme.test", "pw", token_name="cli", http_client=api.client())

        assert mopux.token == "7|new"
        assert "authorization" not in api.requests[0].headers
        assert api.requests[0].json == {"email": "ada@acme.test", "password": "pw", "token_name": "cli"}
        assert mopux.auth.user().name == "Ada"
        assert api.requests[1].headers["authorization"] == "Bearer 7|new"

    def test_group_with_and_without_tasks(self) -> None:
        api = MockApi().push(
            MockApi.json({"group": {"id": 7, "title": "Sprint"}, "tasks": [{"id": 101}]}),
            MockApi.json({"id": 8, "title": "Empty"}),
        )
        mopux = client(api)
        with_tasks = mopux.task_groups.create(12, "Sprint", [{"title": "First"}])
        assert (with_tasks.id, [task.id for task in with_tasks.tasks]) == (7, [101])
        assert mopux.task_groups.create(12, "Empty").tasks == []


class TestAsync:
    async def test_async_client_works_end_to_end(self, no_sleep: list[float]) -> None:
        api = MockApi().push(MockApi.error(503, "Unavailable"), MockApi.json([{"id": 1, "title": "T", "status": -1}]))
        async with AsyncMopux("https://acme.test", "t", http_client=api.async_client()) as mopux:
            tasks = await mopux.tasks.my()
        assert [(task.id, task.status) for task in tasks] == [(1, -1)]
        assert len(no_sleep) == 1

    async def test_async_iteration_and_errors(self) -> None:
        uuid = "9b2f6a3e-1c1d-4e8f-9f0a-6f1d2c3b4a5e"
        api = MockApi().push(MockApi.json([{"id": uuid}]), MockApi.plan_restricted())
        async with AsyncMopux("https://acme.test", "t", http_client=api.async_client()) as mopux:
            assert [str(n.id) async for n in mopux.notifications.iter(per_page=5)] == [uuid]
            with pytest.raises(AuthorizationError) as caught:
                await mopux.tasks.my()
        assert caught.value.is_plan_restriction()
