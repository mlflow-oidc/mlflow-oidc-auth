"""Review queues (``/3.0/mlflow/review-queues/*``) follow MLflow's own auth plugin.

Permission comes from the queue's experiment, combined with the queue's owner
(``created_by``) and assigned users (``users``):

* create: EDIT; a custom queue's name may not be a registered username (admins included).
* view (get, get-by-name, items/list): READ plus MANAGE, membership, or EDIT and ownership.
* update: MANAGE, or EDIT and ownership; ``new_owner`` needs MANAGE.
* delete, items/remove: MANAGE, or EDIT and ownership of a CUSTOM queue.
* items/add: EDIT.
* items/set-status: EDIT and membership.
* list: READ; a caller without EDIT sees only queues they are assigned to.

A personal queue can be created for any active person (the UI assigns work that way), and
review work can only be attributed to the caller. Driven through the real hook and permission
store (see ``authz_harness``).
"""

from types import SimpleNamespace

import pytest
from flask import jsonify
from mlflow.exceptions import MlflowException
from mlflow.genai.review_queues import ReviewQueueType
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    MANAGER,
    OUTSIDER,
    OWN,
    PREFIXES,
    READER,
    VICTIM,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)

NOBODY = "nobody@example.com"
INACTIVE = "former@example.com"
ROBOT = "robot-account"
EDITOR2 = "editor2@example.com"  # EDIT on VICTIM; assigned to rq-member, owns nothing
READER2 = "reader2@example.com"  # READ on VICTIM; owns rq-reader-owned, assigned to nothing

CUSTOM, USER = ReviewQueueType.CUSTOM, ReviewQueueType.USER


def _queue(queue_id, name, queue_type, created_by, users, experiment_id=VICTIM):
    return SimpleNamespace(queue_id=queue_id, name=name, experiment_id=experiment_id, queue_type=queue_type, created_by=created_by, users=users)


QUEUES = {
    q.queue_id: q
    for q in (
        # Owner stored in another case: ownership compares case-insensitively.
        _queue("rq-owned", "owned", CUSTOM, " Editor@Example.com", []),
        _queue("rq-member", "member", CUSTOM, MANAGER, [READER, EDITOR2, OUTSIDER]),
        _queue("rq-user", EDITOR, USER, EDITOR, [EDITOR]),
        _queue("rq-unowned", "unowned", CUSTOM, None, None),
        _queue("rq-reader-owned", "reader-owned", CUSTOM, READER2, []),
        _queue("rq-no-experiment", "no-experiment", CUSTOM, EDITOR, [EDITOR], experiment_id=None),
    )
}


class _FakeTrackingStore(BaseFakeTrackingStore):
    def get_review_queue(self, queue_id):
        if queue_id not in QUEUES:
            raise MlflowException(f"Review queue '{queue_id}' not found", RESOURCE_DOES_NOT_EXIST)
        return QUEUES[queue_id]

    def get_review_queue_by_name(self, experiment_id, *, name):
        for queue in QUEUES.values():
            if queue.experiment_id == experiment_id and queue.name == name:
                return queue
        raise MlflowException(f"Review queue '{name}' not found", RESOURCE_DOES_NOT_EXIST)


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _FakeTrackingStore())
    s.create_user(INACTIVE, "pw", INACTIVE)
    s.update_user(INACTIVE, active=False)
    s.create_user(ROBOT, "pw", ROBOT, is_service_account=True)
    s.create_user(EDITOR2, "pw", EDITOR2)
    s.create_user(READER2, "pw", READER2)
    s.create_experiment_permission(VICTIM, EDITOR2, "EDIT")
    s.create_experiment_permission(VICTIM, READER2, "READ")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _rq(prefix, action):
    return f"{prefix}/3.0/mlflow/review-queues/{action}"


def _bad_request(resp) -> bool:
    return resp is not None and resp.status_code == 400


# --- create ------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_create_requires_update_on_the_experiment(prefix):
    body = {"experiment_id": VICTIM, "name": "q", "queue_type": "CUSTOM"}
    assert denied(hook(_rq(prefix, "create"), "POST", OUTSIDER, body=body))
    assert denied(hook(_rq(prefix, "create"), "POST", READER, body=body))
    assert allowed(hook(_rq(prefix, "create"), "POST", EDITOR, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("caller", [EDITOR, ADMIN])
@pytest.mark.parametrize("name", [READER, "  Reader@Example.COM ", ROBOT])
@pytest.mark.parametrize("queue_type", ["CUSTOM", 2])
def test_a_custom_queue_cannot_be_named_after_a_registered_user(prefix, caller, name, queue_type):
    body = {"experiment_id": VICTIM, "name": name, "queue_type": queue_type}
    assert _bad_request(hook(_rq(prefix, "create"), "POST", caller, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_the_username_rule_applies_to_a_name_in_any_request_source(prefix):
    body = {"experiment_id": VICTIM, "name": "fine", "queue_type": "CUSTOM"}
    assert _bad_request(hook(_rq(prefix, "create"), "POST", EDITOR, body=body, query={"name": READER}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("caller", [EDITOR, ADMIN])
def test_a_user_queue_is_named_after_its_user(prefix, caller):
    body = {"experiment_id": VICTIM, "name": READER, "queue_type": "USER"}
    assert allowed(hook(_rq(prefix, "create"), "POST", caller, body=body))
    body = {"experiment_id": VICTIM, "name": "not-a-user", "queue_type": "CUSTOM"}
    assert allowed(hook(_rq(prefix, "create"), "POST", caller, body=body))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("assignee", [NOBODY, INACTIVE, ROBOT], ids=["nonexistent", "inactive", "service-account"])
def test_a_user_queue_is_created_only_for_an_active_person(prefix, assignee):
    body = {"experiment_id": VICTIM, "name": assignee, "queue_type": "USER"}
    assert denied(hook(_rq(prefix, "create"), "POST", EDITOR, body=body))
    assert denied(hook(_rq(prefix, "create"), "POST", EDITOR, body={**body, "name": READER}, query={"name": assignee}))
    assert denied(hook(_rq(prefix, "create"), "POST", EDITOR, body={**body, "queue_type": 1}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_the_username_rule_is_checked_only_after_the_permission(prefix):
    """A caller without the permission gets 403, not a hint about which usernames exist."""
    body = {"experiment_id": VICTIM, "name": READER, "queue_type": "CUSTOM"}
    assert denied(hook(_rq(prefix, "create"), "POST", OUTSIDER, body=body))


# --- get-or-create-user (unchanged) ------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_personal_queue_can_be_assigned_to_a_teammate_with_update(prefix):
    """MLflow's UI calls get-or-create-user with the ASSIGNEE when it routes a trace."""
    path = _rq(prefix, "get-or-create-user")
    assert allowed(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": EDITOR}))
    assert allowed(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": READER}))
    assert allowed(hook(path, "POST", EDITOR, body={"experiment_id": VICTIM, "user": READER.upper()}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_personal_queue_needs_update_on_the_experiment(prefix):
    path = _rq(prefix, "get-or-create-user")
    assert denied(hook(path, "POST", READER, body={"experiment_id": VICTIM, "user": READER}))
    assert denied(hook(path, "POST", OUTSIDER, body={"experiment_id": VICTIM, "user": EDITOR}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("assignee", [NOBODY, INACTIVE, ROBOT], ids=["nonexistent", "inactive", "service-account"])
def test_personal_queue_is_refused_for_anyone_but_an_active_person(prefix, assignee):
    path = _rq(prefix, "get-or-create-user")
    assert denied(hook(path, "POST", MANAGER, body={"experiment_id": VICTIM, "user": assignee}))
    # A second assignee hidden in the query string is checked too.
    assert denied(hook(path, "POST", MANAGER, body={"experiment_id": VICTIM, "user": READER}, query={"user": assignee}))


# --- view: get, items/list, get-by-name --------------------------------------

_VIEW_ALLOWED = [
    (MANAGER, "rq-owned"),
    (MANAGER, "rq-unowned"),
    (EDITOR, "rq-owned"),  # EDIT owner
    (READER, "rq-member"),  # READ member
    (EDITOR2, "rq-member"),  # EDIT member
]
_VIEW_DENIED = [
    (EDITOR2, "rq-owned"),  # EDIT, neither owner nor member
    (READER, "rq-owned"),  # READ, not a member
    (READER2, "rq-member"),  # READ, not a member
    (READER2, "rq-reader-owned"),  # ownership needs EDIT
    (EDITOR, "rq-unowned"),  # a queue with no owner and no users
    (OUTSIDER, "rq-member"),  # assigned, but no READ on the experiment
    (EDITOR, "rq-no-experiment"),  # the experiment cannot be resolved
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["get", "items/list"])
@pytest.mark.parametrize("user, queue_id", _VIEW_ALLOWED)
def test_viewing_a_queue_is_allowed_to_managers_members_and_edit_owners(prefix, action, user, queue_id):
    assert allowed(hook(_rq(prefix, action), "GET", user, query={"queue_id": queue_id}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["get", "items/list"])
@pytest.mark.parametrize("user, queue_id", _VIEW_DENIED)
def test_viewing_a_queue_is_refused_to_everyone_else(prefix, action, user, queue_id):
    assert denied(hook(_rq(prefix, action), "GET", user, query={"queue_id": queue_id}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("user, queue_id", _VIEW_ALLOWED)
def test_viewing_a_queue_by_name_is_allowed_to_managers_members_and_edit_owners(prefix, user, queue_id):
    query = {"experiment_id": VICTIM, "name": QUEUES[queue_id].name}
    assert allowed(hook(_rq(prefix, "get-by-name"), "GET", user, query=query))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("user, queue_id", [d for d in _VIEW_DENIED if d[1] != "rq-no-experiment"])
def test_viewing_a_queue_by_name_is_refused_to_everyone_else(prefix, user, queue_id):
    query = {"experiment_id": VICTIM, "name": QUEUES[queue_id].name}
    assert denied(hook(_rq(prefix, "get-by-name"), "GET", user, query=query))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_an_unknown_queue_name_is_refused_unless_the_caller_manages_the_experiment(prefix):
    query = {"experiment_id": VICTIM, "name": "missing"}
    assert denied(hook(_rq(prefix, "get-by-name"), "GET", READER, query=query))
    assert denied(hook(_rq(prefix, "get-by-name"), "GET", EDITOR, query=query))
    # A manager reaches MLflow, which answers with its own not-found error.
    assert allowed(hook(_rq(prefix, "get-by-name"), "GET", MANAGER, query=query))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_listing_an_experiment_s_queues_requires_read(prefix):
    assert denied(hook(_rq(prefix, "list"), "GET", OUTSIDER, query={"experiment_id": VICTIM}))
    assert allowed(hook(_rq(prefix, "list"), "GET", READER, query={"experiment_id": VICTIM}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_second_queue_id_in_another_source_must_be_viewable_too(prefix):
    assert denied(hook(_rq(prefix, "get"), "GET", READER, query=[("queue_id", "rq-member"), ("queue_id", "rq-owned")]))


# --- update ------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_updating_a_queue_is_for_its_edit_owner_or_a_manager(prefix):
    path = _rq(prefix, "update")
    assert allowed(hook(path, "POST", EDITOR, body={"queue_id": "rq-owned", "name": "renamed"}))
    assert allowed(hook(path, "POST", MANAGER, body={"queue_id": "rq-owned", "name": "renamed"}))
    assert denied(hook(path, "POST", EDITOR2, body={"queue_id": "rq-owned", "name": "renamed"}))
    assert denied(hook(path, "POST", EDITOR2, body={"queue_id": "rq-member", "name": "renamed"}))  # member, not owner
    assert denied(hook(path, "POST", READER2, body={"queue_id": "rq-reader-owned", "name": "renamed"}))  # owner, but READ
    assert denied(hook(path, "POST", OUTSIDER, body={"queue_id": "rq-owned", "name": "renamed"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_changing_a_queue_owner_requires_manage(prefix):
    path = _rq(prefix, "update")
    assert denied(hook(path, "POST", EDITOR, body={"queue_id": "rq-owned", "new_owner": EDITOR2}))
    assert denied(hook(path, "POST", EDITOR, body={"queue_id": "rq-owned"}, query={"new_owner": EDITOR2}))
    assert allowed(hook(path, "POST", MANAGER, body={"queue_id": "rq-owned", "new_owner": EDITOR2}))


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("caller", [EDITOR, ADMIN])
def test_a_custom_queue_cannot_be_renamed_to_a_registered_user(prefix, caller):
    path = _rq(prefix, "update")
    assert _bad_request(hook(path, "POST", caller, body={"queue_id": "rq-owned", "name": READER.upper()}))
    assert allowed(hook(path, "POST", caller, body={"queue_id": "rq-owned", "name": "fresh-name"}))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_rename_by_a_caller_without_permission_is_refused_before_the_name_is_checked(prefix):
    assert denied(hook(_rq(prefix, "update"), "POST", EDITOR2, body={"queue_id": "rq-owned", "name": READER}))


# --- delete and items/remove -------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action, extra", [("delete", {}), ("items/remove", {"item_ids": ["t"]})])
def test_deleting_or_pruning_a_queue_is_for_a_manager_or_the_edit_owner_of_a_custom_queue(prefix, action, extra):
    path = _rq(prefix, action)
    assert allowed(hook(path, "POST", MANAGER, body={"queue_id": "rq-owned", **extra}))
    assert allowed(hook(path, "POST", MANAGER, body={"queue_id": "rq-user", **extra}))
    assert allowed(hook(path, "POST", EDITOR, body={"queue_id": "rq-owned", **extra}))
    # A USER queue's lifecycle belongs to a manager, even when the caller owns it.
    assert denied(hook(path, "POST", EDITOR, body={"queue_id": "rq-user", **extra}))
    assert denied(hook(path, "POST", EDITOR2, body={"queue_id": "rq-owned", **extra}))
    assert denied(hook(path, "POST", EDITOR2, body={"queue_id": "rq-member", **extra}))
    assert denied(hook(path, "POST", READER2, body={"queue_id": "rq-reader-owned", **extra}))
    assert denied(hook(path, "POST", EDITOR, body={"queue_id": "rq-no-experiment", **extra}))


# --- items/add ---------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_adding_items_requires_update_on_the_experiment(prefix):
    path = _rq(prefix, "items/add")
    body = {"queue_id": "rq-owned", "item_ids": ["t"]}
    assert allowed(hook(path, "POST", EDITOR2, body=body))
    assert denied(hook(path, "POST", READER, body={**body, "queue_id": "rq-member"}))
    assert denied(hook(path, "POST", OUTSIDER, body=body))


# --- items/set-status --------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("status", ["COMPLETE", "DECLINED", 2])
def test_finishing_an_item_requires_update_membership_and_names_the_caller_as_reviewer(prefix, status):
    path = _rq(prefix, "items/set-status")
    body = {"queue_id": "rq-member", "item_id": "t", "status": status, "completed_by": EDITOR2}
    assert allowed(hook(path, "POST", EDITOR2, body=body))
    assert denied(hook(path, "POST", READER, body={**body, "completed_by": READER}))  # member, but READ
    assert denied(hook(path, "POST", EDITOR, body={**body, "completed_by": EDITOR}))  # EDIT, not a member
    assert denied(hook(path, "POST", MANAGER, body={**body, "completed_by": MANAGER}))  # a manager must be assigned too
    assert denied(hook(path, "POST", EDITOR2, body={**body, "completed_by": MANAGER}))
    # Omitted reviewer on a terminal state: the item would carry no attribution.
    no_reviewer = {k: v for k, v in body.items() if k != "completed_by"}
    assert denied(hook(path, "POST", EDITOR2, body=no_reviewer))


@pytest.mark.parametrize("prefix", PREFIXES)
def test_reopening_an_item_needs_no_reviewer_but_refuses_someone_else(prefix):
    path = _rq(prefix, "items/set-status")
    body = {"queue_id": "rq-member", "item_id": "t", "status": "PENDING"}
    assert allowed(hook(path, "POST", EDITOR2, body=body))
    assert allowed(hook(path, "POST", EDITOR2, body={**body, "completed_by": EDITOR2}))
    assert denied(hook(path, "POST", EDITOR2, body={**body, "completed_by": MANAGER}))
    assert denied(hook(path, "POST", READER, body=body))
    assert denied(hook(path, "POST", EDITOR, body=body))


# --- list response filter ----------------------------------------------------


def _list_as(username, prefix="/api", query=None):
    from mlflow.server import app as mlflow_app

    from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
    from mlflow_oidc_auth.hooks.after_request import after_request_hook

    payload = {
        "review_queues": [
            {"queue_id": "rq-owned", "name": "owned", "experiment_id": VICTIM, "created_by": EDITOR, "users": []},
            {"queue_id": "rq-member", "name": "member", "experiment_id": VICTIM, "created_by": MANAGER, "users": [READER, EDITOR2]},
            {"queue_id": "rq-user", "name": READER2, "experiment_id": VICTIM, "users": ["Reader2@Example.com"]},
        ],
        "next_page_token": "tok",
    }
    environ = {AUTH_CONTEXT_KEY: AuthContext(username=username, is_admin=username == ADMIN)}
    with mlflow_app.test_request_context(_rq(prefix, "list"), method="GET", query_string=query or {"experiment_id": VICTIM}, environ_base=environ):
        body = after_request_hook(jsonify(payload)).get_json()
    return [q["queue_id"] for q in body.get("review_queues", [])], body.get("next_page_token")


@pytest.mark.parametrize("user", [ADMIN, MANAGER, EDITOR])
def test_the_queue_list_is_complete_for_admins_and_editors(user):
    assert _list_as(user) == (["rq-owned", "rq-member", "rq-user"], "tok")


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("user, visible", [(READER, ["rq-member"]), (READER2, ["rq-user"]), (OUTSIDER, [])])
def test_the_queue_list_shows_a_read_only_caller_only_their_assigned_queues(prefix, user, visible):
    queue_ids, token = _list_as(user, prefix)
    assert queue_ids == visible
    assert token == "tok"


def test_the_queue_list_is_filtered_when_a_second_experiment_is_read_only(permission_store):
    """EDIT on one experiment does not widen the list when another source names one with READ."""
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    permission_store.create_experiment_permission(OWN, EDITOR, "READ")
    flush_permission_cache()
    queue_ids, _ = _list_as(EDITOR, query=[("experiment_id", VICTIM), ("experiment_id", OWN)])
    assert queue_ids == []


# --- misc --------------------------------------------------------------------


def test_the_hook_tells_mlflow_who_the_caller_is():
    """MLflow stamps a queue's owner and an item's reviewer from g.mlflow_authenticated_user."""
    from mlflow.server import app as mlflow_app
    from mlflow.server.handlers import _get_request_username

    from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    body = {"experiment_id": VICTIM, "name": "q", "queue_type": "CUSTOM"}
    for user, is_admin in ((EDITOR, False), ("admin@example.com", True)):
        environ = {AUTH_CONTEXT_KEY: AuthContext(username=user, is_admin=is_admin)}
        with mlflow_app.test_request_context("/api/3.0/mlflow/review-queues/create", method="POST", json=body, environ_base=environ):
            assert before_request_hook() is None
            assert _get_request_username() == user


def test_the_hook_does_not_overwrite_an_already_authenticated_user():
    from flask import g
    from mlflow.server import app as mlflow_app

    from mlflow_oidc_auth.entities.auth_context import AUTH_CONTEXT_KEY, AuthContext
    from mlflow_oidc_auth.hooks.before_request import before_request_hook

    environ = {AUTH_CONTEXT_KEY: AuthContext(username=EDITOR, is_admin=False)}
    with mlflow_app.test_request_context("/api/3.0/mlflow/review-queues/list", query_string={"experiment_id": VICTIM}, environ_base=environ):
        g.mlflow_authenticated_user = "set-earlier"
        before_request_hook()
        assert g.mlflow_authenticated_user == "set-earlier"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_an_unknown_queue_is_not_served(prefix):
    resp = hook(_rq(prefix, "get"), "GET", MANAGER, query={"queue_id": "rq-missing"})
    assert resp is not None and resp.status_code in (403, 404)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_second_experiment_in_the_query_string_is_authorized_too(prefix):
    body = {"experiment_id": OWN, "name": "q", "queue_type": "CUSTOM"}
    assert denied(hook(_rq(prefix, "create"), "POST", OUTSIDER, body=body, query={"experiment_id": VICTIM}))
