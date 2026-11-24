from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

config = context.config
fileConfig(config.config_file_name)

# Let alembic autogenerate use our models
# ensure the parent directory ("/app") is on sys.path so `models` can be imported when env runs
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# load .env from the api folder (so alembic can read DATABASE_URL from api/.env)
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))
except Exception:
    pass

from models import Base

target_metadata = Base.metadata

# Allow DATABASE_URL override via env
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    config.set_main_option('sqlalchemy.url', DATABASE_URL)


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
