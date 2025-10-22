# Novel2Comic

Novel2Comic 将长篇小说文本转换为带配音的漫画分镜稿。系统串联 OpenAI LLM、图像生成与 TTS 服务，配合 SQL 持久化与 JWT 鉴权，提供可落地的创作流程。

## 系统架构图

```
┌───────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│ React/Vite│────▶│ FastAPI REST│────▶│ Pipeline 协调 │────▶│ OpenAI APIs │
└────┬──────┘     └────┬───────┘     └────┬────────┘     └────┬────────┘
     │                  │                │                   │
     │                  │                │                   │
     │                  │        ┌───────▼──────┐    ┌───────▼─────┐
     │                  │        │ SQLModel ORM │    │ 本地存储输出 │
     │                  └────────┤  Comic/Panel │    └──────────────┘
     │                           └──────────────┘
     ▼
 浏览器用户
```

- **前端**：React + Axios 处理登录、任务提交、历史记录与结果预览。
- **FastAPI**：挂载鉴权与漫画路由，初始化数据库并提供静态资源服务。
- **Pipeline**：异步协同故事拆分、图像生成、语音合成，持续回写状态，支持 Responses API 或 Chat Completions 兼容接口自动回退。
- **SQLModel**：持久化 `User`、`Comic`、`Panel` 数据，实现任务可追溯与重放。
- **OpenAI / 兼容服务**：默认指向如云兼容 OpenAI 的 `https://api.ruyun.fun/v1`，`Responses`/`Chat Completions` 拆分分镜，`Images` 生成画面，`Audio TTS` 输出旁白。
- **本地存储**：PNG / MP3 落盘至 `backend/output/`，通过 `/static` 公开访问。

## 模块设计与依赖

### Backend (`backend/`)
- `app/main.py`：FastAPI 应用，CORS、静态文件、数据库初始化。
- `app/config.py`：集中管理 OpenAI、JWT、数据库等环境变量。
- `app/database.py`：提供异步 `sqlmodel` Session 工厂用于 API 与后台任务。
- `app/models.py`：`User`, `Comic`, `Panel` ORM 模型及关系映射。
- `app/schemas.py`：Pydantic 输入 / 输出模型（Comic 请求、状态、Token 等）。
- `app/auth.py`：PBKDF2-SHA256 密码哈希（兼容加盐），JWT 生成与校验、当前用户依赖。
- `app/services.py`：OpenAI 调用封装、资产落盘与数据库状态刷新。
- `app/routers/auth.py`：注册、登录，返回 Bearer Token。
- `app/routers/comics.py`：漫画生成、状态轮询、历史列表、结果获取。
- 主要依赖：`fastapi`, `sqlmodel`, `openai`, `python-jose[cryptography]`, `passlib[bcrypt]`, `httpx`, `alembic`, `uvicorn`。

### Frontend (`frontend/`)
- `src/App.tsx`：登录表单、生成配置、任务轮询、历史记录与面板展示。
- `src/main.tsx`：React 入口。
- `src/style.css`：暗色系 UI、历史面板与状态卡片样式。
- 依赖：`react`, `react-dom`, `axios`；开发工具 `vite`, `typescript`, `@vitejs/plugin-react`。

## 环境准备与运行

### 后端

```pwsh
cd backend
python -m venv .venv
\.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload  # 可按需添加 --host / --port
```

在 `.env` 或环境变量中准备必需配置：

```pwsh
$env:OPENAI_API_KEY = "sk-..."             # 勿使用仓库里的占位密钥
$env:OPENAI_BASE_URL = "https://api.ruyun.fun/v1"  # 使用官方地址时可省略或改为 https://api.openai.com/v1
$env:OPENAI_OUTLINE_MODEL = "gpt-4.1-mini"
$env:OPENAI_PROMPT_MODEL = "gpt-4o-mini"
$env:OPENAI_IMAGE_MODEL = "dall-e-3"
$env:OPENAI_TTS_VOICE = "alloy"
$env:JWT_SECRET_KEY = "replace-with-a-strong-secret"
$env:DATABASE_URL = "sqlite+aiosqlite:///./novel2comic.db"
```

若需接入第三方 OpenAI 兼容服务（如自建或代理），请同时设置 `OPENAI_BASE_URL` 与对应模型名称；`services.LLMClient` 会自动在 Responses 与 Chat Completions 之间切换。首次启动时会自动创建表结构，后续扩展可引入 Alembic 迁移。

### 前端

```pwsh
cd frontend
npm install
npm run dev
```

开发阶段可将 `.env.local`（Vite）写入 `VITE_API_BASE=http://localhost:8000`，Vite dev server 默认把 `/api` 请求代理到 `http://localhost:8000`。首次使用请在页面内注册并登录，后续请求会自动携带 `Authorization: Bearer <token>`。

## API 调用流程

1. **注册 / 登录**

```http
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "P@ssw0rd"
}

POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=user@example.com&password=P%40ssw0rd
```

返回：`{"access_token":"...","token_type":"bearer"}`。

2. **提交生成任务**（需要 Bearer Token）

```http
POST /api/v1/comics
{
  "title": "裂缝初行",
  "chapter": "第一章",
  "novel_text": "主角林墨踏入无人探索的次元裂缝...",
  "settings": {
    "narrative_style": "manga",
    "panel_resolution": "1024x1024",
    "voice": "alloy",
    "language": "zh-CN"
  }
}
```

响应：`{"comic_id":"7c79b7ac...","status":"queued","progress":0.0}`。

3. **轮询状态**

```http
GET /api/v1/comics/7c79b7ac.../status
```

返回示例：`{"status":"processing","progress":0.35,"detail":"…"}`。

4. **获取生成结果**

```http
GET /api/v1/comics/7c79b7ac...
```

```json
{
  "comic_id": "7c79b7ac-2b42-4fbe-ad19-3669186f6c35",
  "chapter": "第一章",
  "outline": [
    {"title": "裂缝初现", "summary": "林墨踏入裂缝..."},
    {"title": "未知相遇", "summary": "光芒中浮现少女..."}
  ],
  "assets": [
    {
      "panel_id": "af7b4ded-6a27-4aa0-a893-0fbc63ba4f1d",
      "image_url": "/static/img-....png",
      "caption": "Neon rift slicing through ruins...",
      "narration_audio_url": "/static/tts-....mp3"
    }
  ]
}
```

5. **历史记录**

```http
GET /api/v1/comics
```

返回当前登录用户的漫画生成列表，可在前端点击回看。

## 示例结果亮点

- **鉴权安全**：JWT Bearer Token 确保任务仅限本人访问。
- **分镜拆分**：OpenAI Responses API 将小说片段拆成 4~8 个分镜。
- **图像生成**：`gpt-image-1` 输出 base64 PNG，落盘至 `backend/output` 并通过 `/static` 暴露。
- **语音合成**：`gpt-4o-mini-tts` 生成旁白 MP3 音频流。
- **持久化**：SQLModel 存储 Comic/Panel，便于历史查询与复核。
- **前端体验**：身份验证 + 任务进度条 + 历史列表 + 图像与配音预览。

> 提示词与模型名称可根据实际账号与预算调整，必要时可替换为第三方兼容的 OpenAI 接口。落地部署时请配置 HTTPS、对象存储、队列任务与缓存等生产级服务。

## 使用第三方兼容模型服务

若使用如「如云」等兼容 OpenAI 协议的模型服务：

1. 在后端运行环境中配置：

  ```pwsh
  $env:OPENAI_BASE_URL = "https://api.ruyun.fun/v1"
  $env:OPENAI_API_KEY = "sk-xxxx"
  $env:OPENAI_OUTLINE_MODEL = "gpt-4.1-mini"      # 兼容服务提供的模型名
  $env:OPENAI_PROMPT_MODEL  = "gpt-4o-mini"
  $env:OPENAI_IMAGE_MODEL   = "gpt-image-1"       # 若服务不支持生图，可换成可用模型
  ```

2. 重启 `uvicorn app.main:app --reload`，前端刷新后重新登录即可。

3. 若兼容服务暂不支持 Responses API，会自动降级为 Chat Completions；如图像或语音生成功能不可用，可在 `.env` 中仅保留文本模型，并在前端忽略相应失败提示。

4. 不要将真实密钥写入仓库，可使用 `.env` 或部署平台的秘密变量保管。PBKDF2-SHA256 密码哈希已内置 8-32 位长度校验，请为生产环境准备强口令策略。
