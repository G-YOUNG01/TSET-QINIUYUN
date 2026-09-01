# Novel2Comic

> 将长篇小说文本一键转换为带配音的漫画分镜稿——AI 智能分镜 + 图像生成 + TTS 语音合成，支持日漫 / 电影 / 欧美三种叙事风格。

## ✨ 功能特性

- **小说转漫画**：输入小说章节文本，自动拆分为分镜大纲，逐格生成画面与旁白配音
- **AI 智能分镜**：可手动指定分镜数量（4/6/8/10），或让 AI 根据内容复杂度自适应决定（4–10 格）
- **三种叙事风格**：日漫（manga）、电影感（cinematic）、欧美漫画（western），同作品内风格一致
- **图像生成**：基于 `gpt-image-1` 输出 1024×1024 PNG，落盘后通过 `/static` 公开访问
- **TTS 配音**：6 种语音可选（alloy / echo / fable / onyx / nova / shimmer），支持"无配音"选项
- **异步任务流水线**：故事拆分 → 提示词生成 → 图像生成 → 语音合成，持续回写进度，前端轮询展示
- **多模型兼容**：自动在 OpenAI Responses API 与 Chat Completions 之间切换，支持第三方兼容服务（如自建代理）
- **用户鉴权**：JWT Bearer Token，注册 / 登录，任务数据与历史记录仅限本人访问
- **历史记录**：所有生成任务持久化存储，可随时回看与重新预览
- **暗色 UI**：React + Vite 前端，登录、任务配置、进度条、历史面板、图像与音频预览一体化

## 🛠 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 后端语言 | Python | 3.x |
| Web 框架 | FastAPI | 0.111.0 |
| ASGI 服务器 | Uvicorn | 0.30.1 |
| ORM | SQLModel | 0.0.22 |
| 数据库 | SQLite（aiosqlite 异步驱动） | — |
| 数据库迁移 | Alembic | 1.13.2 |
| AI SDK | OpenAI Python | 1.35.3 |
| HTTP 客户端 | httpx | 0.27.0 |
| 鉴权 | python-jose（JWT）+ passlib[bcrypt] | 3.3.0 / 1.7.4 |
| 配置管理 | pydantic-settings | 2.4.0 |
| 前端框架 | React | 18.3.1 |
| 构建工具 | Vite | 5.3.3 |
| 前端语言 | TypeScript | 5.5.4 |
| HTTP 库 | axios | 1.7.2 |

## 📁 项目结构

```
Novel2Comic-1/
├── backend/                    # 后端服务（FastAPI）
│   ├── app/
│   │   ├── main.py             # FastAPI 应用入口：CORS、静态文件、数据库初始化、路由挂载
│   │   ├── config.py           # 环境变量集中管理（OpenAI / JWT / 数据库）
│   │   ├── database.py         # 异步 SQLModel Session 工厂
│   │   ├── models.py           # ORM 模型：User / Comic / Panel 及关系映射
│   │   ├── schemas.py          # Pydantic 输入输出模型（Comic 请求、状态、Token 等）
│   │   ├── auth.py             # PBKDF2-SHA256 密码哈希 + JWT 生成校验 + 当前用户依赖
│   │   ├── services.py         # OpenAI 调用封装、资产落盘、数据库状态刷新
│   │   └── routers/
│   │       ├── auth.py         # 注册 / 登录路由，返回 Bearer Token
│   │       └── comics.py       # 漫画生成、状态轮询、历史列表、结果获取
│   ├── output/                 # 生成产物（PNG / MP3），通过 /static 暴露（运行时自动创建）
│   └── requirements.txt        # Python 依赖
├── frontend/                   # 前端应用（React + Vite）
│   ├── src/
│   │   ├── App.tsx             # 主界面：登录、生成配置、任务轮询、历史记录、面板展示
│   │   ├── main.tsx            # React 入口
│   │   └── style.css           # 暗色系 UI 样式
│   ├── index.html
│   ├── vite.config.ts          # Vite 配置（/api 代理至 localhost:8000）
│   └── package.json
├── novel-test/                 # 示例小说文本（第一/二/三章）
├── 产品说明文档.md              # 产品定位、用户分析、技术选型、路线图
├── CHANGELOG.md                # 版本变更记录
└── README.md
```

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 18
- OpenAI API Key（或第三方兼容服务密钥）

### 后端启动

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端默认运行在 `http://localhost:8000`，首次启动自动创建数据库表结构。

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器运行在 `http://localhost:5173`，`/api` 请求自动代理至 `http://localhost:8000`。

### 环境变量配置

在后端 `.env` 文件或系统环境变量中配置：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI（或兼容服务）API 密钥 |
| `OPENAI_BASE_URL` | 否 | API 基础地址，官方可省略；第三方兼容服务必填 |
| `OPENAI_OUTLINE_MODEL` | 否 | 分镜大纲模型，默认 `gpt-4.1-mini` |
| `OPENAI_PROMPT_MODEL` | 否 | 提示词生成模型，默认 `gpt-4o-mini` |
| `OPENAI_IMAGE_MODEL` | 否 | 图像生成模型，默认 `gpt-image-1` |
| `OPENAI_TTS_VOICE` | 否 | TTS 语音，默认 `alloy` |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥，生产环境请使用强随机字符串 |
| `DATABASE_URL` | 否 | 数据库连接串，默认 `sqlite+aiosqlite:///./novel2comic.db` |

> 使用第三方兼容服务时，同时设置 `OPENAI_BASE_URL` 与对应模型名称即可；`services.LLMClient` 会自动在 Responses API 与 Chat Completions 之间切换。

## 📖 使用说明

### 操作流程

1. 打开前端页面，注册账号并登录（JWT Token 自动附带于后续请求）
2. 填写小说标题、章节、正文，选择分镜数量（或启用 AI 智能分镜）
3. 选择叙事风格（日漫 / 电影 / 欧美）、画面分辨率、配音选项
4. 提交任务，前端实时轮询展示生成进度
5. 生成完成后预览分镜图像与旁白音频，可在历史记录中回看

### API 接口

所有接口前缀 `/api/v1`，除注册 / 登录外均需 `Authorization: Bearer <token>`。

#### 认证

```http
POST /api/v1/auth/register
Content-Type: application/json

{"email": "user@example.com", "password": "P@ssw0rd"}

POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=user@example.com&password=P%40ssw0rd
```

返回：`{"access_token": "...", "token_type": "bearer"}`

#### 提交生成任务

```http
POST /api/v1/comics
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "裂缝初行",
  "chapter": "第一章",
  "novel_text": "主角林墨踏入无人探索的次元裂缝...",
  "panel_count": 6,
  "use_smart_panel": false,
  "settings": {
    "narrative_style": "manga",
    "panel_resolution": "1024x1024",
    "voice": "alloy",
    "language": "zh-CN"
  }
}
```

响应：`{"comic_id": "7c79b7ac...", "status": "queued", "progress": 0.0}`

#### 轮询状态

```http
GET /api/v1/comics/{comic_id}/status
```

返回示例：`{"status": "processing", "progress": 0.35, "detail": "正在生成第 3 格图像..."}`

#### 获取结果

```http
GET /api/v1/comics/{comic_id}
```

返回包含分镜大纲（outline）与每格资产（assets：图像 URL、字幕、配音音频 URL）。

#### 历史记录

```http
GET /api/v1/comics
```

返回当前用户的所有漫画生成任务列表。

### 生成产物存储

- 图像（PNG）与音频（MP3）落盘至 `backend/output/`
- 通过 FastAPI `StaticFiles` 挂载在 `/static` 路径公开访问
- 数据库中存储文件路径与元数据，便于历史追溯

## 📊 系统架构

```
浏览器用户 ──▶ React/Vite 前端 (:5173)
                    │  /api 代理
                    ▼
              FastAPI 后端 (:8000)
              ├── 鉴权路由（注册 / 登录 → JWT）
              ├── 漫画路由（提交 / 状态 / 历史 / 结果）
              ├── Pipeline 协调器（异步：拆分→生图→TTS）
              ├── SQLModel ORM ──▶ SQLite（novel2comic.db）
              └── /static ──▶ backend/output/（PNG / MP3）
                    │
                    ▼
              OpenAI / 兼容服务
              ├── LLM（分镜拆分 + 提示词生成）
              ├── Images（图像生成）
              └── Audio TTS（语音合成）
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

- 提交前请确保后端通过 `pip install -r requirements.txt` 正常运行
- 前端代码请通过 `npm run build` 构建验证
- 新增功能请同步更新 README 与 CHANGELOG

## 📄 许可证

未指定（保留所有权利）。

## 👤 作者

**GYOUNG** - [GitHub](https://github.com/G-YOUNG01)
