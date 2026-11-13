# Ensure sample seeding is repeatable and does not overwrite existing account edits.

from sqlalchemy import func, select

from app import models as m
from app.sample_data import sample_id, seed_samples


def test_samples_are_consistent_and_reruns_preserve_edits(api):
    password = "Sample-test-password-only!"
    with api.app.state.sessions() as db:
        result = seed_samples(db, password)
        db.commit()
        assert result["workers"] == 24
        assert db.scalar(select(func.count()).select_from(m.Booking)) == 60
        assert db.scalar(select(func.count()).select_from(m.Review)) == 40
        assert db.scalar(select(func.count()).select_from(m.Complaint)) == 3
        for worker in db.scalars(select(m.Worker)):
            reviews = list(db.scalars(select(m.Review).where(m.Review.worker_id == worker.id)))
            assert worker.review_count == len(reviews)
            assert worker.rating_total == sum(r.rating for r in reviews)
            assert worker.services and worker.towns and worker.latitude and worker.rate_lkr
            completed = db.scalar(
                select(func.count())
                .select_from(m.Booking)
                .where(
                    m.Booking.worker_id == worker.id,
                    m.Booking.status == "completed",
                )
            )
            assert sum(metric.completed_jobs for metric in worker.metrics) == completed
        for booking in db.scalars(select(m.Booking)):
            assert booking.history[-1].status == booking.status
            assert booking.scheduled_at < booking.scheduled_end_at <= booking.deadline_at
            assert booking.request.status == (
                "closed"
                if booking.status == "completed"
                else "submitted"
                if booking.status in {"cancelled", "rejected"}
                else "booked"
            )
        owner = db.get(m.User, sample_id("worker01"))
        owner.name = "Edited sample worker"
        previous_hash = owner.password_hash
        db.commit()
        assert seed_samples(db, "Different-sample-password!") == {"created": False}
        db.commit()
        assert owner.name == "Edited sample worker"
        assert owner.password_hash == previous_hash
        assert db.scalar(select(func.count()).select_from(m.User)) == 29
    response = api.post(
        "/api/v1/auth/login",
        json={
            "email": "sample.worker01@example.com",
            "password": password,
        },
    )
    assert response.status_code == 200
    workers = api.get("/api/v1/workers", params={"perPage": 100}).json()["data"]
    assert len(workers) == 21
    assert all(w["approvalStatus"] == "approved" for w in workers)


def test_sample_email_collision_does_not_modify_existing_account(api):
    import pytest

    with api.app.state.sessions() as db:
        existing = m.User(
            name="Existing account",
            email="sample.admin@example.com",
            password_hash="untouched",
            role="customer",
            town="Colombo",
        )
        db.add(existing)
        db.commit()
        with pytest.raises(ValueError, match="already in use"):
            seed_samples(db, "Sample-test-password-only!")
        db.rollback()
        assert existing.role == "customer"
        assert existing.password_hash == "untouched"
        assert db.scalar(select(func.count()).select_from(m.User)) == 1
