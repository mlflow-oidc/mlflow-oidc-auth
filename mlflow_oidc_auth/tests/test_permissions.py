"""
Test cases for mlflow_oidc_auth.permissions module.

This module contains comprehensive tests for the core permission system
including permission objects, validation, comparison, and edge cases.
"""

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.permissions import (
    Permission,
    READ,
    EDIT,
    MANAGE,
    NO_PERMISSIONS,
    ALL_PERMISSIONS,
    get_permission,
    _validate_permission,
    compare_permissions,
)


class TestPermissionDataclass:
    """Test cases for the Permission dataclass."""

    def test_permission_creation(self):
        """Test Permission dataclass creation with all attributes."""
        perm = Permission(
            name="TEST",
            priority=5,
            can_read=True,
            can_update=False,
            can_delete=True,
            can_manage=False,
        )

        assert perm.name == "TEST"
        assert perm.priority == 5
        assert perm.can_read is True
        assert perm.can_update is False
        assert perm.can_delete is True
        assert perm.can_manage is False

    def test_permission_equality(self):
        """Test Permission dataclass equality comparison."""
        perm1 = Permission("TEST", 1, True, False, False, False)
        perm2 = Permission("TEST", 1, True, False, False, False)
        perm3 = Permission("OTHER", 1, True, False, False, False)

        assert perm1 == perm2
        assert perm1 != perm3

    def test_permission_repr(self):
        """Test Permission dataclass string representation."""
        perm = Permission("TEST", 1, True, False, False, False)
        repr_str = repr(perm)

        assert "Permission" in repr_str
        assert "TEST" in repr_str
        assert "priority=1" in repr_str


class TestPredefinedPermissions:
    """Test cases for predefined permission constants."""

    def test_read_permission(self):
        """Test READ permission properties."""
        assert READ.name == "READ"
        assert READ.priority == 1
        assert READ.can_read is True
        assert READ.can_update is False
        assert READ.can_delete is False
        assert READ.can_manage is False

    def test_edit_permission(self):
        """Test EDIT permission properties."""
        assert EDIT.name == "EDIT"
        assert EDIT.priority == 2
        assert EDIT.can_read is True
        assert EDIT.can_update is True
        assert EDIT.can_delete is False
        assert EDIT.can_manage is False

    def test_manage_permission(self):
        """Test MANAGE permission properties."""
        assert MANAGE.name == "MANAGE"
        assert MANAGE.priority == 3
        assert MANAGE.can_read is True
        assert MANAGE.can_update is True
        assert MANAGE.can_delete is True
        assert MANAGE.can_manage is True

    def test_no_permissions(self):
        """Test NO_PERMISSIONS properties."""
        assert NO_PERMISSIONS.name == "NO_PERMISSIONS"
        assert NO_PERMISSIONS.priority == 100
        assert NO_PERMISSIONS.can_read is False
        assert NO_PERMISSIONS.can_update is False
        assert NO_PERMISSIONS.can_delete is False
        assert NO_PERMISSIONS.can_manage is False

    def test_all_permissions_dict(self):
        """Test ALL_PERMISSIONS dictionary contains all predefined permissions."""
        assert len(ALL_PERMISSIONS) == 4
        assert ALL_PERMISSIONS["READ"] == READ
        assert ALL_PERMISSIONS["EDIT"] == EDIT
        assert ALL_PERMISSIONS["MANAGE"] == MANAGE
        assert ALL_PERMISSIONS["NO_PERMISSIONS"] == NO_PERMISSIONS

    def test_permission_priority_hierarchy(self):
        """Test that permission priorities follow expected hierarchy."""
        assert READ.priority < EDIT.priority
        assert EDIT.priority < MANAGE.priority
        assert MANAGE.priority < NO_PERMISSIONS.priority


class TestGetPermission:
    """Test cases for get_permission function."""

    def test_get_valid_permissions(self):
        """Test retrieving valid permissions."""
        # Test line 62: return ALL_PERMISSIONS[permission]
        read_perm = get_permission("READ")
        assert read_perm == READ
        assert read_perm.name == "READ"

        edit_perm = get_permission("EDIT")
        assert edit_perm == EDIT
        assert edit_perm.name == "EDIT"

        manage_perm = get_permission("MANAGE")
        assert manage_perm == MANAGE
        assert manage_perm.name == "MANAGE"

        no_perm = get_permission("NO_PERMISSIONS")
        assert no_perm == NO_PERMISSIONS
        assert no_perm.name == "NO_PERMISSIONS"

    def test_get_invalid_permission(self):
        """Test retrieving invalid permission raises KeyError."""
        with pytest.raises(KeyError):
            get_permission("INVALID_PERMISSION")

    def test_get_permission_case_sensitive(self):
        """Test that permission retrieval is case sensitive."""
        with pytest.raises(KeyError):
            get_permission("read")  # lowercase

        with pytest.raises(KeyError):
            get_permission("Read")  # mixed case

    def test_get_permission_empty_string(self):
        """Test retrieving permission with empty string."""
        with pytest.raises(KeyError):
            get_permission("")

    def test_get_permission_none(self):
        """Test retrieving permission with None."""
        with pytest.raises(KeyError):
            get_permission(None)


class TestValidatePermission:
    """Test cases for _validate_permission function."""

    def test_validate_valid_permissions(self):
        """Test validation of valid permissions passes without exception."""
        # These should not raise any exceptions
        _validate_permission("READ")
        _validate_permission("EDIT")
        _validate_permission("MANAGE")
        _validate_permission("NO_PERMISSIONS")

    def test_validate_invalid_permission(self):
        """Test validation of invalid permission raises MlflowException."""
        # Test lines 66-67: exception raising in _validate_permission
        with pytest.raises(MlflowException) as exc_info:
            _validate_permission("INVALID_PERMISSION")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'INVALID_PERMISSION'" in str(exc_info.value)
        assert "Valid permissions are:" in str(exc_info.value)
        assert "('READ', 'EDIT', 'MANAGE', 'NO_PERMISSIONS')" in str(exc_info.value)

    def test_validate_permission_case_sensitive(self):
        """Test validation is case sensitive."""
        with pytest.raises(MlflowException) as exc_info:
            _validate_permission("read")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'read'" in str(exc_info.value)

    def test_validate_permission_empty_string(self):
        """Test validation of empty string."""
        with pytest.raises(MlflowException) as exc_info:
            _validate_permission("")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission ''" in str(exc_info.value)

    def test_validate_permission_none(self):
        """Test validation of None value."""
        with pytest.raises(MlflowException) as exc_info:
            _validate_permission(None)

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'None'" in str(exc_info.value)

    def test_validate_permission_numeric(self):
        """Test validation of numeric input."""
        with pytest.raises(MlflowException) as exc_info:
            _validate_permission("123")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"

    def test_validate_permission_special_characters(self):
        """Test validation with special characters."""
        special_chars = ["@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "+", "="]

        for char in special_chars:
            with pytest.raises(MlflowException) as exc_info:
                _validate_permission(char)

            assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"


class TestComparePermissions:
    """Test cases for compare_permissions function."""

    def test_compare_same_permissions(self):
        """Test comparing identical permissions."""
        # Test lines 84-86: validation calls and comparison logic
        assert compare_permissions("READ", "READ") is True
        assert compare_permissions("EDIT", "EDIT") is True
        assert compare_permissions("MANAGE", "MANAGE") is True
        assert compare_permissions("NO_PERMISSIONS", "NO_PERMISSIONS") is True

    def test_compare_different_valid_permissions(self):
        """Test comparing different valid permissions."""
        # READ (priority 1) <= EDIT (priority 2)
        assert compare_permissions("READ", "EDIT") is True

        # READ (priority 1) <= MANAGE (priority 3)
        assert compare_permissions("READ", "MANAGE") is True

        # READ (priority 1) <= NO_PERMISSIONS (priority 100)
        assert compare_permissions("READ", "NO_PERMISSIONS") is True

        # EDIT (priority 2) <= MANAGE (priority 3)
        assert compare_permissions("EDIT", "MANAGE") is True

        # EDIT (priority 2) <= NO_PERMISSIONS (priority 100)
        assert compare_permissions("EDIT", "NO_PERMISSIONS") is True

        # MANAGE (priority 3) <= NO_PERMISSIONS (priority 100)
        assert compare_permissions("MANAGE", "NO_PERMISSIONS") is True

    def test_compare_reverse_priority_order(self):
        """Test comparing permissions in reverse priority order."""
        # EDIT (priority 2) > READ (priority 1)
        assert compare_permissions("EDIT", "READ") is False

        # MANAGE (priority 3) > READ (priority 1)
        assert compare_permissions("MANAGE", "READ") is False

        # MANAGE (priority 3) > EDIT (priority 2)
        assert compare_permissions("MANAGE", "EDIT") is False

        # NO_PERMISSIONS (priority 100) > all others
        assert compare_permissions("NO_PERMISSIONS", "READ") is False
        assert compare_permissions("NO_PERMISSIONS", "EDIT") is False
        assert compare_permissions("NO_PERMISSIONS", "MANAGE") is False

    def test_compare_invalid_first_permission(self):
        """Test comparing with invalid first permission."""
        with pytest.raises(MlflowException) as exc_info:
            compare_permissions("INVALID", "READ")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'INVALID'" in str(exc_info.value)

    def test_compare_invalid_second_permission(self):
        """Test comparing with invalid second permission."""
        with pytest.raises(MlflowException) as exc_info:
            compare_permissions("READ", "INVALID")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'INVALID'" in str(exc_info.value)

    def test_compare_both_invalid_permissions(self):
        """Test comparing with both invalid permissions."""
        with pytest.raises(MlflowException) as exc_info:
            compare_permissions("INVALID1", "INVALID2")

        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"
        assert "Invalid permission 'INVALID1'" in str(exc_info.value)

    def test_compare_permissions_edge_cases(self):
        """Test permission comparison edge cases."""
        # Empty strings
        with pytest.raises(MlflowException):
            compare_permissions("", "READ")

        with pytest.raises(MlflowException):
            compare_permissions("READ", "")

        # Case sensitivity
        with pytest.raises(MlflowException):
            compare_permissions("read", "READ")

        with pytest.raises(MlflowException):
            compare_permissions("READ", "edit")

    def test_compare_permissions_none_values(self):
        """Test permission comparison with None values."""
        with pytest.raises(MlflowException) as exc_info:
            compare_permissions(None, "READ")
        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"

        with pytest.raises(MlflowException) as exc_info:
            compare_permissions("READ", None)
        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"

        with pytest.raises(MlflowException) as exc_info:
            compare_permissions(None, None)
        assert exc_info.value.error_code == "INVALID_PARAMETER_VALUE"


class TestPermissionSystemIntegration:
    """Integration tests for the permission system."""

    def test_permission_hierarchy_consistency(self):
        """Test that permission hierarchy is consistent across all functions."""
        permissions = ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]

        # Test that each permission can be retrieved and validated
        for perm_name in permissions:
            perm = get_permission(perm_name)
            assert perm.name == perm_name
            _validate_permission(perm_name)  # Should not raise

    def test_permission_comparison_transitivity(self):
        """Test transitivity of permission comparisons."""
        # If A <= B and B <= C, then A <= C
        assert compare_permissions("READ", "EDIT") is True
        assert compare_permissions("EDIT", "MANAGE") is True
        assert compare_permissions("READ", "MANAGE") is True  # Transitivity

    def test_permission_comparison_reflexivity(self):
        """Test reflexivity of permission comparisons."""
        # A <= A should always be true
        for perm_name in ALL_PERMISSIONS.keys():
            assert compare_permissions(perm_name, perm_name) is True

    def test_permission_system_completeness(self):
        """Test that the permission system covers all expected scenarios."""
        # Verify all predefined permissions are in ALL_PERMISSIONS
        expected_permissions = {"READ", "EDIT", "MANAGE", "NO_PERMISSIONS"}
        actual_permissions = set(ALL_PERMISSIONS.keys())

        assert expected_permissions == actual_permissions

    def test_permission_capabilities_hierarchy(self):
        """Test that permission capabilities follow logical hierarchy."""
        # READ: only read
        assert READ.can_read is True
        assert READ.can_update is False
        assert READ.can_delete is False
        assert READ.can_manage is False

        # EDIT: read + update
        assert EDIT.can_read is True
        assert EDIT.can_update is True
        assert EDIT.can_delete is False
        assert EDIT.can_manage is False

        # MANAGE: read + update + delete + manage
        assert MANAGE.can_read is True
        assert MANAGE.can_update is True
        assert MANAGE.can_delete is True
        assert MANAGE.can_manage is True

        # NO_PERMISSIONS: nothing
        assert NO_PERMISSIONS.can_read is False
        assert NO_PERMISSIONS.can_update is False
        assert NO_PERMISSIONS.can_delete is False
        assert NO_PERMISSIONS.can_manage is False


class TestPermissionPerformance:
    """Performance tests for permission operations."""

    def test_get_permission_performance(self):
        """Test performance of get_permission function."""
        import time

        # Warm up
        for _ in range(100):
            get_permission("READ")

        # Measure performance
        start_time = time.time()
        for _ in range(10000):
            get_permission("READ")
            get_permission("EDIT")
            get_permission("MANAGE")
            get_permission("NO_PERMISSIONS")
        end_time = time.time()

        # Should complete 40,000 operations in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0

    def test_compare_permissions_performance(self):
        """Test performance of compare_permissions function."""
        import time

        # Warm up
        for _ in range(100):
            compare_permissions("READ", "EDIT")

        # Measure performance
        start_time = time.time()
        for _ in range(5000):
            compare_permissions("READ", "EDIT")
            compare_permissions("EDIT", "MANAGE")
            compare_permissions("MANAGE", "NO_PERMISSIONS")
            compare_permissions("READ", "MANAGE")
        end_time = time.time()

        # Should complete 20,000 operations in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0

    def test_validate_permission_performance(self):
        """Test performance of _validate_permission function."""
        import time

        # Warm up
        for _ in range(100):
            _validate_permission("READ")

        # Measure performance
        start_time = time.time()
        for _ in range(10000):
            _validate_permission("READ")
            _validate_permission("EDIT")
            _validate_permission("MANAGE")
            _validate_permission("NO_PERMISSIONS")
        end_time = time.time()

        # Should complete 40,000 operations in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0


class TestPermissionBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_permission_name_boundaries(self):
        """Test permission names at boundaries."""
        # Very long permission name
        long_name = "A" * 1000
        with pytest.raises(MlflowException):
            _validate_permission(long_name)

    def test_permission_with_whitespace(self):
        """Test permissions with whitespace."""
        whitespace_perms = [" READ", "READ ", " READ ", "\tREAD", "READ\n"]

        for perm in whitespace_perms:
            with pytest.raises(MlflowException):
                _validate_permission(perm)

    def test_permission_unicode_characters(self):
        """Test permissions with unicode characters."""
        unicode_perms = ["RËAD", "读取", "ЧТЕНИЕ", "🔒"]

        for perm in unicode_perms:
            with pytest.raises(MlflowException):
                _validate_permission(perm)

    def test_permission_comparison_consistency(self):
        """Test that permission comparison is consistent."""
        # Test all combinations
        perms = ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]

        for perm1 in perms:
            for perm2 in perms:
                result1 = compare_permissions(perm1, perm2)
                result2 = compare_permissions(perm1, perm2)  # Should be same
                assert result1 == result2
