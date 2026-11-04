from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default='editor')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Template(Base):
    __tablename__ = 'templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80), default='Solution Category')
    object_key: Mapped[str] = mapped_column(String(400))
    fields: Mapped[list] = mapped_column(JSON, default=list)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SharedContent(Base):
    __tablename__ = 'shared_content'
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Page(Base):
    __tablename__ = 'pages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey('templates.id'))
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    template_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    seo: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    published_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_edit_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Publication(Base):
    __tablename__ = 'publications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey('pages.id'))
    version: Mapped[int] = mapped_column(Integer)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    html: Mapped[str] = mapped_column(Text)
    seo_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('page_id', 'version'),)


class Redirect(Base):
    __tablename__ = 'redirects'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_path: Mapped[str] = mapped_column(String(255), unique=True)
    to_path: Mapped[str] = mapped_column(String(255))


class Media(Base):
    __tablename__ = 'media'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_key: Mapped[str] = mapped_column(String(400), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(90))
    alt_text: Mapped[str] = mapped_column(String(300), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
