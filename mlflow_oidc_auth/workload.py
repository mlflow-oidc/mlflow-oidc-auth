"""Non-interactive OIDC workload identities."""

import hashlib
from dataclasses import dataclass
from typing import Any, Tuple


class WorkloadIdentityError(Exception):
    """A workload token does not carry a usable identity."""


@dataclass(frozen=True)
class WorkloadIdentity:
    """A workload identity bound to one OIDC issuer and subject."""

    issuer: str
    subject: str
    client_id: str

    @property
    def fingerprint(self) -> str:
        """Return a stable digest bound to the issuer, client, and subject."""
        external_identity = f"{self.issuer}\0{self.client_id}\0{self.subject}"
        digest = hashlib.sha256(external_identity.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @property
    def username(self) -> str:
        """Return a collision-resistant local username."""
        return f"workload.{self.fingerprint.removeprefix('sha256:')}@oidc.local"


def parse_workload_identity(
    payload: dict[str, Any],
    issuer: str,
    client_id_claim: str,
    client_id_allowlist: Tuple[str, ...],
) -> WorkloadIdentity:
    """Validate the identity claims required of a workload access token."""
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise WorkloadIdentityError("Workload token must contain a non-empty string 'sub'")

    client_id = payload.get(client_id_claim)
    if not isinstance(client_id, str) or not client_id.strip():
        raise WorkloadIdentityError(f"Workload token must contain a non-empty string {client_id_claim!r} claim")
    if client_id not in client_id_allowlist:
        raise WorkloadIdentityError("Workload client is not allowed")

    return WorkloadIdentity(
        issuer=issuer,
        subject=subject,
        client_id=client_id,
    )
