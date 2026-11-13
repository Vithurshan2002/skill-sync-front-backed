"""Account creation and session mutations, independent of HTTP request objects."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app import schemas as s
from app.core.auth import issue_token, password_hash, verify_password
from app.core.errors import ApiError, conflict


def register_account(db: Session, data: s.Register, token_ttl_minutes: int) -> dict:
    if db.scalar(select(m.User.id).where(m.User.email == data.email)):
        conflict("An account already exists with that email address.")
    user = m.User(
        name=data.name,
        email=data.email,
        password_hash=password_hash.hash(data.password),
        role=data.role,
        town=data.town,
    )
    db.add(user)
    db.flush()
    if user.role == "worker":
        db.add(m.Worker(user_id=user.id))
        db.flush()
    result = issue_token(db, user, token_ttl_minutes)
    db.commit()
    return result


def login_account(db: Session, data: s.Login, token_ttl_minutes: int) -> dict:
    user = db.scalar(select(m.User).where(m.User.email == data.email))
    if not verify_password(data.password, user):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    result = issue_token(db, user, token_ttl_minutes)
    db.commit()
    return result


def revoke_token(db: Session, digest: str) -> None:
    token = db.get(m.AccessToken, digest)
    if token is not None:
        db.delete(token)
    db.commit()
