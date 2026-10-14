"""Every resource whose creator gets a grant must also have its grants cleaned up on delete and
moved on rename.

The after-request handler map is maintained by hand, so a renamable resource added to MLflow, or
a create handler added here without its delete counterpart, would silently leave grants behind
on a name. This pins the matrix against MLflow's own request messages.
"""

import pytest
from mlflow.protos import model_registry_pb2, service_pb2

from mlflow_oidc_auth.hooks.after_request import AFTER_REQUEST_PATH_HANDLERS, CREATOR_GRANT_HANDLERS

# Resources whose grants are keyed by an id MLflow never reuses: nothing to move or wipe.
ID_KEYED = {"Experiment": "grants are keyed by experiment id, which is never reused"}

# Creates whose message name is not Create<Resource>.
RESOURCE_OF_CREATE = {"RegisterScorer": "Scorer"}

_MESSAGE_MODULES = (service_pb2, model_registry_pb2)


def _message(name):
    for module in _MESSAGE_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    return None


def _creator_grant_resources():
    resources = []
    for message, handler in AFTER_REQUEST_PATH_HANDLERS.items():
        if handler in CREATOR_GRANT_HANDLERS:
            name = message.__name__
            resources.append(RESOURCE_OF_CREATE.get(name, name.removeprefix("Create")))
    return sorted(resources)


def _renames(resource):
    """MLflow request messages that can change the resource's name."""
    found = []
    rename = _message(f"Rename{resource}")
    if rename is not None:
        found.append(rename)
    update = _message(f"Update{resource}")
    if update is not None:
        fields = sorted(update.DESCRIPTOR.fields, key=lambda f: f.number)
        # The first field addresses the resource. An update addressed by id that also carries a
        # name can rename it; one addressed by its name (UpdateRegisteredModel) cannot.
        if fields and fields[0].name.endswith("_id") and {f.name for f in fields} & {"name", "new_name"}:
            found.append(update)
    return found


def test_creator_grant_resources_are_known():
    assert "GatewayModelDefinition" in _creator_grant_resources()


@pytest.mark.parametrize("resource", _creator_grant_resources())
def test_every_rename_moves_grants(resource):
    if resource in ID_KEYED:
        pytest.skip(ID_KEYED[resource])
    missing = [m.__name__ for m in _renames(resource) if m not in AFTER_REQUEST_PATH_HANDLERS]
    assert not missing, f"{resource} can be renamed by {missing} but no after-request handler moves its grants"


@pytest.mark.parametrize("resource", _creator_grant_resources())
def test_every_delete_wipes_grants(resource):
    if resource in ID_KEYED:
        pytest.skip(ID_KEYED[resource])
    delete = _message(f"Delete{resource}")
    if delete is None:
        pytest.skip(f"MLflow has no Delete{resource}")
    assert delete in AFTER_REQUEST_PATH_HANDLERS, f"Delete{resource} has no after-request handler wiping its grants"
