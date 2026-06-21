from __future__ import annotations

from datetime import UTC, datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(75), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    image_file: Mapped[str | None] = mapped_column(
        String(200), nullable=True, default=None
    )
    posts: Mapped[List[Post]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
    reset_token: Mapped[PasswordResetToken] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def image_path(self):
        if self.image_file:
            path_format = "https://{bkt}.s3.{region}.amazonaws.com/profile_pics/{img}"
            s3_path = path_format.format(
                bkt=settings.s3_bucket_name,
                region=settings.s3_region,
                img=self.image_file,
            )
            return s3_path
        return "/static/profile_pics/default.png"


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    author: Mapped[User] = relationship(back_populates="posts")


# The reason why we create dedicated model/table for password reset token
# instead of using it like jwt tokens is because with database storage,
# we can achieve true single-use behavior by deleting the tokens from
# database once they are used (this will invalidate all tokens and keep
# only either 0 or 1 token(s) in the database per user). In jwt tokens,
# a single token can be used multiple times until it is alive, which we
# don't want with reset tokens.
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    user: Mapped[User] = relationship(back_populates="reset_token")
