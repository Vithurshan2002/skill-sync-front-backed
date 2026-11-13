"""Add optional worker profile photo key without changing existing records."""

import sqlalchemy as sa
from alembic import op

revision = "c842a15b730f"
down_revision = "b731f94a620e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workers", sa.Column("photo_key", sa.String(32), nullable=True))
    op.create_unique_constraint("workers_photo_key_unique", "workers", ["photo_key"])


def downgrade():
    op.drop_constraint("workers_photo_key_unique", "workers", type_="unique")
    op.drop_column("workers", "photo_key")
