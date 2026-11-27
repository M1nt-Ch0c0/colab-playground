// 假后端：实现 docs/API.md 的全部行为，让前端在没有 Python 服务的情况下完整可验收。
// 生成任务按真实阶段推进（排队 → 拉起实例 → 上传 → 生成 → 回传），工作流逐步执行并产出示例图。
import { makeArt } from './art'
import type {
  ColabStatus, ComfyPreset, Config, GeneratePayload, Job, Lora, ProxyState, ProxyTest, References, RewriteBody,
  Round, RoundsStats, Status, StepCatalogItem, StudioPreset, WfDef, WfRun, WfStep, WorkflowActive,
  LlmKind, LlmProvider, LlmProviderBody, LlmState,
} from '../api/types'

const sec = () => Math.floor(Date.now() / 1000)
const uid = (p: string) => p + Math.floor(Math.random() * 9000 + 1000).toString(36)

const GPUS = [
  { id: 'A100', label: 'A100', hint: '推荐，生图/视频主力' },
  { id: 'H100', label: 'H100', hint: '高算力，适合 FLUX.2 / 视频' },
  { id: 'G4', label: 'G4 · RTX PRO 6000', hint: '大显存新卡，适合视频' },
  { id: 'L4', label: 'L4', hint: '适合 Q5 量化生图' },
  { id: 'T4', label: 'T4', hint: '仅轻量测试' },
]
const MODELS = [
  { id: 'qwen-2.1-bf16', label: 'Qwen-Image-2.1 · BF16', hint: '满血约 33GB，支持参考图改图' },
  { id: 'qwen-2.1-q5', label: 'Qwen-Image-2.1 · Q5 GGUF', hint: '约 23GB，L4 可跑，可换自定义 GGUF' },
  { id: 'flux2-dev', label: 'FLUX.2 [dev] · 32B', hint: '约 70GB，建议 H100 / G4' },
]
const VIDEO_WF = [
  { id: 't2va' as const, label: '文生视频 + 音频', needs: [] as string[] },
  { id: 'fl2va' as const, label: '首帧 / 首尾帧生视频 + 音频', needs: ['first'] },
  { id: 'ref2va' as const, label: '参考图生视频 + 音频', needs: ['first'] },
]
const SAMPLERS = ['euler', 'er_sde', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_2m_sde', 'dpmpp_3m_sde', 'uni_pc', 'heun', 'res_multistep']
const SCHEDULERS = ['simple', 'normal', 'karras', 'exponential', 'sgm_uniform', 'beta', 'ddim_uniform']

const OMNI = 'https://huggingface.co/chatrlabs/Qwen-Image-2.1-Uncensored-Omni-Quantized/blob/main/qwen-image-2.1-step90000-BF16/diffusion_pytorch_model.safetensors'
const QWEN_TE = 'https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_bf16.safetensors'
const QWEN_VAE = 'https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors'

const STEP_CATALOG: StepCatalogItem[] = [
  { type: 'asset_input', label: '视觉资产输入', icon: '🎭', category: '输入', hint: '绑定人设图、风格参考图或画廊历史作品，供后续步骤按需引用', default_config: { role: 'character', asset_files: [], round_ids: [], note: '上传角色人设图或从画廊挑选参考图' } },
  { type: 'llm_script', label: 'AI 脚本与分镜', icon: '📝', category: '规划', hint: '调用大模型撰写结构化分镜脚本', default_config: { scene_count: 3, output_format: 'storyboard', instruction: '请根据主题「{{topic}}」拆解为 {{scene_count}} 个连贯镜头。' } },
  { type: 'web_asset_fetch', label: '网页 Agent 找图', icon: '🌐', category: '检索', hint: '访问目标网页或公开图库检索参考图并下载', default_config: { url: '', search_query: '{{topic}}', scenes_from: '', instruction: '优先选择轮廓清晰、构图干净的参考图', max_images: 2 } },
  { type: 'image_gen', label: '关键帧融合生图', icon: '🎨', category: '生图', hint: '把参考图送入生图模型，按分镜批量生成关键帧', default_config: { scenes_from: 'script', ref_sources: [], prompt_template: '{{scene.keyframe_prompt}}', model: 'qwen-2.1-bf16', gpu: 'A100', gpu_pool: ['A100', 'H100'], poll_rounds: 2, poll_all_proxies: false, width: 1280, height: 768, steps: 35, cfg: 5.0, max_scenes: 6 } },
  { type: 'h3_prompt', label: 'H3 多模态写视频词', icon: '✨', category: '提示词', hint: '看图把每个关键帧改写为音画同步视频提示词', default_config: { scenes_from: 'script', keyframe_from: 'keyframes', workflow: 'fl2va', num_frames: 124, instruction: '保持画面风格与角色外观一致，加入自然镜头运动与环境音。' } },
  { type: 'video_gen', label: '逐镜生成视频+音频', icon: '🎬', category: '视频', hint: '将每镜关键帧与提示词送入 MiniMax-H3 逐段生成', default_config: { scenes_from: 'script', keyframe_from: 'keyframes', prompts_from: 'h3_prompts', workflow: 'fl2va', gpu: 'H100', gpu_pool: ['H100', 'G4', 'A100'], poll_rounds: 2, poll_all_proxies: false, width: 1280, height: 768, num_frames: 124, steps: 30, cfg: 5.0, auto_offload: true } },
  { type: 'video_stitch', label: 'FFmpeg 剪辑合成', icon: '🎞️', category: '成片', hint: '统一分辨率与音轨，把全部片段合成为长视频', default_config: { clips_from: 'clips', clip_round_ids: [], transition: 'fade', fade_s: 0.35, target_width: 1280, target_height: 768, fps: 24 } },
]
const defCfg = (t: string) => STEP_CATALOG.find(s => s.type === t)!.default_config

function step(id: string, type: WfStep['type'], name: string, pause: boolean, cfg: Record<string, unknown> = {}): WfStep {
  return { id, type, name, enabled: true, pause_after: pause, config: { ...defCfg(type), ...cfg } }
}

const BUILTIN_WF: WfDef[] = [
  {
    id: 'builtin:agent-long-video', builtin: true, name: '长视频 Agent 流水线',
    description: '人设资产 → AI 分镜 → 网页找白模 → 融合生关键帧 → H3 提示词 → 逐镜生视频 → FFmpeg 剪辑。',
    default_topic: '赛博雨夜街头，主角手持机械伞走过霓虹巷口并回头凝望远处飞船升空，3 镜头短片',
    steps: [
      step('character_assets', 'asset_input', '1. 角色人设图资产', false),
      step('script', 'llm_script', '2. AI 导演分镜脚本', true, { scene_count: 3 }),
      step('web_refs', 'web_asset_fetch', '3. 网页 Agent 抓白模/参考图', true, { scenes_from: 'script', max_images: 2 }),
      step('keyframes', 'image_gen', '4. 白模 + 人设融合生关键帧', true, { scenes_from: 'script', ref_sources: ['web_refs', 'character_assets'], width: 1280, height: 768 }),
      step('h3_prompts', 'h3_prompt', '5. 多模态写 MiniMax-H3 视频提示词', true, { scenes_from: 'script', keyframe_from: 'keyframes' }),
      step('clips', 'video_gen', '6. 逐镜生成音画视频片段', false, { scenes_from: 'script', keyframe_from: 'keyframes', prompts_from: 'h3_prompts' }),
      step('stitch', 'video_stitch', '7. FFmpeg 剪辑合成长视频', false, { clips_from: 'clips' }),
    ],
  },
  {
    id: 'builtin:story-short', builtin: true, name: '多镜故事短片',
    description: '人设参考 → AI 拆 3 镜 → 批量关键帧 → H3 提示词 → 逐镜生视频 → 拼接成片。',
    default_topic: '山间清晨，旅人推开木屋门，雾气散去时看见远处的湖面，3 镜头',
    steps: [
      step('refs', 'asset_input', '1. 人设 / 风格参考图', false),
      step('script', 'llm_script', '2. AI 拆解 3 镜分镜', true, { scene_count: 3 }),
      step('keyframes', 'image_gen', '3. 批量生成镜头关键帧', true, { scenes_from: 'script', ref_sources: ['refs'] }),
      step('h3_prompts', 'h3_prompt', '4. 生成 H3 视频提示词', false, { scenes_from: 'script', keyframe_from: 'keyframes' }),
      step('clips', 'video_gen', '5. 逐镜生视频', false, { scenes_from: 'script', keyframe_from: 'keyframes', prompts_from: 'h3_prompts' }),
      step('stitch', 'video_stitch', '6. FFmpeg 拼接成片', false, { clips_from: 'clips' }),
    ],
  },
  {
    id: 'builtin:lookbook', builtin: true, name: '角色多景别设定集',
    description: '基础人设 → 网页找姿态参考 → AI 规划 4 组景别 → 批量定妆照。',
    default_topic: '银发剑客，四组景别：全身、半身、侧面特写、背影',
    steps: [
      step('base', 'asset_input', '1. 基础人设图', false),
      step('poses', 'web_asset_fetch', '2. 网页找姿态/白模参考', true, { max_images: 4 }),
      step('plan', 'llm_script', '3. AI 规划 4 组景别变体', true, { scene_count: 4 }),
      step('shots', 'image_gen', '4. 批量生成定妆照', false, { scenes_from: 'plan', ref_sources: ['base', 'poses'], width: 1024, height: 1536 }),
    ],
  },
]

const STUDIO_BUILTIN: StudioPreset[] = [
  { id: 'builtin:img-portrait-qwen', builtin: true, name: '写实人像 2:3 · Qwen BF16', mode: 'image', gpu: 'A100', width: 768, height: 1152, steps: 35, cfg: 5, model: 'qwen-2.1-bf16' },
  { id: 'builtin:img-cinematic-169', builtin: true, name: '电影分镜 16:9 · 关键帧', mode: 'image', gpu: 'A100', width: 1344, height: 768, steps: 35, cfg: 5, model: 'qwen-2.1-bf16' },
  { id: 'builtin:img-hd-portrait', builtin: true, name: '高清精绘 2:3 · 1024×1536', mode: 'image', gpu: 'H100', width: 1024, height: 1536, steps: 40, cfg: 5, model: 'qwen-2.1-bf16' },
  { id: 'builtin:img-flux2-square', builtin: true, name: 'FLUX.2 [dev] · 1:1 精绘', mode: 'image', gpu: 'H100', width: 1024, height: 1024, steps: 28, cfg: 3.5, model: 'flux2-dev' },
  { id: 'builtin:vid-h3-fl2va-5s', builtin: true, name: 'H3 首帧动态 · 5.2s 电影感', mode: 'video', gpu: 'H100', width: 1280, height: 768, steps: 30, cfg: 5, workflow: 'fl2va', num_frames: 124, offload_mode: 'auto' },
  { id: 'builtin:vid-h3-ref2va-7s', builtin: true, name: 'H3 多图角色参考 · 7.5s', mode: 'video', gpu: 'H100', width: 1280, height: 768, steps: 30, cfg: 5, workflow: 'ref2va', num_frames: 175, offload_mode: 'auto' },
]
const COMFY_BUILTIN: ComfyPreset[] = [
  { id: 'builtin:omni-bf16-35', builtin: true, name: 'Omni BF16 · 35步精细', template: 'qwen-image-2.1', diffusion: OMNI, text_encoder: QWEN_TE, vae: QWEN_VAE, loras: [], sampler: 'euler', scheduler: 'simple', steps: 35, cfg: 5, width: 1024, height: 1536 },
  { id: 'builtin:omni-turbo-8', builtin: true, name: 'Omni · 8步 Turbo', template: 'qwen-image-2.1', diffusion: OMNI, text_encoder: QWEN_TE, vae: QWEN_VAE, loras: [], sampler: 'euler', scheduler: 'simple', steps: 8, cfg: 1, width: 1024, height: 1536 },
]

const SEED_ROUNDS: { id: string; kind: 'image' | 'video'; prompt: string; model: string; w: number; h: number; daysAgo: number; starred: boolean; seed: number; wf?: string; frames?: number; dur?: number }[] = [
  { id: '018', kind: 'image', prompt: '雨夜霓虹街头，撑透明雨伞的人回头微笑，湿润的柏油路面倒映招牌，电影感宽银幕构图，细腻胶片颗粒', model: 'qwen-2.1-bf16', w: 1344, h: 768, daysAgo: 0.02, starred: true, seed: 4821933 },
  { id: '017', kind: 'image', prompt: '银发剑客立于雪原，半身像，冷色侧光，风吹起衣摆，写实人像质感', model: 'qwen-2.1-bf16', w: 768, h: 1152, daysAgo: 0.2, starred: false, seed: 2201847 },
  { id: '016', kind: 'video', prompt: '镜头缓缓推进，雨伞上的水珠滑落，远处飞船的光穿过雾气，环境音：雨声与远处引擎低频', model: 'MiniMax-H3', w: 1280, h: 768, daysAgo: 0.4, starred: true, seed: 7731204, wf: 'fl2va', frames: 124, dur: 5.2 },
  { id: '015', kind: 'image', prompt: '山间木屋清晨，门半开，雾气贴着湖面，暖色窗光与冷色雾气对撞', model: 'flux2-dev', w: 1152, h: 768, daysAgo: 1.1, starred: false, seed: 991230 },
  { id: '014', kind: 'image', prompt: '机械花在废弃工厂里盛开，锈蚀金属与透明花瓣，微距特写', model: 'qwen-2.1-q5', w: 1024, h: 1024, daysAgo: 1.4, starred: false, seed: 551902 },
  { id: '013', kind: 'image', prompt: '图书馆顶层，斜阳穿过高窗落在翻开的书页上，尘埃可见', model: 'qwen-2.1-bf16', w: 896, h: 1152, daysAgo: 2.3, starred: true, seed: 1288004 },
  { id: '012', kind: 'video', prompt: '旅人推开木屋门，雾气散开露出湖面，鸟鸣与木门吱呀声', model: 'MiniMax-H3', w: 1280, h: 768, daysAgo: 3.2, starred: false, seed: 664210, wf: 't2va', frames: 175, dur: 7.3 },
  { id: '011', kind: 'image', prompt: '深夜便利店，冷白灯管，玻璃门上的雨痕，一个人站在货架尽头', model: 'qwen-2.1-bf16', w: 768, h: 1344, daysAgo: 5, starred: false, seed: 330192 },
  { id: '010', kind: 'image', prompt: '陶罐与干花静物，柔光棚拍，浅景深，暖灰背景', model: 'flux2-dev', w: 1024, h: 1024, daysAgo: 8, starred: false, seed: 77261 },
  { id: '009', kind: 'image', prompt: '旧港栈桥，黄昏，渔船剪影，海面一条金色反光', model: 'qwen-2.1-bf16', w: 1536, h: 1024, daysAgo: 12, starred: false, seed: 441290 },
]

interface RefRec { id: string; bytes: number; source: string; updated_at: number; url: string }
interface State {
  phase: Status['phase']; error: string; activeGpu: string; idleMinutes: number; idleDeadline: number | null
  current: Job | null; queue: Job[]; history: Job[]
  rounds: Round[]; trash: Round[]; rev: number; nextId: number
  refs: RefRec[]; last: RefRec | null
  recentModels: string[]; comfyPresets: ComfyPreset[]; studioPresets: StudioPreset[]
  colab: ColabStatus; proxy: ProxyState
  wfCustom: WfDef[]; runs: WfRun[]
  llm: LlmState
  logs: { seq: number; line: string }[]; seq: number
  urls: Record<string, string>
}
const S: State = {
  phase: 'ready', error: '', activeGpu: 'A100 (HIGH_RAM)', idleMinutes: 10, idleDeadline: null,
  current: null, queue: [], history: [],
  rounds: [], trash: [], rev: 1, nextId: 19,
  refs: [], last: null,
  recentModels: ['qwen-2.1-bf16', 'flux2-dev'], comfyPresets: [], studioPresets: [],
  colab: {
    authed: true, ok: true, email: 'studio@example.com', balance: 128.4, rate_per_hour: 3.2,
    sessions: [{ name: 'colab-a100-7f', gpu: 'A100', shape: 'HIGH_RAM', endpoint: 'https://colab.example/a100' }],
    any_running: true, eligible_gpus: ['A100', 'H100', 'G4', 'L4', 'T4'], eligible_tpus: [],
    gpu_health: { A100: { status: 'ok', at: sec() - 240 }, H100: { status: 'unavailable', at: sec() - 900, code: 503 } },
    hf_token_set: true, refreshing: false, error: '',
  },
  proxy: {
    active: 'primary',
    profiles: [
      { id: 'primary', label: '主线路', hint: '', configured: true, masked: 'http://proxy.example:8080' },
      { id: 'backup', label: '备用线路', hint: '', configured: true, masked: 'socks5://backup.example:1080' },
    ],
    last_test: null,
  },
  wfCustom: [], runs: [], logs: [], seq: 0, urls: {},
  llm: {
    providers: [{ id: 'llm_local', kind: 'openai', name: '本地网关', base_url: 'https://models.example/v1', enhanced_rewrite: false, legacy_template: false, key_set: true, key_masked: 'sk-…7f2a', models: ['demo-text', 'gemini-2.5-flash', 'gpt-5.4-mini'], models_fetched_at: sec() - 3600 }],
    active: { provider_id: 'llm_local', model: 'demo-text' },
  },
}

// 各类型服务商在 mock 里「拉取」到的模型列表
const LLM_MODELS: Record<LlmKind, string[]> = {
  openai: ['gpt-5.4', 'gpt-5.4-mini', 'demo-text'],
  anthropic: ['claude-opus-4-8', 'claude-sonnet-4-8', 'claude-haiku-4-5'],
  gemini: ['gemini-3.1-pro', 'gemini-3-flash'],
}
const maskKey = (k: string) => (k.length > 8 ? `${k.slice(0, 3)}…${k.slice(-4)}` : '已设置')

function log(msg: string) {
  S.seq++
  S.logs.push({ seq: S.seq, line: new Date().toLocaleTimeString('zh-CN', { hour12: false }) + '  ' + msg })
  if (S.logs.length > 600) S.logs.splice(0, S.logs.length - 600)
}
function newId(): string { const id = String(S.nextId++).padStart(3, '0'); return id }
function stats(): RoundsStats {
  return {
    count: S.rounds.length,
    images: S.rounds.filter(r => r.kind === 'image').length,
    videos: S.rounds.filter(r => r.kind === 'video').length,
    starred: S.rounds.filter(r => r.starred).length,
    bytes: S.rounds.reduce((a, r) => a + r.bytes, 0),
  }
}
function refsReport(): References {
  const item = (r: RefRec) => ({ id: r.id, bytes: r.bytes, source: r.source, updated_at: r.updated_at })
  const first = S.refs[0]
  return {
    first: first ? { set: true, bytes: first.bytes, source: first.source, updated_at: first.updated_at } : { set: false, bytes: 0, source: '', updated_at: 0 },
    last: S.last ? { set: true, bytes: S.last.bytes, source: S.last.source, updated_at: S.last.updated_at } : { set: false, bytes: 0, source: '', updated_at: 0 },
    items: S.refs.map(item), max: 6,
  }
}
function repairSelection(st: LlmState) {
  if (st.providers.some(p => p.key_set && p.id === st.active?.provider_id && p.models.includes(st.active.model))) return
  const first = st.providers.find(p => p.key_set && p.models.length)
  st.active = first ? { provider_id: first.id, model: first.models[0] } : null
}

function runSummary(r: WfRun): WorkflowActive {
  const steps = r.workflow.steps
  const done = steps.filter(s => r.step_states[s.id]?.status === 'done' || r.step_states[s.id]?.status === 'skipped').length
  let finalRid: string | null = null
  for (const s of [...steps].reverse()) { const o = r.step_states[s.id]?.output; if (o?.final_round_id) { finalRid = o.final_round_id; break } }
  return {
    id: r.id, workflow_id: r.workflow.id, workflow_name: r.workflow.name, topic: r.topic.slice(0, 120), status: r.status,
    current_step_id: r.current_step_id, done_steps: done, total_steps: steps.length, final_round_id: finalRid,
    created_at: r.created_at, updated_at: r.updated_at, error: r.error,
  }
}
function publicJob(j: Job): Job { return { ...j, prompt: j.prompt.slice(0, 160) } }

function status(since: number): Status {
  const active = S.runs.find(r => r.status === 'running') || S.runs.filter(r => r.status === 'paused').sort((a, b) => b.updated_at - a.updated_at)[0]
  return {
    phase: S.phase, error: S.error, active_gpu: S.activeGpu, idle_minutes: S.idleMinutes,
    idle_deadline: S.idleDeadline,
    current: S.current ? publicJob(S.current) : null,
    queue: S.queue.map(publicJob), history: S.history.slice(0, 10).map(publicJob),
    logs: S.logs.filter(l => l.seq > since).map(l => l.line), log_seq: S.seq,
    gallery_rev: S.rev, latest: S.rounds[0] || null,
    references: refsReport(), recent_models: S.recentModels, comfy_presets: S.comfyPresets, studio_presets: S.studioPresets,
    workflow_active: active ? runSummary(active) : null,
    proxy: S.proxy, colab: S.colab, server_time: sec(),
  }
}

function config(): Config {
  return {
    version: '4.0-mock', gpus: GPUS, image_models: MODELS, recent_models: S.recentModels,
    video_workflows: VIDEO_WF,
    video_offload_modes: [
      { id: 'auto', label: '自动', hint: '按显存自动选择组件级或逐层卸载' },
      { id: 'component', label: '组件级', hint: '适合 H100 / G4' },
      { id: 'group', label: '逐层', hint: '无损 BF16，适配 A100 / L4' },
      { id: 'none', label: '关闭', hint: '全常驻显存' },
    ],
    comfy: {
      templates: [
        { id: 'qwen-image-2.1', label: 'Qwen-Image 2.1（文生图 / 修图）', clip_type: 'qwen_image', defaults: { diffusion: OMNI, text_encoder: QWEN_TE, vae: QWEN_VAE, sampler: 'euler', scheduler: 'simple', steps: 35, cfg: 5, width: 1024, height: 1536 } },
        { id: 'flux', label: 'FLUX（单文本编码器 + UNET + VAE）', clip_type: 'flux', defaults: { diffusion: '', text_encoder: '', vae: '', sampler: 'euler', scheduler: 'simple', steps: 28, cfg: 3.5, width: 1024, height: 1024 } },
        { id: 'sd-generic', label: '通用三件套（UNET + CLIP + VAE）', clip_type: 'stable_diffusion', defaults: { diffusion: '', text_encoder: '', vae: '', sampler: 'euler', scheduler: 'normal', steps: 28, cfg: 5, width: 1024, height: 1024 } },
      ],
      samplers: SAMPLERS, schedulers: SCHEDULERS,
      clip_types: ['qwen_image', 'flux', 'flux2', 'sd3', 'stable_diffusion', 'lumina2', 'wan', 'chroma', 'hidream'],
      builtin_presets: COMFY_BUILTIN, presets: S.comfyPresets,
    },
    studio_presets: { builtin: STUDIO_BUILTIN, custom: S.studioPresets },
    workflow_step_catalog: STEP_CATALOG,
    limits: {
      size_min: 512, size_max: 1536, size_step: 64, steps_min: 2, steps_max: 60, cfg_min: 1, cfg_max: 12,
      frames_min: 120, frames_max: 360, count_max: 4, loras_max: 4, lora_scale_max: 2.5, refs_max: 6,
      idle_minutes_min: 5, idle_minutes_max: 60, poll_rounds_min: 1, poll_rounds_max: 10,
      prompt_max: 12000, negative_max: 1200, upload_max_mb: 12, queue_max: 12,
    },
    defaults: {
      image: { width: 768, height: 1152, steps: 35, cfg: 5, model: 'qwen-2.1-bf16' },
      video: { width: 1280, height: 768, steps: 30, cfg: 5, num_frames: 124, workflow: 't2va', offload_mode: 'auto' },
      gpu: 'A100', idle_minutes: 10,
    },
    trash_retention_days: 7,
  }
}

function err(status: number, error: string) { return { status, json: { error } } }
function ok(json: unknown, status = 200) { return { status, json } }

function armIdle() {
  if (S.idleMinutes <= 0 || S.current || S.queue.length) { S.idleDeadline = null; return }
  if (S.colab.any_running) S.idleDeadline = sec() + S.idleMinutes * 60
}
function bumpRev() { S.rev++ }

function addRound(partial: Partial<Round> & { prompt: string; kind: 'image' | 'video'; width: number; height: number; model: string }): Round {
  const id = newId()
  const url = makeArt({ w: partial.width, h: partial.height, seed: (partial.seed ?? +id) + 3, label: `#${+id}`, video: partial.kind === 'video' })
  S.urls[id] = url
  const r: Round = {
    id, kind: partial.kind, prompt: partial.prompt, model: partial.model, created_at: sec(), bytes: 900_000 + Math.floor(Math.random() * 2_400_000),
    starred: false, has_thumb: true, mtime: sec(), negative: partial.negative || '', workflow: partial.workflow ?? null,
    gpu: partial.gpu || 'A100', width: partial.width, height: partial.height, steps: partial.steps, cfg: partial.cfg,
    seed: partial.seed, num_frames: partial.num_frames ?? null, loras: partial.loras || [], has_image: !!partial.has_image,
    chain: !!partial.chain, duration_s: partial.duration_s, job_id: partial.job_id, idea: partial.idea, engine: partial.engine,
    comfy: partial.comfy, offload_mode: partial.offload_mode,
  }
  S.rounds.unshift(r); bumpRev(); return r
}

/* ── 生成队列 ── */
const STAGES: Job['stage'][] = ['provisioning', 'uploading', 'generating', 'downloading', 'done']
function enqueue(p: GeneratePayload) {
  if (!S.colab.authed) return err(400, '还没有连接 Google Colab，请先在设置里完成授权')
  if (!p.prompt?.trim()) return err(400, '提示词不能为空')
  if (p.prompt.length > 12000) return err(400, '提示词不超过 12000 字')
  if (S.queue.length + (S.current ? 1 : 0) + (p.count || 1) > 12) return err(409, '队列已满（最多 12 个），请等当前任务完成')
  const n = Math.max(1, Math.min(4, p.count || 1))
  const base = p.seed === -1 || p.seed == null ? Math.floor(Math.random() * 9_000_000) + 100_000 : p.seed
  const jobs: { id: string; status: string }[] = []
  for (let i = 0; i < n; i++) {
    const j: Job = {
      id: 'j' + sec().toString().slice(-5) + String(i) + Math.floor(Math.random() * 90 + 10),
      status: 'queued', mode: p.mode, model: p.model || (p.mode === 'video' ? 'MiniMax-H3' : 'qwen-2.1-bf16'),
      workflow: p.workflow || null, gpu: p.gpu, width: p.width, height: p.height, steps: p.steps, seed: base + i,
      prompt: p.prompt, created_at: sec(), started_at: null, finished_at: null, stage: 'queued', progress: null,
      round_id: null, error: '',
    }
    ;(j as Job & { _payload: GeneratePayload })._payload = { ...p, seed: base + i }
    S.queue.push(j); jobs.push({ id: j.id, status: 'queued' })
  }
  log(`已入队 ${n} 个${p.mode === 'video' ? '视频' : '生图'}任务 · ${p.width}×${p.height} · ${p.gpu}`)
  if (p.model && !S.recentModels.includes(p.model)) { S.recentModels.unshift(p.model); S.recentModels = S.recentModels.slice(0, 16) }
  else if (p.model) S.recentModels = [p.model, ...S.recentModels.filter(m => m !== p.model)]
  pump()
  return ok({ ok: true, jobs }, 202)
}

function pump() {
  if (S.current || !S.queue.length) return
  const j = S.queue.shift()!
  j.status = 'running'; j.started_at = sec(); j.stage = 'provisioning'
  S.current = j; S.phase = S.colab.any_running ? 'generating' : 'starting'; S.idleDeadline = null
  log(`开始任务 ${j.id} · ${j.gpu}`)
  advance(j, 0)
}
function advance(j: Job, i: number) {
  if (S.current?.id !== j.id) return
  const stage = STAGES[i]
  j.stage = stage
  if (stage === 'provisioning') { S.phase = 'starting'; log(`正在申请 ${j.gpu} 实例…`); setTimeout(() => advance(j, 1), 1400); return }
  if (stage === 'uploading') { S.phase = 'generating'; S.activeGpu = `${j.gpu} (HIGH_RAM)`; log('实例就绪，上传任务参数'); setTimeout(() => advance(j, 2), 900); return }
  if (stage === 'generating') {
    const total = j.steps
    let stepN = 0
    const tick = () => {
      if (S.current?.id !== j.id) return
      stepN = Math.min(total, stepN + Math.max(1, Math.round(total / 8)))
      j.progress = { label: '采样', pct: Math.round(stepN / total * 100), detail: `${stepN}/${total}`, rate: '1.6it/s' }
      log(`\r采样 ${stepN}/${total}`)
      if (stepN >= total) setTimeout(() => advance(j, 3), 500)
      else setTimeout(tick, 420)
    }
    tick(); return
  }
  if (stage === 'downloading') { j.progress = { label: '回传', pct: 96, detail: '', rate: '' }; log('回传成品'); setTimeout(() => advance(j, 4), 700); return }
  finish(j)
}
function finish(j: Job) {
  const p = (j as Job & { _payload?: GeneratePayload })._payload
  const r = addRound({
    kind: j.mode, prompt: j.prompt, model: j.model, width: j.width, height: j.height, gpu: j.gpu, steps: j.steps,
    cfg: p?.cfg, seed: j.seed, negative: p?.negative, workflow: j.workflow, num_frames: p?.num_frames,
    loras: p?.loras, has_image: p?.has_image, chain: p?.chain, idea: p?.idea, engine: p?.engine,
    comfy: p?.comfy as Record<string, unknown> | undefined, offload_mode: p?.offload_mode,
    duration_s: j.mode === 'video' ? Math.round(((p?.num_frames || 124) / 24) * 10) / 10 : undefined, job_id: j.id,
  })
  j.status = 'done'; j.stage = 'done'; j.round_id = r.id; j.finished_at = sec(); j.progress = { label: '完成', pct: 100, detail: '', rate: '' }
  S.history.unshift(j); S.current = null
  log(`任务完成 · 作品 #${+r.id}`)
  if (S.queue.length) { S.phase = 'generating'; pump() }
  else { S.phase = 'ready'; armIdle() }
}

/* ── 工作流执行 ── */
const TITLES = ['巷口回望', '雨中驻足', '飞船升空', '雾散见湖', '推门而出', '侧身特写', '远景收束', '灯下独行']
function fakeScenes(topic: string, n: number) {
  return Array.from({ length: n }, (_, i) => ({
    index: i + 1,
    title: TITLES[i % TITLES.length],
    duration_s: 5,
    search_query: `${topic.slice(0, 24)} scene ${i + 1} reference`,
    keyframe_prompt: `图1 参考构图，图2 保持角色外观。${topic.slice(0, 40)}，镜头 ${i + 1}：${['远景建立', '中景跟随', '特写情绪', '背影收束'][i % 4]}，电影感光线`,
    video_prompt: `镜头${['缓慢推进', '横向跟随', '轻微上摇', '固定后拉远'][i % 4]}，主体自然移动，环境光稳定`,
    audio_notes: ['雨声与远处低频引擎', '脚步踩过积水', '风声穿过巷口', '环境底噪渐弱'][i % 4],
  }))
}
function wfLog(r: WfRun, msg: string) { r.logs.push(new Date().toLocaleTimeString('zh-CN', { hour12: false }) + '  ' + msg); r.updated_at = sec() }

function execStep(r: WfRun, st: WfStep): Record<string, unknown> {
  const cfg = st.config
  const prev = (type: string) => r.workflow.steps.filter(s => s.type === type).map(s => r.step_states[s.id]?.output).find(Boolean)
  if (st.type === 'llm_script') {
    const n = Math.max(1, Math.min(8, +cfg.scene_count || 3))
    return { format: 'storyboard', model: S.llm.active?.model || '', title: r.topic.slice(0, 30) || '未命名短片', style_bible: '冷暖对撞的电影感光线，胶片颗粒，角色外观全程一致', scenes: fakeScenes(r.topic || '主题', n), text: '' }
  }
  if (st.type === 'web_asset_fetch') {
    const n = Math.max(1, Math.min(6, +cfg.max_images || 2))
    const images = Array.from({ length: n }, (_, i) => {
      const fn = `web_${st.id}_${i + 1}.jpg`
      S.urls[fn] = makeArt({ w: 768, h: 768, seed: 400 + i * 17, label: `参考 ${i + 1}` })
      r.assets.push({ filename: fn, bytes: 180_000 })
      return { filename: fn, title: `参考图 ${i + 1}`, source_url: cfg.url || 'https://images.example/search' }
    })
    return { source_url: cfg.url || '', search_query: cfg.search_query || r.topic, page_summary: '检索到构图清晰的参考图', images, count: images.length }
  }
  if (st.type === 'image_gen') {
    const sc = (prev('llm_script')?.scenes as { title: string; keyframe_prompt: string }[]) || [{ title: '单帧', keyframe_prompt: r.topic }]
    const items = sc.slice(0, +cfg.max_scenes || 6).map((s, i) => {
      const round = addRound({ kind: 'image', prompt: s.keyframe_prompt || r.topic, model: String(cfg.model || 'qwen-2.1-bf16'), width: +cfg.width || 1280, height: +cfg.height || 768, gpu: String(cfg.gpu || 'A100'), steps: +cfg.steps || 35, cfg: +cfg.cfg || 5, seed: 1000 + i })
      return { round_id: round.id, title: s.title, scene_index: i + 1 }
    })
    return { items, round_ids: items.map(it => it.round_id), count: items.length }
  }
  if (st.type === 'h3_prompt') {
    const sc = (prev('llm_script')?.scenes as { title: string; video_prompt: string; audio_notes: string }[]) || []
    const kf = (prev('image_gen')?.items as { round_id: string }[]) || []
    const items = (sc.length ? sc : [{ title: '镜头 1', video_prompt: r.topic, audio_notes: '' }]).map((s, i) => ({
      scene_index: i + 1, title: s.title, keyframe_round_id: kf[i]?.round_id || null,
      video_prompt: `【画面】${s.video_prompt || r.topic}\n【运镜】平稳推进，主体保持在画面三分线\n【声音】${s.audio_notes || '自然环境音'}`,
    }))
    return { workflow: cfg.workflow || 'fl2va', num_frames: cfg.num_frames || 124, items, count: items.length }
  }
  if (st.type === 'video_gen') {
    const prompts = (prev('h3_prompt')?.items as { title: string; video_prompt: string }[]) || (prev('llm_script')?.scenes as { title: string; video_prompt: string }[]) || []
    const items = (prompts.length ? prompts : [{ title: '片段 1', video_prompt: r.topic }]).map((s, i) => {
      const round = addRound({ kind: 'video', prompt: s.video_prompt || r.topic, model: 'MiniMax-H3', width: +cfg.width || 1280, height: +cfg.height || 768, gpu: String(cfg.gpu || 'H100'), steps: +cfg.steps || 30, workflow: String(cfg.workflow || 'fl2va'), num_frames: +cfg.num_frames || 124, duration_s: Math.round((+cfg.num_frames || 124) / 24 * 10) / 10 })
      return { round_id: round.id, title: s.title, scene_index: i + 1 }
    })
    return { items, round_ids: items.map(it => it.round_id), count: items.length }
  }
  if (st.type === 'video_stitch') {
    const clips = (prev('video_gen')?.items as { round_id: string }[]) || []
    const ids = [...clips.map(c => c.round_id), ...((cfg.clip_round_ids as string[]) || [])]
    const round = addRound({ kind: 'video', prompt: `[长视频工作流成片] ${r.topic || r.workflow.name}`, model: 'Workflow Studio · FFmpeg', width: +cfg.target_width || 1280, height: +cfg.target_height || 768, workflow: 'stitch', duration_s: ids.length * 5 })
    return { final_round_id: round.id, source_rounds: ids, clip_count: ids.length || 1, duration_s: (ids.length || 1) * 5, transition: cfg.transition || 'fade', width: +cfg.target_width || 1280, height: +cfg.target_height || 768 }
  }
  return {}
}

function driveRun(r: WfRun, fromId?: string, single = false) {
  const steps = r.workflow.steps.filter(s => s.enabled !== false)
  let idx = fromId ? steps.findIndex(s => s.id === fromId) : steps.findIndex(s => r.step_states[s.id]?.status !== 'done' && r.step_states[s.id]?.status !== 'skipped')
  if (idx < 0) idx = 0
  r.status = 'running'; r.error = ''; r.pause_reason = ''
  const runNext = () => {
    if (r.status === 'canceled') return
    if (idx >= steps.length) { r.status = 'done'; r.current_step_id = null; wfLog(r, '工作流执行完成'); log(`工作流「${r.workflow.name}」完成`); return }
    const st = steps[idx]
    r.current_step_id = st.id
    const ss = r.step_states[st.id]
    ss.status = 'running'; ss.started_at = sec(); ss.error = ''; ss.progress = '执行中'
    wfLog(r, `开始步骤「${st.name}」`)
    setTimeout(() => {
      if (r.status === 'canceled') return
      try {
        ss.output = execStep(r, st); ss.status = 'done'; ss.finished_at = sec(); ss.progress = ''
        wfLog(r, `步骤「${st.name}」完成`)
      } catch (e) {
        ss.status = 'error'; ss.error = String(e); r.status = 'error'; r.error = String(e); return
      }
      idx++
      if (single || (st.pause_after && idx < steps.length)) {
        r.status = 'paused'; r.current_step_id = null
        r.pause_reason = `「${st.name}」已完成，检查结果后继续`
        wfLog(r, r.pause_reason); return
      }
      runNext()
    }, 1100)
  }
  runNext()
}

function freshStates(steps: WfStep[]) {
  return Object.fromEntries(steps.map(s => [s.id, { status: 'pending' as const, started_at: null, finished_at: null, progress: '', output: {}, error: '' }]))
}
function makeRun(wf: WfDef, topic: string, requestId?: string): WfRun {
  const now = sec()
  const id = requestId ? `wr_${requestId}` : `wr_${String(now % 1_000_000).padStart(6, '0')}_${Math.floor(Math.random() * 9000 + 1000)}`
  const run: WfRun = {
    id, topic, workflow: structuredClone(wf), status: 'draft', current_step_id: null, pause_reason: '', error: '',
    step_states: freshStates(wf.steps), logs: [new Date().toLocaleTimeString('zh-CN', { hour12: false }) + `  已创建工作流实例「${wf.name}」`],
    created_at: now, updated_at: now, assets: [],
  }
  S.runs.unshift(run); return run
}

/* ── 路由 ── */
function body<T>(b: unknown): T { return (b || {}) as T }

export async function handle(method: string, path: string, raw: unknown, q: URLSearchParams) {
  const seg = path.replace(/^\/?api\//, '').split('/').filter(Boolean)
  const head = seg[0] || ''
  if (method === 'POST' && (head === 'login' || head === 'logout')) return ok({ ok: true })

  if (head === 'config' && method === 'GET') return ok(config())
  if (head === 'status' && method === 'GET') return ok(status(+(q.get('log_since') || 0)))
  if (head === 'storage' && method === 'GET') return ok({ rounds: stats(), trash: { count: S.trash.length, bytes: S.trash.reduce((a, r) => a + r.bytes, 0), retention_days: 7 }, total_bytes: stats().bytes, disk_free_bytes: 248_000_000_000, disk_total_bytes: 500_000_000_000 })

  if (head === 'generate' && method === 'POST') return enqueue(body<GeneratePayload>(raw))
  if (head === 'prompt' && method === 'POST') {
    const b = body<RewriteBody>(raw)
    if (!b.text?.trim()) return err(400, '先写一句想法')
    const pid = b.provider_id || S.llm.active?.provider_id
    const prov = S.llm.providers.find(p => p.id === pid)
    if (!prov) return err(400, '还没有配置改写模型，去设置里添加')
    if (!prov.key_set) return err(400, `「${prov.name}」没有填 API Key`)
    log(`改写提示词 · ${prov.name} / ${b.model || S.llm.active?.model}`)
    const wf = b.mode === 'video' ? `（${b.workflow} · ${b.num_frames} 帧）` : ''
    const edit = b.editing ? '保持参考图中的人物身份与构图关系，' : ''
    return ok({ prompt: `${edit}${b.text.trim()}，电影感光线，细腻质感，主体清晰，背景层次分明${wf ? '，镜头运动自然，环境音真实' : ''}`, model: b.model || S.llm.active?.model, images_used: b.ref_count || 0, format: b.mode === 'video' ? 'h3-3section' : 'image' })
  }
  if (head === 'stop' && method === 'POST') {
    const b = body<{ clear_queue?: boolean }>(raw)
    if (S.current) { S.current.status = 'canceled'; S.current.error = '已取消'; S.history.unshift(S.current); log(`已取消任务 ${S.current.id}`); S.current = null }
    if (b.clear_queue) { const n = S.queue.length; S.queue = []; log(`已清空队列 ${n} 个任务`) }
    S.phase = S.queue.length ? 'generating' : 'ready'; pump(); armIdle()
    return ok({ ok: true })
  }
  if (head === 'release' && method === 'POST') {
    S.queue = []; if (S.current) { S.current.status = 'canceled'; S.current = null }
    S.phase = 'stopping'; S.colab.any_running = false; S.colab.sessions = []; S.colab.rate_per_hour = 0; S.activeGpu = ''
    log('正在释放全部 Colab 运行时…')
    setTimeout(() => { S.phase = 'idle'; S.idleDeadline = null; log('已释放，停止计费') }, 1200)
    return ok({ ok: true })
  }
  if (head === 'queue') {
    if (seg[1] === 'clear' && method === 'POST') { const n = S.queue.length; S.queue = []; return ok({ ok: true, removed: n }) }
    if (seg[1] && method === 'DELETE') { const i = S.queue.findIndex(j => j.id === seg[1]); if (i < 0) return err(404, '任务不在队列中'); S.queue.splice(i, 1); return ok({ ok: true }) }
  }
  if (head === 'settings' && method === 'POST') {
    const m = +body<{ idle_minutes: number }>(raw).idle_minutes
    if (![0, 5, 10, 20, 30, 60].includes(m) && !(m >= 5 && m <= 60)) return err(400, '空闲时间需在 5–60 分钟，或 0 表示永不超期')
    S.idleMinutes = m; armIdle(); log(m === 0 ? '已设为永不超期' : `空闲 ${m} 分钟后自动释放`); return ok({ ok: true, idle_minutes: m })
  }

  if (head === 'rounds') {
    if (seg.length === 1 && method === 'GET') return ok({ rounds: S.rounds, total: S.rounds.length, rev: S.rev, stats: stats() })
    if (seg[1] === 'delete' && method === 'POST') {
      const ids = body<{ ids: string[] }>(raw).ids || []
      const permanent = !!body<{ permanent?: boolean }>(raw).permanent
      const deleted: string[] = []
      for (const id of ids) {
        const i = S.rounds.findIndex(r => r.id === id); if (i < 0) continue
        const [r] = S.rounds.splice(i, 1); deleted.push(id)
        if (!permanent) S.trash.unshift({ ...r, deleted_at: sec(), purge_at: sec() + 7 * 86400 })
      }
      bumpRev(); return ok({ deleted, bytes: 0 })
    }
    if (seg[1] === 'star' && method === 'POST') {
      const b = body<{ ids: string[]; starred: boolean }>(raw)
      const updated = b.ids.filter(id => { const r = S.rounds.find(x => x.id === id); if (r) { r.starred = b.starred; return true } return false })
      bumpRev(); return ok({ ok: true, updated, starred: b.starred })
    }
    if (seg[1] === 'cleanup' && method === 'POST') {
      const b = body<{ older_than_days?: number | null; keep_latest?: number | null; kind?: string; include_starred?: boolean; dry_run?: boolean; permanent?: boolean }>(raw)
      if (b.older_than_days == null && b.keep_latest == null) return err(400, '至少填写一个条件')
      const sorted = [...S.rounds].sort((a, c) => c.created_at - a.created_at)
      const keep = new Set(b.keep_latest != null ? sorted.slice(0, b.keep_latest).map(r => r.id) : [])
      const matched = S.rounds.filter(r => {
        if (b.kind && r.kind !== b.kind) return false
        if (!b.include_starred && r.starred) return false
        const old = b.older_than_days != null ? sec() - r.created_at > b.older_than_days * 86400 : true
        const extra = b.keep_latest != null ? !keep.has(r.id) : true
        return (b.older_than_days != null && b.keep_latest != null) ? old && extra : (b.older_than_days != null ? old : extra)
      }).map(r => r.id)
      const bytes = matched.reduce((a, id) => a + (S.rounds.find(r => r.id === id)?.bytes || 0), 0)
      if (!b.dry_run) {
        for (const id of matched) {
          const i = S.rounds.findIndex(r => r.id === id); if (i < 0) continue
          const [r] = S.rounds.splice(i, 1)
          if (!b.permanent) S.trash.unshift({ ...r, deleted_at: sec(), purge_at: sec() + 7 * 86400 })
        }
        bumpRev()
      }
      return ok({ matched, count: matched.length, bytes, deleted: b.dry_run ? undefined : matched })
    }
    const id = seg[1]
    if (seg[2] === 'meta' && method === 'GET') { const r = S.rounds.find(x => x.id === id); return r ? ok({ ...r, meta: r }) : err(404, '作品不存在') }
    if (seg[2] === 'star') { const r = S.rounds.find(x => x.id === id); if (!r) return err(404, '作品不存在'); r.starred = !!body<{ starred: boolean }>(raw).starred; bumpRev(); return ok({ ok: true }) }
    if (seg[2] === 'use' && method === 'POST') {
      const r = S.rounds.find(x => x.id === id); if (!r || r.kind !== 'image') return err(400, '只能把图片作品设为参考图')
      const b = body<{ slot?: string; append?: boolean }>(raw)
      const rec: RefRec = { id: b.slot === 'last' ? 'last' : uid('ref'), bytes: r.bytes, source: `round:${id}`, updated_at: sec(), url: S.urls[id] }
      S.urls[rec.id] = rec.url
      if (b.slot === 'last') S.last = rec
      else if (b.append) { if (S.refs.length >= 6) return err(400, '最多 6 张参考图'); S.refs.push({ ...rec }); S.urls[rec.id] = S.urls[id] }
      else { S.refs = [{ ...rec, id: S.refs[0]?.id || rec.id }]; S.urls[S.refs[0].id] = S.urls[id] }
      return ok({ ok: true, references: refsReport() })
    }
  }

  if (head === 'trash') {
    if (seg.length === 1) return ok({ items: S.trash, count: S.trash.length, bytes: S.trash.reduce((a, r) => a + r.bytes, 0), retention_days: 7, now: sec() })
    if (seg[1] === 'restore' && method === 'POST') {
      const ids = body<{ ids: string[] }>(raw).ids || []
      const restored: string[] = [], missing: string[] = []
      for (const id of ids) {
        const i = S.trash.findIndex(r => r.id === id)
        if (i < 0) { missing.push(id); continue }
        const [r] = S.trash.splice(i, 1); delete r.deleted_at; delete r.purge_at; S.rounds.push(r); restored.push(id)
      }
      S.rounds.sort((a, c) => c.created_at - a.created_at); bumpRev(); return ok({ restored, missing })
    }
    if (seg[1] === 'purge' && method === 'POST') {
      const b = body<{ ids?: string[]; all?: boolean }>(raw)
      const ids = b.all ? S.trash.map(r => r.id) : (b.ids || [])
      let bytes = 0
      S.trash = S.trash.filter(r => { if (ids.includes(r.id)) { bytes += r.bytes; return false } return true })
      return ok({ purged: ids, bytes })
    }
  }

  if (head === 'reference') {
    if (method === 'DELETE') {
      const id = q.get('id')
      if (id && q.get('slot') !== 'last') { S.refs = S.refs.filter(r => r.id !== id) }
      else if (q.get('slot') === 'last') S.last = null
      else S.refs = []
      return ok({ ok: true, references: refsReport() })
    }
    if (method === 'POST') {
      const slot = q.get('slot') === 'last' ? 'last' : 'first'
      const rec: RefRec = { id: slot === 'last' ? 'last' : uid('ref'), bytes: 240_000, source: 'upload', updated_at: sec(), url: makeArt({ w: 768, h: 1024, seed: Math.floor(Math.random() * 9999), label: '参考图' }) }
      S.urls[rec.id] = rec.url
      if (slot === 'last') S.last = rec
      else if (q.get('append') === '1') { if (S.refs.length >= 6) return err(400, '最多 6 张参考图，请先移除不需要的图片'); S.refs.push(rec) }
      else S.refs = [rec]
      return ok({ ok: true, references: refsReport() })
    }
  }

  if (head === 'models' && seg[1] === 'recent') {
    const model = (body<{ model?: string }>(raw).model || q.get('model') || '').trim()
    if (method === 'POST') { if (!/^[\w.-]+\/[\w.-]+$/.test(model) && !MODELS.some(m => m.id === model)) return err(400, '模型名应为内置名或 owner/repo'); S.recentModels = [model, ...S.recentModels.filter(m => m !== model)].slice(0, 16) }
    if (method === 'DELETE') S.recentModels = S.recentModels.filter(m => m !== model)
    return ok({ ok: true, recent_models: S.recentModels })
  }
  if (head === 'comfy' && seg[1] === 'parse-link' && method === 'POST') {
    const url = body<{ url: string }>(raw).url || ''
    const m = url.match(/huggingface\.co\/([^/]+\/[^/]+)\/(?:blob|resolve)\/([^/]+)\/(.+?)(?:\?|$)/)
    const file = m ? m[3] : url.split('/').pop() || url
    return ok({ ok: true, spec: { source: 'hf', repo_id: m?.[1] || '', filename: file, revision: m?.[2] || 'main', url, basename: file.split('/').pop() || '', ext: file.split('.').pop() || '', format: file.toLowerCase().includes('gguf') ? 'gguf' : 'safetensors' } })
  }
  if (head === 'comfy' && seg[1] === 'presets') {
    if (method === 'POST') {
      const b = body<Partial<ComfyPreset>>(raw)
      if (!b.name?.trim()) return err(400, '请填写方案名称')
      const p = { ...b, id: 'cp_' + uid(''), builtin: false } as ComfyPreset
      S.comfyPresets.unshift(p); return ok({ ok: true, preset: p, presets: S.comfyPresets })
    }
    if (method === 'DELETE' && seg[2]) { S.comfyPresets = S.comfyPresets.filter(p => p.id !== seg[2]); return ok({ ok: true, presets: S.comfyPresets }) }
    return ok({ presets: S.comfyPresets, builtin_presets: COMFY_BUILTIN })
  }
  if (head === 'presets') {
    if (method === 'GET') return ok({ builtin: STUDIO_BUILTIN, custom: S.studioPresets })
    if (method === 'POST') {
      const b = body<Partial<StudioPreset>>(raw)
      if (!b.name?.trim() || b.name.length > 60) return err(400, '预设名称不能为空且不超过 60 字')
      const p = { ...b, id: 'sp_' + uid('') } as StudioPreset
      S.studioPresets.unshift(p); return ok({ ok: true, preset: p, custom: S.studioPresets })
    }
    if (method === 'DELETE' && seg[1]) { S.studioPresets = S.studioPresets.filter(p => p.id !== seg[1]); return ok({ ok: true, custom: S.studioPresets }) }
  }
  if (head === 'llm') {
    const st = S.llm
    if (seg.length === 1 && method === 'GET') return ok(st)
    if (seg[1] === 'active' && method === 'POST') {
      const b = body<{ provider_id: string; model: string }>(raw)
      const p = st.providers.find(x => x.id === b.provider_id)
      if (!p) return err(404, '服务商不存在')
      if (!p.key_set || !p.models.includes(b.model)) return err(400, '请选择该服务商已保存的模型')
      st.active = { provider_id: p.id, model: b.model.trim() }
      return ok(st)
    }
    if (seg[1] === 'providers') {
      if (seg.length === 2 && method === 'POST') {
        const b = body<LlmProviderBody>(raw)
        if (!['openai', 'anthropic', 'gemini'].includes(b.kind)) return err(400, '类型只能是 OpenAI、Anthropic 或 Gemini')
        if (!b.name?.trim()) return err(400, '请填写名称')
        if (!/^https?:\/\/[^\s]+$/.test(b.base_url?.trim() || '')) return err(400, 'BASE_URL 需要以 http:// 或 https:// 开头')
        const old = b.id ? st.providers.find(x => x.id === b.id) : undefined
        if (b.id && !old) return err(404, '服务商不存在')
        if (!old && !b.api_key?.trim()) return err(400, '新服务商需要填写 API Key')
        const p: LlmProvider = {
          id: old?.id || uid('llm_'), kind: b.kind, name: b.name.trim(), base_url: b.base_url.trim().replace(/\/+$/, ''),
          key_set: !!(b.api_key?.trim() || old?.key_set), key_masked: b.api_key?.trim() ? maskKey(b.api_key.trim()) : old?.key_masked || '',
          enhanced_rewrite: b.enhanced_rewrite ?? old?.enhanced_rewrite ?? false, legacy_template: false,
          models: [...new Set(b.models ?? old?.models ?? [])], models_fetched_at: old?.models_fetched_at ?? null,
        }
        st.providers = old ? st.providers.map(x => x.id === p.id ? p : x) : [...st.providers, p]
        repairSelection(st)
        return ok(st)
      }
      const p = st.providers.find(x => x.id === seg[2])
      if (!p) return err(404, '服务商不存在')
      if (seg.length === 3 && method === 'DELETE') {
        st.providers = st.providers.filter(x => x.id !== p.id)
        repairSelection(st)
        return ok(st)
      }
      if (seg[3] === 'models' && method === 'POST') {
        if (!p.key_set) return err(400, '先填写 API Key')
        p.models = LLM_MODELS[p.kind]; p.models_fetched_at = sec()
        repairSelection(st)
        return ok(st)
      }
      if (seg[3] === 'test' && method === 'POST') {
        const m = body<{ model?: string }>(raw).model || p.models[0] || ''
        return ok({ ok: p.key_set, ms: 300 + Math.floor(Math.random() * 500), model: m, error: p.key_set ? '' : '没有 API Key' })
      }
    }
  }
  if (head === 'hf' && seg[1] === 'list-loras') {
    const repo = body<{ repo_id: string }>(raw).repo_id || ''
    if (!repo.includes('/')) return err(400, '仓库 ID 应为 owner/repo')
    return ok({ files: [`${repo.split('/')[1]}.safetensors`, `${repo.split('/')[1]}_v2.safetensors`] })
  }

  if (head === 'colab') {
    if (seg[1] === 'status') return ok(S.colab)
    if (seg[1] === 'auth' && seg[2] === 'start') return ok({ auth_url: 'https://accounts.google.com/o/oauth2/v2/auth?mock=1' })
    if (seg[1] === 'auth' && seg[2] === 'complete') {
      const code = body<{ code: string }>(raw).code || ''
      if (code.length < 4) return err(400, '授权码不正确')
      S.colab = { ...S.colab, authed: true, ok: true, email: 'studio@example.com', balance: 128.4, error: '' }
      log('Google Colab 授权完成'); return ok(S.colab)
    }
    if (seg[1] === 'auth' && seg[2] === 'logout') { S.colab = { ...S.colab, authed: false, email: '', balance: null, sessions: [], any_running: false }; return ok({ ok: true }) }
    if (seg[1] === 'hf-token') { const t = body<{ token: string }>(raw).token; if (t && !/^hf_/.test(t)) return err(400, 'HF Token 应以 hf_ 开头'); S.colab.hf_token_set = !!t; return ok({ ok: true }) }
    if (seg[1] === 'grab' && method === 'POST') {
      if (S.phase === 'starting' || S.current) return err(409, '正在抢卡或有任务在跑')
      const b = body<{ gpu_pool: string[]; poll_rounds: number; poll_all_proxies: boolean }>(raw)
      if (!b.gpu_pool?.length) return err(400, '请先勾选要抢的卡')
      S.phase = 'starting'; S.error = ''
      const order = b.gpu_pool.join(' → ')
      log(`开始抢卡：${order} · ${b.poll_rounds || 1} 轮${b.poll_all_proxies ? ' · 全部代理' : ''}`)
      const target = b.gpu_pool[0]
      setTimeout(() => {
        S.colab.sessions = [{ name: `colab-${target.toLowerCase()}-${uid('')}`, gpu: target, shape: 'HIGH_RAM', endpoint: `https://colab.example/${target.toLowerCase()}` }]
        S.colab.any_running = true; S.colab.rate_per_hour = target === 'H100' ? 6.4 : target === 'T4' ? 1.1 : 3.2
        S.colab.gpu_health[target] = { status: 'ok', at: sec() }
        S.activeGpu = `${target} (HIGH_RAM)`; S.phase = 'ready'; armIdle()
        log(`抢到 ${target}，实例已就绪`)
      }, 1800)
      return ok({ ok: true }, 202)
    }
  }
  if (head === 'proxy') {
    const px = S.proxy
    if (seg[1] === 'profiles' && method === 'POST') {
      const b = body<{ id?: string; label: string; url?: string }>(raw)
      const old = px.profiles.find(p => p.id === b.id)
      if (b.id && !old) return err(404, '代理线路不存在')
      if (!b.label?.trim() || (!old && !b.url)) return err(400, '请填写名称和地址')
      let masked = old?.masked || ''
      if (b.url) {
        try {
          const u = new URL(b.url)
          if (!['http:', 'https:', 'socks5:', 'socks5h:'].includes(u.protocol)) return err(400, '代理协议无效')
          masked = `${u.protocol}//${u.username || u.password ? '***@' : ''}${u.host}`
        } catch { return err(400, '代理地址无效') }
      }
      const p = { id: old?.id || uid('px_'), label: b.label.trim(), masked, hint: '', configured: true }
      if (!px.profiles.length) px.active = p.id
      px.profiles = old ? px.profiles.map(row => row.id === p.id ? p : row) : [...px.profiles, p]
      if (px.last_test?.profile === p.id) px.last_test = null
    } else if (seg[1] === 'profiles' && method === 'DELETE') {
      if (!px.profiles.some(p => p.id === seg[2])) return err(404, '代理线路不存在')
      px.profiles = px.profiles.filter(p => p.id !== seg[2])
      if (px.active === seg[2]) px.active = px.profiles[0]?.id || ''
      if (px.last_test?.profile === seg[2]) px.last_test = null
    } else if (seg[1] === 'test' && method === 'POST') {
      const id = body<{ profile?: string }>(raw).profile || px.active
      if (!px.profiles.some(p => p.id === id)) return err(404, '代理线路不存在')
      const t: ProxyTest = { profile: id, ok: true, loc: 'US', colo: 'EWR', ms: 260, at: sec(), error: '' }
      px.last_test = t
      return ok(t)
    } else if (seg.length === 1 && method === 'POST') {
      const id = body<{ active: string }>(raw).active
      if (id && !px.profiles.some(p => p.id === id)) return err(404, '代理线路不存在')
      px.active = id
    }
    return ok(px)
  }

  if (head === 'workflows') {
    if (seg.length === 1 && method === 'GET') return ok({ builtin: BUILTIN_WF, custom: S.wfCustom, runs: S.runs.map(runSummary), step_catalog: STEP_CATALOG, ffmpeg_available: true })
    if (seg.length === 1 && method === 'POST') {
      const b = body<Partial<WfDef>>(raw)
      if (!b.name?.trim() || !b.steps?.length) return err(400, '模板需要名称和至少一个步骤')
      const wf: WfDef = { id: 'wf_' + uid(''), builtin: false, name: b.name!, description: b.description || '', steps: b.steps! }
      S.wfCustom.unshift(wf); return ok({ ok: true, workflow: wf, custom: S.wfCustom })
    }
    if (seg[1] === 'runs') {
      if (seg.length === 2 && method === 'GET') return ok({ runs: S.runs.map(runSummary) })
      if (seg.length === 2 && method === 'POST') {
        const b = body<{ request_id?: string; workflow_id?: string; workflow?: Partial<WfDef>; topic?: string }>(raw)
        const existing = b.request_id && S.runs.find(r => r.id === `wr_${b.request_id}`)
        if (existing) return ok({ ok: true, run: existing }, 201)
        let wf: WfDef | undefined
        if (b.workflow?.steps) wf = { id: b.workflow.id || 'wf_' + uid(''), name: b.workflow.name || '自定义工作流', description: b.workflow.description || '', steps: b.workflow.steps }
        else wf = [...BUILTIN_WF, ...S.wfCustom].find(w => w.id === (b.workflow_id || 'builtin:agent-long-video'))
        if (!wf) return err(400, `未找到工作流：${b.workflow_id}`)
        return ok({ ok: true, run: makeRun(wf, (b.topic ?? wf.default_topic ?? '').slice(0, 2000), b.request_id) }, 201)
      }
      const run = S.runs.find(r => r.id === seg[2])
      if (!run) return err(404, '工作流运行记录不存在')
      if (seg.length === 3 && method === 'GET') return ok({ run })
      if (seg.length === 3 && method === 'PATCH') {
        if (run.status === 'running') return err(409, '运行中不能修改配置')
        const b = body<{ topic?: string; workflow?: WfDef }>(raw)
        if (b.topic != null) run.topic = b.topic
        if (b.workflow) {
          const old = run.step_states
          run.workflow = b.workflow
          run.step_states = Object.fromEntries(b.workflow.steps.map(s => [s.id, old[s.id] || freshStates([s])[s.id]]))
        }
        run.updated_at = sec(); return ok({ ok: true, run })
      }
      if (seg.length === 3 && method === 'DELETE') { if (run.status === 'running') return err(409, '运行中不能删除'); S.runs = S.runs.filter(r => r.id !== run.id); return ok({ ok: true }) }
      const action = seg[3]
      if ((action === 'start' || action === 'resume') && method === 'POST') {
        if (body<{ draft_only?: boolean }>(raw).draft_only && run.status !== 'draft') return err(409, '草稿已启动')
        if (S.runs.some(r => r.status === 'running')) return err(409, '已有工作流在运行')
        const b = body<{ from_step_id?: string; single_step?: boolean }>(raw)
        driveRun(run, b.from_step_id, !!b.single_step); return ok({ ok: true, run }, 202)
      }
      if (action === 'cancel' && method === 'POST') { run.status = 'canceled'; run.current_step_id = null; wfLog(run, '已终止'); return ok({ ok: true, run }) }
      if (action === 'steps' && seg[5] === 'retry' && method === 'POST') { driveRun(run, seg[4], !!body<{ single_step?: boolean }>(raw).single_step); return ok({ ok: true, run }, 202) }
      if (action === 'steps' && seg[5] === 'output' && method === 'POST') {
        const patch = body<{ output?: Record<string, unknown> }>(raw).output || body<Record<string, unknown>>(raw)
        run.step_states[seg[4]].output = { ...run.step_states[seg[4]].output, ...patch }; return ok({ ok: true, run })
      }
      if (action === 'assets' && method === 'POST') {
        if (!(raw instanceof Blob)) return err(400, '需要上传图片')
        const sid = q.get('step_id') || ''
        const hash = await crypto.subtle.digest('SHA-256', await raw.arrayBuffer())
        const fn = `upload_${run.id}_${sid}_${Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, '0')).join('')}.jpg`
        if (!S.urls[fn]) S.urls[fn] = URL.createObjectURL(raw)
        const asset = { filename: fn, bytes: raw.size }
        if (!run.assets.some(a => a.filename === fn)) run.assets.push(asset)
        const st = run.workflow.steps.find(s => s.id === sid)
        if (st?.type === 'asset_input') st.config.asset_files = [...new Set([...(st.config.asset_files || []), fn])]
        return ok({ ok: true, filename: fn, asset, assets: run.assets })
      }
      if (action === 'assets' && seg[4] && method === 'DELETE') {
        const fn = seg[4]
        run.assets = run.assets.filter(a => a.filename !== fn)
        for (const st of run.workflow.steps) {
          if (st.type === 'asset_input') st.config.asset_files = (st.config.asset_files || []).filter((f: string) => f !== fn)
        }
        if (S.urls[fn]?.startsWith('blob:')) URL.revokeObjectURL(S.urls[fn])
        delete S.urls[fn]
        return ok({ ok: true, assets: run.assets })
      }
    }
    if (seg.length === 2 && method === 'DELETE') { S.wfCustom = S.wfCustom.filter(w => w.id !== seg[1]); return ok({ ok: true, custom: S.wfCustom }) }
  }
  return err(404, `mock 未实现：${method} ${path}`)
}

export function mediaOf(key: string): string { return S.urls[key] || '' }

export function boot() {
  for (const s of SEED_ROUNDS) {
    const url = makeArt({ w: s.w, h: s.h, seed: s.seed, label: s.kind === 'video' ? `${s.dur}s` : '', video: s.kind === 'video' })
    S.urls[s.id] = url
    S.rounds.push({
      id: s.id, kind: s.kind, prompt: s.prompt, model: s.model, created_at: sec() - Math.round(s.daysAgo * 86400),
      bytes: 1_100_000 + s.seed % 3_000_000, starred: s.starred, has_thumb: true, mtime: sec(),
      width: s.w, height: s.h, steps: s.kind === 'video' ? 30 : 35, cfg: 5, seed: s.seed, gpu: s.kind === 'video' ? 'H100' : 'A100',
      workflow: s.wf || null, num_frames: s.frames || null, duration_s: s.dur, negative: 'blurry, lowres, watermark, text',
    })
  }
  S.urls['seed-ref'] = makeArt({ w: 768, h: 1024, seed: 42, label: '' })
  S.refs = [{ id: 'refseed1', bytes: 310_000, source: 'upload', updated_at: sec() - 3600, url: S.urls['seed-ref'] }]
  S.urls['refseed1'] = S.urls['seed-ref']
  armIdle()
  log('Colab Studio mock 后端已就绪（示例数据，不会产生真实费用）')
  log('Colab 已授权（studio@example.com），余额 128.4 CU，当前运行实例 1 台')
  setInterval(() => {
    if (S.idleDeadline && sec() > S.idleDeadline && !S.current && !S.queue.length && S.colab.any_running) {
      S.colab.any_running = false; S.colab.sessions = []; S.colab.rate_per_hour = 0; S.activeGpu = ''; S.phase = 'idle'; S.idleDeadline = null
      log('空闲到期，已自动释放 Colab 运行时')
    }
  }, 2000)
}

export const MOCK_CONFIG_GPUS = GPUS
export type { Lora }
