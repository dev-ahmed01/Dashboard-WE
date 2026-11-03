from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import User

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    if len(password) < 12:
        raise ValueError('Passwords must be at least 12 characters')
    return hasher.hash(password)


def verify_password(password, digest):
    try:
        return hasher.verify(digest, password)
    except (VerifyMismatchError, Exception):
        return False


def issue_token(user: User):
    settings = get_settings()
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        raise RuntimeError('JWT_SECRET must contain at least 32 characters')
    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({'sub': str(user.id), 'role': user.role, 'exp': expires}, settings.jwt_secret, algorithm='HS256')


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, 'Login required')
    try:
        data = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=['HS256'])
        user = db.get(User, int(data['sub']))
        if not user or not user.active:
            raise ValueError('User not active')
        return user
    except Exception:
        raise HTTPException(401, 'Invalid or expired session')


def admin(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user


def seed_admin(session: Session):
    settings = get_settings()
    if session.scalar(select(User.id).limit(1)):
        return
    if not settings.admin_email or not settings.admin_password:
        raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD before first startup')
    session.add(User(email=settings.admin_email.lower(),password_hash=hash_password(settings.admin_password),role='admin'))
    session.commit()
