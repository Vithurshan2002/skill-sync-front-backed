from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Envelope[T](Schema):
    data: T


class PageMeta(Schema):
    page: int
    per_page: int
    total: int
    last_page: int


class Page[T](Envelope[list[T]]):
    meta: PageMeta


class ErrorDetail(Schema):
    code: str
    message: str
    fields: dict[str, list[str]] | None = None


class ErrorEnvelope(Schema):
    error: ErrorDetail


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Town = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Money = Annotated[Decimal, Field(gt=0, le=9999999999, max_digits=12, decimal_places=2)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


def future(value: datetime) -> datetime:
    if value <= datetime.now(UTC):
        raise ValueError("Choose a future date and time, including a timezone offset.")
    return value


FutureTime = Annotated[AwareDatetime, AfterValidator(future)]


class Register(Schema):
    name: Name
    email: EmailStr
    password: Password
    role: Literal["customer", "worker"]
    town: Town

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class Login(Schema):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ProfilePatch(Schema):
    name: Name | None = None
    town: Town | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    contact_preference: Literal["email", "phone"] | None = None

    @model_validator(mode="after")
    def reject_required_nulls(self):
        for field in self.model_fields_set - {
            "phone",
            "latitude",
            "longitude",
            "service_radius_km",
        }:
            if getattr(self, field) is None:
                raise ValueError(f"{to_camel(field)} cannot be null.")
        return self


Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Radius = Annotated[float, Field(ge=0.1, le=500, allow_inf_nan=False)]


class WorkerPatch(ProfilePatch):
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    service_radius_km: Radius | None = None
    bio: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=15, max_length=2000)]
        | None
    ) = None
    categories: Annotated[list[str], Field(min_length=1, max_length=10)] | None = None
    service_towns: Annotated[list[Town], Field(min_length=1, max_length=50)] | None = None
    years_experience: Annotated[int, Field(ge=0, le=60, strict=True)] | None = None
    rate_lkr: Money | None = None
    rate_unit: Literal["hour", "visit"] | None = None
    available: bool | None = None


class RequestCreate(Schema):
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=15, max_length=2000)
    ]
    town: Town
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=250)] | None = None
    preferred_at: FutureTime
    budget_lkr: Money | None = None
    category: str | None = None


class RequestPatch(Schema):
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)]
        | None
    ) = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=15, max_length=2000)]
        | None
    ) = None
    town: Town | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=250)] | None = None
    preferred_at: FutureTime | None = None
    budget_lkr: Money | None = None
    category: str | None = None

    @model_validator(mode="after")
    def reject_required_nulls(self):
        for field in self.model_fields_set - {
            "address",
            "budget_lkr",
            "category",
            "latitude",
            "longitude",
        }:
            if getattr(self, field) is None:
                raise ValueError(f"{to_camel(field)} cannot be null.")
        return self


class RecommendationFilters(Schema):
    available: bool = True
    max_rate: Money | None = None


class BookingCreate(Schema):
    request_id: str
    worker_id: str
    scheduled_at: FutureTime
    scheduled_end_at: AwareDatetime
    deadline_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered_times(self):
        if self.scheduled_end_at <= self.scheduled_at:
            raise ValueError("Expected end time must follow the appointment.")
        if self.deadline_at is None:
            self.deadline_at = self.scheduled_end_at
        if self.deadline_at < self.scheduled_end_at:
            raise ValueError("Completion deadline must be at or after the expected end time.")
        return self


class BookingTransition(Schema):
    status: Literal[
        "accepted", "rejected", "cancelled", "in_progress", "awaiting_confirmation", "completed"
    ]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ReviewCreate(Schema):
    rating: Annotated[int, Field(ge=1, le=5, strict=True)]
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class NotificationRead(Schema):
    read: Literal[True] = True


class CategoryPatch(Schema):
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)
    ]
    example_request: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=15, max_length=2000)
    ]


class VerificationPatch(Schema):
    verified: bool
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class ComplaintCreate(Schema):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]


class ComplaintResolution(Schema):
    status: Literal["upheld", "dismissed"]
    resolution: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
    ]


class Identity(Schema):
    id: str
    name: str
    email: str
    role: Literal["customer", "worker", "admin"]
    worker_id: str | None
    town: str
    phone: str | None
    contact_preference: str


class TokenResult(Schema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: Identity


class CategoryView(Schema):
    id: str
    label: str
    slug: str
    icon: str
    description: str
    example_request: str


class PerformanceMetric(Schema):
    category: str
    completed_jobs: int
    skill_score: int | None = None


class WorkerView(Schema):
    photo_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    service_radius_km: float | None = None
    location_updated_at: datetime | None = None
    approval_status: str = "pending"
    review_ready: bool = False
    review_note: str | None = None
    reviewed_at: datetime | None = None
    profile_changes: list[dict] = Field(default_factory=list)
    id: str
    name: str
    town: str
    service_towns: list[str]
    categories: list[str]
    bio: str
    years_experience: int
    rate_lkr: float | None
    rate_unit: str
    available: bool
    rating: float | None
    review_count: int
    performance: list[PerformanceMetric]
    reliability_probability: float | None = None
    verified: bool


class ReviewView(Schema):
    id: str
    booking_id: str
    customer_id: str
    customer_name: str
    worker_id: str
    rating: int
    comment: str
    created_at: datetime


class PublicReview(Schema):
    customer_name: str = "Customer"
    rating: int
    comment: str
    created_at: datetime


class WorkerDetail(WorkerView):
    reviews: list[PublicReview]


class RequestView(Schema):
    latitude: float | None = None
    longitude: float | None = None
    id: str
    customer_id: str
    title: str
    description: str
    town: str
    address: str | None
    preferred_at: datetime
    budget_lkr: float | None
    category: str | None
    status: str
    created_at: datetime


class HistoryEvent(Schema):
    status: str
    at: datetime
    note: str | None


class BookingView(Schema):
    scheduled_end_at: datetime | None = None
    deadline_at: datetime | None = None
    accepted_at: datetime | None = None
    started_at: datetime | None = None
    reported_completed_at: datetime | None = None
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by_role: str | None = None
    cancellation_reason: str | None = None
    complaint: dict | None = None
    id: str
    request_id: str
    customer_id: str
    worker_id: str
    scheduled_at: datetime
    status: str
    quoted_rate_lkr: float
    rate_unit: str
    history: list[HistoryEvent]
    request: RequestView
    worker: WorkerView
    review: ReviewView | None


class NotificationView(Schema):
    id: str
    user_id: str
    message: str
    target_path: str
    created_at: datetime
    read_at: datetime | None


class Recommendation(Schema):
    distance_km: float | None = None
    worker_id: str
    rank: int
    match_score: float | None = None
    category_skill_score: int | None = None
    reliability_probability: float | None = None
    reasons: list[str]
    source: Literal["rule_based"] = "rule_based"
    worker: WorkerView


class RecommendationResult(Schema):
    request_id: str
    category: str
    source: Literal["rule_based"] = "rule_based"
    recommendations: list[Recommendation]
