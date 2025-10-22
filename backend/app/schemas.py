from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class NarrativeStyle(str, Enum):
    cinematic = "cinematic"
    manga = "manga"
    western = "western"


class GenerationSettings(BaseModel):
    narrative_style: NarrativeStyle = Field(
        NarrativeStyle.manga, description="High level tone for prompts"
    )
    panel_resolution: str = Field(
        "1024x1024", description="Resolution passed to image generator"
    )
    voice: str = Field("alloy", description="TTS voice identifier")
    language: str = Field("zh-CN", description="Locale for LLM and TTS")


class PanelRequest(BaseModel):
    title: str = Field(..., description="Scene title")
    summary: str = Field(..., description="Narrative summary for the scene")


class ComicRequest(BaseModel):
    novel_text: str = Field(..., description="Raw novel chapter text")
    chapter: Optional[str] = Field(None, description="Chapter identifier")
    settings: GenerationSettings = Field(
        default_factory=GenerationSettings, description="Model tuning switches"
    )
    title: Optional[str] = Field(None, description="Comic title")


class PanelAsset(BaseModel):
    panel_id: str
    image_url: str
    caption: str
    narration_audio_url: str


class ComicResponse(BaseModel):
    comic_id: str
    title: Optional[str]
    chapter: Optional[str]
    outline: List[PanelRequest]
    assets: List[PanelAsset]


class ComicStatus(BaseModel):
    comic_id: str
    status: str
    progress: float
    detail: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ComicListItem(BaseModel):
    comic_id: str
    title: Optional[str]
    chapter: Optional[str]
    status: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=32)


class UserRead(BaseModel):
    id: int
    email: str
    created_at: datetime


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float = Field(0.0, ge=0.0, le=1.0)
    detail: Optional[str] = None
