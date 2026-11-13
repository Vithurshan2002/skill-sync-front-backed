from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category

CATALOG = [
    (
        "Air Conditioning Repair",
        "sparkles",
        "Cooling care, servicing and repairs for your home.",
        "My air conditioner runs but does not cool the room.",
    ),
    (
        "Appliance Repair",
        "cog-6-tooth",
        "Repair everyday household appliances.",
        "My washing machine stops before the spin cycle.",
    ),
    (
        "Carpentry",
        "square-3-stack-3d",
        "Repairs and custom work in wood.",
        "I need a wooden wardrobe door repaired.",
    ),
    (
        "Electrical",
        "bolt",
        "Help with wiring, lighting and electrical faults.",
        "The bedroom ceiling fan does not turn on.",
    ),
    (
        "Gardening",
        "sun",
        "Keep your outdoor spaces healthy and cared for.",
        "The garden needs trimming and removal of weeds.",
    ),
    (
        "Masonry",
        "building-office",
        "Brickwork, plastering and structural repairs.",
        "A section of my boundary wall needs plastering.",
    ),
    (
        "Painting",
        "paint-brush",
        "A fresh finish for walls, ceilings and woodwork.",
        "I need the walls of my living room painted.",
    ),
    (
        "Plumbing",
        "wrench-screwdriver",
        "Repairs for taps, pipes and household plumbing.",
        "My kitchen tap keeps leaking even when it is closed.",
    ),
    (
        "Roofing",
        "home",
        "Repairs and maintenance to keep your roof in shape.",
        "Rainwater is leaking through the roof above my kitchen.",
    ),
    (
        "Welding",
        "fire",
        "Metal repairs, fabrication and finishing work.",
        "The metal hinge on my front gate has broken.",
    ),
]


def seed_categories(db: Session) -> None:
    existing = set(db.scalars(select(Category.id)).all())
    for index, (label, icon, description, example) in enumerate(CATALOG, start=1):
        category_id = f"cat{index:02}"
        if category_id not in existing:
            db.add(
                Category(
                    id=category_id,
                    label=label,
                    slug=label.lower().replace(" ", "-"),
                    icon=f"heroicon-o-{icon}",
                    description=description,
                    example_request=example,
                )
            )
    db.commit()
