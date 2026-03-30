"""
Tests for AuthContext frozen dataclass.
"""

import pytest
from mlflow_oidc_auth.entities.auth_context import AuthContext


class TestAuthContext:
    """Test cases for AuthContext dataclass"""

    def test_construction_all_fields(self):
        """Test AuthContext construction with all fields"""
        ctx = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        assert ctx.username == "user@example.com"
        assert ctx.is_admin is True
        assert ctx.workspace == "ws1"

    def test_construction_default_workspace(self):
        """Test AuthContext default workspace is None"""
        ctx = AuthContext(username="user@example.com", is_admin=False)
        assert ctx.username == "user@example.com"
        assert ctx.is_admin is False
        assert ctx.workspace is None

    def test_frozen_immutable_username(self):
        """Test AuthContext is frozen — cannot change username"""
        ctx = AuthContext(username="user@example.com", is_admin=False)
        with pytest.raises(AttributeError):
            ctx.username = "other@example.com"

    def test_frozen_immutable_is_admin(self):
        """Test AuthContext is frozen — cannot change is_admin"""
        ctx = AuthContext(username="user@example.com", is_admin=False)
        with pytest.raises(AttributeError):
            ctx.is_admin = True

    def test_frozen_immutable_workspace(self):
        """Test AuthContext is frozen — cannot change workspace"""
        ctx = AuthContext(username="user@example.com", is_admin=False, workspace="ws1")
        with pytest.raises(AttributeError):
            ctx.workspace = "ws2"

    def test_equality(self):
        """Test AuthContext equality (dataclass default)"""
        ctx1 = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        ctx2 = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        assert ctx1 == ctx2

    def test_inequality_different_username(self):
        """Test AuthContext inequality with different username"""
        ctx1 = AuthContext(username="user1@example.com", is_admin=True)
        ctx2 = AuthContext(username="user2@example.com", is_admin=True)
        assert ctx1 != ctx2

    def test_inequality_different_workspace(self):
        """Test AuthContext inequality with different workspace"""
        ctx1 = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        ctx2 = AuthContext(username="user@example.com", is_admin=True, workspace="ws2")
        assert ctx1 != ctx2

    def test_repr(self):
        """Test AuthContext string representation"""
        ctx = AuthContext(username="user@example.com", is_admin=False, workspace="ws1")
        repr_str = repr(ctx)
        assert "user@example.com" in repr_str
        assert "False" in repr_str
        assert "ws1" in repr_str

    def test_hash(self):
        """Test AuthContext is hashable (frozen dataclass)"""
        ctx = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        # frozen dataclasses are hashable
        assert hash(ctx) is not None

        # Equal objects have equal hashes
        ctx2 = AuthContext(username="user@example.com", is_admin=True, workspace="ws1")
        assert hash(ctx) == hash(ctx2)

    def test_workspace_none_vs_absent(self):
        """Test that explicit None and default are identical"""
        ctx1 = AuthContext(username="user@example.com", is_admin=False, workspace=None)
        ctx2 = AuthContext(username="user@example.com", is_admin=False)
        assert ctx1 == ctx2
