"""FastAPI web front end for the novel-to-comic pipeline."""
from __future__ import annotations

import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..chapter_loader import load_chapters
from ..config import ImageConfig, LLMConfig, PipelineConfig, TTSConfig
from ..pipeline import ComicPipeline
from ..models import ChapterBundle

app = FastAPI(title="novel2comic", description="Generate comics from novels via a web UI.")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@dataclass
class GenerationJob:
    """In-memory representation of a pipeline run."""

    job_id: str
    status: str
    message: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    output_dir: str = ""
    chapters_dir: str = ""
    metadata_files: List[str] = field(default_factory=list)
    error_trace: Optional[str] = None


_JOB_STORE: Dict[str, GenerationJob] = {}
_JOB_LOCK = Lock()


def _set_job(job: GenerationJob) -> None:
    with _JOB_LOCK:
        _JOB_STORE[job.job_id] = job


def _get_job(job_id: str) -> GenerationJob:
    with _JOB_LOCK:
        job = _JOB_STORE.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job


def _list_jobs() -> List[GenerationJob]:
    with _JOB_LOCK:
        return list(_JOB_STORE.values())


def _run_pipeline_job(
    job_id: str,
    chapters_dir: Path,
    output_dir: Path,
    with_tts: bool,
    enable_quality: bool,
    database_path: Optional[Path],
    panel_concurrency: int,
) -> None:
    job = _get_job(job_id)
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.message = "正在处理章节与生成面板..."
    try:
        config = PipelineConfig(
            output_dir=output_dir,
            llm=LLMConfig(model="gpt-4o-mini"),
            image=ImageConfig(model="stability-core"),
            tts=TTSConfig(voice="default", model="standard") if with_tts else None,
            panel_concurrency=panel_concurrency,
            enable_quality=enable_quality,
            database_path=database_path,
        )
        chapters = load_chapters(chapters_dir)
        pipeline = ComicPipeline(config)
        bundles: List[ChapterBundle] = pipeline.run(chapters)
        job.metadata_files = [str(bundle.metadata_path) for bundle in bundles]
        job.status = "success"
        job.message = f"共生成 {len(bundles)} 章的漫画资源。"
    except Exception as exc:  # noqa: BLE001 - surface errors to the UI
        job.status = "error"
        job.message = str(exc)
        job.error_trace = traceback.format_exc()
    finally:
        job.finished_at = datetime.utcnow()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    jobs = sorted(_list_jobs(), key=lambda item: item.created_at, reverse=True)
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs})


@app.post("/submit")
async def submit_job(
    files: List[UploadFile] = File(..., description="章节文本文件"),
    output_dir: str = Form("output"),
    with_tts: bool = Form(False),
    enable_quality: bool = Form(False),
    database: Optional[str] = Form(None),
    panel_concurrency: int = Form(2),
) -> RedirectResponse:
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个章节文件。")

    temp_root = Path(tempfile.mkdtemp(prefix="novel2comic_"))
    chapters_dir = temp_root / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        content = await upload.read()
        if not upload.filename:
            continue
        destination = chapters_dir / Path(upload.filename).name
        destination.write_bytes(content)

    job_id = uuid4().hex
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    database_path = Path(database).expanduser().resolve() if database else None

    job = GenerationJob(
        job_id=job_id,
        status="pending",
        message="排队中...",
        created_at=datetime.utcnow(),
        output_dir=str(output_path),
        chapters_dir=str(chapters_dir),
    )
    _set_job(job)

    worker = Thread(
        target=_run_pipeline_job,
        args=(
            job_id,
            chapters_dir,
            output_path,
            with_tts,
            enable_quality,
            database_path,
            max(1, panel_concurrency),
        ),
        daemon=True,
    )
    worker.start()
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str) -> HTMLResponse:
    try:
        job = _get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="未找到指定任务。") from None
    return templates.TemplateResponse("job.html", {"request": request, "job": job})


def main() -> None:
    import uvicorn

    uvicorn.run("src.web.app:app", host="127.0.0.1", port=8000, reload=False)
