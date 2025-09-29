from typing import List, Literal

from sqlalchemy import ForeignKey, Integer, String

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(129), unique=True, nullable=False)
    totp_secret: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[Literal["NORMAL", "DELETED", "DISABLED"]] = mapped_column(
        String, nullable=False
    )
    characters: Mapped[List["Character"]] = relationship(back_populates="owner")


class Character(Base):
    __tablename__ = "character"

    name: Mapped[str] = mapped_column(String(15), primary_key=True)
    user_id = mapped_column(ForeignKey("account.id"))
    owner: Mapped["Account"] = relationship(back_populates="characters")


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_code"

    email: Mapped[str] = mapped_column(String(129), primary_key=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expire: Mapped[float] = mapped_column(nullable=False)  # POSIX timestamp
