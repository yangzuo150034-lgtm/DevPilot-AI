export type Repository = {
  id: string
  name: string
  url: string
  commit: string
  paths: string[]
  stats: { files: number; chunks: number; partial?: boolean }
  created_at: string
}
export type Citation = {
  path: string
  start_line: number
  end_line: number
  text: string
  commit: string
  score: number
  embedding: string
}
export type Patch = {
  digest: string
  diff: string
  changed_paths: string[]
  proposal: { summary: string }
}
export type TestResult = { status: string; reason?: string; output?: string; baseline?: TestResult }
export type Result = {
  summary?: string
  proposal?: { summary: string }
  plan?: { steps: string[]; rationale: string }
  evidence?: Citation[]
  patch?: Patch
  review?: { approved: boolean; findings: string[] }
  test_result?: TestResult
  usage?: {
    input_tokens: number
    output_tokens: number
    model_calls: number
    api_cost_usd: number | null
  }
  error?: string
  message?: string
}
export type Task = {
  id: string
  repository_id: string
  prompt: string
  provider: 'demo' | 'openai'
  variant: string
  status: string
  result: Result
  events: { at: string; role: string; message: string }[]
  created_at: string
}
export type Capabilities = {
  model_configured: boolean
  model: string
  embedding: string
  sandbox_enabled: boolean
  queue: string
  version: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

function headers(): HeadersInit {
  const token = sessionStorage.getItem('devpilot-token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(150000)])
      : AbortSignal.timeout(150000),
  })
  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') message = data.detail
    } catch {
      /* response may not be JSON */
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export async function download(path: string, filename: string) {
  const response = await fetch(`/api/v1${path}`, {
    headers: headers(),
    signal: AbortSignal.timeout(30000),
  })
  if (!response.ok) throw new ApiError('下载失败，请确认补丁已批准', response.status)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
