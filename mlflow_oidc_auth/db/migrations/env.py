from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mlflow_oidc_auth.config import config as app_config
from mlflow_oidc_auth.db.models._base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
#
# Two guards, both for issue #342. ``fileConfig`` defaults to ``disable_existing_loggers=True``,
# which sets ``.disabled`` on every logger that already exists:
#
# * This plugin applies migrations from inside the running server, on first access to the store
#   singleton — which is the first authenticated request. By then the application logger, the
#   audit logger and uvicorn's own loggers all exist, and all of them were being silenced for
#   the life of the process. The audit trail in particular recorded nothing at all: events were
#   still constructed, then dropped by a disabled logger, with no error and no visible gap.
# * A library has no business reconfiguring the logging of the process that embeds it. The
#   ``.ini``'s logging sections exist for the ``alembic`` CLI, where Alembic owns the process.
#
# So: skip it entirely when embedded, and even under the CLI leave existing loggers alone.
#
# "Embedded" is signalled explicitly by ``db/utils.py::_get_alembic_config``, which every
# in-process caller goes through. Inferring it from something incidental — the presence of a
# ``connection`` attribute, say — is how this was missed the first time: ``migrate_if_needed``,
# the function that actually runs on startup, never sets one.
_configure_logging = config.attributes.get("configure_logging", True)
if config.config_file_name is not None and _configure_logging:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=app_config.OIDC_ALEMBIC_VERSION_TABLE,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=app_config.OIDC_ALEMBIC_VERSION_TABLE,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
