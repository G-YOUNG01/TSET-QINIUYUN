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
        # 智能分镜逻辑：如果用户选择智能分镜，让AI决定最佳分镜数量
        if request.use_smart_panel:
            # 智能分镜：让AI分析小说内容并决定最佳分镜数量
            style_name = {
                "manga": "日漫叙事",
                "cinematic": "电影分镜", 
                "western": "欧美漫画"
            }.get(request.settings.narrative_style, "漫画")
            
            system_prompt = (
                f"你是一名资深{style_name}漫画分镜师。请分析小说内容，根据剧情复杂度、关键转折点和叙事节奏，"
                f"决定最适合的分镜数量（建议4-10个）。输出格式：先给出分镜数量建议，然后是JSON数组。"
                f"示例：'建议分镜数量：6'，然后换行输出JSON数组。"
                "每个JSON元素包含title与summary字段。"
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
                temperature=0.7,  # 稍高温度以鼓励创造性分析
            )
            
            # 解析AI返回的分镜数量建议和分镜内容
            lines = outline_text.strip().split('\n')
            panel_count = 6  # 默认值
            json_start_index = 0
            
            for i, line in enumerate(lines):
                if '建议分镜数量：' in line:
                    try:
                        panel_count = int(line.split('：')[1].strip())
                        # 确保分镜数量在合理范围内
                        panel_count = max(4, min(10, panel_count))
                        json_start_index = i + 1
                        break
                    except (ValueError, IndexError):
                        pass
            
            # 提取JSON部分
            json_text = '\n'.join(lines[json_start_index:])
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试直接解析整个文本
                try:
                    data = json.loads(outline_text)
                except json.JSONDecodeError as exc:
                    raise ValueError("模型返回非 JSON 格式，请调整提示词") from exc
        else:
            # 手动指定分镜数量
            panel_count = request.panel_count or 6  # 默认6个分镜
            style_name = {
                "manga": "日漫叙事",
                "cinematic": "电影分镜", 
                "western": "欧美漫画"
            }.get(request.settings.narrative_style, "漫画")
            
            system_prompt = (
                f"你是一名资深{style_name}漫画分镜师。请从输入小说中提炼 {panel_count} 个关键场景。"
                f"确保分镜风格保持{style_name}的一致性，包括角色设计、画面构图和叙事节奏。"
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
            except json.JSONDecodeError as exc:
                raise ValueError("模型返回非 JSON 格式，请调整提示词") from exc
        
        # 处理分镜数量与要求不符的情况
        if len(data) > panel_count:
            data = data[:panel_count]
        elif len(data) < panel_count:
            # 如果分镜数量不足，使用最后一个分镜补充
            last_panel = data[-1] if data else {"title": "补充场景", "summary": "延续前一个场景的剧情发展"}
            for i in range(len(data), panel_count):
                data.append({
                    "title": f"{last_panel.get('title', '场景')} {i+1}",
                    "summary": f"{last_panel.get('summary', '剧情延续')} - 补充视角"
                })
        
        panels: List[PanelRequest] = []
        for item in data:
            panels.append(
                PanelRequest(title=item.get("title", ""), summary=item["summary"])
            )
        return panels

    async def describe_panel(self, panel: PanelRequest, narrative_style: str = "manga") -> str:
        # 根据叙事风格调整提示词
        style_prompts = {
            "manga": "日式漫画风格，强调动态线条、夸张表情、速度线效果，使用网点纸纹理",
            "cinematic": "电影镜头风格，强调光影对比、景深效果、电影构图，使用电影胶片质感",
            "western": "欧美漫画风格，强调肌肉线条、写实比例、粗犷笔触，使用美漫色彩风格"
        }
        style_prompt = style_prompts.get(narrative_style, "漫画风格")
        
        return await self._generate_text(
            [
                {
                    "role": "system",
                    "content": f"你是{style_prompt}视觉提示词专家，需生成适合扩散模型的英文提示。",
                },
                {
                    "role": "user",
                    "content": (
                        f"请将以下分镜摘要转换为图像生成提示：\n{panel.summary}" \
                        f"\n输出应强调{style_prompt}的视觉特征，包括构图、光影、角色神态、服装与背景。" \
                        "\n确保提示词能够保持风格一致性。"
                    ),
                },
            ],
            model=settings.openai_prompt_model,
            temperature=0.5,  # 降低温度以提高一致性
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
        response = await self._client.audio.speech.create(
            model="tts-1",
            voice=voice or settings.openai_tts_voice,
            input=text,
            # 第三方API可能不支持language参数，暂时移除
            # language=language,
        )
        file_name = f"tts-{uuid.uuid4()}.mp3"
        file_path = _storage_root / file_name
        file_path.write_bytes(response.content)
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
        prompt = await self._llm.describe_panel(panel, request.settings.narrative_style)
        image_url = await self._media.generate_image(
            prompt=prompt, resolution=request.settings.panel_resolution
        )
        narration_audio_url = ""
        if panel.summary.strip():
            try:
                logger.info("开始TTS语音合成，文本长度: %d", len(panel.summary))
                narration_audio_url = await self._media.synthesize_speech(
                    text=panel.summary,
                    voice=request.settings.voice,
                    language=request.settings.language,
                )
                logger.info("TTS语音合成成功，音频URL: %s", narration_audio_url)
            except Exception as exc:  # pragma: no cover - external service
                logger.error("TTS generation failed: %s", exc)
                logger.error("TTS调用详情 - 文本: %s, 语音: %s, 语言: %s", 
                           panel.summary, request.settings.voice, request.settings.language)
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
