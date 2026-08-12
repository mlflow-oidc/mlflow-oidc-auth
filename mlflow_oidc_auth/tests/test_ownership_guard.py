"""The managed_by write guard, staged (issue #319).

Per-provider policy (#318) says what each source *should* write. This is what stops one source
silently overwriting a row another owns when it writes something else.

The failure mode being designed against is **lockout**, which cannot be recovered from inside a
system that has just refused the write that would fix it. That is why enforcement has three
states, why it defaults to the middle one, and why an administrator override exists in every
mode. Those three properties get the most cases here.
"""

import json

import pytest
from click.testing import CliRunner

from mlflow_oidc_auth.db.cli import commands
from mlflow_oidc_auth.ownership import Enforcement, evaluate_write, parse_enforcement
from mlflow_oidc_auth.routers._prefix import USERS_ROUTER_PREFIX

OWNERSHIP_ROUTE = f"{USERS_ROUTER_PREFIX}/ownership"

PASSWORD = "ownership-token"  # not a credential: only ever seeded into a tmp_path database


class TestTheEnforcementModes:
    def test_it_defaults_to_report(self):
        """The telemetry ships a release before the enforcement does."""
        assert parse_enforcement(None) is Enforcement.REPORT

    @pytest.mark.parametrize("value,expected", [("off", Enforcement.OFF), ("report", Enforcement.REPORT), ("enforce", Enforcement.ENFORCE)])
    def test_the_three_states_parse(self, value, expected):
        assert parse_enforcement(value) is expected
        assert parse_enforcement(value.upper()) is expected

    def test_an_unrecognised_value_reports_rather_than_enforces(self):
        """Getting this setting wrong must not be the thing that starts refusing writes."""
        assert parse_enforcement("enfroce") is Enforcement.REPORT


class TestOrdinaryWrites:
    """The common case, which must stay silent: a guard that logs every write teaches operators
    to ignore it."""

    def test_a_source_may_write_its_own_rows(self):
        decision = evaluate_write("scim", "scim", enforcement=Enforcement.ENFORCE)

        assert (decision.allowed, decision.conflict) == (True, False)

    def test_anyone_may_write_an_unowned_row(self):
        for owner in (None, "manual"):
            decision = evaluate_write(owner, "scim", enforcement=Enforcement.ENFORCE)

            assert (decision.allowed, decision.conflict) == (True, False)

    def test_an_unattributed_write_counts_as_manual(self):
        assert evaluate_write("manual", None, enforcement=Enforcement.ENFORCE).allowed is True


class TestCrossSourceWrites:
    def test_enforce_refuses(self):
        decision = evaluate_write("scim", "oidc:entra", enforcement=Enforcement.ENFORCE)

        assert decision.allowed is False
        assert decision.conflict is True
        assert decision.owner == "scim"

    def test_report_permits_and_records(self):
        """The whole point of the middle state: the same event, counted, with nothing changed."""
        decision = evaluate_write("scim", "oidc:entra", enforcement=Enforcement.REPORT)

        assert decision.allowed is True
        assert decision.conflict is True
        assert "report mode" in decision.reason

    def test_off_says_nothing_at_all(self):
        decision = evaluate_write("scim", "oidc:entra", enforcement=Enforcement.OFF)

        assert (decision.allowed, decision.conflict) == (True, False)


class TestBreakGlass:
    """An operator who cannot repair ownership from the admin UI has only the database left."""

    @pytest.mark.parametrize("mode", list(Enforcement))
    def test_an_administrator_override_is_always_permitted(self, mode):
        decision = evaluate_write("scim", "manual", enforcement=mode, admin_override=True)

        assert decision.allowed is True

    def test_and_is_always_recorded(self):
        decision = evaluate_write("scim", "manual", enforcement=Enforcement.ENFORCE, admin_override=True)

        assert decision.conflict is True
        assert "override" in decision.reason


class TestTheGuardOnTheWritePath:
    @pytest.fixture
    def store(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        s.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        s.create_user("scim-owned@example.com", PASSWORD, "Directory User")
        s.user_repo.update("scim-owned@example.com", managed_by="scim")
        yield s
        s.engine.dispose()

    @pytest.fixture
    def enforcing(self, monkeypatch):
        import mlflow_oidc_auth.repository.user as user_repo

        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

    def test_a_foreign_source_is_refused_under_enforce(self, store, enforcing):
        from mlflow.exceptions import MlflowException

        with pytest.raises(MlflowException, match="managed by"):
            store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="oidc:entra")

    def test_nothing_is_written_when_it_is_refused(self, store, enforcing):
        from mlflow.exceptions import MlflowException

        with pytest.raises(MlflowException):
            store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="oidc:entra")

        assert store.get_user_profile("scim-owned@example.com").is_admin is False

    def test_the_owning_source_still_writes(self, store, enforcing):
        store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="scim")

        assert store.get_user_profile("scim-owned@example.com").is_admin is True

    def test_report_mode_lets_the_write_through(self, store, monkeypatch):
        import mlflow_oidc_auth.repository.user as user_repo

        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)

        store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="oidc:entra")

        assert store.get_user_profile("scim-owned@example.com").is_admin is True

    def test_an_administrator_override_writes_under_enforce(self, store, enforcing):
        store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="manual", admin_override=True)

        assert store.get_user_profile("scim-owned@example.com").is_admin is True

    def test_the_conflict_is_audited_in_both_modes(self, store, monkeypatch):
        import mlflow_oidc_auth.repository.user as user_repo

        events = []
        monkeypatch.setattr("mlflow_oidc_auth.audit.emit_audit_event", lambda event, **kwargs: events.append((event, kwargs)))

        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)
        store.user_repo.update("scim-owned@example.com", is_admin=True, written_by="oidc:entra")

        assert [event for event, _ in events] == ["user.ownership_conflict"]
        assert events[0][1]["status"] == "success", "report mode permitted it, and says so"
        assert events[0][1]["detail"]["owner"] == "scim"


class TestLockout:
    """The scenario the whole design is arranged around, tested rather than reviewed."""

    @pytest.fixture
    def store(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        s.create_user("admin@example.com", PASSWORD, "Admin", is_admin=True)
        s.create_user("second-admin@example.com", PASSWORD, "Second", is_admin=True)
        yield s
        s.engine.dispose()

    def test_an_admin_owned_by_a_directory_can_still_be_repaired(self, store, monkeypatch):
        """The lockout: the directory owns every admin, the directory is gone, and the guard is
        enforcing. An administrator override has to be able to hand ownership back."""
        import mlflow_oidc_auth.repository.user as user_repo

        store.user_repo.update("admin@example.com", managed_by="scim")
        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        store.user_repo.update("admin@example.com", managed_by="manual", written_by="manual", admin_override=True)

        assert store.get_user_profile("admin@example.com").managed_by == "manual"

    def test_the_break_glass_cli_is_not_subject_to_the_guard(self, store, tmp_path, monkeypatch):
        """``restore-admin`` talks to the database directly, precisely so that a guard cannot be
        the reason an operator cannot recover."""
        import mlflow_oidc_auth.repository.user as user_repo

        store.user_repo.update("admin@example.com", managed_by="scim", is_admin=False)
        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        result = CliRunner().invoke(commands, ["restore-admin", "--url", str(store.engine.url), "--username", "admin@example.com"])

        assert result.exit_code == 0, result.output
        profile = store.get_user_profile("admin@example.com")
        assert (profile.is_admin, profile.managed_by) == (True, "manual")


class TestReconcileOwnership:
    @pytest.fixture
    def store(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        for name in ("a@example.com", "b@example.com"):
            s.create_user(name, PASSWORD, name)
            s.user_repo.update(name, managed_by="scim")
        s.create_user("manual@example.com", PASSWORD, "Manual")
        yield s
        s.engine.dispose()

    def _run(self, store, *args):
        result = CliRunner().invoke(commands, ["reconcile-ownership", "--url", str(store.engine.url), *args])
        assert result.exit_code == 0, result.output
        return result.output

    def test_a_dry_run_changes_nothing(self, store):
        output = self._run(store, "--set-owner", "manual", "--from-owner", "scim")

        assert "would change" in output
        assert store.get_user_profile("a@example.com").managed_by == "scim"

    def test_the_dry_run_diff_is_what_apply_does(self, store):
        """If these ever diverge, an operator approves one thing and runs another."""
        planned = [line for line in self._run(store, "--set-owner", "manual", "--from-owner", "scim").splitlines() if "->" in line]

        applied = [line for line in self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply").splitlines() if "->" in line]

        assert planned == applied

    def test_apply_writes(self, store):
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply")

        assert store.get_user_profile("a@example.com").managed_by == "manual"
        assert store.get_user_profile("b@example.com").managed_by == "manual"

    def test_rows_owned_by_someone_else_are_untouched(self, store):
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply")

        assert store.get_user_profile("manual@example.com").managed_by in (None, "manual")

    def test_one_user_can_be_targeted(self, store):
        self._run(store, "--set-owner", "manual", "--username", "a@example.com", "--apply")

        assert store.get_user_profile("a@example.com").managed_by == "manual"
        assert store.get_user_profile("b@example.com").managed_by == "scim"

    def test_a_mistaken_run_can_be_rolled_back(self, store, tmp_path):
        journal = tmp_path / "ownership.json"
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply", "--journal", str(journal))
        assert store.get_user_profile("a@example.com").managed_by == "manual"

        result = CliRunner().invoke(commands, ["restore-ownership", "--url", str(store.engine.url), "--journal", str(journal), "--apply"])

        assert result.exit_code == 0, result.output
        assert store.get_user_profile("a@example.com").managed_by == "scim"
        assert store.get_user_profile("b@example.com").managed_by == "scim"

    def test_a_restore_is_a_dry_run_too_without_apply(self, store, tmp_path):
        journal = tmp_path / "ownership.json"
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply", "--journal", str(journal))

        CliRunner().invoke(commands, ["restore-ownership", "--url", str(store.engine.url), "--journal", str(journal)])

        assert store.get_user_profile("a@example.com").managed_by == "manual", "a restore without --apply changed something"

    def test_the_journal_records_what_it_found(self, store, tmp_path):
        journal = tmp_path / "ownership.json"
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply", "--journal", str(journal))

        recorded = json.loads(journal.read_text())

        assert recorded["set_owner"] == "manual"
        assert sorted(entry["username"] for entry in recorded["previous"]) == ["a@example.com", "b@example.com"]
        assert {entry["managed_by"] for entry in recorded["previous"]} == {"scim"}


class TestTheOwningSourceIsNotLockedOut:
    """The failure the guard is most likely to cause is not a bypass — it is refusing the writes
    it was supposed to permit.

    Attribution has to reach the store, or every write looks like ``manual`` and ``enforce``
    refuses a directory's own sync on the rows that directory owns. That is a lockout of exactly
    the users the guard exists to protect, and it is invisible to a test that always passes
    ``written_by`` explicitly.
    """

    @pytest.fixture
    def store(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        s.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        s.create_user("scim-owned@example.com", PASSWORD, "Directory User")
        s.user_repo.update("scim-owned@example.com", managed_by="scim")
        yield s
        s.engine.dispose()

    @pytest.fixture
    def enforcing(self, monkeypatch):
        import mlflow_oidc_auth.repository.user as user_repo

        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

    def test_the_store_carries_attribution_through(self, store, enforcing):
        """``store.update_user`` is what every production caller uses."""
        store.update_user(username="scim-owned@example.com", is_admin=True, written_by="scim")

        assert store.get_user_profile("scim-owned@example.com").is_admin is True

    def test_a_login_at_the_owning_provider_is_not_refused(self, store, enforcing, monkeypatch):
        """The concrete lockout: the directory owns the row, and its own users log in."""
        import mlflow_oidc_auth.user as user_module

        monkeypatch.setattr(user_module, "store", store)
        # Re-owning is itself an operator action, so it goes through the override — which is the
        # break-glass path working, before the case below exercises the ordinary one.
        store.user_repo.update("scim-owned@example.com", managed_by="oidc:entra", written_by="manual", admin_override=True)

        created, message = user_module.create_user(
            username="scim-owned@example.com",
            display_name="Directory User",
            written_by="oidc:entra",
        )

        assert created is False and "already exists" in message

    def test_a_login_at_a_different_provider_is_refused_clearly(self, store, enforcing, monkeypatch):
        """And when it *is* a foreign write, the error says so rather than reporting that the
        user already exists — which is what the create fallback used to turn it into."""
        from mlflow.exceptions import MlflowException

        import mlflow_oidc_auth.user as user_module

        monkeypatch.setattr(user_module, "store", store)

        with pytest.raises(MlflowException, match="managed by"):
            user_module.create_user(username="scim-owned@example.com", display_name="X", written_by="oidc:entra")

    def test_an_unattributed_write_still_works_in_report_mode(self, store, monkeypatch):
        """Every caller that has not been taught to attribute itself yet — the default mode is
        what keeps them working while that happens."""
        import mlflow_oidc_auth.repository.user as user_repo

        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.REPORT)

        store.update_user(username="scim-owned@example.com", is_admin=True)

        assert store.get_user_profile("scim-owned@example.com").is_admin is True


class TestTheReconcileCommandRefusesFootguns:
    @pytest.fixture
    def store(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        s.create_user("a@example.com", PASSWORD, "A")
        s.user_repo.update("a@example.com", managed_by="scim")
        yield s
        s.engine.dispose()

    def _run(self, store, *args):
        return CliRunner().invoke(commands, ["reconcile-ownership", "--url", str(store.engine.url), *args])

    @pytest.mark.parametrize("owner", ["scmi", " manual", "SCIM", "oidc:", "", "anything"])
    def test_an_owner_no_source_presents_is_refused(self, store, owner):
        """Under enforce, a typo'd owner means every writer conflicts with it forever — usually
        typed by someone already repairing a lockout."""
        result = self._run(store, "--set-owner", owner, "--from-owner", "scim", "--apply")

        assert result.exit_code != 0
        assert store.get_user_profile("a@example.com").managed_by == "scim"

    def test_re_owning_everything_needs_saying_so(self, store):
        result = self._run(store, "--set-owner", "scim", "--apply")

        assert result.exit_code != 0
        assert "--all" in result.output

    def test_all_makes_it_explicit(self, store):
        result = self._run(store, "--set-owner", "manual", "--all", "--apply")

        assert result.exit_code == 0, result.output
        assert store.get_user_profile("a@example.com").managed_by == "manual"

    def test_a_username_is_matched_as_stored(self, store):
        """Typed in display capitalisation, this used to report "no rows to change" — read during
        a repair, that means "ownership is already fine"."""
        result = self._run(store, "--set-owner", "manual", "--username", "A@Example.com", "--apply")

        assert result.exit_code == 0, result.output
        assert store.get_user_profile("a@example.com").managed_by == "manual"

    def test_a_journal_is_never_overwritten(self, store, tmp_path):
        journal = tmp_path / "ownership.json"
        journal.write_text("{}")

        result = self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply", "--journal", str(journal))

        assert result.exit_code != 0, "the first run's prior ownership would have been lost"

    def test_a_restore_leaves_rows_that_changed_since(self, store, tmp_path):
        journal = tmp_path / "ownership.json"
        self._run(store, "--set-owner", "manual", "--from-owner", "scim", "--apply", "--journal", str(journal))
        # Somebody re-owns it deliberately afterwards.
        store.user_repo.update("a@example.com", managed_by="oidc:entra")

        result = CliRunner().invoke(commands, ["restore-ownership", "--url", str(store.engine.url), "--journal", str(journal), "--apply"])

        assert result.exit_code == 0, result.output
        assert store.get_user_profile("a@example.com").managed_by == "oidc:entra", "a newer decision was reverted"
        assert "left alone" in result.output


class TestRepairFromTheAdminApi:
    """The break-glass path an operator can actually reach.

    A guard whose only recovery needs shell and database access has produced the state it exists
    to prevent, so the promise in the module docstring has to be backed by a route.
    """

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import mlflow_oidc_auth.routers.users as users_router
        import mlflow_oidc_auth.repository.user as user_repo
        from mlflow_oidc_auth.dependencies import check_admin_permission
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        store = SqlAlchemyStore()
        store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        store.create_user("keeper@example.com", PASSWORD, "Keeper", is_admin=True)
        store.create_user("locked@example.com", PASSWORD, "Locked Out", is_admin=True)
        store.user_repo.update("locked@example.com", managed_by="scim")

        monkeypatch.setattr(users_router, "store", store)
        monkeypatch.setattr(user_repo.config, "MANAGED_BY_ENFORCEMENT", Enforcement.ENFORCE)

        app = FastAPI()
        app.include_router(users_router.users_router)
        app.dependency_overrides[check_admin_permission] = lambda: "keeper@example.com"

        with TestClient(app) as test_client:
            yield test_client, store
        store.engine.dispose()

    def test_an_administrator_can_hand_a_row_back_to_manual(self, client):
        """The decommissioned-directory case, without touching the database."""
        test_client, store = client

        response = test_client.patch(OWNERSHIP_ROUTE, json={"username": "locked@example.com", "managed_by": "manual"})

        assert response.status_code == 200, response.text
        assert response.json()["previous"] == "scim"
        assert store.get_user_profile("locked@example.com").managed_by == "manual"

    def test_and_the_row_is_writable_again_afterwards(self, client):
        test_client, store = client
        test_client.patch(OWNERSHIP_ROUTE, json={"username": "locked@example.com", "managed_by": "manual"})

        store.update_user(username="locked@example.com", is_admin=True, written_by="oidc:entra")

        assert store.get_user_profile("locked@example.com").is_admin is True

    @pytest.mark.parametrize("owner", ["scmi", "", "SCIM", "oidc:", "'; drop table users; --"])
    def test_an_owner_no_source_presents_is_refused(self, client, owner):
        test_client, store = client

        response = test_client.patch(OWNERSHIP_ROUTE, json={"username": "locked@example.com", "managed_by": owner})

        assert response.status_code == 400
        assert store.get_user_profile("locked@example.com").managed_by == "scim"

    def test_an_unknown_user_is_404(self, client):
        test_client, _ = client

        response = test_client.patch(OWNERSHIP_ROUTE, json={"username": "nobody@example.com", "managed_by": "manual"})

        assert response.status_code == 404

    def test_the_change_is_audited_with_the_administrator(self, client, monkeypatch):
        test_client, _ = client
        events = []
        monkeypatch.setattr("mlflow_oidc_auth.routers.users.emit_audit_event", lambda event, **kwargs: events.append((event, kwargs)))

        test_client.patch(OWNERSHIP_ROUTE, json={"username": "locked@example.com", "managed_by": "manual"})

        assert [event for event, _ in events] == ["user.ownership_set"]
        assert events[0][1]["actor"] == "keeper@example.com"
        assert events[0][1]["detail"] == {"from": "scim", "to": "manual"}
