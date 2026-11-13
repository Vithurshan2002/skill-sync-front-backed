# Upgrade legacy records and check that historical facts are preserved.

from datetime import UTC, datetime
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, text

from app.core.config import ROOT, Settings


def test_upgrade_preserves_legacy_records_without_fabricating_deadlines_or_confirmation():
    settings = Settings(app_env="testing")
    schema = "skillsync_migration_test_" + uuid4().hex
    control = create_engine(settings.database_dsn())
    with control.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        settings.database_dsn(), connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "a2ba729fb94c")
            old = MetaData()
            old.reflect(connection)
            now = datetime.now(UTC)
            for identity, role in [
                ("customer", "customer"),
                ("verified-user", "worker"),
                ("pending-user", "worker"),
            ]:
                connection.execute(
                    old.tables["users"]
                    .insert()
                    .values(
                        id=identity,
                        name=identity,
                        role=role,
                        email=identity + "@example.com",
                        password_hash="isolated-test-only",
                        town="Colombo",
                        contact_preference="email",
                        created_at=now,
                    )
                )
            for worker_id, verified in [("verified", True), ("pending", False)]:
                connection.execute(
                    old.tables["workers"]
                    .insert()
                    .values(
                        id=worker_id,
                        user_id=worker_id + "-user",
                        bio="Existing worker biography.",
                        years_experience=5,
                        rate_lkr=2500,
                        rate_unit="visit",
                        available=True,
                        verified=verified,
                        review_count=0,
                        rating_total=0,
                    )
                )
            connection.execute(
                old.tables["service_requests"]
                .insert()
                .values(
                    id="legacy-request",
                    customer_id="customer",
                    title="Existing request",
                    description="A previously completed service request.",
                    town="Colombo",
                    preferred_at=now,
                    status="closed",
                    created_at=now,
                )
            )
            connection.execute(
                old.tables["bookings"]
                .insert()
                .values(
                    id="legacy-booking",
                    request_id="legacy-request",
                    customer_id="customer",
                    worker_id="verified",
                    scheduled_at=now,
                    status="completed",
                    quoted_rate_lkr=2500,
                    rate_unit="visit",
                    created_at=now,
                )
            )
            connection.execute(
                old.tables["booking_events"]
                .insert()
                .values(
                    id="legacy-event",
                    booking_id="legacy-booking",
                    actor_id="verified-user",
                    status="in_progress",
                    at=now,
                )
            )
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT count(*) FROM users")) == 3
            assert connection.scalar(text("SELECT count(*) FROM bookings")) == 1
            assert connection.scalar(text("SELECT count(*) FROM booking_events")) == 1
            assert dict(
                connection.execute(text("SELECT id, approval_status FROM workers")).all()
            ) == {"verified": "approved", "pending": "pending"}
            record = (
                connection.execute(text("SELECT * FROM bookings WHERE id='legacy-booking'"))
                .mappings()
                .one()
            )
            assert record["status"] == "completed" and record["started_at"] == now
            for field in [
                "scheduled_end_at",
                "deadline_at",
                "reported_completed_at",
                "confirmed_at",
            ]:
                assert record[field] is None
            assert connection.scalar(text("SELECT count(*) FROM complaints")) == 0
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()
