import type { components } from './schema'

type Wire = components['schemas']
export type AssetUpload = Wire['AssetUpload']

// 与 docs/API.md 及 draw_studio 的生成、工作流、作品库接口 的返回结构一一对应。
// 后端适配时只需保证字段一致，组件层不直接接触 fetch。

export type Mode = 'image' | 'video'
export type Engine = 'diffusers' | 'comfyui'
export type VideoWorkflow = 't2va' | 'fl2va' | 'ref2va'
export type OffloadMode = 'auto' | 'component' | 'group' | 'none'
export type Phase = 'idle' | 'starting' | 'ready' | 'generating' | 'stopping' | 'error'
export type JobStatus = 'queued' | 'running' | 'done' | 'error' | 'canceled'
export type JobStage = 'queued' | 'provisioning' | 'uploading' | 'generating' | 'downloading' | 'done'

export interface GpuInfo { id: string; label: string; hint: string; vram?: number }
export interface ModelInfo { id: string; label: string; hint: string }
export interface VideoWorkflowInfo { id: VideoWorkflow; label: string; needs: string[] }
export interface OffloadInfo { id: OffloadMode; label: string; hint: string }

export interface ComfyTemplate {
  id: string; label: string; clip_type: string
  defaults: { diffusion: string; text_encoder: string; vae: string; sampler: string; scheduler: string; steps: number; cfg: number; width: number; height: number }
}
export interface Lora { repo_id: string; weight_name: string; scale: number }
export interface ComfyPreset {
  id: string; name: string; builtin?: boolean; template: string
  diffusion: string; text_encoder: string; vae: string; sampler: string; scheduler: string
  steps: number; cfg: number; width: number; height: number; loras: Lora[]
}
export interface StudioPreset {
  id: string; name: string; builtin?: boolean; mode: Mode; gpu?: string
  width: number; height: number; steps: number; cfg: number; loras?: Lora[]
  engine?: Engine; comfy?: GeneratePayload['comfy']; model?: string; workflow?: VideoWorkflow; num_frames?: number; offload_mode?: OffloadMode; auto_offload?: boolean
}

export interface Limits {
  size_min: number; size_max: number; size_step: number
  steps_min: number; steps_max: number; cfg_min: number; cfg_max: number
  frames_min: number; frames_max: number; count_max: number
  loras_max: number; lora_scale_max: number; refs_max: number
  idle_minutes_min: number; idle_minutes_max: number
  poll_rounds_min: number; poll_rounds_max: number
  prompt_max: number; negative_max: number; upload_max_mb: number; queue_max: number
}

export interface StepCatalogItem { type: StepType; label: string; icon: string; category: string; hint: string; default_config: Record<string, unknown> }

export interface Config {
  version: string
  gpus: GpuInfo[]
  image_models: ModelInfo[]
  recent_models: string[]
  video_workflows: VideoWorkflowInfo[]
  video_offload_modes: OffloadInfo[]
  comfy: { templates: ComfyTemplate[]; samplers: string[]; schedulers: string[]; clip_types: string[]; builtin_presets: ComfyPreset[]; presets: ComfyPreset[] }
  studio_presets: { builtin: StudioPreset[]; custom: StudioPreset[] }
  limits: Limits
  defaults: {
    image: { width: number; height: number; steps: number; cfg: number; model: string }
    video: { width: number; height: number; steps: number; cfg: number; num_frames: number; workflow: VideoWorkflow; offload_mode: OffloadMode }
    gpu: string; idle_minutes: number
  }
  trash_retention_days: number
  workflow_step_catalog?: StepCatalogItem[]
}

export interface Progress { label: string; pct: number | null; detail: string; rate: string }
export interface Job {
  id: string; status: JobStatus; mode: Mode; model: string; workflow: VideoWorkflow | null; gpu: string
  width: number; height: number; steps: number; seed: number; prompt: string
  created_at: number; started_at: number | null; finished_at: number | null
  stage: JobStage; progress: Progress | null; round_id: string | null; error: string
}

export interface ColabSession { name: string; gpu: string; shape: string; endpoint: string }
export interface GpuHealth { status: 'ok' | 'unavailable' | 'error'; at: number; code?: number }
export interface ColabStatus {
  authed: boolean; ok: boolean; email: string; balance: number | null; rate_per_hour: number | null
  sessions: ColabSession[]; any_running: boolean; eligible_gpus: string[]; eligible_tpus: string[]
  gpu_health: Record<string, GpuHealth>; hf_token_set: boolean; refreshing: boolean; error: string
}
export type ProxyProfile = Wire['ProxyInfo']
export type ProxyProfileBody = Wire['ProfileInput']
export type ProxyTest = Wire['ProxyTest']
export type ProxyState = Wire['ProxyState']

export interface RefItem { id: string; bytes: number; source: string; updated_at: number }
export interface RefSlot { set: boolean; bytes: number; source: string; updated_at: number }
export interface References { first: RefSlot; last: RefSlot; items: RefItem[]; max: number }

export interface WorkflowActive {
  id: string; workflow_id: string; workflow_name: string; topic: string; status: RunStatus
  current_step_id: string | null; done_steps: number; total_steps: number; final_round_id: string | null
  created_at: number; updated_at: number; error: string
}

export interface Status {
  phase: Phase; error: string; active_gpu: string; idle_minutes: number; idle_deadline: number | null
  current: Job | null; queue: Job[]; history: Job[]
  logs: string[]; log_seq: number; gallery_rev: number; latest: Round | null
  references: References; recent_models: string[]; comfy_presets: ComfyPreset[]; studio_presets: StudioPreset[]
  workflow_active: WorkflowActive | null; proxy: ProxyState; colab: ColabStatus; server_time: number
}

export interface Round {
  id: string; kind: Mode; prompt: string; model: string; created_at: number; bytes: number
  starred: boolean; has_thumb: boolean; mtime: number
  negative?: string; workflow?: string | null; gpu?: string; width?: number; height?: number
  steps?: number; cfg?: number; seed?: number; num_frames?: number | null; loras?: Lora[]
  has_image?: boolean; chain?: boolean; duration_s?: number; job_id?: string; idea?: string
  engine?: Engine; comfy?: Record<string, unknown>; offload_mode?: OffloadMode
  deleted_at?: number; purge_at?: number
}
export interface RoundsStats { count: number; images: number; videos: number; starred: number; bytes: number }
export interface RoundsResponse { rounds: Round[]; total: number; rev: number; stats: RoundsStats }
export interface Storage {
  rounds: RoundsStats; trash: { count: number; bytes: number; retention_days: number }
  total_bytes: number; disk_free_bytes: number; disk_total_bytes: number
}
export interface TrashResponse { items: Round[]; count: number; bytes: number; retention_days: number; now: number }
export interface CleanupBody {
  older_than_days?: number | null; keep_latest?: number | null; max_mb?: number | null
  kind?: '' | Mode; include_starred?: boolean; dry_run?: boolean; permanent?: boolean
}
export interface CleanupResult { matched: string[]; count: number; bytes: number; deleted?: string[] }

export interface GeneratePayload {
  mode: Mode; prompt: string; negative: string; idea?: string
  gpu: string; gpu_pool: string[]; poll_rounds: number; poll_all_proxies: boolean
  width: number; height: number; steps: number; cfg: number; seed: number; count: number; loras: Lora[]
  has_image: boolean
  engine?: Engine; model?: string; chain?: boolean
  comfy?: { template: string; diffusion: string; text_encoder: string; vae: string; sampler: string; scheduler: string }
  custom_transformer_repo?: string; custom_transformer_file?: string
  workflow?: VideoWorkflow; num_frames?: number; offload_mode?: OffloadMode; auto_offload?: boolean; has_last_image?: boolean
}
export type RewriteBody = Wire['Rewrite']
export type RewriteResult = Wire['RewriteResult']
export type ProbeResult = Wire['ProbeResult']
export type SessionResult = Wire['Ok']
export interface LinkSpec { source: string; repo_id: string; filename: string; revision: string; url: string; basename: string; ext: string; format: string }

export type LlmProvider = Wire['ProviderInfo']
export type LlmKind = LlmProvider['kind']
export type LlmState = Wire['LlmState']
export type LlmProviderBody = Wire['ProviderInput']

// ── Workflow Studio ──
export type StepType = 'asset_input' | 'llm_script' | 'web_asset_fetch' | 'image_gen' | 'h3_prompt' | 'video_gen' | 'video_stitch'
export type RunStatus = 'draft' | 'running' | 'paused' | 'done' | 'error' | 'canceled'
export type StepStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped' | 'canceled'
export interface WfStep { id: string; type: StepType; name: string; enabled: boolean; pause_after: boolean; config: Record<string, any> }
export interface WfDef { id: string; builtin?: boolean; name: string; description: string; default_topic?: string; steps: WfStep[] }
export interface StepState { status: StepStatus; started_at: number | null; finished_at: number | null; progress: string; output: Record<string, any>; error: string }
export interface WfRun {
  id: string; topic: string; workflow: WfDef; status: RunStatus; current_step_id: string | null
  pause_reason: string; error: string; step_states: Record<string, StepState>; logs: string[]
  created_at: number; updated_at: number; assets: { filename: string; bytes: number }[]
}
export interface WorkflowsResponse { builtin: WfDef[]; custom: WfDef[]; runs: WorkflowActive[]; step_catalog: StepCatalogItem[]; ffmpeg_available: boolean }
