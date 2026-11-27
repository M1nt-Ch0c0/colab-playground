// 唯一的网络出口。组件只调用 api.xxx()，不直接 fetch。
// mock 模式下请求交给 src/mock/server.ts，真实模式走同源 /api/*。
import type {
  CleanupBody, CleanupResult, ColabStatus, ComfyPreset, Config, GeneratePayload, LinkSpec, ProxyState, ProxyTest,
  References, RewriteBody, RoundsResponse, Round, Status, Storage, StudioPreset, TrashResponse, WfDef, WfRun, WorkflowsResponse,
  LlmProviderBody, LlmState,
} from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

type Body = unknown
type Handler = (method: string, path: string, body: Body, query: URLSearchParams) => Promise<{ status: number; json?: unknown; text?: string }>
let mockHandler: Handler | null = null
export const installMock = (h: Handler) => { mockHandler = h }

/** 相对路径，兼容部署在子路径下（旧版就是这么做的） */
const BASE = ''

async function request<T>(method: string, path: string, body?: Body): Promise<T> {
  if (__MOCK__ && mockHandler) {
    const [p, qs] = path.split('?')
    const r = await mockHandler(method, p, body, new URLSearchParams(qs || ''))
    if (r.status >= 400) throw new ApiError(r.status, (r.json as { error?: string })?.error || `HTTP ${r.status}`)
    return r.json as T
  }
  const init: RequestInit = { method, credentials: 'same-origin', headers: {} }
  if (body instanceof Blob) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    ;(init.headers as Record<string, string>)['Content-Type'] = 'application/json'
  }
  const res = await fetch(BASE + path, init)
  if (res.status === 401) { location.href = 'login'; throw new ApiError(401, '需要登录') }
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('json') ? await res.json().catch(() => ({})) : {}
  if (!res.ok) throw new ApiError(res.status, (data as { error?: string }).error || `HTTP ${res.status}`)
  return data as T
}
const get = <T>(p: string) => request<T>('GET', p)
const post = <T>(p: string, b: Body = {}) => request<T>('POST', p, b)
const del = <T>(p: string, b?: Body) => request<T>('DELETE', p, b)
const patch = <T>(p: string, b: Body) => request<T>('PATCH', p, b)
const enc = encodeURIComponent

/** 媒体地址。mock 模式由 mock 层生成 data/blob URL */
export const media = {
  round: (id: string, v?: number) => (__MOCK__ ? mockMedia.round(id) : `api/rounds/${id}${v ? `?v=${v}` : ''}`),
  thumb: (r: Round) => (__MOCK__ ? mockMedia.thumb(r.id) : r.has_thumb ? `api/rounds/${r.id}/thumb?v=${r.mtime}` : `api/rounds/${r.id}`),
  download: (id: string) => (__MOCK__ ? mockMedia.round(id) : `api/rounds/${id}?download=1`),
  trashThumb: (r: Round) => (__MOCK__ ? mockMedia.thumb(r.id) : r.has_thumb ? `api/trash/${r.id}/thumb` : `api/trash/${r.id}`),
  ref: (id: string, t: number) => (__MOCK__ ? mockMedia.ref(id) : `api/reference?id=${enc(id)}&t=${t}`),
  slot: (slot: 'first' | 'last', t: number) => (__MOCK__ ? mockMedia.ref(slot) : `api/reference?slot=${slot}&t=${t}`),
  asset: (runId: string, f: string) => (__MOCK__ ? mockMedia.ref(f) : `api/workflows/runs/${enc(runId)}/assets/${enc(f)}`),
}
export const mockMedia = {
  round: (_id: string) => '', thumb: (_id: string) => '', ref: (_k: string) => '',
}

export const api = {
  config: () => get<Config>('api/config'),
  status: (since: number) => get<Status>(`api/status?log_since=${since}`),
  storage: () => get<Storage>('api/storage'),

  generate: (p: GeneratePayload) => post<{ ok: true; jobs: { id: string; status: string }[] }>('api/generate', p),
  rewrite: (b: RewriteBody) => post<{ prompt: string; format?: string }>('api/prompt', b),
  stop: (clear_queue = false) => post('api/stop', { clear_queue }),
  release: () => post('api/release'),
  unqueue: (id: string) => del(`api/queue/${enc(id)}`),
  clearQueue: () => post<{ ok: true; removed: number }>('api/queue/clear'),
  setIdle: (idle_minutes: number) => post<{ ok: true; idle_minutes: number }>('api/settings', { idle_minutes }),

  rounds: () => get<RoundsResponse>('api/rounds?limit=0'),
  roundMeta: (id: string) => get<Round & { meta: Record<string, unknown> }>(`api/rounds/${id}/meta`),
  star: (ids: string[], starred: boolean) => post<{ ok: true; updated: string[] }>('api/rounds/star', { ids, starred }),
  deleteRounds: (ids: string[], permanent = false) => post<{ deleted: string[] }>('api/rounds/delete', { ids, permanent }),
  cleanup: (b: CleanupBody) => post<CleanupResult>('api/rounds/cleanup', b),
  trash: () => get<TrashResponse>('api/trash'),
  restore: (ids: string[]) => post<{ restored: string[]; missing: string[] }>('api/trash/restore', { ids }),
  purge: (b: { ids?: string[]; all?: boolean }) => post<{ purged: string[]; bytes: number }>('api/trash/purge', b),

  uploadRef: (file: Blob, slot: 'first' | 'last', append: boolean) =>
    request<{ references: References }>('POST', `api/reference?slot=${slot}${append && slot === 'first' ? '&append=1' : ''}`, file),
  removeRef: (id: string) => del<{ references: References }>(`api/reference?id=${enc(id)}`),
  clearSlot: (slot: 'first' | 'last') => del<{ references: References }>(`api/reference?slot=${slot}`),
  useRound: (id: string, slot: 'first' | 'last', append = false) =>
    post<{ references: References }>(`api/rounds/${id}/use`, { slot, append }),

  recentModels: { add: (model: string) => post<{ recent_models: string[] }>('api/models/recent', { model }), remove: (model: string) => del<{ recent_models: string[] }>('api/models/recent', { model }) },
  comfy: {
    parseLink: (url: string) => post<{ ok: true; spec: LinkSpec }>('api/comfy/parse-link', { url }),
    savePreset: (p: Partial<ComfyPreset>) => post<{ preset: ComfyPreset; presets: ComfyPreset[] }>('api/comfy/presets', p),
    deletePreset: (id: string) => del<{ presets: ComfyPreset[] }>(`api/comfy/presets/${enc(id)}`),
  },
  presets: {
    save: (p: Partial<StudioPreset>) => post<{ preset: StudioPreset; presets: StudioPreset[] }>('api/presets', p),
    delete: (id: string) => del<{ presets: StudioPreset[] }>(`api/presets/${enc(id)}`),
  },
  listLoras: (repo_id: string) => post<{ files: string[] }>('api/hf/list-loras', { repo_id }),

  llm: {
    get: () => get<LlmState>('api/llm'),
    save: (b: LlmProviderBody) => post<LlmState>('api/llm/providers', b),
    remove: (id: string) => del<LlmState>(`api/llm/providers/${enc(id)}`),
    fetchModels: (id: string) => post<LlmState>(`api/llm/providers/${enc(id)}/models`, {}),
    test: (id: string, model?: string) => post<{ ok: boolean; ms: number; model: string; error: string }>(`api/llm/providers/${enc(id)}/test`, { model }),
    setActive: (provider_id: string, model: string) => post<LlmState>('api/llm/active', { provider_id, model }),
  },

  colab: {
    status: () => get<ColabStatus>('api/colab/status'),
    authStart: () => post<{ auth_url: string }>('api/colab/auth/start'),
    authComplete: (code: string) => post<ColabStatus>('api/colab/auth/complete', { code }),
    logout: () => post('api/colab/auth/logout'),
    hfToken: (token: string) => post('api/colab/hf-token', { token }),
    grab: (b: { gpu_pool: string[]; poll_rounds: number; poll_all_proxies: boolean }) => post('api/colab/grab', b),
  },
  proxy: {
    set: (active: string, custom_url?: string) => post<ProxyState>('api/proxy', custom_url ? { active, custom_url } : { active }),
    test: () => post<ProxyTest>('api/proxy/test', {}),
  },

  wf: {
    list: () => get<WorkflowsResponse>('api/workflows'),
    saveTemplate: (wf: Partial<WfDef>) => post<{ workflow: WfDef; custom: WfDef[] }>('api/workflows', wf),
    deleteTemplate: (id: string) => del<{ custom: WfDef[] }>(`api/workflows/${enc(id)}`),
    createRun: (b: { workflow_id?: string; workflow?: Partial<WfDef>; topic?: string }) => post<{ run: WfRun }>('api/workflows/runs', b),
    run: (id: string) => get<{ run: WfRun }>(`api/workflows/runs/${enc(id)}`),
    update: (id: string, b: { topic?: string; workflow?: WfDef }) => patch<{ run: WfRun }>(`api/workflows/runs/${enc(id)}`, b),
    deleteRun: (id: string) => del(`api/workflows/runs/${enc(id)}`),
    start: (id: string, from_step_id?: string) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/start`, { from_step_id }),
    resume: (id: string) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/resume`, {}),
    cancel: (id: string) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/cancel`, {}),
    retry: (id: string, step: string, single_step = true) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/retry`, { single_step }),
    saveOutput: (id: string, step: string, output: Record<string, unknown>) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/output`, { output }),
    uploadAsset: (id: string, file: Blob, step_id: string) => request<{ assets: unknown[]; filename: string }>('POST', `api/workflows/runs/${enc(id)}/assets?step_id=${enc(step_id)}&label=upload`, file),
    deleteAsset: (id: string, f: string) => del(`api/workflows/runs/${enc(id)}/assets/${enc(f)}`),
  },
}
