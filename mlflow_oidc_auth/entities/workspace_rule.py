"""Domain entity for a group → workspace rule (issue #418)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class WorkspaceGroupRule:
    """A rule that grants ``permission`` on workspace ``ws`` to every group whose name matches ``pattern``.

    Attributes:
        id: Primary key. Also the precedence: when several rules match the same group and
            workspace, the lowest id wins.
        name: Unique, admin-chosen label.
        pattern: Python regex, matched with ``re.fullmatch`` against the local group name; its
            named group ``ws`` is the workspace.
        permission: ``READ``, ``USE``, ``EDIT`` or ``MANAGE``, capped by
            ``WORKSPACE_RULES_MAX_PERMISSION``.
        mode: ``report`` (write nothing, only say what would change) or ``enforce``.
        enabled: A disabled rule holds no grants and matches nothing.
        created_by: The administrator who created it.
        created_at: Creation time (UTC, naive).
        updated_at: Last change (UTC, naive).
    """

    id: int
    name: str
    pattern: str
    permission: str
    mode: str
    enabled: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RuleGrantChange:
    """One line of a rule's plan: what happens, or would happen, to one group's grant on one workspace.

    Attributes:
        action: ``grant`` (create a rule-owned grant), ``update`` (change the permission of one the
            rule already owns), ``keep`` (already as the rule wants it), ``remove`` (delete one the
            rule owns and no longer wants), ``skip`` (left alone; see ``reason``) or ``shadowed``
            (a lower-id rule wins this group and workspace).
        group: Local group name.
        workspace: Workspace name.
        permission: The permission the rule grants, or held before a ``remove``.
        reason: Why a ``skip`` or ``shadowed`` happened; None otherwise.
        previous: The permission before an ``update``; None otherwise.
        applied: Whether this was written. False for a preview and for every line of a
            ``report``-mode rule, and always False for ``keep``, ``skip`` and ``shadowed``.
        rule_id: The rule this line belongs to. A response can carry another rule's lines — the
            grants a rule takes over after the one it was shadowed by is removed.
    """

    action: str
    group: str
    workspace: str
    permission: Optional[str]
    reason: Optional[str] = None
    previous: Optional[str] = None
    applied: bool = False
    rule_id: Optional[int] = None
