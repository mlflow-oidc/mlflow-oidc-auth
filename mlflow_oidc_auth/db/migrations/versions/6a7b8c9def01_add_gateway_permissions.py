"""add_gateway_permissions

Revision ID: 6a7b8c9def01
Revises: 913635c83867
Create Date: 2026-01-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "6a7b8c9def01"
down_revision = "3c3272527ade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # secret permissions
    op.create_table(
        "gateway_secret_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("secret_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_secret_perm_user_id"),
        sa.UniqueConstraint("secret_id", "user_id", name="unique_secret_user"),
    )

    op.create_table(
        "gateway_secret_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("secret_id", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_secret_group_perm_group_id"),
        sa.UniqueConstraint("secret_id", "group_id", name="unique_secret_group"),
    )

    op.create_table(
        "gateway_secret_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_secret_regex_perm_user_id"),
        sa.UniqueConstraint("regex", "user_id", name="unique_secret_user_regex"),
    )

    op.create_table(
        "gateway_secret_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_secret_group_regex_perm_group_id"),
        sa.UniqueConstraint("regex", "group_id", name="unique_secret_group_regex"),
    )

    # endpoint permissions
    op.create_table(
        "gateway_endpoint_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("endpoint_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_endpoint_perm_user_id"),
        sa.UniqueConstraint("endpoint_id", "user_id", name="unique_endpoint_user"),
    )

    op.create_table(
        "gateway_endpoint_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("endpoint_id", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_endpoint_group_perm_group_id"),
        sa.UniqueConstraint("endpoint_id", "group_id", name="unique_endpoint_group"),
    )

    op.create_table(
        "gateway_endpoint_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_endpoint_regex_perm_user_id"),
        sa.UniqueConstraint("regex", "user_id", name="unique_endpoint_user_regex"),
    )

    op.create_table(
        "gateway_endpoint_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_endpoint_group_regex_perm_group_id"),
        sa.UniqueConstraint("regex", "group_id", name="unique_endpoint_group_regex"),
    )

    # model definition permissions
    op.create_table(
        "gateway_model_definition_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("model_definition_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_model_def_perm_user_id"),
        sa.UniqueConstraint("model_definition_id", "user_id", name="unique_model_def_user"),
    )

    op.create_table(
        "gateway_model_definition_group_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("model_definition_id", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_model_def_group_perm_group_id"),
        sa.UniqueConstraint("model_definition_id", "group_id", name="unique_model_def_group"),
    )

    op.create_table(
        "gateway_model_definition_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_gateway_model_def_regex_perm_user_id"),
        sa.UniqueConstraint("regex", "user_id", name="unique_model_def_user_regex"),
    )

    op.create_table(
        "gateway_model_definition_group_regex_permissions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("regex", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_gateway_model_def_group_regex_perm_group_id"),
        sa.UniqueConstraint("regex", "group_id", name="unique_model_def_group_regex"),
    )


def downgrade() -> None:
    # drop in reverse order
    op.drop_table("gateway_model_definition_group_regex_permissions")
    op.drop_table("gateway_model_definition_regex_permissions")
    op.drop_table("gateway_model_definition_group_permissions")
    op.drop_table("gateway_model_definition_permissions")

    op.drop_table("gateway_endpoint_group_regex_permissions")
    op.drop_table("gateway_endpoint_regex_permissions")
    op.drop_table("gateway_endpoint_group_permissions")
    op.drop_table("gateway_endpoint_permissions")

    op.drop_table("gateway_secret_group_regex_permissions")
    op.drop_table("gateway_secret_regex_permissions")
    op.drop_table("gateway_secret_group_permissions")
    op.drop_table("gateway_secret_permissions")
