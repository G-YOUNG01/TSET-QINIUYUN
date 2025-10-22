"""Orchestration services for the Novel2Comic pipeline."""

from __future__ import annotations

import asyncio
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from openai import AsyncOpenAI
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Comic, Panel
from .schemas import ComicRequest, ComicResponse, PanelAsset, PanelRequest

logger = logging.getLogger(__name__)

settings = get_settings()
_storage_root = Path(__file__).resolve().parent.parent / "output"
_storage_root.mkdir(parents=True, exist_ok=True)


class LLMClient:
    """Wrapper around OpenAI's Responses API for story decomposition."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key, 
            base_url=settings.openai_base_url,
            timeout=300.0  # 增加超时时间到300秒（5分钟）
        )
        self._supports_responses = hasattr(self._client, "responses")

    async def _generate_text(
        self,
        messages: List[dict],
        *,
        model: str,
        temperature: float,
    ) -> str:
        if self._supports_responses:
            response = await self._client.responses.create(
                model=model,
                input=messages,
                temperature=temperature,
            )
            return getattr(response, "output_text", "").strip()

        chat_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in messages
        ]
        response = await self._client.chat.completions.create(
            model=model,
            messages=chat_messages,
            temperature=temperature,
        )
        choice = response.choices[0].message if response.choices else None
        return (choice.content if choice and choice.content else "").strip()

    async def build_outline(self, request: ComicRequest) -> List[PanelRequest]:
        system_prompt = (
            "你是一名资深漫画分镜师。请从输入小说中提炼 4-8 个场景。"
            "严格输出 JSON 数组，每个元素包含 title 与 summary 字段。"
        )
        outline_text = await self._generate_text(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"小说内容：\n{request.novel_text}",
                },
            ],
            model=settings.openai_outline_model,
            temperature=0.6,
        )
        try:
            data = json.loads(outline_text)
        except json.JSONDecodeError as exc:  # pragma: no cover - depends on model
            raise ValueError("模型返回非 JSON 格式，请调整提示词") from exc
        panels: List[PanelRequest] = []
        for item in data:
            panels.append(
                PanelRequest(title=item.get("title", ""), summary=item["summary"])
            )
        return panels

    async def describe_panel(self, panel: PanelRequest) -> str:
        return await self._generate_text(
            [
                {
                    "role": "system",
                    "content": "你是漫画视觉提示词专家，需生成适合扩散模型的英文提示。",
                },
                {
                    "role": "user",
                    "content": (
                        f"请将以下分镜摘要转换为图像生成提示：\n{panel.summary}" \
                        "\n输出应强调构图、光影、角色神态、服装与背景。"
                    ),
                },
            ],
            model=settings.openai_prompt_model,
            temperature=0.7,
        )


class MediaClient:
    """Handles OpenAI image 和语音生成并落盘。"""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key, 
            base_url=settings.openai_base_url,
            timeout=300.0  # 增加超时时间到300秒（5分钟）
        )

    async def generate_image(self, prompt: str, resolution: str) -> str:
        response = await self._client.images.generate(
            model=settings.openai_image_model,
            prompt=prompt,
            size=resolution,
        )
        
        # 检查返回的是base64数据还是URL
        image_data = response.data[0]
        
        if image_data.b64_json:
            # 如果是base64数据，保存到本地
            file_name = f"img-{uuid.uuid4()}.png"
            file_path = _storage_root / file_name
            file_path.write_bytes(_decode_base64(image_data.b64_json))
            if settings.storage_base_url:
                return f"{settings.storage_base_url.rstrip('/')}/{file_name}"
            return f"/static/{file_name}"
        elif image_data.url:
            # 如果是URL，直接返回URL
            return image_data.url
        else:
            raise ValueError("图像生成API返回的数据格式不支持")


    async def synthesize_speech(self, text: str, voice: str, language: str) -> str:
        speech = await self._client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice or settings.openai_tts_voice,
            input=text,
            language=language,
        )
        file_name = f"tts-{uuid.uuid4()}.mp3"
        file_path = _storage_root / file_name
        with file_path.open("wb") as output_file:
            async for chunk in speech.iter_bytes():
                output_file.write(chunk)
        if settings.storage_base_url:
            return f"{settings.storage_base_url.rstrip('/')}/{file_name}"
        return f"/static/{file_name}"


def _decode_base64(data: str) -> bytes:
    import base64

    return base64.b64decode(data)


class GenerationPipeline:
    """Coordinates the outline, image, and audio steps, persisting them to DB."""

    def __init__(self) -> None:
        self._llm = LLMClient()
        self._media = MediaClient()

    async def run(self, comic: Comic, request: ComicRequest, session: AsyncSession) -> ComicResponse:
        panels = await self._llm.build_outline(request)
        await self._save_outline(session, comic, panels)

        tasks = [self._create_panel_assets(comic, panel, request) for panel in panels]
        assets = await asyncio.gather(*tasks)

        await self._persist_assets(session, comic, assets)

        return ComicResponse(
            comic_id=str(comic.id),
            title=comic.title,
            chapter=comic.chapter,
            outline=panels,
            assets=assets,
        )

    async def _create_panel_assets(
        self, comic: Comic, panel: PanelRequest, request: ComicRequest
    ) -> PanelAsset:
        prompt = await self._llm.describe_panel(panel)
        image_url = await self._media.generate_image(
            prompt=prompt, resolution=request.settings.panel_resolution
        )
        narration_audio_url = ""
        if panel.summary.strip():
            try:
                narration_audio_url = await self._media.synthesize_speech(
                    text=panel.summary,
                    voice=request.settings.voice,
                    language=request.settings.language,
                )
            except Exception as exc:  # pragma: no cover - external service
                logger.warning("TTS generation failed: %s", exc)
        return PanelAsset(
            panel_id=str(uuid.uuid4()),
            image_url=image_url,
            caption=prompt,
            narration_audio_url=narration_audio_url,
        )

    async def _save_outline(
        self, session: AsyncSession, comic: Comic, panels: Iterable[PanelRequest]
    ) -> None:
        for index, panel in enumerate(panels):
            session.add(
                Panel(
                    comic_id=comic.id,
                    title=panel.title,
                    summary=panel.summary,
                    order_index=index,
                )
            )
        comic.status = "processing"
        comic.progress = 0.35
        comic.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(comic)

    async def _persist_assets(
        self,
        session: AsyncSession,
        comic: Comic,
        assets: List[PanelAsset],
    ) -> None:
        for index, asset in enumerate(assets):
            statement = select(Panel).where(
                Panel.comic_id == comic.id, Panel.order_index == index
            )
            result = await session.execute(statement)
            panel_row = result.scalar_one()
            panel_row.image_url = asset.image_url
            panel_row.caption = asset.caption
            panel_row.narration_audio_url = asset.narration_audio_url
            assets[index] = PanelAsset(
                panel_id=str(panel_row.id),
                image_url=panel_row.image_url or "",
                caption=panel_row.caption or "",
                narration_audio_url=panel_row.narration_audio_url or "",
            )
        comic.status = "completed"
        comic.progress = 1.0
        comic.detail = "生成完成"
        comic.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(comic)
