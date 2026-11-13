from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.catalog import seed_categories
from app.core.config import ROOT, Settings
from app.core.database import session_factory
from app.main import create_app


@pytest.fixture
def api(tmp_path):
    """Each test uses a new PostgreSQL schema; application tables are never reset."""
    settings = Settings(app_env="testing", photo_storage_path=tmp_path / "worker-photos")
    control = create_engine(settings.database_dsn())
    schema = "skillsync_test_" + uuid4().hex
    with control.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        settings.database_dsn(),
        isolation_level="READ COMMITTED",
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with engine.begin() as connection:
            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with session_factory(engine)() as db:
            seed_categories(db)
        app = create_app(settings, engine=engine)
        with TestClient(app) as client:
            yield client
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()
