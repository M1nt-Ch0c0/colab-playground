// 全局状态。服务端数据以轮询为准，本地只保留草稿、视图偏好和弹层。
import { create } from 'zustand'
import { api, ApiError } from '../api/client'
import type {
  Config, GeneratePayload, LlmState, Lora, References, Round, Status, Storage, StudioPreset, WfRun, WorkflowsResponse,
} from '../api/types'
import { lsGet, lsSet, now, setClockSkew } from '../lib/util'

export interface ToastItem { id: number; text: string; kind: 'ok' | 'err' | ''; undo?: { label: string; fn: () => void } }
export type Workspace = 'image' | 'video' | 'workflow'
export type SheetName = 'settings' | 'library' | 'trash' | 'cleanup' | 'logs' | 'compare' | 'picker' | 'lightbox' | null

export interface Draft {
  engine: 'diffusers' | 'comfyui'
  model: string; ggufRepo: string; ggufFile: string
  comfyTemplate: string; comfyDiff: string; comfyTe: string; comfyVae: string; comfySampler: string; comfyScheduler: string
  workflow: 't2va' | 'fl2va' | 'ref2va'; frames: number; offload: 'auto' | 'component' | 'group' | 'none'
  idea: string; prompt: string; negative: string
  width: number; height: number; steps: number; cfg: number; seed: string
  count: number; useRef: boolean; chain: boolean
  loras: Lora[]
  gpu: string
}

const EMPTY_DRAFT: Draft = {
  engine: 'diffusers', model: 'qwen-2.1-bf16', ggufRepo: '', ggufFile: '',
  comfyTemplate: 'qwen-image-2.1', comfyDiff: '', comfyTe: '', comfyVae: '', comfySampler: 'euler', comfyScheduler: 'simple',
  workflow: 't2va', frames: 124, offload: 'auto',
  idea: '', prompt: '', negative: 'blurry, lowres, jpeg artifacts, deformed, bad anatomy, watermark, text, logo, signature',
  width: 768, height: 1152, steps: 35, cfg: 5, seed: '-1',
  count: 1, useRef: false, chain: false, loras: [], gpu: 'A100',
}

interface Store {
  booted: boolean; bootError: string
  cfg: Config | null; status: Status | null; storage: Storage | null
  rounds: Round[]; roundsRev: number
  logSeq: number; logs: string[]
  workspace: Workspace
  draft: Draft
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
  applyPreset: (p: StudioPreset) => void
  loadWf: () => Promise<void>
  openRun: (id: string) => Promise<void>
  setWfRun: (r: WfRun | null) => void
}

let toastSeq = 1
let saveTimer = 0

export const useStore = create<Store>((set, get) => ({
  booted: false, bootError: '',
  cfg: null, status: null, storage: null,
  rounds: [], roundsRev: -1,
  logSeq: 0, logs: [],
  workspace: 'image',
  draft: { ...EMPTY_DRAFT, ...lsGet<Partial<Draft>>('cs.draft', {}) },
  sheet: null, sheetArgs: {},
  viewing: null,
  galleryFilter: { kind: '', starred: false, q: '' },
  selected: [], selecting: false,
  promptHist: lsGet<string[]>('cs.phist', []),
  toasts: [],
  theme: lsGet<Store['theme']>('cs.theme', 'system'),
  wfData: null, wfRun: null,
  llm: null,
  // 作品库默认收起，和旧版一致；展开状态按浏览器记住
  libraryOpen: lsGet<boolean>('cs.libopen', false),
  loadLlm: async () => { try { set({ llm: await api.llm.get() }) } catch { /* 设置页会提示 */ } },
  setLibraryOpen: v => { lsSet('cs.libopen', v); set({ libraryOpen: v }) },
  grabPool: lsGet<string[]>('cs.grab', ['A100', 'H100']),
  pollRounds: lsGet<number>('cs.rounds', 2),
  pollAllProxies: lsGet<boolean>('cs.pollpx', false),

  boot: async () => {
    try {
      const cfg = await api.config()
      set({ cfg, booted: true })
      await get().refresh()
      get().loadRounds()
      get().loadLlm()
      api.storage().then(storage => set({ storage })).catch(() => {})
      const loop = () => {
        window.setTimeout(async () => { await get().refresh(); loop() }, document.hidden ? 10000 : busy() ? 1300 : 5000)
      }
      loop()
    } catch (e) {
      set({ bootError: e instanceof ApiError ? e.message : '无法连接服务' })
    }
  },
  refresh: async () => {
    try {
      const st = await api.status(get().logSeq)
      setClockSkew(st.server_time)
      const logs = st.logs.length ? [...get().logs, ...st.logs].slice(-600) : get().logs
      const patch: Partial<Store> = { status: st, logs, logSeq: st.log_seq }
      if (st.gallery_rev !== get().roundsRev && get().booted) get().loadRounds()
      set(patch)
      if (st.phase === 'error' && st.error && get().toasts.every(t => t.text !== st.error)) get().toast(st.error, 'err')
    } catch (e) {
      if (e instanceof ApiError && e.status !== 401) { /* 断线时顶栏会显示状态 */ }
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
    set({ draft })
    clearTimeout(saveTimer); saveTimer = window.setTimeout(() => lsSet('cs.draft', draft), 300)
  },
  openSheet: (s, args = {}) => set({ sheet: s, sheetArgs: args }),
  closeSheet: () => set({ sheet: null, sheetArgs: {} }),
  toast: (text, kind = '', undo) => {
    const id = toastSeq++
    set({ toasts: [...get().toasts, { id, text, kind, undo }].slice(-4) })
    setTimeout(() => get().dismissToast(id), undo ? 6000 : 3200)
  },
  dismissToast: id => set({ toasts: get().toasts.filter(t => t.id !== id) }),
  setTheme: t => { lsSet('cs.theme', t); set({ theme: t }); applyTheme(t) },
  setViewing: id => set({ viewing: id }),
  toggleSelect: id => {
    const s = new Set(get().selected)
    if (s.has(id)) s.delete(id); else s.add(id)
    set({ selected: [...s] })
  },
  generate: async () => {
    const { draft, status, cfg, toast, promptHist } = get()
    const v = get().workspace === 'video'
    const refs = status?.references
    if (status?.phase === 'starting' && !status.current) { toast('正在抢卡，等算力就绪后再生成', 'err'); return }
    if (status?.colab.authed && !status.colab.sessions.length) { toast('还没有持有的算力，先去设置里抢卡', 'err'); get().openSheet('settings'); return }
    if (!draft.prompt.trim()) { toast('先写提示词', 'err'); return }
    if (!v && draft.engine === 'comfyui' && (!draft.comfyDiff || !draft.comfyTe || !draft.comfyVae)) { toast('ComfyUI 需要填齐扩散模型、文本编码器和 VAE 三个链接', 'err'); return }
    if ((v ? draft.workflow !== 't2va' : draft.useRef && !draft.chain) && !(refs?.first.set)) { toast('这个设置需要参考图，先上传或从作品库选一张', 'err'); return }
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
      p.has_image = draft.workflow !== 't2va'; p.has_last_image = draft.workflow === 'fl2va' && !!refs?.last.set
    } else {
      p.engine = draft.engine; p.chain = draft.chain; p.has_image = draft.useRef && !draft.chain
      if (draft.engine === 'comfyui') p.comfy = { template: draft.comfyTemplate, diffusion: draft.comfyDiff.trim(), text_encoder: draft.comfyTe.trim(), vae: draft.comfyVae.trim(), sampler: draft.comfySampler, scheduler: draft.comfyScheduler }
      else { p.model = draft.model.trim(); p.custom_transformer_repo = draft.ggufRepo.trim(); p.custom_transformer_file = draft.ggufFile.trim() }
    }
    try {
      const r = await api.generate(p)
      const hist = [p.prompt, ...promptHist.filter(h => h !== p.prompt)].slice(0, 15)
      lsSet('cs.phist', hist); set({ promptHist: hist, viewing: null })
      toast(r.jobs.length > 1 ? `已加入队列，${r.jobs.length} 个任务` : '已提交', 'ok')
      if (cfg) { /* 触达 */ }
      get().refresh()
    } catch (e) { toast(e instanceof Error ? e.message : '提交失败', 'err') }
  },
  applyPreset: p => {
    const d: Partial<Draft> = { width: p.width, height: p.height, steps: p.steps, cfg: p.cfg, gpu: p.gpu || get().draft.gpu }
    if (p.loras) d.loras = p.loras
    if (p.mode === 'video') { d.workflow = p.workflow || 't2va'; d.frames = p.num_frames || 124; d.offload = p.offload_mode || 'auto'; set({ workspace: 'video' }) }
    else { d.model = p.model || get().draft.model; d.engine = 'diffusers'; set({ workspace: 'image' }) }
    get().patchDraft(d); get().toast(`已套用「${p.name}」`, 'ok')
  },
  loadWf: async () => {
    try {
      const wfData = await api.wf.list()
      set({ wfData })
      if (!get().wfRun && wfData.runs.length) await get().openRun(wfData.runs[0].id)
    } catch (e) { get().toast(e instanceof Error ? e.message : '加载工作流失败', 'err') }
  },
  openRun: async id => {
    try { const r = await api.wf.run(id); set({ wfRun: r.run }) } catch (e) { get().toast(e instanceof Error ? e.message : '打开失败', 'err') }
  },
  setWfRun: r => set({ wfRun: r }),
}))

function busy() {
  const st = useStore.getState().status
  return !!(st && (st.current || st.queue.length || st.phase === 'stopping' || st.phase === 'starting' || st.workflow_active?.status === 'running'))
}

export function applyTheme(t: Store['theme']) {
  const dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = t === 'system' ? '' : t
  if (t === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.dataset.theme = dark && t === 'dark' ? 'dark' : t
}

export const selectRefs = (s: Store): References | null => s.status?.references || null
export const serverNow = now
