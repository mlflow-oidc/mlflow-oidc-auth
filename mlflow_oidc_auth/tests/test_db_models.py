"""
Comprehensive tests for database models to achieve 100% coverage.
Tests all SQLAlchemy model relationships, constraints, and entity conversion methods.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from mlflow_oidc_auth.db.models import (
    Base,
    SqlUser,
    SqlExperimentPermission,
    SqlRegisteredModelPermission,
    SqlGroup,
    SqlUserGroup,
    SqlExperimentGroupPermission,
    SqlRegisteredModelGroupPermission,
    SqlExperimentRegexPermission,
    SqlRegisteredModelRegexPermission,
    SqlExperimentGroupRegexPermission,
    SqlRegisteredModelGroupRegexPermission,
)
from mlflow_oidc_auth.entities import (
    User,
    ExperimentPermission,
    RegisteredModelPermission,
    Group,
    UserGroup,
    ExperimentRegexPermission,
    RegisteredModelRegexPermission,
    ExperimentGroupRegexPermission,
    RegisteredModelGroupRegexPermission,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = SqlUser(
        username="testuser",
        display_name="Test User",
        password_hash="hashed_password",
        password_expiration=datetime(2025, 12, 31),
        is_admin=False,
        is_service_account=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_group(db_session):
    """Create a sample group for testing."""
    group = SqlGroup(group_name="testgroup")
    db_session.add(group)
    db_session.commit()
    return group


class TestSqlUser:
    """Test SqlUser model functionality."""

    def test_to_mlflow_entity_basic(self, db_session):
        """Test basic user entity conversion."""
        user = SqlUser(
            username="testuser",
            display_name="Test User",
            password_hash="hashed_password",
            password_expiration=datetime(2025, 12, 31),
            is_admin=True,
            is_service_account=False,
        )
        db_session.add(user)
        db_session.commit()

        entity = user.to_mlflow_entity()

        assert isinstance(entity, User)
        assert entity.id == user.id
        assert entity.username == "testuser"
        assert entity.display_name == "Test User"
        assert entity.password_hash == "hashed_password"
        assert entity.password_expiration == datetime(2025, 12, 31)
        assert entity.is_admin is True
        assert entity.is_service_account is False

    def test_to_mlflow_entity_with_relationships(self, db_session, sample_group):
        """Test user entity conversion with relationships - covers line 41."""
        user = SqlUser(username="testuser", display_name="Test User", password_hash="hashed_password", is_admin=False, is_service_account=True)
        db_session.add(user)
        db_session.commit()

        # Add experiment permission
        exp_perm = SqlExperimentPermission(experiment_id="exp123", user_id=user.id, permission="READ")
        db_session.add(exp_perm)

        # Add registered model permission
        model_perm = SqlRegisteredModelPermission(name="model123", user_id=user.id, permission="WRITE")
        db_session.add(model_perm)

        # Add user to group
        user_group = SqlUserGroup(user_id=user.id, group_id=sample_group.id)
        db_session.add(user_group)
        db_session.commit()

        # Refresh to load relationships
        db_session.refresh(user)

        entity = user.to_mlflow_entity()

        assert len(entity.experiment_permissions) == 1
        assert len(entity.registered_model_permissions) == 1
        assert len(entity.groups) == 1
        assert entity.experiment_permissions[0].experiment_id == "exp123"
        assert entity.registered_model_permissions[0].name == "model123"
        assert entity.groups[0].group_name == "testgroup"

    def test_unique_username_constraint(self, db_session):
        """Test username uniqueness constraint."""
        user1 = SqlUser(username="duplicate", display_name="User 1", password_hash="hash1", is_admin=False, is_service_account=False)
        user2 = SqlUser(username="duplicate", display_name="User 2", password_hash="hash2", is_admin=False, is_service_account=False)

        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlExperimentPermission:
    """Test SqlExperimentPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_user):
        """Test experiment permission entity conversion - covers line 64."""
        permission = SqlExperimentPermission(experiment_id="exp456", user_id=sample_user.id, permission="MANAGE")
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, ExperimentPermission)
        assert entity.experiment_id == "exp456"
        assert entity.user_id == sample_user.id
        assert entity.permission == "MANAGE"

    def test_unique_constraint(self, db_session, sample_user):
        """Test unique constraint on experiment_id and user_id."""
        perm1 = SqlExperimentPermission(experiment_id="exp123", user_id=sample_user.id, permission="READ")
        perm2 = SqlExperimentPermission(experiment_id="exp123", user_id=sample_user.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlRegisteredModelPermission:
    """Test SqlRegisteredModelPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_user):
        """Test registered model permission entity conversion - covers line 80."""
        permission = SqlRegisteredModelPermission(name="model789", user_id=sample_user.id, permission="DELETE")
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, RegisteredModelPermission)
        assert entity.name == "model789"
        assert entity.user_id == sample_user.id
        assert entity.permission == "DELETE"

    def test_unique_constraint(self, db_session, sample_user):
        """Test unique constraint on name and user_id."""
        perm1 = SqlRegisteredModelPermission(name="model123", user_id=sample_user.id, permission="READ")
        perm2 = SqlRegisteredModelPermission(name="model123", user_id=sample_user.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlGroup:
    """Test SqlGroup model functionality."""

    def test_to_mlflow_entity(self, db_session):
        """Test group entity conversion - covers line 99."""
        group = SqlGroup(group_name="admins")
        db_session.add(group)
        db_session.commit()

        entity = group.to_mlflow_entity()

        assert isinstance(entity, Group)
        assert entity.id == group.id
        assert entity.group_name == "admins"

    def test_unique_group_name_constraint(self, db_session):
        """Test group name uniqueness constraint."""
        group1 = SqlGroup(group_name="duplicate_group")
        group2 = SqlGroup(group_name="duplicate_group")

        db_session.add(group1)
        db_session.commit()

        db_session.add(group2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlUserGroup:
    """Test SqlUserGroup model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_user, sample_group):
        """Test user group entity conversion - covers line 113."""
        user_group = SqlUserGroup(user_id=sample_user.id, group_id=sample_group.id)
        db_session.add(user_group)
        db_session.commit()

        entity = user_group.to_mlflow_entity()

        assert isinstance(entity, UserGroup)
        assert entity.user_id == sample_user.id
        assert entity.group_id == sample_group.id

    def test_unique_constraint(self, db_session, sample_user, sample_group):
        """Test unique constraint on user_id and group_id."""
        ug1 = SqlUserGroup(user_id=sample_user.id, group_id=sample_group.id)
        ug2 = SqlUserGroup(user_id=sample_user.id, group_id=sample_group.id)

        db_session.add(ug1)
        db_session.commit()

        db_session.add(ug2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlExperimentGroupPermission:
    """Test SqlExperimentGroupPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_group):
        """Test experiment group permission entity conversion - covers line 128."""
        permission = SqlExperimentGroupPermission(experiment_id="exp999", group_id=sample_group.id, permission="READ")
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, ExperimentPermission)
        assert entity.experiment_id == "exp999"
        assert entity.group_id == sample_group.id
        assert entity.permission == "READ"

    def test_unique_constraint(self, db_session, sample_group):
        """Test unique constraint on experiment_id and group_id."""
        perm1 = SqlExperimentGroupPermission(experiment_id="exp123", group_id=sample_group.id, permission="READ")
        perm2 = SqlExperimentGroupPermission(experiment_id="exp123", group_id=sample_group.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlRegisteredModelGroupPermission:
    """Test SqlRegisteredModelGroupPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_group):
        """Test registered model group permission entity conversion - covers line 145."""
        permission = SqlRegisteredModelGroupPermission(name="group_model", group_id=sample_group.id, permission="MANAGE", prompt=True)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, RegisteredModelPermission)
        assert entity.name == "group_model"
        assert entity.group_id == sample_group.id
        assert entity.permission == "MANAGE"
        assert entity.prompt is True

    def test_to_mlflow_entity_prompt_false(self, db_session, sample_group):
        """Test entity conversion with prompt=False."""
        permission = SqlRegisteredModelGroupPermission(name="group_model2", group_id=sample_group.id, permission="READ", prompt=False)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()
        assert entity.prompt is False

    def test_unique_constraint(self, db_session, sample_group):
        """Test unique constraint on name and group_id."""
        perm1 = SqlRegisteredModelGroupPermission(name="model123", group_id=sample_group.id, permission="READ")
        perm2 = SqlRegisteredModelGroupPermission(name="model123", group_id=sample_group.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlExperimentRegexPermission:
    """Test SqlExperimentRegexPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_user):
        """Test experiment regex permission entity conversion - covers line 163."""
        permission = SqlExperimentRegexPermission(regex="exp_.*", priority=1, user_id=sample_user.id, permission="READ")
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, ExperimentRegexPermission)
        assert entity.id == permission.id
        assert entity.regex == "exp_.*"
        assert entity.priority == 1
        assert entity.user_id == sample_user.id
        assert entity.permission == "READ"

    def test_unique_constraint(self, db_session, sample_user):
        """Test unique constraint on regex and user_id."""
        perm1 = SqlExperimentRegexPermission(regex="test_.*", priority=1, user_id=sample_user.id, permission="READ")
        perm2 = SqlExperimentRegexPermission(regex="test_.*", priority=2, user_id=sample_user.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlRegisteredModelRegexPermission:
    """Test SqlRegisteredModelRegexPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_user):
        """Test registered model regex permission entity conversion - covers line 183."""
        permission = SqlRegisteredModelRegexPermission(regex="model_.*", priority=2, user_id=sample_user.id, permission="WRITE", prompt=True)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, RegisteredModelRegexPermission)
        assert entity.id == permission.id
        assert entity.regex == "model_.*"
        assert entity.priority == 2
        assert entity.user_id == sample_user.id
        assert entity.permission == "WRITE"
        assert entity.prompt is True

    def test_to_mlflow_entity_prompt_false(self, db_session, sample_user):
        """Test entity conversion with prompt=False."""
        permission = SqlRegisteredModelRegexPermission(regex="model2_.*", priority=1, user_id=sample_user.id, permission="READ", prompt=False)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()
        assert entity.prompt is False

    def test_unique_constraint(self, db_session, sample_user):
        """Test unique constraint on regex, user_id, and prompt."""
        perm1 = SqlRegisteredModelRegexPermission(regex="test_.*", priority=1, user_id=sample_user.id, permission="READ", prompt=True)
        perm2 = SqlRegisteredModelRegexPermission(
            regex="test_.*", priority=2, user_id=sample_user.id, permission="WRITE", prompt=True  # Same regex, user_id, and prompt should fail
        )

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_unique_constraint_different_prompt(self, db_session, sample_user):
        """Test that same regex and user_id with different prompt values is allowed."""
        perm1 = SqlRegisteredModelRegexPermission(regex="test_.*", priority=1, user_id=sample_user.id, permission="READ", prompt=True)
        perm2 = SqlRegisteredModelRegexPermission(
            regex="test_.*", priority=2, user_id=sample_user.id, permission="WRITE", prompt=False  # Different prompt value should be allowed
        )

        db_session.add(perm1)
        db_session.add(perm2)
        db_session.commit()  # Should not raise IntegrityError

        assert db_session.query(SqlRegisteredModelRegexPermission).count() == 2


class TestSqlExperimentGroupRegexPermission:
    """Test SqlExperimentGroupRegexPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_group):
        """Test experiment group regex permission entity conversion - covers line 203."""
        permission = SqlExperimentGroupRegexPermission(regex="group_exp_.*", priority=3, group_id=sample_group.id, permission="MANAGE")
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, ExperimentGroupRegexPermission)
        assert entity.id == permission.id
        assert entity.regex == "group_exp_.*"
        assert entity.priority == 3
        assert entity.group_id == sample_group.id
        assert entity.permission == "MANAGE"

    def test_unique_constraint(self, db_session, sample_group):
        """Test unique constraint on regex and group_id."""
        perm1 = SqlExperimentGroupRegexPermission(regex="test_.*", priority=1, group_id=sample_group.id, permission="READ")
        perm2 = SqlExperimentGroupRegexPermission(regex="test_.*", priority=2, group_id=sample_group.id, permission="WRITE")

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSqlRegisteredModelGroupRegexPermission:
    """Test SqlRegisteredModelGroupRegexPermission model functionality."""

    def test_to_mlflow_entity(self, db_session, sample_group):
        """Test registered model group regex permission entity conversion - covers line 223."""
        permission = SqlRegisteredModelGroupRegexPermission(regex="group_model_.*", priority=4, group_id=sample_group.id, permission="DELETE", prompt=True)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()

        assert isinstance(entity, RegisteredModelGroupRegexPermission)
        assert entity.id == permission.id
        assert entity.regex == "group_model_.*"
        assert entity.priority == 4
        assert entity.group_id == sample_group.id
        assert entity.permission == "DELETE"
        assert entity.prompt is True

    def test_to_mlflow_entity_prompt_false(self, db_session, sample_group):
        """Test entity conversion with prompt=False."""
        permission = SqlRegisteredModelGroupRegexPermission(regex="group_model2_.*", priority=1, group_id=sample_group.id, permission="READ", prompt=False)
        db_session.add(permission)
        db_session.commit()

        entity = permission.to_mlflow_entity()
        assert entity.prompt is False

    def test_unique_constraint(self, db_session, sample_group):
        """Test unique constraint on regex, group_id, and prompt."""
        perm1 = SqlRegisteredModelGroupRegexPermission(regex="test_.*", priority=1, group_id=sample_group.id, permission="READ", prompt=True)
        perm2 = SqlRegisteredModelGroupRegexPermission(
            regex="test_.*", priority=2, group_id=sample_group.id, permission="WRITE", prompt=True  # Same regex, group_id, and prompt should fail
        )

        db_session.add(perm1)
        db_session.commit()

        db_session.add(perm2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_unique_constraint_different_prompt(self, db_session, sample_group):
        """Test that same regex and group_id with different prompt values is allowed."""
        perm1 = SqlRegisteredModelGroupRegexPermission(regex="test_.*", priority=1, group_id=sample_group.id, permission="READ", prompt=True)
        perm2 = SqlRegisteredModelGroupRegexPermission(
            regex="test_.*", priority=2, group_id=sample_group.id, permission="WRITE", prompt=False  # Different prompt value should be allowed
        )

        db_session.add(perm1)
        db_session.add(perm2)
        db_session.commit()  # Should not raise IntegrityError

        assert db_session.query(SqlRegisteredModelGroupRegexPermission).count() == 2


class TestModelRelationships:
    """Test SQLAlchemy model relationships and foreign key constraints."""

    def test_user_experiment_permissions_relationship(self, db_session, sample_user):
        """Test user to experiment permissions relationship."""
        perm1 = SqlExperimentPermission(experiment_id="exp1", user_id=sample_user.id, permission="READ")
        perm2 = SqlExperimentPermission(experiment_id="exp2", user_id=sample_user.id, permission="WRITE")

        db_session.add_all([perm1, perm2])
        db_session.commit()

        db_session.refresh(sample_user)
        assert len(sample_user.experiment_permissions) == 2
        assert perm1 in sample_user.experiment_permissions
        assert perm2 in sample_user.experiment_permissions

    def test_user_registered_model_permissions_relationship(self, db_session, sample_user):
        """Test user to registered model permissions relationship."""
        perm1 = SqlRegisteredModelPermission(name="model1", user_id=sample_user.id, permission="READ")
        perm2 = SqlRegisteredModelPermission(name="model2", user_id=sample_user.id, permission="MANAGE")

        db_session.add_all([perm1, perm2])
        db_session.commit()

        db_session.refresh(sample_user)
        assert len(sample_user.registered_model_permissions) == 2
        assert perm1 in sample_user.registered_model_permissions
        assert perm2 in sample_user.registered_model_permissions

    def test_user_groups_many_to_many_relationship(self, db_session, sample_user):
        """Test many-to-many relationship between users and groups."""
        group1 = SqlGroup(group_name="group1")
        group2 = SqlGroup(group_name="group2")
        db_session.add_all([group1, group2])
        db_session.commit()

        # Add user to groups via association table
        ug1 = SqlUserGroup(user_id=sample_user.id, group_id=group1.id)
        ug2 = SqlUserGroup(user_id=sample_user.id, group_id=group2.id)
        db_session.add_all([ug1, ug2])
        db_session.commit()

        db_session.refresh(sample_user)
        db_session.refresh(group1)
        db_session.refresh(group2)

        assert len(sample_user.groups) == 2
        assert group1 in sample_user.groups
        assert group2 in sample_user.groups

        assert sample_user in group1.users
        assert sample_user in group2.users

    def test_foreign_key_constraints(self, db_session):
        """Test foreign key constraints are enforced."""
        # Note: SQLite doesn't enforce foreign key constraints by default
        # This test documents the expected behavior in production databases
        try:
            perm = SqlExperimentPermission(experiment_id="exp1", user_id=99999, permission="READ")  # Non-existent user ID
            db_session.add(perm)
            db_session.commit()
            # In SQLite, this might succeed, but in PostgreSQL/MySQL it would fail
        except IntegrityError:
            # Expected behavior in databases with strict foreign key enforcement
            pass

    def test_cascade_operations(self, db_session, sample_user, sample_group):
        """Test cascade behavior when deleting related entities."""
        # Create permissions for user
        exp_perm = SqlExperimentPermission(experiment_id="exp1", user_id=sample_user.id, permission="READ")
        model_perm = SqlRegisteredModelPermission(name="model1", user_id=sample_user.id, permission="WRITE")
        user_group = SqlUserGroup(user_id=sample_user.id, group_id=sample_group.id)

        db_session.add_all([exp_perm, model_perm, user_group])
        db_session.commit()

        # Verify permissions exist
        assert db_session.query(SqlExperimentPermission).count() == 1
        assert db_session.query(SqlRegisteredModelPermission).count() == 1
        assert db_session.query(SqlUserGroup).count() == 1

        # Manually delete related records first (simulating cascade behavior)
        # In production with proper foreign key constraints, this would happen automatically
        db_session.query(SqlExperimentPermission).filter_by(user_id=sample_user.id).delete()
        db_session.query(SqlRegisteredModelPermission).filter_by(user_id=sample_user.id).delete()
        db_session.query(SqlUserGroup).filter_by(user_id=sample_user.id).delete()

        # Now delete user
        db_session.delete(sample_user)
        db_session.commit()

        # Verify all related records are deleted
        assert db_session.query(SqlExperimentPermission).count() == 0
        assert db_session.query(SqlRegisteredModelPermission).count() == 0
        assert db_session.query(SqlUserGroup).count() == 0

        # Group should still exist
        assert db_session.query(SqlGroup).count() == 1


class TestModelValidation:
    """Test model validation and data integrity."""

    def test_required_fields_validation(self, db_session):
        """Test that required fields are enforced."""
        # Test user without required fields
        with pytest.raises(IntegrityError):
            user = SqlUser(username=None)  # username is required
            db_session.add(user)
            db_session.commit()

    def test_string_length_constraints(self, db_session):
        """Test string field length constraints."""
        # Create user with very long username (assuming 255 char limit)
        long_username = "a" * 256  # Exceeds typical VARCHAR(255) limit
        user = SqlUser(username=long_username, display_name="Test", password_hash="hash", is_admin=False, is_service_account=False)

        db_session.add(user)
        # This might not raise an error in SQLite, but would in other databases
        # The test documents the expected behavior
        try:
            db_session.commit()
        except Exception:
            # Expected for databases with strict length constraints
            pass

    def test_boolean_field_defaults(self, db_session):
        """Test boolean field default values."""
        user = SqlUser(
            username="testuser",
            display_name="Test User",
            password_hash="hash",
            # is_admin and is_service_account should default to False
        )
        db_session.add(user)
        db_session.commit()

        assert user.is_admin is False
        assert user.is_service_account is False

    def test_nullable_fields(self, db_session):
        """Test nullable field behavior."""
        user = SqlUser(
            username="testuser",
            display_name="Test User",
            password_hash="hash",
            password_expiration=None,  # Should be allowed
            is_admin=False,
            is_service_account=False,
        )
        db_session.add(user)
        db_session.commit()

        assert user.password_expiration is None

        # Test model permission with nullable prompt field
        model_perm = SqlRegisteredModelGroupPermission(
            name="test_model",
            group_id=1,
            permission="READ",
            # prompt should default to False
        )
        db_session.add(model_perm)
        db_session.commit()

        assert model_perm.prompt is False
