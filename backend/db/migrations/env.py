from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# ensure backend package is importable
# Ensure the repository root (parent of `backend`) is on sys.path so imports like
# `backend.db.models` resolve correctly when Alembic runs from different CWDs.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

# this is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# MongoDB does not use Alembic metadata or SQLAlchemy migrations.
target_metadata = None


def run_migrations_online():
    # No-op: MongoDB schema is managed in application code.
    return None


if context.is_offline_mode():
    pass
else:
    run_migrations_online()
