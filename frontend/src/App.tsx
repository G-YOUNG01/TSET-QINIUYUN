import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import axios from "axios";
import type { AxiosError } from "axios";

interface PanelRequest {
  title: string;
  summary: string;
}

interface PanelAsset {
  panel_id: string;
  image_url: string;
  caption: string;
  narration_audio_url: string;
}

interface ComicResponse {
  comic_id: string;
  title?: string;
  chapter?: string;
  outline: PanelRequest[];
  assets: PanelAsset[];
}

interface ComicStatus {
  comic_id: string;
  status: string;
  progress: number;
  detail?: string;
  created_at: string;
  updated_at: string;
}

interface ComicListItem {
  comic_id: string;
  title?: string;
  chapter?: string;
  status: string;
  created_at: string;
}

const statusCopy: Record<string, string> = {
  queued: "排队中",
  running: "生成中",
  processing: "画面合成",
  completed: "已完成",
  failed: "失败"
};

const defaultText =
  "主角林墨踏入无人探索的次元裂缝，光影交错之间，一个陌生的少女伸出手——";

function App() {
  const [novelText, setNovelText] = useState(defaultText);
  const [chapter, setChapter] = useState("第一章");
  const [title, setTitle] = useState("裂缝初行");
  const [voice, setVoice] = useState("alloy");
  const [style, setStyle] = useState("manga");
  const [panelCount, setPanelCount] = useState<number>(4); // 默认4个分镜
  const [useSmartPanel, setUseSmartPanel] = useState(false); // 是否使用智能分镜

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");

  const [status, setStatus] = useState<ComicStatus | null>(null);
  const [result, setResult] = useState<ComicResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ComicListItem[]>([]);
  const [activeComicId, setActiveComicId] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common.Authorization = `Bearer ${token}`;
      refreshHistory();
    } else {
      delete axios.defaults.headers.common.Authorization;
    }
  }, [token]);

  useEffect(() => {
    if (!activeComicId || !token) {
      return;
    }
    const interval = setInterval(async () => {
      try {
        const response = await axios.get<ComicStatus>(
          `/api/v1/comics/${activeComicId}/status`
        );
        setStatus(response.data);
        if (response.data.status === "completed") {
          await fetchComic(activeComicId);
          clearInterval(interval);
        }
        if (response.data.status === "failed") {
          clearInterval(interval);
        }
      } catch (pollError) {
        setError("轮询失败，请稍后重试。");
        clearInterval(interval);
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [activeComicId, token]);

  const progressPct = useMemo(() => {
    if (!status) {
      return 0;
    }
    return Math.round(status.progress * 100);
  }, [status]);

  const handleRegister = async () => {
    setAuthError(null);
    setAuthSuccess(null);
    try {
      await axios.post("/api/v1/auth/register", { email, password });
      setAuthMode("login");
      setAuthSuccess("注册成功，请使用该账号登录。");
    } catch (registerError: unknown) {
      if (axios.isAxiosError(registerError)) {
        if (!registerError.response) {
          setAuthError("无法连接后端服务，请确认 FastAPI 已在 http://localhost:8000 运行。");
          return;
        }
        if (registerError.response.status === 409) {
          setAuthError("该邮箱已注册，请直接登录。");
          return;
        }
        const detail = (registerError.response.data as { detail?: string } | undefined)?.detail;
        setAuthError(detail ?? "注册失败，请稍后再试。");
      } else {
        setAuthError("注册失败，请稍后再试。");
      }
    }
  };

  const handleLogin = async () => {
    setAuthError(null);
    setAuthSuccess(null);
    try {
      const params = new URLSearchParams();
      params.append("username", email);
      params.append("password", password);
      params.append("grant_type", "password");
      const response = await axios.post("/api/v1/auth/login", params);
      setToken(response.data.access_token);
    } catch (loginError: unknown) {
      if (axios.isAxiosError(loginError)) {
        if (!loginError.response) {
          setAuthError("无法连接后端服务，请确认 FastAPI 已在 http://localhost:8000 运行。");
          return;
        }
        if (loginError.response.status === 401) {
          setAuthError("登录失败，请检查邮箱或密码是否正确。");
          return;
        }
        const detail = (loginError.response.data as { detail?: string } | undefined)?.detail;
        setAuthError(detail ?? "登录失败，请稍后再试。");
      } else {
        setAuthError("登录失败，请稍后再试。");
      }
    }
  };

  const handleAuthSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (authMode === "login") {
      await handleLogin();
    } else {
      await handleRegister();
    }
  };

  const refreshHistory = async () => {
    try {
      const response = await axios.get<ComicListItem[]>("/api/v1/comics");
      setHistory(response.data);
    } catch (historyError: unknown) {
      console.error(historyError);
    }
  };

  const fetchComic = async (comicId: string) => {
    try {
      const response = await axios.get<ComicResponse>(`/api/v1/comics/${comicId}`);
      setResult(response.data);
      await refreshHistory();
    } catch (fetchError: unknown) {
      if (axios.isAxiosError(fetchError)) {
        const apiError = fetchError as AxiosError;
        if (apiError.response?.status === 202) {
          return;
        }
      }
      setError("获取漫画详情失败，请稍后再试。");
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) {
      return;
    }
    setError(null);
    setResult(null);
    setStatus(null);
    try {
      const payload = {
        novel_text: novelText,
        chapter,
        title,
        panel_count: useSmartPanel ? null : panelCount, // 智能分镜时传null
        use_smart_panel: useSmartPanel, // 添加智能分镜标志
        settings: {
          voice,
          narrative_style: style,
          panel_resolution: "1024x1024",
          language: "zh-CN"
        }
      };
      const response = await axios.post<ComicStatus>("/api/v1/comics", payload);
      setStatus(response.data);
      setActiveComicId(response.data.comic_id);
      await refreshHistory();
    } catch (submitError: unknown) {
      setError("提交失败，请检查后端服务是否启动并配置了 OpenAI 凭证。");
    }
  };

  const handleSelectHistory = async (comicId: string) => {
    setActiveComicId(comicId);
    setResult(null);
    await fetchComic(comicId);
    const match = history.find((item: ComicListItem) => item.comic_id === comicId);
    if (match) {
      setStatus({
        comic_id: match.comic_id,
        status: match.status,
        progress: match.status === "completed" ? 1 : 0,
        detail: undefined,
        created_at: match.created_at,
        updated_at: match.created_at
      });
    }
  };

  const handleDeleteHistory = async (comicId: string) => {
    if (!window.confirm('确定要删除这条历史记录吗？此操作不可撤销。')) {
      return;
    }
    
    try {
      const response = await axios.delete(`/api/v1/comics/${comicId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      if (response.status === 200) {
        // 从本地历史记录中移除
        setHistory(history.filter(item => item.comic_id !== comicId));
        
        // 如果删除的是当前正在查看的记录，清空预览
        if (activeComicId === comicId) {
          setActiveComicId(null);
          setResult(null);
        }
        
        setStatus((prevStatus) => (
          prevStatus
            ? { ...prevStatus, detail: "记录删除成功" }
            : prevStatus
        ));
      }
    } catch (error) {
      console.error('删除记录失败:', error);
      setError('删除记录失败，请重试');
    }
  };

  const handleLogout = () => {
    setToken(null);
    setAuthMode("login");
    setEmail("");
    setPassword("");
    setStatus(null);
    setResult(null);
    setHistory([]);
    setActiveComicId(null);
    setError(null);
  };

  if (!token) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1>Novel2Comic 控制台</h1>
          <p className="auth-subtitle">请先登录后再使用漫画生成与历史功能。</p>
          <div className="auth-mode-toggle">
            <button
              type="button"
              className={authMode === "login" ? "active" : ""}
              onClick={() => {
                setAuthMode("login");
                setAuthError(null);
                setAuthSuccess(null);
              }}
            >
              登录
            </button>
            <button
              type="button"
              className={authMode === "register" ? "active" : ""}
              onClick={() => {
                setAuthMode("register");
                setAuthError(null);
                setAuthSuccess(null);
              }}
            >
              注册
            </button>
          </div>
          <form className="auth-form" onSubmit={handleAuthSubmit}>
            <label>
              邮箱
              <input
                value={email}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.target.value)}
                placeholder="your@email.com"
                type="email"
                required
              />
            </label>
            <label>
              密码
              <input
                value={password}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setPassword(event.target.value)}
                placeholder="请输入密码"
                type="password"
                required
              />
            </label>
            <button type="submit">
              {authMode === "login" ? "登录" : "注册"}
            </button>
          </form>
          {authError && <p className="error auth-message">{authError}</p>}
          {authSuccess && <p className="success auth-message">{authSuccess}</p>}
          <p className="auth-hint">确保后端 FastAPI 服务正在 http://localhost:8000 运行。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>Novel2Comic</h1>
        <p>将长篇小说直接转换为带配音的漫画脚本与画面。</p>
        <button className="logout" type="button" onClick={handleLogout}>
          退出登录
        </button>
      </header>
      <main>
        <section className="editor">
          <form onSubmit={handleSubmit}>
            <label>
              漫画标题
              <input
                value={title}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setTitle(event.target.value)
                }
                placeholder="裂缝初行"
              />
            </label>
            <label>
              章节标题
              <input
                value={chapter}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  setChapter(event.target.value)
                }
                placeholder="第一章"
              />
            </label>
            <label>
              小说文本
              <textarea
                value={novelText}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                  setNovelText(event.target.value)
                }
                rows={10}
                placeholder="请输入小说片段"
              />
            </label>
            <div className="row">
              <label>
                风格
                <select
                  value={style}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    setStyle(event.target.value)
                  }
                >
                  <option value="manga">日漫叙事</option>
                  <option value="cinematic">电影分镜</option>
                  <option value="western">欧美漫画</option>
                </select>
              </label>
              <div className="panel-count-container">
                <label>
                  分镜数量
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={panelCount}
                    onChange={(event: ChangeEvent<HTMLInputElement>) => {
                      const value = parseInt(event.target.value);
                      if (value >= 1 && value <= 20) {
                        setPanelCount(value);
                      } else if (value > 20) {
                        setPanelCount(20);
                      } else if (event.target.value === "") {
                        setPanelCount(1);
                      }
                    }}
                    disabled={useSmartPanel}
                    placeholder="输入分镜数量（1-20）"
                  />
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={useSmartPanel}
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      setUseSmartPanel(event.target.checked)
                    }
                  />
                  AI智能分镜
                </label>
              </div>
            </div>
            <div className="row">
              <label>
                配音选项
                <select
                  value={voice}
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    setVoice(event.target.value)
                  }
                >
                  <option value="">无配音</option>
                  <option value="alloy">Alloy</option>
                  <option value="echo">Echo</option>
                  <option value="fable">Fable</option>
                  <option value="onyx">Onyx</option>
                  <option value="nova">Nova</option>
                  <option value="shimmer">Shimmer</option>
                </select>
              </label>
            </div>
            <button type="submit" disabled={!token}>
              生成漫画
            </button>
          </form>
          {error && <p className="error">{error}</p>}
          {status && (
            <div className="status">
              <strong>{statusCopy[status.status] ?? status.status}</strong>
              <span>{progressPct}%</span>
              {status.detail && <small>{status.detail}</small>}
            </div>
          )}

          <aside className="history">
            <h2>历史记录</h2>
            <ul>
              {history.map((item) => (
                <li key={item.comic_id}>
                  <button onClick={() => handleSelectHistory(item.comic_id)}>
                    <div className="history-item-content">
                      <span className="history-title">{item.title ?? "未命名"}</span>
                      <div className="history-meta">
                        <small className="history-status">{statusCopy[item.status] ?? item.status}</small>
                        <small className="history-time">{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '未知时间'}</small>
                      </div>
                    </div>
                  </button>
                  <button 
                    className="delete-btn" 
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteHistory(item.comic_id);
                    }}
                    title="删除记录"
                  >
                    🗑️
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        </section>
        <section className="preview">
          {result ? (
            <div>
              <h2>{result.title ?? result.chapter ?? "分镜与资产"}</h2>
              <ul className="panel-list">
                {result.assets.map((panel, index) => (
                  <li key={panel.panel_id}>
                    <div className="panel-header">
                      <h3>
                        {index + 1}. {result.outline[index]?.title ?? "分镜"}
                      </h3>
                      <audio controls src={panel.narration_audio_url}></audio>
                    </div>
                    <p>{result.outline[index]?.summary}</p>
                    <img src={panel.image_url} alt={panel.caption} />
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p>提交后可在此查看生成的分镜、图像和配音。</p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
