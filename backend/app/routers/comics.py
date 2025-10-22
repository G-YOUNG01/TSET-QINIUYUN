import asyncio
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_session, get_sessionmaker
from ..models import Comic, Panel, User
from ..schemas import (
    ComicListItem,
    ComicRequest,
    ComicResponse,
    ComicStatus,
    PanelAsset,
    PanelRequest,
)
from ..services import GenerationPipeline

router = APIRouter(prefix="/api/v1/comics", tags=["comics"])
_pipeline = GenerationPipeline()
_sessionmaker = get_sessionmaker()


async def _run_pipeline_task(comic_id: uuid.UUID, request: ComicRequest) -> None:
    async with _sessionmaker() as session:
        statement = select(Comic).where(Comic.id == comic_id)
        result = await session.execute(statement)
        comic = result.scalar_one()
        try:
            comic.status = "running"
            comic.progress = 0.15
            comic.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(comic)
 
            response = await _pipeline.run(comic, request, session)
            comic.detail = f"生成完成，共 {len(response.assets)} 幅面板"
            comic.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(comic)
        except Exception as exc:  # pragma: no cover - runtime safety
            comic.status = "failed"
            comic.progress = 1.0
            comic.detail = str(exc)
            comic.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(comic)
            raise


@router.post("", response_model=ComicStatus, status_code=status.HTTP_202_ACCEPTED)
async def create_comic(
    payload: ComicRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ComicStatus:
    comic = Comic(
        title=payload.title,
        chapter=payload.chapter,
        novel_text=payload.novel_text,
        status="queued",
        progress=0.0,
        owner_id=current_user.id,
    )
    session.add(comic)
    await session.commit()
    await session.refresh(comic)

    asyncio.create_task(_run_pipeline_task(comic.id, payload))

    return ComicStatus(
        comic_id=str(comic.id),
        status=comic.status,
        progress=comic.progress,
        detail=comic.detail,
        created_at=comic.created_at,
        updated_at=comic.updated_at,
    )


@router.get("", response_model=List[ComicListItem])
async def list_comics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> List[ComicListItem]:
    statement = (
        select(Comic)
        .where(Comic.owner_id == current_user.id)
        .order_by(Comic.created_at.desc())
    )
    result = await session.execute(statement)
    comics = result.scalars().all()
    return [
        ComicListItem(
            comic_id=str(item.id),
            title=item.title,
            chapter=item.chapter,
            status=item.status,
            created_at=item.created_at,
        )
        for item in comics
    ]


@router.get("/{comic_id}", response_model=ComicResponse)
async def get_comic(
    comic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ComicResponse:
    comic = await _get_user_comic(session, current_user, comic_id)
    if comic.status != "completed":
        raise HTTPException(status_code=202, detail=comic.status)

    statement = select(Panel).where(Panel.comic_id == comic.id).order_by(Panel.order_index)
    result = await session.execute(statement)
    panels = result.scalars().all()

    outline = [
        PanelRequest(title=panel.title, summary=panel.summary) for panel in panels
    ]
    assets = [
        PanelAsset(
            panel_id=str(panel.id),
            image_url=panel.image_url or "",
            caption=panel.caption or "",
            narration_audio_url=panel.narration_audio_url or "",
        )
        for panel in panels
    ]

    return ComicResponse(
        comic_id=str(comic.id),
        title=comic.title,
        chapter=comic.chapter,
        outline=outline,
        assets=assets,
    )


@router.get("/{comic_id}/status", response_model=ComicStatus)
async def comic_status(
    comic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ComicStatus:
    comic = await _get_user_comic(session, current_user, comic_id)
    return ComicStatus(
        comic_id=str(comic.id),
        status=comic.status,
        progress=comic.progress,
        detail=comic.detail,
        created_at=comic.created_at,
        updated_at=comic.updated_at,
    )


async def _get_user_comic(
    session: AsyncSession, current_user: User, comic_id: uuid.UUID
) -> Comic:
    statement = select(Comic).where(Comic.id == comic_id, Comic.owner_id == current_user.id)
    result = await session.execute(statement)
    comic = result.scalar_one_or_none()
    if not comic:
        raise HTTPException(status_code=404, detail="Comic not found")
    return comic
