import pytest

from mlflow_oidc_auth.db.models import (
    SqlExperimentPermission,
    SqlGatewayEndpointPermission,
    SqlGatewayModelDefinitionPermission,
    SqlGatewaySecretPermission,
    SqlUser,
)
from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


def test_delete_user_with_experiment_permissions_deletes_permissions_rows(
    tmp_path,
) -> None:
    store = SqlAlchemyStore()
    db_path = tmp_path / "test.db"
    store.init_db(f"sqlite:///{db_path.as_posix()}")

    username = "user@example.com"
    store.create_user(username=username, display_name="User")
    store.create_experiment_permission(experiment_id="exp1", username=username, permission="READ")

    with store.ManagedSessionMaker() as session:
        user = session.query(SqlUser).filter(SqlUser.username == username).one()
        user_id = user.id
        assert session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).count() == 1

    store.delete_user(username)

    with store.ManagedSessionMaker() as session:
        assert session.query(SqlUser).filter(SqlUser.username == username).one_or_none() is None
        assert session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).count() == 0


def test_delete_user_with_gateway_permissions_deletes_all_gateway_rows(
    tmp_path,
) -> None:
    """Test that deleting a user also removes gateway endpoint, secret, and model definition permissions."""
    store = SqlAlchemyStore()
    db_path = tmp_path / "test.db"
    store.init_db(f"sqlite:///{db_path.as_posix()}")

    username = "gw-user@example.com"
    store.create_user(username=username, display_name="GW User")

    store.create_gateway_endpoint_permission(gateway_name="ep1", username=username, permission="READ")
    store.create_gateway_secret_permission(gateway_name="sec1", username=username, permission="READ")
    store.create_gateway_model_definition_permission(gateway_name="md1", username=username, permission="READ")

    with store.ManagedSessionMaker() as session:
        user = session.query(SqlUser).filter(SqlUser.username == username).one()
        user_id = user.id
        assert session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user_id).count() == 1
        assert session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user_id).count() == 1
        assert session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user_id).count() == 1

    store.delete_user(username)

    with store.ManagedSessionMaker() as session:
        assert session.query(SqlUser).filter(SqlUser.username == username).one_or_none() is None
        assert session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user_id).count() == 0
        assert session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user_id).count() == 0
        assert session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user_id).count() == 0
