import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    comics: list["Comic"] = Relationship(back_populates="owner")


class Comic(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: Optional[str] = None
    chapter: Optional[str] = None
    novel_text: str
    status: str = Field(default="queued")
    progress: float = Field(default=0.0)
    detail: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="comics")

    panels: list["Panel"] = Relationship(back_populates="comic")


class Panel(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    summary: str
    image_url: Optional[str] = None
    caption: Optional[str] = None
    narration_audio_url: Optional[str] = None
    order_index: int = Field(default=0, index=True)

    comic_id: uuid.UUID = Field(foreign_key="comic.id")
    comic: Optional[Comic] = Relationship(back_populates="panels")
