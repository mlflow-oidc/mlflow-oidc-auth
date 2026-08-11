"""Deleting a user must clear every row that references them (issue #333 follow-up).

``UserRepository.delete`` removes dependent rows by an explicit list, so a new foreign key to
``users.id`` is only handled if someone remembers to add it here. #333 added ``user_identities``
and did not, and its backfill gave **every pre-existing user** a row in that table — so after
upgrading, no account that predates the migration could be deleted.

The general case is the one worth guarding: any table with a foreign key to ``users.id`` must be
covered, or the delete fails at the database rather than in code anyone reads.
"""


import pytest
from mlflow.exceptions import MlflowException
from sqlalchemy import inspect

TOKEN = "delete-token"  # not a credential: only ever seeded into a tmp_path database


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    # A second admin, so the last-active-admin invariant (#311) never masks a delete failure.
    s.create_user("keeper@example.com", TOKEN, "Keeper", is_admin=True)
    yield s
    s.engine.dispose()


class TestDeleteClearsDependents:
    def test_a_user_with_an_identity_can_be_deleted(self, store):
        """The regression: the #333 backfill gives every pre-existing user an identity row."""
        store.create_user("legacy@example.com", TOKEN, "Legacy")
        store.user_identity_repo.link("default", "legacy@example.com", "legacy@example.com")

        store.delete_user("legacy@example.com")

        assert store.has_user("legacy@example.com") is False

    def test_the_identity_row_is_gone_too(self, store):
        """Left behind, it would collide with the next user who arrives with the same subject."""
        store.create_user("legacy@example.com", TOKEN, "Legacy")
        store.user_identity_repo.link("default", "legacy@example.com", "legacy@example.com")

        store.delete_user("legacy@example.com")

        assert store.user_identity_repo.get_username_by_identity("default", "legacy@example.com") is None

    def test_a_user_with_several_identities_can_be_deleted(self, store):
        store.create_user("multi@example.com", TOKEN, "Multi")
        store.user_identity_repo.link("okta", "sub-1", "multi@example.com")
        store.user_identity_repo.link("entra", "sub-2", "multi@example.com", allow_additional_provider=True)

        store.delete_user("multi@example.com")

        assert store.has_user("multi@example.com") is False

    def test_a_user_with_permissions_and_an_identity_can_be_deleted(self, store):
        """The combination, since the identity delete was inserted among the existing ones."""
        store.create_user("both@example.com", TOKEN, "Both")
        store.user_identity_repo.link("default", "both@example.com", "both@example.com")
        store.create_experiment_permission("exp-1", "both@example.com", "READ")

        store.delete_user("both@example.com")

        assert store.has_user("both@example.com") is False

    def test_deleting_an_unknown_user_still_raises(self, store):
        """The fix must not turn a missing user into a silent success."""
        with pytest.raises(MlflowException):
            store.delete_user("ghost@example.com")


class TestEveryForeignKeyToUsersIsCovered:
    """A guard against the next one.

    This is the check that would have caught #333: rather than listing the tables the delete
    happens to handle, ask the schema which tables reference ``users.id`` and require that a user
    holding a row in each can still be deleted.
    """

    def test_delete_succeeds_with_a_row_in_every_referencing_table(self, store):
        inspector = inspect(store.engine)
        referencing = {table: fk for table in inspector.get_table_names() for fk in inspector.get_foreign_keys(table) if fk.get("referred_table") == "users"}

        assert referencing, "expected at least one foreign key to users; the schema check itself is broken"

        # Named explicitly so a newly added table fails this test until it is handled, rather
        # than silently passing because nothing populated it.
        known = {
            "user_groups",
            "user_identities",
            "auth_sessions",
            "experiment_permissions",
            "experiment_regex_permissions",
            "registered_model_permissions",
            "registered_model_regex_permissions",
            "scorer_permissions",
            "scorer_regex_permissions",
            "gateway_endpoint_permissions",
            "gateway_endpoint_regex_permissions",
            "gateway_secret_permissions",
            "gateway_secret_regex_permissions",
            "gateway_model_definition_permissions",
            "gateway_model_definition_regex_permissions",
            "workspace_permissions",
            "workspace_regex_permissions",
            "prompt_permissions",
            "prompt_regex_permissions",
        }
        unexpected = set(referencing) - known
        assert not unexpected, (
            f"tables {sorted(unexpected)} reference users.id but are not accounted for in this test. "
            "Add them to UserRepository.delete and to this list — an unhandled foreign key makes users undeletable."
        )
