"""Add location, approval, deadlines, confirmation and complaints without resetting data."""

import sqlalchemy as sa
from alembic import op

revision = "b731f94a620e"
down_revision = "a2ba729fb94c"
branch_labels = None
depends_on = None


def upgrade():
    for table in ["workers", "service_requests"]:
        op.add_column(table, sa.Column("latitude", sa.Numeric(10, 7), nullable=True))
        op.add_column(table, sa.Column("longitude", sa.Numeric(10, 7), nullable=True))
        op.create_check_constraint(
            f"{table}_coordinates",
            table,
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 "
            "AND longitude BETWEEN -180 AND 180)",
        )
    op.add_column("workers", sa.Column("service_radius_km", sa.Numeric(6, 2), nullable=True))
    op.add_column(
        "workers", sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "workers",
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="pending"),
    )
    op.add_column("workers", sa.Column("review_note", sa.String(500), nullable=True))
    op.add_column("workers", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workers", sa.Column("review_baseline", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "worker_approval_status",
        "workers",
        "approval_status IN ('pending','approved','changes_requested')",
    )
    op.create_check_constraint(
        "worker_location_radius",
        "workers",
        "(latitude IS NULL AND service_radius_km IS NULL) OR (latitude IS NOT NULL "
        "AND service_radius_km IS NOT NULL AND service_radius_km BETWEEN 0.1 AND 500)",
    )
    # Preserve previously recorded administrative decisions; never auto-approve others.
    op.execute("UPDATE workers SET approval_status = 'approved' WHERE verified = true")
    for name in [
        "scheduled_end_at",
        "deadline_at",
        "accepted_at",
        "started_at",
        "reported_completed_at",
        "confirmed_at",
        "cancelled_at",
    ]:
        op.add_column("bookings", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("cancelled_by_role", sa.String(20), nullable=True))
    op.add_column("bookings", sa.Column("cancellation_reason", sa.String(500), nullable=True))
    op.alter_column("bookings", "status", type_=sa.String(32), existing_type=sa.String(20))
    op.alter_column("booking_events", "status", type_=sa.String(32), existing_type=sa.String(20))
    op.drop_constraint("booking_status", "bookings", type_="check")
    op.create_check_constraint(
        "booking_status",
        "bookings",
        "status IN ('pending','accepted','in_progress','awaiting_confirmation',"
        "'completed','rejected','cancelled')",
    )
    op.drop_index("uq_active_booking_request", table_name="bookings")
    op.create_index(
        "uq_active_booking_request",
        "bookings",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending','accepted','in_progress','awaiting_confirmation')"
        ),
    )
    op.create_check_constraint(
        "booking_time_order",
        "bookings",
        "(scheduled_end_at IS NULL OR scheduled_end_at > scheduled_at) AND "
        "(deadline_at IS NULL OR (deadline_at > scheduled_at AND "
        "(scheduled_end_at IS NULL OR deadline_at >= scheduled_end_at)))",
    )
    # Recover only known timestamps from history; legacy deadlines/confirmations remain null.
    for column, status in [
        ("accepted_at", "accepted"),
        ("started_at", "in_progress"),
        ("cancelled_at", "cancelled"),
    ]:
        op.execute(
            f"UPDATE bookings b SET {column} = (SELECT min(e.at) FROM booking_events e "
            f"WHERE e.booking_id = b.id AND e.status = '{status}')"
        )
    op.create_table(
        "complaints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False, unique=True
        ),
        sa.Column("reported_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(2000), nullable=True),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','upheld','dismissed')", name="complaint_status"),
    )


def downgrade():
    raise RuntimeError(
        "This migration contains workflow history; "
        "restore a reviewed backup instead of discarding records."
    )
