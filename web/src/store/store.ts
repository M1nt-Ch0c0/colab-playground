// 全局状态。服务端数据以轮询为准，本地只保留草稿、视图偏好和弹层。
import { create } from 'zustand'
import { api, ApiError } from '../api/client'
import type {
  ComfyConfig, ComposerContext, ComposerPatch, ComposerPrompt, Config, EditMask, GeneratePayload,
  LlmState, Lora, References, Round, SavedModelLink, Status, Storage, StudioPreset, VideoTask, WfRun, WorkflowsResponse,
} from '../api/types'
import { LS_KEYS, lsGet, lsSet, migrateLocalStorage, now, parseHfLink, requestId, setClockSkew } from '../lib/util'

export interface ToastItem { id: number; text: string; kind: 'ok' | 'err' | ''; undo?: { label: string; fn: () => void } }
export type Workspace = 'image' | 'video' | 'workflow'
export type SheetName = 'settings' | 'library' | 'trash' | 'cleanup' | 'logs' | 'compare' | 'picker' | 'lightbox' | 'mask' | 'crop' | 'clip' | null

export interface Draft {
  engine: 'diffusers' | 'comfyui'
  model: string; ggufRepo: string; ggufFile: string
  comfyTemplate: string; comfyDiff: string; comfyTe: string; comfyVae: string; comfySampler: string; comfyScheduler: string
  comfyClipType?: string; comfyDenoise?: number
  workflow: 't2va' | 'fl2va' | 'ref2va'; frames: number; offload: 'auto' | 'component' | 'group' | 'none'
  videoTask: VideoTask | 'images'
  videoUseImages: boolean
  useFirstFrame: boolean
  idea: string; prompt: string; negative: string
  width: number; height: number; steps: number; cfg: number; seed: string
  count: number; useRef: boolean; chain: boolean
  editMask: EditMask | null
  maskId: string | null
  loras: Lora[]
  gpu: string
}

const EMPTY_DRAFT: Draft = {
  engine: 'diffusers', model: 'qwen-2.1-bf16', ggufRepo: '', ggufFile: '',
  comfyTemplate: 'qwen-image-2.1', comfyDiff: '', comfyTe: '', comfyVae: '', comfySampler: 'euler', comfyScheduler: 'simple',
  workflow: 't2va', frames: 124, offload: 'auto', videoTask: 'images', videoUseImages: false, useFirstFrame: true,
  idea: '', prompt: '', negative: 'blurry, lowres, jpeg artifacts, deformed, bad anatomy, watermark, text, logo, signature',
  width: 768, height: 1152, steps: 35, cfg: 5, seed: '-1',
  count: 1, useRef: false, chain: false, editMask: null, maskId: null, loras: [], gpu: 'A100',
}

function modelLink(link: SavedModelLink | undefined): string {
  return typeof link === 'string' ? link.trim() : link?.raw?.trim() || link?.url?.trim() || ''
}

export function comfyDraftFields(comfy: Round['comfy']) {
  return {
    comfyTemplate: comfy?.template || EMPTY_DRAFT.comfyTemplate,
    comfyDiff: modelLink(comfy?.diffusion), comfyTe: modelLink(comfy?.text_encoder), comfyVae: modelLink(comfy?.vae),
    comfySampler: comfy?.sampler || EMPTY_DRAFT.comfySampler, comfyScheduler: comfy?.scheduler || EMPTY_DRAFT.comfyScheduler,
    comfyClipType: comfy?.clip_type, comfyDenoise: comfy?.denoise,
  }
}

export function comfyPayload(draft: Draft): ComfyConfig {
  return {
    template: draft.comfyTemplate, diffusion: draft.comfyDiff.trim(), text_encoder: draft.comfyTe.trim(), vae: draft.comfyVae.trim(),
    sampler: draft.comfySampler, scheduler: draft.comfyScheduler, clip_type: draft.comfyClipType, denoise: draft.comfyDenoise,
  }
}

interface Store {
  booted: boolean; bootError: string; statusError: string
  cfg: Config | null; status: Status | null; storage: Storage | null
  rounds: Round[]; roundsRev: number
  logSeq: number; logs: string[]
  workspace: Workspace
  draft: Draft
  draftRevision: string
  sheet: SheetName; sheetArgs: Record<string, unknown>
  viewing: string | null
  galleryFilter: { kind: '' | 'image' | 'video'; starred: boolean; q: string }
  selected: string[]; selecting: boolean
  promptHist: string[]
  toasts: ToastItem[]
  theme: 'light' | 'dark' | 'system'
  wfData: WorkflowsResponse | null; wfRun: WfRun | null
  llm: LlmState | null
  libraryOpen: boolean
  loadLlm: () => Promise<void>
  setLibraryOpen: (v: boolean) => void
  grabPool: string[]; pollRounds: number; pollAllProxies: boolean
  setGrabPool: (pool: string[]) => void

  boot: () => Promise<void>
  refresh: () => Promise<void>
  loadRounds: () => Promise<void>
  setWorkspace: (w: Workspace) => void
  patchDraft: (p: Partial<Draft>) => void
  openSheet: (s: SheetName, args?: Record<string, unknown>) => void
  closeSheet: () => void
  toast: (text: string, kind?: ToastItem['kind'], undo?: ToastItem['undo']) => void
  dismissToast: (id: number) => void
  setTheme: (t: Store['theme']) => void
  setViewing: (id: string | null) => void
  toggleSelect: (id: string) => void
  generate: () => Promise<void>
  videoRefBusy: boolean
  setVideoRef: (source: File | string | null) => Promise<boolean>
  applyPreset: (p: StudioPreset) => void
  loadWf: () => Promise<void>
  setWfRun: (r: WfRun | null) => void
  agentPluginRev: number
  bumpAgentPluginRev: () => void
}

let toastSeq = 1
let saveTimer = 0
let booting: Promise<void> | null = null
let statusRequest = 0
const initialTheme = document.documentElement.dataset.theme

function shouldNotifyError(st: Status, previous: Status | null) {
  if (st.phase !== 'error' || !st.error) return false
  if (previous?.phase === 'error' && previous.error_id === st.error_id && previous.error === st.error) return false
  if (st.error_id) {
    try {
      if (sessionStorage.getItem('colabreel.lastStatusError') === st.error_id) return false
      sessionStorage.setItem('colabreel.lastStatusError', st.error_id)
    } catch { /* 存储不可用时仍按当前页面收到的状态去重 */ }
  }
  return true
}

// 初始状态在模块加载时读取 localStorage，必须先把旧 key 搬过来。
migrateLocalStorage()

export const useStore = create<Store>((set, get) => ({
  booted: false, bootError: '', statusError: '',
  cfg: null, status: null, storage: null,
  rounds: [], roundsRev: -1,
  logSeq: 0, logs: [],
  workspace: new URLSearchParams(location.search).has('workflow') ? 'workflow' : 'image',
  videoRefBusy: false,
  draft: { ...EMPTY_DRAFT, ...lsGet<Partial<Draft>>(LS_KEYS.draft, {}) },
  draftRevision: requestId(),
  sheet: null, sheetArgs: {},
  viewing: null,
  galleryFilter: { kind: '', starred: false, q: '' },
  selected: [], selecting: false,
  promptHist: lsGet<string[]>(LS_KEYS.phist, []),
  toasts: [],
  theme: initialTheme === 'light' || initialTheme === 'dark' ? initialTheme : 'system',
  wfData: null, wfRun: null,
  llm: null,
  // 作品库默认收起，和旧版一致；展开状态按浏览器记住
  libraryOpen: lsGet<boolean>(LS_KEYS.libopen, false),
  loadLlm: async () => { try { set({ llm: await api.llm.get() }) } catch (e) { if (!(e instanceof ApiError && e.status === 401)) get().toast(e instanceof Error ? e.message : '加载改写模型失败', 'err') } },
  setLibraryOpen: v => { lsSet(LS_KEYS.libopen, v); set({ libraryOpen: v }) },
  grabPool: lsGet<string[]>(LS_KEYS.grab, ['A100', 'H100']),
  setGrabPool: pool => { lsSet(LS_KEYS.grab, pool); set({ grabPool: pool }) },
  pollRounds: lsGet<number>(LS_KEYS.rounds, 2),
  pollAllProxies: lsGet<boolean>(LS_KEYS.pollpx, false),

  boot: () => {
    if (booting) return booting
    booting = (async () => {
      try {
        const cfg = await api.config()
        set({ cfg, booted: true, bootError: '' })
        await get().refresh()
        await get().loadLlm()
      } catch (e) {
        set({ bootError: e instanceof Error ? e.message : '无法连接服务' })
      }
    })().finally(() => { booting = null })
    return booting
  },
  refresh: async () => {
    const request = ++statusRequest
    try {
      const st = await api.status(get().logSeq)
      if (request !== statusRequest) return
      const notifyError = shouldNotifyError(st, get().status)
      setClockSkew(st.server_time)
      const logs = st.logs.length ? [...get().logs, ...st.logs].slice(-600) : get().logs
      const patch: Partial<Store> = { status: st, logs, logSeq: st.log_seq }
      if (st.gallery_rev !== get().roundsRev && get().booted) get().loadRounds()
      set({ ...patch, bootError: '', statusError: '' })
      if (notifyError) get().toast(st.error, 'err')
    } catch (e) {
      if (request !== statusRequest || (e instanceof ApiError && e.status === 401)) return
      const message = e instanceof Error ? e.message : '无法读取工作台状态'
      set(get().status ? { statusError: message } : { bootError: message })
    }
  },
  loadRounds: async () => {
    try {
      const r = await api.rounds()
      set({ rounds: r.rounds, roundsRev: r.rev })
    } catch { /* 轮询会重试 */ }
  },
  setWorkspace: w => set({ workspace: w }),
  patchDraft: p => {
    const draft = { ...get().draft, ...p }
    if (p.useRef || p.chain) { draft.editMask = null; draft.maskId = null }
    if (Object.hasOwn(p, 'editMask') && !Object.hasOwn(p, 'maskId')) draft.maskId = null
    set({ draft, draftRevision: requestId() })
    clearTimeout(saveTimer); saveTimer = window.setTimeout(() => lsSet(LS_KEYS.draft, draft), 300)
  },
  openSheet: (s, args = {}) => set({ sheet: s, sheetArgs: args }),
  closeSheet: () => set({ sheet: null, sheetArgs: {} }),
  toast: (text, kind = '', undo) => {
    const toasts = get().toasts
    if (kind === 'err' && !undo && toasts.some(t => t.kind === 'err' && t.text === text && !t.undo)) return
    const id = toastSeq++
    set({ toasts: [...toasts, { id, text, kind, undo }].slice(-4) })
    setTimeout(() => get().dismissToast(id), undo ? 6000 : 3200)
  },
  dismissToast: id => set({ toasts: get().toasts.filter(t => t.id !== id) }),
  setTheme: theme => {
    if (theme === 'system') delete document.documentElement.dataset.theme
    else document.documentElement.dataset.theme = theme
    lsSet(LS_KEYS.theme, theme)
    set({ theme })
  },
  setViewing: id => set({ viewing: id }),
  toggleSelect: id => {
    const s = new Set(get().selected)
    if (s.has(id)) s.delete(id); else s.add(id)
    set({ selected: [...s] })
  },
  setVideoRef: async source => {
    const { status, cfg, toast, videoRefBusy } = get()
    if (videoRefBusy) return false
    const clip = status?.references.video
    const maxMB = cfg?.limits.video_upload_max_mb ?? 64
    if (source instanceof Blob && source.size > maxMB * 1048576) { toast(`参考视频超过 ${maxMB} MB`, 'err'); return false }
    if (source === null && !clip) return true
    set({ videoRefBusy: true })
    try {
      let result: { references: References }
      if (typeof source === 'string') result = await api.useRound(source, 'video')
      else if (source) result = await api.uploadVideoRef(source)
      else result = await api.clearVideoRef(clip!.id)
      const st = get().status
      if (st) set({ status: { ...st, references: result.references } })
      return true
    } catch (e) { toast(e instanceof Error ? e.message : '设置参考视频失败', 'err'); return false }
    finally { set({ videoRefBusy: false }) }
  },
  generate: async () => {
    const { draft, status, cfg, toast, promptHist } = get()
    const v = get().workspace === 'video'
    const refs = status?.references
    if (status?.phase === 'starting' && !status.current) { toast('正在抢卡，等算力就绪后再生成', 'err'); return }
    if (status?.colab.authed && !status.colab.sessions.length) { toast('还没有持有的算力，先去设置里抢卡', 'err'); get().openSheet('settings'); return }
    if (!draft.prompt.trim()) { toast('先写提示词', 'err'); return }
    if (!v && draft.engine === 'comfyui' && (!draft.comfyDiff || !draft.comfyTe || !draft.comfyVae)) { toast('ComfyUI 需要填齐扩散模型、文本编码器和 VAE 三个链接', 'err'); return }
    const videoTask = v && draft.workflow === 'ref2va' && draft.videoTask !== 'images' ? draft.videoTask : null
    if (videoTask && get().videoRefBusy) { toast('正在读取参考视频，请稍候'); return }
    if (videoTask && !refs?.video) { toast('请上传参考视频，或从作品库选一段', 'err'); return }
    const firstFrame = draft.useFirstFrame && !!refs?.first.set
    if (v && draft.workflow === 'fl2va' && !firstFrame && !refs?.last.set) { toast('请设置首帧或尾帧', 'err'); return }
    const needsImage = v ? draft.workflow === 'ref2va' && (!videoTask || videoTask === 'motion') : draft.useRef && !draft.chain && !draft.editMask
    if (needsImage && !refs?.first.set) { toast(videoTask === 'motion' ? '请添加一张人设图' : '请上传参考图，或从作品库选一张', 'err'); return }
    const held = (status?.colab.sessions || []).map(s => s.gpu.toUpperCase())
    const gpu = held.includes(draft.gpu) ? draft.gpu : held[0] || draft.gpu
    const p: GeneratePayload = {
      mode: v ? 'video' : 'image', prompt: draft.prompt.trim(), negative: draft.negative, idea: draft.idea.trim(),
      gpu, gpu_pool: [gpu], poll_rounds: 1, poll_all_proxies: false,
      width: draft.width, height: draft.height, steps: draft.steps, cfg: draft.cfg,
      seed: draft.seed === '' ? -1 : +draft.seed, count: draft.count,
      loras: draft.loras.filter(l => l.repo_id.trim()), has_image: false,
    }
    if (v) {
      p.workflow = draft.workflow; p.num_frames = draft.frames; p.offload_mode = draft.offload; p.auto_offload = draft.offload !== 'none'
      p.has_image = draft.workflow === 'fl2va' ? firstFrame
        : draft.workflow === 'ref2va' && !!refs?.first.set && (!videoTask || videoTask === 'motion' || draft.videoUseImages)
      p.has_last_image = draft.workflow === 'fl2va' && !!refs?.last.set
      if (videoTask && refs?.video) { p.video_task = videoTask; p.video_reference_id = refs.video.id }
    } else {
      p.engine = draft.engine; p.chain = draft.chain; p.has_image = draft.useRef && !draft.chain
      if (draft.editMask) { p.edit_mask = draft.editMask; p.has_image = true }
      if (draft.engine === 'comfyui') p.comfy = comfyPayload(draft)
      else { p.model = draft.model.trim(); p.custom_transformer_repo = draft.ggufRepo.trim(); p.custom_transformer_file = draft.ggufFile.trim() }
    }
    try {
      const r = await api.generate(p)
      const hist = [p.prompt, ...promptHist.filter(h => h !== p.prompt)].slice(0, 15)
      lsSet(LS_KEYS.phist, hist); set({ promptHist: hist, viewing: null })
      toast(r.jobs.length > 1 ? `已加入队列，${r.jobs.length} 个任务` : '已提交', 'ok')
      if (cfg) { /* 触达 */ }
      get().refresh()
    } catch (e) { toast(e instanceof Error ? e.message : '提交失败', 'err') }
  },
  applyPreset: p => {
    const d: Partial<Draft> = { width: p.width, height: p.height, steps: p.steps, cfg: p.cfg, gpu: p.gpu || get().draft.gpu }
    if (p.loras) d.loras = p.loras
    if (p.mode === 'video') { d.workflow = p.workflow || 't2va'; d.videoTask = p.video_task || 'images'; d.frames = p.num_frames || 124; d.offload = p.offload_mode || 'auto'; set({ workspace: 'video' }) }
    else {
      d.engine = p.engine || 'diffusers'
      d.model = p.model || get().draft.model
      if (d.engine === 'comfyui') Object.assign(d, comfyDraftFields(p.comfy))
      set({ workspace: 'image' })
    }
    get().patchDraft(d); get().toast(`已套用「${p.name}」`, 'ok')
  },
  loadWf: async () => {
    try {
      const wfData = await api.wf.list()
      set({ wfData })
    } catch (e) { get().toast(e instanceof Error ? e.message : '加载工作流失败', 'err') }
  },
  setWfRun: r => set({ wfRun: r }),
  agentPluginRev: 0,
  bumpAgentPluginRev: () => set(s => ({ agentPluginRev: s.agentPluginRev + 1 })),
}))

export function selectPollInterval({ status }: Store) {
  if (status?.phase === 'starting' && !status.current) return 750
  if (status && (status.current || status.queue.length || status.phase === 'stopping' || status.workflow_active?.status === 'running')) return 1300
  return 5000
}

export const selectRefs = (s: Store): References | null => s.status?.references || null
export const serverNow = now

export function assistantComposerScope() {
  const stored = lsGet<string>(LS_KEYS.composerScope, '')
  if (/^cr_[a-f0-9]{32}$/.test(stored)) return stored
  const key = 'cr_' + requestId()
  lsSet(LS_KEYS.composerScope, key)
  return key
}

const HF_REPO_RE = /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/
const MASK_ID_RE = /^mk_[a-f0-9]{24}$/
const VIDEO_REF_ID_RE = /^v[a-f0-9]{32}$/

function clampInt(value: number, low: number, high: number, fallback: number): number {
  return Number.isFinite(value) ? Math.min(high, Math.max(low, Math.round(value))) : fallback
}

function clampFloat(value: number, low: number, high: number, fallback: number): number {
  return Number.isFinite(value) ? Math.min(high, Math.max(low, value)) : fallback
}

function safeDecode(text: string): string {
  try { return decodeURIComponent(text) } catch { return text }
}

function sanitizeContextLora(row: Lora, maxScale: number): Lora | null {
  const rawRepo = row.repo_id.trim()
  if (!rawRepo) return null
  let repo = rawRepo.replace(/^\/+|\/+$/g, '')
  let weight = row.weight_name.trim()
  const hf = rawRepo.match(/^(?:https?:\/\/)?(?:www\.)?(?:huggingface\.co|hf-mirror\.com|hf\.co)\/(?:models\/)?([^/]+\/[^/]+)\/(?:blob|resolve|raw)\/[^/]+\/(.+?)(?:[?#].*)?$/i)
  if (hf) {
    repo = hf[1]
    weight = weight || safeDecode(hf[2]).trim()
  } else {
    const parsed = parseHfLink(rawRepo)
    if (parsed && parsed.repo !== '直链') {
      repo = parsed.repo.trim()
      weight = weight || parsed.file.trim()
    } else if (rawRepo.includes(':') && !rawRepo.startsWith('/') && !/^https?:\/\//i.test(rawRepo)) {
      const idx = rawRepo.indexOf(':')
      const left = rawRepo.slice(0, idx).trim().replace(/^\/+|\/+$/g, '')
      const right = rawRepo.slice(idx + 1).replace(/^:+/, '').trim()
      if (HF_REPO_RE.test(left)) {
        repo = left
        weight = weight || right
      }
    } else {
      const segs = repo.split('/').filter(Boolean)
      if (segs.length >= 3 && HF_REPO_RE.test(`${segs[0]}/${segs[1]}`)) {
        repo = `${segs[0]}/${segs[1]}`
        weight = weight || segs.slice(2).join('/')
      }
    }
  }
  if (!HF_REPO_RE.test(repo) || repo.length > 160) return null
  return { repo_id: repo, weight_name: weight.slice(0, 360), scale: clampFloat(row.scale, 0, maxScale, 1) }
}

export function assistantComposerContext(): ComposerContext {
  const { draft: d, workspace, status, draftRevision, cfg } = useStore.getState()
  const refs = status?.references
  const lim = cfg?.limits
  const seed = d.seed.trim() ? Number(d.seed) : -1
  const maxLoras = lim?.loras_max ?? 4
  const maxScale = lim?.lora_scale_max ?? 2.5
  const loras = d.loras
    .map(row => sanitizeContextLora(row, maxScale))
    .filter((row): row is Lora => row !== null)
    .slice(0, maxLoras)
  const common = {
    revision: draftRevision,
    prompt: d.prompt.slice(0, lim?.prompt_max ?? 12000),
    idea: d.idea.slice(0, 600),
    negative: d.negative.slice(0, lim?.negative_max ?? 1200),
    width: clampInt(d.width, 1, 4096, EMPTY_DRAFT.width),
    height: clampInt(d.height, 1, 4096, EMPTY_DRAFT.height),
    steps: clampInt(d.steps, 1, 200, EMPTY_DRAFT.steps),
    count: clampInt(d.count, 1, lim?.count_max ?? 4, 1),
    cfg: clampFloat(d.cfg, 0, 100, EMPTY_DRAFT.cfg),
    seed: Number.isInteger(seed) && seed >= 0 && seed <= 2 ** 31 - 1 ? seed : -1,
    loras,
  }
  if (workspace === 'video') {
    const task = d.workflow === 'ref2va' ? d.videoTask : 'images'
    const videoRefId = task !== 'images' && refs?.video?.id && VIDEO_REF_ID_RE.test(refs.video.id) ? refs.video.id : undefined
    return {
      ...common, mode: 'video', workflow: d.workflow,
      num_frames: clampInt(d.frames, 1, 400, EMPTY_DRAFT.frames),
      offload_mode: d.offload, video_task: task, video_reference_id: videoRefId,
      has_image: d.workflow === 'fl2va' ? d.useFirstFrame && !!refs?.first.set
        : d.workflow === 'ref2va' && !!refs?.first.set && (task === 'images' || task === 'motion' || d.videoUseImages),
      has_last_image: d.workflow === 'fl2va' && !!refs?.last.set,
    }
  }
  const ggufRepo = d.ggufRepo.trim().replace(/^\/+|\/+$/g, '')
  const comfyRaw = d.engine === 'comfyui' ? comfyPayload(d) : undefined
  const comfy = comfyRaw ? {
    template: comfyRaw.template.trim().slice(0, 80),
    diffusion: comfyRaw.diffusion.slice(0, 500),
    text_encoder: comfyRaw.text_encoder.slice(0, 500),
    vae: comfyRaw.vae.slice(0, 500),
    sampler: comfyRaw.sampler.trim().slice(0, 80),
    scheduler: comfyRaw.scheduler.trim().slice(0, 80),
    clip_type: comfyRaw.clip_type ? comfyRaw.clip_type.trim().slice(0, 80) : undefined,
    denoise: typeof comfyRaw.denoise === 'number' && Number.isFinite(comfyRaw.denoise)
      && comfyRaw.denoise >= 0.05 && comfyRaw.denoise <= 1 ? comfyRaw.denoise : undefined,
  } : undefined
  return {
    ...common, mode: 'image', engine: d.engine, model: d.model.trim().slice(0, 160), chain: d.chain,
    has_image: d.useRef || !!d.editMask,
    mask_id: d.maskId && MASK_ID_RE.test(d.maskId) ? d.maskId : null,
    comfy,
    custom_transformer_repo: HF_REPO_RE.test(ggufRepo) && ggufRepo.length <= 160 ? ggufRepo : '',
    custom_transformer_file: d.ggufFile.trim().slice(0, 200),
  }
}

export async function applyAssistantComposerPatch({ workspace, base_revision, changes }: ComposerPatch) {
  const applies = () => {
    const s = useStore.getState()
    return workspace === s.workspace && !!base_revision && base_revision === s.draftRevision
  }
  if (!applies()) return false
  const mask = changes.mask_id ? await api.wf.mask(changes.mask_id) : undefined
  if (!applies()) return false
  const { draft, patchDraft } = useStore.getState()
  const patch: Partial<Draft> = {}
  for (const field of ['prompt', 'idea', 'negative', 'model'] as const) {
    if (typeof changes[field] === 'string') patch[field] = changes[field]
  }
  for (const field of ['width', 'height', 'steps', 'cfg', 'count'] as const) {
    if (typeof changes[field] === 'number') patch[field] = changes[field]
  }
  if (changes.seed != null) patch.seed = String(changes.seed)
  if (changes.loras) patch.loras = changes.loras.map(row => ({ ...row, scale: row.scale ?? 1 }))
  if (workspace === 'image') {
    if (changes.engine) patch.engine = changes.engine
    if (changes.comfy) Object.assign(patch, comfyDraftFields({ ...comfyPayload(draft), ...Object.fromEntries(
      Object.entries(changes.comfy).filter(([, value]) => value != null),
    ) }))
    if (changes.custom_transformer_repo != null) patch.ggufRepo = changes.custom_transformer_repo
    if (changes.custom_transformer_file != null) patch.ggufFile = changes.custom_transformer_file
    if (changes.chain != null) patch.chain = changes.chain
    if (changes.has_image != null) patch.useRef = changes.has_image
    if (mask) Object.assign(patch, { editMask: { source_id: mask.source_id, strokes: mask.strokes },
      maskId: mask.mask_id, chain: false, useRef: false })
    else if (('mask_id' in changes && changes.mask_id === null) || changes.chain === true || changes.has_image === false) {
      Object.assign(patch, { editMask: null, maskId: null })
    }
  } else {
    if (changes.workflow) patch.workflow = changes.workflow
    if (changes.num_frames) patch.frames = changes.num_frames
    if (changes.offload_mode) patch.offload = changes.offload_mode
    if (changes.video_task) patch.videoTask = changes.video_task
    if (changes.has_image != null) {
      if ((changes.workflow ?? draft.workflow) === 'fl2va') patch.useFirstFrame = changes.has_image
      else patch.videoUseImages = changes.has_image
    }
  }
  patchDraft(patch)
  return true
}

export function assistantComposerPrompt(): ComposerPrompt | undefined {
  const { workspace, draft } = useStore.getState()
  if (workspace === 'workflow') return
  return { workspace, prompt: draft.prompt }
}

export function applyAssistantComposerPrompt(expected: ComposerPrompt, prompt: string) {
  const current = assistantComposerPrompt()
  if (current?.workspace !== expected.workspace || current.prompt !== expected.prompt) return false
  useStore.getState().patchDraft({ prompt })
  return true
}
