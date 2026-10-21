import { useCallback, useEffect, useState } from 'react'
import { ApiError, download, request } from './client'
import type { Capabilities, Citation, Repository, Task } from './client'

const labels: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  awaiting_approval: '等待审批',
  completed: '测试通过',
  approved_unverified: '已批准 · 未验证',
  test_failed: '测试失败',
  rejected: '已拒绝',
  failed: '执行失败',
}
const active = (status: string) => ['queued', 'running'].includes(status)
type View = 'workspace' | 'repositories' | 'search'

function Badge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{labels[status] || status}</span>
}

function Source({ path, content, start = 1 }: { path: string; content: string; start?: number }) {
  return (
    <div className="source">
      <div className="source-title">{path}</div>
      <pre>
        {content.split('\n').map((line, index) => (
          <span className="source-line" key={index}>
            <span className="line-number">{start + index}</span>
            <code>{line || ' '}</code>
            {'\n'}
          </span>
        ))}
      </pre>
    </div>
  )
}

function Diff({ text }: { text: string }) {
  return (
    <pre className="diff" aria-label="代码差异">
      {text.split('\n').map((line, index) => (
        <span
          key={index}
          className={line.startsWith('+') ? 'addition' : line.startsWith('-') ? 'deletion' : ''}
        >
          {line}
          {'\n'}
        </span>
      ))}
    </pre>
  )
}

export default function App() {
  const [view, setView] = useState<View>('workspace')
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [repos, setRepos] = useState<Repository[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [repoId, setRepoId] = useState('')
  const [selected, setSelected] = useState<Task | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [locked, setLocked] = useState(false)
  const [token, setToken] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [prompt, setPrompt] = useState('修复 add 函数：它应当返回两个数之和，保留已有测试。')
  const [provider, setProvider] = useState('demo')
  const [variant, setVariant] = useState('D')
  const [query, setQuery] = useState('add sum return')
  const [mode, setMode] = useState('hybrid')
  const [citations, setCitations] = useState<Citation[]>([])
  const [source, setSource] = useState<{ path: string; content: string } | null>(null)
  const repository = repos.find((repo) => repo.id === repoId)

  const handleError = useCallback((value: unknown) => {
    if (value instanceof ApiError && value.status === 401) setLocked(true)
    setError(value instanceof Error ? value.message : '操作失败，请重试')
  }, [])

  const refresh = useCallback(async () => {
    const [capabilities, repositories, allTasks] = await Promise.all([
      request<Capabilities>('/capabilities'),
      request<Repository[]>('/repositories'),
      request<Task[]>('/tasks'),
    ])
    setCaps(capabilities)
    setRepos(repositories)
    setTasks(allTasks)
    setLocked(false)
    setRepoId((current) => current || repositories[0]?.id || '')
  }, [])

  useEffect(() => {
    refresh().catch(handleError)
  }, [refresh, handleError])
  useEffect(() => {
    if (!selected || !active(selected.status)) return
    const controller = new AbortController()
    const timer = setInterval(() => {
      request<Task>(`/tasks/${selected.id}`, undefined, controller.signal)
        .then((task) => {
          setSelected(task)
          setTasks((current) => current.map((item) => (item.id === task.id ? task : item)))
        })
        .catch((value) => {
          if (!controller.signal.aborted) handleError(value)
        })
    }, 1500)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [selected?.id, selected?.status, handleError])

  async function perform(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (value) {
      handleError(value)
    } finally {
      setBusy(false)
    }
  }

  async function importRepo(url: string) {
    await perform(async () => {
      const repo = await request<Repository>('/repositories', { url })
      await refresh()
      setRepoId(repo.id)
      setSource(null)
      setRepoUrl('')
    })
  }

  async function createTask() {
    await perform(async () => {
      const task = await request<Task>('/tasks', {
        repository_id: repoId,
        prompt,
        provider,
        variant,
        retrieval: mode,
      })
      setSelected(task)
      setTasks((current) => [task, ...current])
      setView('workspace')
    })
  }

  async function decide(approved: boolean) {
    if (!selected?.result.patch) return
    const task = selected
    await perform(async () => {
      const updated = await request<Task>(`/tasks/${task.id}/approval`, {
        approved,
        patch_digest: task.result.patch!.digest,
      })
      setSelected(updated)
      await refresh()
    })
  }

  async function openFile(path: string, id = repoId) {
    await perform(async () => {
      setSource(
        await request<{ path: string; content: string }>(
          `/repositories/${id}/file?path=${encodeURIComponent(path)}`,
        ),
      )
    })
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <a href="/" className="brand">
          <span className="brand-icon">D/</span> DevPilot <b>AI</b>
        </a>
        <p className="nav-label">DEVELOPMENT CONSOLE</p>
        <nav aria-label="主导航">
          {(
            [
              ['workspace', '◫', '任务工作台'],
              ['repositories', '▱', '代码仓库'],
              ['search', '⌕', '代码检索'],
            ] as const
          ).map(([key, icon, title]) => (
            <button
              key={key}
              className={view === key ? 'nav-item current' : 'nav-item'}
              onClick={() => {
                setView(key)
                setSource(null)
              }}
            >
              <span aria-hidden="true">{icon}</span>
              {title}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" /> 本地优先，审批后执行
          <p>每次修改都有代码依据、差异和执行记录。</p>
        </div>
        <div className="sidebar-footer">
          DEV BUILD <span>{caps?.version || '0.2.0'}</span>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <span>
            工作空间 <span className="separator">/</span>{' '}
            {view === 'workspace'
              ? '任务工作台'
              : view === 'repositories'
                ? '代码仓库'
                : '代码检索'}
          </span>
          <div className="header-actions">
            <span className={caps ? 'connection online' : 'connection'}>
              {caps ? 'API 已连接' : 'API 未连接'}
            </span>
            <button className="quiet" onClick={() => perform(refresh)} disabled={busy}>
              刷新
            </button>
            <button className="quiet" onClick={() => setLocked((value) => !value)}>
              访问令牌
            </button>
          </div>
        </header>
        <main>
          {error && (
            <div className="alert" role="alert">
              {error}
              <button aria-label="关闭错误提示" onClick={() => setError('')}>
                ×
              </button>
            </div>
          )}
          {locked && (
            <form
              className="token-form panel"
              onSubmit={(event) => {
                event.preventDefault()
                sessionStorage.setItem('devpilot-token', token)
                perform(refresh)
              }}
            >
              <label htmlFor="api-token">服务访问令牌</label>
              <p>部署时由你在服务端设置。此处只填工作台令牌，不填模型 API Key。</p>
              <input
                id="api-token"
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                autoComplete="off"
              />
              <button className="primary">连接服务</button>
            </form>
          )}

          <div className="page-heading">
            <div>
              <p className="eyebrow">HARNESS-ENHANCED ENGINEERING</p>
              <h1>
                {view === 'workspace'
                  ? '让每一步修改，都有据可查。'
                  : view === 'repositories'
                    ? '从代码，建立项目上下文。'
                    : '找到答案，也保留它的出处。'}
              </h1>
              <p className="subtitle">
                {view === 'workspace'
                  ? '提出任务，审查补丁，再决定下一步。'
                  : view === 'repositories'
                    ? '导入固定版本的文本快照，查看结构与源码。'
                    : '对比关键词、向量和混合检索，查看路径与行号。'}
              </p>
            </div>
            <span className="project-tag">PERSONAL WORKSPACE</span>
          </div>

          <div className="metrics">
            <div>
              <span>已导入仓库</span>
              <strong>{repos.length.toString().padStart(2, '0')}</strong>
            </div>
            <div>
              <span>任务记录（最近 100 条）</span>
              <strong>{tasks.length.toString().padStart(2, '0')}</strong>
            </div>
            <div>
              <span>等待人工审批</span>
              <strong>
                {tasks
                  .filter((task) => task.status === 'awaiting_approval')
                  .length.toString()
                  .padStart(2, '0')}
              </strong>
            </div>
            <div>
              <span>沙箱配置</span>
              <strong className="metric-text">{caps?.sandbox_enabled ? '已启用' : '未启用'}</strong>
              <small>
                {caps?.sandbox_enabled ? '实际状态见每次测试结果' : '不在宿主机执行仓库代码'}
              </small>
            </div>
          </div>

          <div className="environment-note">
            {caps?.model_configured ? `模型：${caps.model}` : '未配置模型密钥，可运行内置演示'}
            <span>
              检索向量：
              {caps?.embedding === 'openai' ? 'OpenAI Embedding' : '离线哈希（非语义模型）'}
            </span>
          </div>

          {view === 'repositories' && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>仓库快照</h2>
                  <p>仅导入受限文本，不执行仓库代码。再次导入会检查新版本。</p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => importRepo('demo://calculator')}
                >
                  导入演示仓库
                </button>
              </div>
              <form
                className="inline-form"
                onSubmit={(event) => {
                  event.preventDefault()
                  importRepo(repoUrl)
                }}
              >
                <label className="sr-only" htmlFor="repo-url">
                  GitHub 仓库地址
                </label>
                <input
                  id="repo-url"
                  type="url"
                  placeholder="https://github.com/owner/repository"
                  required
                  value={repoUrl}
                  onChange={(event) => setRepoUrl(event.target.value)}
                />
                <button className="primary" disabled={busy}>
                  {busy ? '处理中…' : '导入 GitHub 仓库'}
                </button>
              </form>
              <div className="repo-grid">
                {repos.map((repo) => (
                  <button
                    className={`repo-card ${repo.id === repoId ? 'selected' : ''}`}
                    key={repo.id}
                    onClick={() => {
                      setRepoId(repo.id)
                      setSource(null)
                    }}
                  >
                    <span className="repo-icon">▱</span>
                    <strong>{repo.name}</strong>
                    <span>
                      {repo.stats.files} 个文件 · {repo.stats.chunks} 个片段
                    </span>
                    <code>{repo.commit.slice(0, 12)}</code>
                    {repo.stats.partial && <small>受限导入，未包含全部文件</small>}
                  </button>
                ))}
              </div>
              {!repos.length && (
                <div className="empty-state">尚无仓库。先导入演示仓库，体验完整审批流程。</div>
              )}
              {repository && (
                <div className="files-layout">
                  <div className="file-list">
                    <h3>{repository.name}</h3>
                    {repository.paths.map((path) => (
                      <button key={path} onClick={() => openFile(path)}>
                        {path}
                      </button>
                    ))}
                  </div>
                  <div>
                    {source ? (
                      <Source {...source} />
                    ) : (
                      <div className="empty-state">选择文件查看固定版本的源码</div>
                    )}
                  </div>
                </div>
              )}
            </section>
          )}

          {view === 'search' && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>检索代码</h2>
                  <p>行号引用对应导入时的固定 commit。</p>
                </div>
              </div>
              <form
                className="search-form"
                onSubmit={(event) => {
                  event.preventDefault()
                  perform(async () => {
                    setCitations(
                      await request<Citation[]>(
                        `/repositories/${repoId}/search?q=${encodeURIComponent(query)}&mode=${mode}`,
                      ),
                    )
                  })
                }}
              >
                <label>
                  仓库
                  <select
                    value={repoId}
                    onChange={(event) => {
                      setRepoId(event.target.value)
                      setCitations([])
                    }}
                  >
                    <option value="">选择仓库</option>
                    {repos.map((repo) => (
                      <option key={repo.id} value={repo.id}>
                        {repo.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  检索方式
                  <select value={mode} onChange={(event) => setMode(event.target.value)}>
                    <option value="keyword">关键词 BM25</option>
                    <option value="vector">向量检索</option>
                    <option value="hybrid">混合 RRF + 路径重排</option>
                  </select>
                </label>
                <label className="query-field">
                  查询
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    required
                    maxLength={1000}
                  />
                </label>
                <button className="primary" disabled={!repoId || busy}>
                  检索
                </button>
              </form>
              <div className="search-results">
                {citations.map((citation, index) => (
                  <article key={`${citation.path}-${citation.start_line}`}>
                    <div className="result-heading">
                      <button onClick={() => openFile(citation.path)}>
                        {index + 1}. {citation.path}:{citation.start_line}–{citation.end_line}
                      </button>
                      <span>score {citation.score.toFixed(4)}</span>
                    </div>
                    <Source
                      path={citation.path}
                      content={citation.text}
                      start={citation.start_line}
                    />
                  </article>
                ))}
              </div>
              {!citations.length && (
                <div className="empty-state">输入查询并点击检索，结果将显示在这里。</div>
              )}
              {source && <Source {...source} />}
            </section>
          )}

          {view === 'workspace' && (
            <div className="workspace-grid">
              <div className="task-column">
                <section className="panel task-form">
                  <div className="section-heading">
                    <div>
                      <h2>创建工程任务</h2>
                      <p>从一个具体问题开始。</p>
                    </div>
                    <span className="step-number">01</span>
                  </div>
                  {!repos.length ? (
                    <div className="empty-state">
                      <p>先添加一个仓库上下文</p>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => importRepo('demo://calculator')}
                      >
                        导入演示仓库
                      </button>
                    </div>
                  ) : (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault()
                        createTask()
                      }}
                    >
                      <label>
                        代码仓库
                        <select
                          value={repoId}
                          onChange={(event) => setRepoId(event.target.value)}
                          required
                        >
                          {repos.map((repo) => (
                            <option key={repo.id} value={repo.id}>
                              {repo.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        任务描述
                        <textarea
                          value={prompt}
                          onChange={(event) => setPrompt(event.target.value)}
                          minLength={5}
                          maxLength={4000}
                          rows={4}
                          required
                        />
                      </label>
                      <div className="form-pair">
                        <label>
                          运行模式
                          <select
                            value={provider}
                            onChange={(event) => setProvider(event.target.value)}
                          >
                            <option value="demo">内置演示（不调用 LLM）</option>
                            <option value="openai" disabled={!caps?.model_configured}>
                              真实模型
                            </option>
                          </select>
                        </label>
                        <label>
                          实验配置
                          <select
                            value={variant}
                            onChange={(event) => setVariant(event.target.value)}
                          >
                            <option value="A">A · 单 Agent</option>
                            <option value="B">B · 单 Agent + RAG</option>
                            <option value="C">C · 多 Agent + RAG</option>
                            <option value="D">D · 多 Agent + Harness</option>
                          </select>
                        </label>
                      </div>
                      {provider === 'demo' && (
                        <p className="field-note">
                          演示只修复内置 calculator 样例，不代表真实模型能力。
                        </p>
                      )}
                      <button className="primary wide" disabled={busy || !repoId}>
                        {busy ? '处理中…' : '创建并运行任务 →'}
                      </button>
                    </form>
                  )}
                </section>
                <section className="panel task-history">
                  <div className="section-heading">
                    <h2>最近任务</h2>
                    <span className="count">{tasks.length}</span>
                  </div>
                  {!tasks.length && <div className="empty-state compact">还没有任务记录</div>}
                  {tasks.map((task) => (
                    <button
                      key={task.id}
                      className={`task-item ${selected?.id === task.id ? 'selected' : ''}`}
                      onClick={() =>
                        perform(async () => {
                          setSelected(await request<Task>(`/tasks/${task.id}`))
                          setSource(null)
                        })
                      }
                    >
                      <span className="task-title">{task.prompt}</span>
                      <div>
                        <Badge status={task.status} />
                        <small>
                          {task.provider === 'demo' ? '演示' : 'LLM'} · {task.variant}
                        </small>
                      </div>
                    </button>
                  ))}
                </section>
              </div>
              <section className="panel execution-panel">
                {!selected ? (
                  <div className="welcome-state">
                    <div className="welcome-symbol">D/</div>
                    <p className="eyebrow">READY WHEN YOU ARE</p>
                    <h2>你的下一次改进，从这里出发。</h2>
                    <p>
                      创建任务后，计划、检索引用、代码差异
                      <br />
                      与审批记录会出现在这里。
                    </p>
                    <div className="workflow-preview">
                      <span>规划</span>→<span>检索</span>→<span>补丁</span>→<span>审批</span>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="section-heading">
                      <div>
                        <p className="eyebrow">EXECUTION / {selected.id.slice(0, 8)}</p>
                        <h2>任务执行记录</h2>
                      </div>
                      <Badge status={selected.status} />
                    </div>
                    <p className="task-prompt">{selected.prompt}</p>
                    {selected.provider === 'demo' && (
                      <p className="demo-notice">
                        内置演示运行 · 无模型调用 · 测试状态以实际结果为准
                      </p>
                    )}
                    {selected.result.plan && (
                      <div className="result-section">
                        <h3>执行计划</h3>
                        <ol>
                          {selected.result.plan.steps.map((step, index) => (
                            <li key={index}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                    <div className="result-section">
                      <h3>执行轨迹</h3>
                      {selected.events.length === 0 && <p className="muted">等待后台开始执行…</p>}
                      <div className="timeline">
                        {selected.events.map((event, index) => (
                          <div className="timeline-event" key={index}>
                            <span className="timeline-dot" />
                            <div>
                              <strong>{event.role}</strong>
                              <time>{new Date(event.at).toLocaleTimeString()}</time>
                              <p>{event.message}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    {!!selected.result.evidence?.length && (
                      <div className="result-section">
                        <h3>代码依据</h3>
                        <div className="citation-list">
                          {selected.result.evidence.map((citation, index) => (
                            <button
                              key={index}
                              onClick={() => openFile(citation.path, selected.repository_id)}
                            >
                              {citation.path}:{citation.start_line}–{citation.end_line}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {source && <Source {...source} />}
                    {selected.result.patch && (
                      <div className="result-section">
                        <h3>候选补丁</h3>
                        <p>{selected.result.summary || selected.result.proposal?.summary}</p>
                        <Diff text={selected.result.patch.diff} />
                        <p className="digest">SHA-256 {selected.result.patch.digest}</p>
                      </div>
                    )}
                    {selected.result.review && (
                      <div className="result-section">
                        <h3>审查意见</h3>
                        <ul>
                          {selected.result.review.findings.map((finding, index) => (
                            <li key={index}>{finding}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selected.status === 'awaiting_approval' && (
                      <div className="approval-box">
                        <strong>需要你确认这份补丁</strong>
                        <p>
                          批准后生成候选快照并尝试隔离测试。不会修改原 GitHub 仓库。测试目前仅支持
                          Python 标准库 unittest。
                        </p>
                        <div>
                          <button className="primary" disabled={busy} onClick={() => decide(true)}>
                            批准此补丁
                          </button>
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => decide(false)}
                          >
                            拒绝补丁
                          </button>
                        </div>
                      </div>
                    )}
                    {selected.result.test_result && (
                      <div className="result-section">
                        <h3>隔离测试</h3>
                        <p>
                          <code>{selected.result.test_result.status}</code>{' '}
                          {selected.result.test_result.reason}
                        </p>
                        {selected.result.test_result.baseline && (
                          <p className="muted">
                            原始版本：{selected.result.test_result.baseline.status}
                          </p>
                        )}
                        {selected.result.test_result.output && (
                          <pre className="test-output">{selected.result.test_result.output}</pre>
                        )}
                      </div>
                    )}
                    {selected.result.usage && (
                      <div className="usage">
                        <span>
                          输入 Token <b>{selected.result.usage.input_tokens}</b>
                        </span>
                        <span>
                          输出 Token <b>{selected.result.usage.output_tokens}</b>
                        </span>
                        <span>
                          模型调用 <b>{selected.result.usage.model_calls}</b>
                        </span>
                        <span>
                          费用{' '}
                          <b>
                            {selected.provider === 'demo'
                              ? '$0（演示）'
                              : selected.result.usage.api_cost_usd != null
                                ? `$${selected.result.usage.api_cost_usd.toFixed(6)}（按配置估算）`
                                : '未配置价格，不估算'}
                          </b>
                        </span>
                      </div>
                    )}
                    {selected.status === 'failed' && (
                      <div className="alert">
                        <div>
                          {selected.result.error}：{selected.result.message}
                        </div>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() =>
                            perform(async () => {
                              setSelected(await request<Task>(`/tasks/${selected.id}/retry`, {}))
                            })
                          }
                        >
                          从检查点重试
                        </button>
                      </div>
                    )}
                    {!active(selected.status) && (
                      <div className="download-actions">
                        <button
                          className="secondary"
                          onClick={() =>
                            perform(() =>
                              download(
                                `/tasks/${selected.id}/report`,
                                `devpilot-${selected.id}.json`,
                              ),
                            )
                          }
                        >
                          下载执行报告
                        </button>
                        {['completed', 'approved_unverified', 'test_failed'].includes(
                          selected.status,
                        ) && (
                          <button
                            className="primary"
                            onClick={() =>
                              perform(() =>
                                download(
                                  `/tasks/${selected.id}/export`,
                                  `devpilot-${selected.id}.zip`,
                                ),
                              )
                            }
                          >
                            下载补丁与快照
                          </button>
                        )}
                      </div>
                    )}
                  </>
                )}
              </section>
            </div>
          )}
        </main>
        <footer>
          DevPilot AI <span>代码有出处 · 操作有边界 · 结果可复查</span>
        </footer>
      </div>
    </div>
  )
}
