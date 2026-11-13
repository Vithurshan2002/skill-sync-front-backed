"""Explicit, additive local demonstration records; never loaded at application startup."""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models as m
from app.catalog import CATALOG
from app.core.auth import password_hash


def sample_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, "skillsync/local-samples/v1/" + key))


TOWNS = [
    ("Colombo", 6.9271, 79.8612),
    ("Kandy", 7.2906, 80.6337),
    ("Galle", 6.0535, 80.2210),
    ("Jaffna", 9.6615, 80.0255),
]
NAMES = [
    "Amal Perera",
    "Bala Krishnan",
    "Chandra Silva",
    "Dilan Fernando",
    "Elan Kumar",
    "Farhan Ahmed",
    "Gayan Jayasinghe",
    "Hari Selvan",
    "Ishan Mendis",
    "Jeevan Raj",
    "Kamal Wijesinghe",
    "Lakshan Perera",
    "Mohan Rajan",
    "Naveen Silva",
    "Omar Farook",
    "Prakash Selvam",
    "Rajan Kumar",
    "Saman Fernando",
    "Tharun Dias",
    "Vimal Nathan",
    "Anu Perera",
    "Banu Raj",
    "Charan Kumar",
    "Dinesh Silva",
]
BIO_SUMMARIES = {
    "Air Conditioning Repair": "AC servicing, cooling repairs and routine maintenance.",
    "Appliance Repair": "Repairs and maintenance for washing machines and household appliances.",
    "Carpentry": "Furniture repairs, door fitting and custom woodwork.",
    "Electrical": "Wiring repairs, lighting installation and electrical maintenance.",
    "Gardening": "Garden care, pruning and lawn maintenance.",
    "Masonry": "Brickwork, wall repairs and plastering for homes.",
    "Painting": "Interior and exterior painting with neat surface preparation.",
    "Plumbing": "Tap repairs, leak detection and pipe maintenance.",
    "Roofing": "Roof leak repairs, tile replacement and gutter maintenance.",
    "Welding": "Gate repairs, metal fabrication and welding services.",
}


def worker_bio(category: str, town: str) -> str:
    return f"{BIO_SUMMARIES[category]} Serving {town}."


def seed_samples(db: Session, password: str) -> dict:
    """Insert one identifiable batch atomically. Re-running preserves all subsequent edits."""
    db.execute(text("SELECT pg_advisory_xact_lock(734892015)"))
    marker = sample_id("batch")
    if db.get(m.AuditEvent, marker):
        return {"created": False}
    if len(password) < 12:
        raise ValueError("Use a sample password of at least 12 characters.")
    categories = {c.label: c for c in db.scalars(select(m.Category))}
    if any(row[0] not in categories for row in CATALOG):
        raise ValueError("Initialize the ten service categories before adding samples.")
    emails = ["sample.admin@example.com"]
    emails += [f"sample.customer{i:02}@example.com" for i in range(1, 5)]
    emails += [f"sample.worker{i:02}@example.com" for i in range(1, 25)]
    if db.scalar(select(m.User.id).where(m.User.email.in_(emails)).limit(1)):
        raise ValueError("A sample email is already in use. No existing account was changed.")
    now = m.utcnow()
    hashed = password_hash.hash(password)

    def user(key, name, role, town):
        record = m.User(
            id=sample_id(key),
            name=name if role == "worker" else "Sample " + name,
            email=f"sample.{key}@example.com",
            role=role,
            town=town,
            phone=None,
            contact_preference="email",
            password_hash=hashed,
            created_at=now - timedelta(days=90),
        )
        db.add(record)
        db.flush()
        return record

    admin = user("admin", "Administrator", "admin", "Colombo")
    customers = [
        user(f"customer{i:02}", f"Customer {town}", "customer", town)
        for i, (town, _, _) in enumerate(TOWNS, 1)
    ]
    for index, name in enumerate(NAMES):
        category = categories[CATALOG[index % 10][0]]
        town_index = 0 if index < 10 or index >= 20 else 1 + (index % 3)
        town, lat, lon = TOWNS[town_index]
        owner = user(f"worker{index + 1:02}", name, "worker", town)
        approval = (
            "pending" if index in (20, 21) else ("changes_requested" if index == 22 else "approved")
        )
        worker = m.Worker(
            id=sample_id(f"worker-profile-{index}"),
            user_id=owner.id,
            bio=worker_bio(category.label, town),
            years_experience=3 + index % 12,
            rate_lkr=1500 + (index % 8) * 500,
            rate_unit="hour" if index % 3 == 0 else "visit",
            available=index != 23,
            verified=approval == "approved",
            approval_status=approval,
            review_note="Sample setup approval for testing only."
            if approval == "approved"
            else (
                "Sample correction: clarify the types of woodwork you handle."
                if approval == "changes_requested"
                else None
            ),
            reviewed_at=now - timedelta(days=60)
            if approval == "approved"
            else (now if approval == "changes_requested" else None),
            latitude=lat + (index % 3) * 0.003,
            longitude=lon + (index % 2) * 0.003,
            service_radius_km=10 + (index % 4) * 5,
            location_updated_at=now,
        )
        db.add(worker)
        db.flush()
        db.add(m.WorkerCategory(worker_id=worker.id, category_id=category.id))
        db.add(m.WorkerTown(worker_id=worker.id, town=town, town_key=town.casefold()))
        db.add(
            m.Notification(
                user_id=owner.id,
                message="Sample profile ready. Explore your jobs and profile settings.",
                target_path="/worker/profile",
            )
        )
        if approval != "pending":
            db.add(
                m.AuditEvent(
                    actor_id=admin.id,
                    action="sample_worker_review",
                    record_id=worker.id,
                    details={"sampleData": True, "approvalStatus": approval},
                )
            )
        if index >= 20:
            if approval != "approved":
                db.add(
                    m.Notification(
                        user_id=admin.id,
                        message=f"Sample application ready for review: {owner.name}",
                        target_path=f"/admin/records?entity=workers&recordId={worker.id}",
                    )
                )
            continue
        customer = customers[town_index]
        rating_total = 0
        third_status = [
            "pending",
            "accepted",
            "in_progress",
            "awaiting_confirmation",
            "cancelled",
            "rejected",
        ][index % 6]
        for job_index, status in enumerate(["completed", "completed", third_status]):
            key = f"job-{index}-{job_index}"
            if status == "completed":
                start = now - timedelta(days=30 - job_index * 10)
            elif status in {"in_progress", "awaiting_confirmation"}:
                start = now - timedelta(hours=3)
            else:
                start = (now + timedelta(days=3 + index % 4)).replace(
                    hour=4,
                    minute=30,
                    second=0,
                    microsecond=0,
                )
            end = start + timedelta(hours=2)
            created = min(start - timedelta(days=2), now - timedelta(days=1))
            request = m.ServiceRequest(
                id=sample_id(key + "-request"),
                customer_id=customer.id,
                title=f"Sample {category.label}: "
                + ["routine repair", "maintenance visit", "follow-up job"][job_index],
                description="Sample job for testing: " + category.example_request,
                town=town,
                address=f"Sample address {index + 1}, {town} (fictional)",
                latitude=lat,
                longitude=lon,
                preferred_at=start,
                budget_lkr=worker.rate_lkr * 2,
                category_id=category.id,
                status="closed"
                if status == "completed"
                else ("submitted" if status in {"cancelled", "rejected"} else "booked"),
                created_at=created,
            )
            db.add(request)
            db.flush()
            booking = m.Booking(
                id=sample_id(key),
                request_id=request.id,
                customer_id=customer.id,
                worker_id=worker.id,
                scheduled_at=start,
                scheduled_end_at=end,
                deadline_at=end + timedelta(hours=1),
                status=status,
                quoted_rate_lkr=worker.rate_lkr,
                rate_unit=worker.rate_unit,
                created_at=created,
            )
            if status in {"accepted", "in_progress", "awaiting_confirmation", "completed"}:
                booking.accepted_at = created + timedelta(hours=1)
            if status in {"in_progress", "awaiting_confirmation", "completed"}:
                booking.started_at = start
            if status in {"awaiting_confirmation", "completed"}:
                booking.reported_completed_at = end
            if status == "completed":
                booking.confirmed_at = end + timedelta(minutes=30)
            if status == "cancelled":
                booking.cancelled_at = created + timedelta(hours=2)
                booking.cancelled_by_role = "customer"
                booking.cancellation_reason = "Sample cancellation: appointment no longer needed."
            db.add(booking)
            db.flush()
            events = [("pending", created, customer.id)]
            for step, at, actor in [
                ("accepted", booking.accepted_at, owner.id),
                ("in_progress", booking.started_at, owner.id),
                ("awaiting_confirmation", booking.reported_completed_at, owner.id),
                ("completed", booking.confirmed_at, customer.id),
                ("cancelled", booking.cancelled_at, customer.id),
            ]:
                if at is not None:
                    events.append((step, at, actor))
            if status == "rejected":
                events.append(("rejected", created + timedelta(hours=1), owner.id))
            for step, at, actor in events:
                db.add(
                    m.BookingEvent(
                        booking_id=booking.id,
                        actor_id=actor,
                        status=step,
                        at=at,
                        note=booking.cancellation_reason
                        if step == "cancelled"
                        else "Sample booking history for application testing.",
                    )
                )
            if status == "completed":
                rating = 4 + (index + job_index) % 2
                rating_total += rating
                db.add(
                    m.Review(
                        booking_id=booking.id,
                        customer_id=customer.id,
                        worker_id=worker.id,
                        rating=rating,
                        comment="Sample review: clear communication and tidy work. "
                        "Fictional feedback for testing the rating display.",
                        created_at=end + timedelta(hours=1),
                    )
                )
                if index < 3 and job_index == 1:
                    complaint_status = ["pending", "upheld", "dismissed"][index]
                    complaint = m.Complaint(
                        id=sample_id(key + "-complaint"),
                        booking_id=booking.id,
                        reported_by=customer.id,
                        reason="Sample complaint: inspect a reported "
                        "follow-up issue after the completed job.",
                        status=complaint_status,
                        created_at=end + timedelta(days=1),
                        resolution=None
                        if index == 0
                        else "Sample decision after reviewing "
                        "fictional evidence supplied by both participants.",
                        resolved_by=None if index == 0 else admin.id,
                        resolved_at=None if index == 0 else end + timedelta(days=2),
                    )
                    db.add(complaint)
                    db.add(
                        m.Notification(
                            user_id=admin.id,
                            message=f"Sample complaint: {complaint_status}",
                            target_path=f"/admin/records?entity=complaints&recordId={complaint.id}",
                        )
                    )
                    if index:
                        db.add(
                            m.AuditEvent(
                                actor_id=admin.id,
                                action="sample_complaint_resolution",
                                record_id=complaint.id,
                                details={"sampleData": True, "status": complaint_status},
                            )
                        )
            if job_index == 2:
                for recipient, area in [(owner, "worker/jobs"), (customer, "customer/bookings")]:
                    db.add(
                        m.Notification(
                            user_id=recipient.id,
                            message=f"Sample booking {status.replace('_', ' ')}: {category.label}",
                            target_path=f"/{area}/{booking.id}",
                        )
                    )
        worker.review_count = 2
        worker.rating_total = rating_total
        db.add(m.WorkerMetric(worker_id=worker.id, category_id=category.id, completed_jobs=2))
    for index, (town, lat, lon) in enumerate(TOWNS):
        category = categories["Plumbing"]
        db.add(
            m.ServiceRequest(
                id=sample_id(f"open-request-{index}"),
                customer_id=customers[index].id,
                title=f"Sample new plumbing request in {town}",
                description=category.example_request,
                town=town,
                address=f"Sample test address, {town}",
                latitude=lat,
                longitude=lon,
                preferred_at=now + timedelta(days=10),
                budget_lkr=6000,
                category_id=category.id,
                status="submitted",
            )
        )
    summary = {
        "workers": 24,
        "customers": 4,
        "admins": 1,
        "requests": 64,
        "bookings": 60,
        "reviews": 40,
        "complaints": 3,
    }
    db.add(
        m.AuditEvent(
            id=marker,
            actor_id=admin.id,
            action="sample_data_seed",
            record_id=marker,
            details={"sampleData": True, **summary},
        )
    )
    db.flush()
    return {"created": True, **summary}
