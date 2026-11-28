// 唯一的网络出口。组件只调用 api.xxx()，不直接 fetch。
// mock 模式下请求交给 src/mock/server.ts，真实模式走同源 /api/*。
import type {
  AssetUpload, CleanupBody, CleanupResult, ColabStatus, ComfyPreset, Config, CropBox, GeneratePayload, LinkSpec, ProxyProfileBody, ProxyState, ProxyTest,
  References, RewriteBody, RoundsResponse, Round, Status, Storage, StudioPreset, TrashResponse, WfDef, WfRun, WorkflowsResponse,
  LlmProviderBody, LlmState, ProbeResult, RewriteResult, SessionResult, AgentErrorCode, AgentEvent,
  AgentPlugins, AgentPluginAction, AgentTurnBody, SavedAgentExchange, AgentTelemetry,
  Proposal, ProposalAction, RewriteInput, Shot, ShotEdit, ShotWriteResult,
  Operation, MaskRecord, EditMask, ComposerPrompt, ComposerWriteResult,
} from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: AgentErrorCode, public details?: Record<string, unknown>) { super(message) }
}

type Body = unknown
type Handler = (method: string, path: string, body: Body, query: URLSearchParams) => Promise<{ status: number; json?: unknown; text?: string }>
let mockHandler: Handler | null = null
export const installMock = (h: Handler) => { mockHandler = h }

/** 相对路径，兼容部署在子路径下（旧版就是这么做的） */
const BASE = ''

function apiError(status: number, data: unknown) {
  const body = data as { error?: string; code?: AgentErrorCode; details?: Record<string, unknown> } | null
  return new ApiError(status, body?.error || 'HTTP ' + status, body?.code, body?.details)
}

async function request<T>(method: string, path: string, body?: Body): Promise<T> {
  if (__MOCK__ && mockHandler) {
    const [p, qs] = path.split('?')
    const r = await mockHandler(method, p, body, new URLSearchParams(qs || ''))
    if (r.status >= 400) throw apiError(r.status, r.json)
    return r.json as T
  }
  const init: RequestInit = { method, credentials: 'same-origin', headers: {} }
  if (body instanceof Blob) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    ;(init.headers as Record<string, string>)['Content-Type'] = 'application/json'
  }
  const res = await fetch(BASE + path, init)
  if (res.status === 401 && path !== 'api/login') location.hash = 'login'
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('json')) throw new ApiError(res.status, `服务返回了非 JSON 响应（HTTP ${res.status}）`)
  const data = await res.json()
  if (!res.ok) throw apiError(res.status, data)
  return data as T
}
const get = <T>(p: string) => request<T>('GET', p)
const post = <T>(p: string, b: Body = {}) => request<T>('POST', p, b)
const del = <T>(p: string, b?: Body) => request<T>('DELETE', p, b)
const patch = <T>(p: string, b: Body) => request<T>('PATCH', p, b)
const enc = encodeURIComponent

async function agentTurn(body: AgentTurnBody, signal: AbortSignal, receive: (event: AgentEvent) => void) {
  const path = 'api/workflows/agent/turn'
  function consume(event: AgentEvent) {
    if (event.type === 'error') {
      receive(event)
      throw new ApiError(200, event.message, event.code)
    }
    receive(event)
    if (event.type === 'done') return event
  }
  if (__MOCK__ && mockHandler) {
    const events = await request<AgentEvent[]>('POST', path, body)
    let gathering = true
    for (const event of events) {
      if (gathering && (event.type === 'done' || event.type === 'tool' && event.ok !== null)) {
        gathering = false
        await new Promise(resolve => setTimeout(resolve, 540))
      }
      signal.throwIfAborted()
      const done = consume(event)
      if (done) return done
    }
  } else {
    const res = await fetch(BASE + path, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
    if (res.status === 401) location.hash = 'login'
    if (!res.ok) throw apiError(res.status, await res.json().catch(() => null))
    if (!res.body || !res.headers.get('Content-Type')?.includes('application/x-ndjson')) {
      throw new ApiError(res.status, 'Expected NDJSON', 'internal_error')
    }
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
    let buffer = ''
    try {
      while (true) {
        const chunk = await reader.read()
        if (!chunk.done) buffer += chunk.value
        const lines = buffer.split('\n')
        buffer = chunk.done ? '' : lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          let event: AgentEvent
          try { event = JSON.parse(line) }
          catch { throw new ApiError(res.status, 'Invalid NDJSON event', 'internal_error') }
          const done = consume(event)
          if (done) return done
        }
        if (chunk.done) break
      }
    } finally {
      await reader.cancel().catch(() => {})
    }
  }
  throw new ApiError(0, 'The stream ended before a result', 'internal_error')
}

/** 媒体地址。mock 模式由 mock 层生成 data/blob URL */
export const media = {
  round: (id: string, v?: number) => (__MOCK__ ? mockMedia.round(id) : `api/rounds/${id}${v ? `?v=${v}` : ''}`),
  thumb: (r: Round) => (__MOCK__ ? mockMedia.thumb(r.id) : r.has_thumb ? `api/rounds/${r.id}/thumb?v=${r.mtime}` : `api/rounds/${r.id}`),
  download: (id: string) => (__MOCK__ ? mockMedia.round(id) : `api/rounds/${id}?download=1`),
  trashThumb: (r: Round) => (__MOCK__ ? mockMedia.thumb(r.id) : r.has_thumb ? `api/trash/${r.id}/thumb` : `api/trash/${r.id}`),
  ref: (id: string, t: number) => (__MOCK__ ? mockMedia.ref(id) : `api/reference?id=${enc(id)}&t=${t}`),
  videoRef: (id: string) => (__MOCK__ ? mockMedia.ref(id) : `api/video-reference?id=${enc(id)}`),
  slot: (slot: 'first' | 'last', t: number) => (__MOCK__ ? mockMedia.ref(slot) : `api/reference?slot=${slot}&t=${t}`),
  assetThumb: (runId: string, f: string) => (__MOCK__ ? mockMedia.ref(f) : `api/workflows/runs/${enc(runId)}/assets/${enc(f)}?thumb=1`),
}
export const mockMedia = {
  round: (_id: string) => '', thumb: (_id: string) => '', ref: (_k: string) => '',
}

export const api = {
  login: (password: string) => post<SessionResult>('api/login', { password }),
  logout: () => post<SessionResult>('api/logout'),
  config: () => get<Config>('api/config'),
  status: (since: number) => get<Status>(`api/status?log_since=${since}`),
  storage: () => get<Storage>('api/storage'),

  generate: (p: GeneratePayload) => post<{ ok: true; jobs: { id: string; status: string }[] }>('api/generate', p),
  rewrite: (b: RewriteBody) => post<RewriteResult>('api/prompt', b),
  stop: (clear_queue = false) => post('api/stop', { clear_queue }),
  release: () => post('api/release'),
  unqueue: (id: string) => del(`api/queue/${enc(id)}`),
  retry: (id: string) => post<{ id: string }>(`api/queue/${enc(id)}/retry`),
  clearQueue: () => post<{ ok: true; removed: number }>('api/queue/clear'),
  setIdle: (idle_minutes: number) => post<{ ok: true; idle_minutes: number }>('api/settings', { idle_minutes }),

  rounds: () => get<RoundsResponse>('api/rounds?limit=0'),
  importMedia: (file: File, kind: Round['kind']) => post<{ id: string }>(`api/rounds/import?kind=${kind}&name=${enc(file.name)}`, file),
  crop: (id: string, box: CropBox) => post<{ id: string }>(`api/rounds/${enc(id)}/crop`, box),
  frame: (id: string, position: 'first' | 'time' | 'last', time_s = 0) => post<{ id: string }>(`api/rounds/${enc(id)}/frame`, { position, time_s }),
  clip: (id: string, start_s: number, end_s: number, mute: boolean) => post<{ id: string }>(`api/rounds/${enc(id)}/clip`, { start_s, end_s, mute }),
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
  uploadVideoRef: (file: Blob) => request<{ references: References }>('POST', 'api/video-reference', file),
  clearVideoRef: (id: string) => del<{ references: References }>(`api/video-reference?id=${enc(id)}`),
  useRound: (id: string, slot: 'first' | 'last' | 'video', append = false) =>
    post<{ references: References }>(`api/rounds/${id}/use`, { slot, append }),

  recentModels: { add: (model: string) => post<{ recent_models: string[] }>('api/models/recent', { model }), remove: (model: string) => del<{ recent_models: string[] }>('api/models/recent', { model }) },
  comfy: {
    parseLink: (url: string) => post<{ ok: true; spec: LinkSpec }>('api/comfy/parse-link', { url }),
    savePreset: (p: Partial<ComfyPreset>) => post<{ preset: ComfyPreset; presets: ComfyPreset[] }>('api/comfy/presets', p),
    deletePreset: (id: string) => del<{ presets: ComfyPreset[] }>(`api/comfy/presets/${enc(id)}`),
  },
  presets: {
    save: (p: Partial<StudioPreset>) => post<{ preset: StudioPreset; custom: StudioPreset[] }>('api/presets', p),
    delete: (id: string) => del<{ custom: StudioPreset[] }>(`api/presets/${enc(id)}`),
  },
  listLoras: (repo_id: string) => post<{ files: string[] }>('api/hf/list-loras', { repo_id }),

  llm: {
    get: () => get<LlmState>('api/llm'),
    save: (b: LlmProviderBody) => post<LlmState>('api/llm/providers', b),
    remove: (id: string) => del<LlmState>(`api/llm/providers/${enc(id)}`),
    fetchModels: (id: string) => post<LlmState>(`api/llm/providers/${enc(id)}/models`, {}),
    test: (id: string, model?: string) => post<ProbeResult>(`api/llm/providers/${enc(id)}/test`, { model }),
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
    set: (active: string) => post<ProxyState>('api/proxy', { active }),
    save: (b: ProxyProfileBody) => post<ProxyState>('api/proxy/profiles', b),
    remove: (id: string) => del<ProxyState>(`api/proxy/profiles/${enc(id)}`),
    test: (profile: string) => post<ProxyTest>('api/proxy/test', { profile }),
  },

  wf: {
    agentTurn,
    conversation: (key: string) => get<{ exchanges: SavedAgentExchange[] }>(`api/workflows/agent/conversations/${enc(key)}`),
    stopTurn: (key: string, turn_id: string) => post<{ stopped: boolean }>(`api/workflows/agent/conversations/${enc(key)}/stop`, { turn_id }),
    plugins: () => get<AgentPlugins>('api/workflows/agent/plugins'),
    changePlugin: (id: string, action: AgentPluginAction) => post<AgentPlugins>(`api/workflows/agent/plugins/${enc(id)}`, { action }),
    shots: (id: string, step?: string) => get<{ shots: Shot[] }>(`api/workflows/runs/${enc(id)}/shots${step ? '?step_id=' + enc(step) : ''}`),
    rewriteShots: (id: string, step: string, body: RewriteInput) =>
      post<Proposal>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/shots/rewrite`, body),
    applyProposal: (id: string, body: ProposalAction) => post<ShotWriteResult>(`api/workflows/agent/proposals/${enc(id)}/apply`, body),
    rejectProposal: (id: string) => post<Proposal>(`api/workflows/agent/proposals/${enc(id)}/reject`),
    undoShots: (id: string) => post<ShotWriteResult>(`api/workflows/agent/undo/${enc(id)}`),
    applyComposer: (id: string, body: ComposerPrompt) =>
      post<ComposerWriteResult>(`api/workflows/agent/proposals/${enc(id)}/composer-apply`, body),
    undoComposer: (id: string, body: ComposerPrompt) =>
      post<ComposerWriteResult>(`api/workflows/agent/undo/${enc(id)}/composer`, body),
    operations: (scope: string) => get<{ operations: Operation[] }>(`api/workflows/agent/operations?scope_key=${enc(scope)}`),
    operation: (id: string) => get<Operation>(`api/workflows/agent/operations/${enc(id)}`),
    approveOperation: (id: string) => post<Operation>(`api/workflows/agent/operations/${enc(id)}/approve`),
    cancelOperation: (id: string) => post<Operation>(`api/workflows/agent/operations/${enc(id)}/cancel`),
    retryOperation: (id: string, item_keys?: string[]) =>
      post<Operation>(`api/workflows/agent/operations/${enc(id)}/retry-failed`, { item_keys }),
    createMask: (body: EditMask) => post<MaskRecord>('api/workflows/agent/masks', body),
    mask: (id: string) => get<MaskRecord>(`api/workflows/agent/masks/${enc(id)}`),
    telemetry: () => get<AgentTelemetry>('api/workflows/agent/telemetry'),
    list: () => get<WorkflowsResponse>('api/workflows'),
    saveTemplate: (wf: Partial<WfDef>) => post<{ workflow: WfDef; custom: WfDef[] }>('api/workflows', wf),
    deleteTemplate: (id: string) => del<{ custom: WfDef[] }>(`api/workflows/${enc(id)}`),
    createRun: (b: { request_id?: string; workflow_id?: string; workflow?: Partial<WfDef>; topic?: string }) => post<{ run: WfRun }>('api/workflows/runs', b),
    run: (id: string) => get<{ run: WfRun }>(`api/workflows/runs/${enc(id)}`),
    update: (id: string, b: { topic?: string; workflow?: WfDef; if_revision?: string }) => patch<{ run: WfRun }>(`api/workflows/runs/${enc(id)}`, b),
    deleteRun: (id: string) => del(`api/workflows/runs/${enc(id)}`),
    start: (id: string, from_step_id?: string, draft_only = false) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/start`, { from_step_id, draft_only }),
    resume: (id: string) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/resume`, {}),
    cancel: (id: string) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/cancel`, {}),
    retry: (id: string, step: string, single_step = true) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/retry`, { single_step }),
    saveOutput: (id: string, step: string, output: Record<string, unknown>) => post<{ run: WfRun }>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/output`, { output }),
    saveShotEdits: (id: string, step: string, shot_edits: ShotEdit[]) =>
      post<ShotWriteResult>(`api/workflows/runs/${enc(id)}/steps/${enc(step)}/output`, { shot_edits }),
    uploadAsset: (id: string, file: Blob, step_id: string) => request<AssetUpload>('POST', `api/workflows/runs/${enc(id)}/assets?step_id=${enc(step_id)}&label=upload`, file),
    deleteAsset: (id: string, f: string) => del(`api/workflows/runs/${enc(id)}/assets/${enc(f)}`),
  },
}
