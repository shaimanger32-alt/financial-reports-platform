"""Alembic environment.

The connection URL always comes from DATABASE_URL so that credentials stay out
of the repository and the same migrations run against dev, test and CI.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.base import Base
from database.config import get_database_settings

# Importing model modules here registers them on Base.metadata for autogenerate.
# The canonical financial schema is designed in phase 2, after the MAGNA payload
# has been inspected (spec section 52, Task D). Nothing to import yet.

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_database_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
