// 助手、节点图、提案、操作卡的全部用户可见中文文案。
// 规则见 docs/harness/ui-motion-spec.md。组件里不得再写死中文字符串，也不得渲染服务端回退文案。
// 本文件只含常量、类型和纯格式化函数，不依赖任何业务模块。

/* ── 基础类型 ── */

export type StepTypeKey =
  | 'asset_input' | 'llm_script' | 'web_asset_fetch' | 'image_gen' | 'h3_prompt' | 'video_gen' | 'video_stitch'

export type ProposalField = 'keyframe_prompt' | 'video_prompt' | 'prompt'

export type ProposalState = 'pending' | 'applying' | 'applied' | 'undoing' | 'undone' | 'rejected' | 'expired'

export type OperationState =
  | 'awaiting_approval' | 'queued' | 'running' | 'partial' | 'done' | 'failed' | 'canceled' | 'unknown'

export type OperationKind = 'image' | 'video'

export interface Suggestion {
  /** 列表里显示的短句 */
  readonly label: string
  /** 点击后填入输入框的完整指令 */
  readonly prompt: string
}

/* ── 格式化工具 ── */

const DIGIT_START = /^[0-9]/

/** 拼接中文与数字开头的片段时补一个空格，与现有界面「3 个镜头」的排版一致。 */
function glue(head: string, tail: string): string {
  return DIGIT_START.test(tail) ? `${head} ${tail}` : head + tail
}

/** 「第 3 镜」 */
export function shotLabel(n: number): string {
  return `第 ${n} 镜`
}

/** 最多列出 3 个镜号：「第 3、5 镜」；更多时只给数量：「7 镜」。 */
export function shotList(nums: readonly number[]): string {
  if (nums.length === 0) return ''
  if (nums.length <= 3) return `第 ${nums.join('、')} 镜`
  return `${nums.length} 镜`
}

/** 「约 25.8 秒」「约 1 分 05 秒」 */
export function approxDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return ''
  if (seconds < 60) return `约 ${Number(seconds.toFixed(1))} 秒`
  const total = Math.round(seconds)
  const m = Math.floor(total / 60)
  const s = String(total % 60).padStart(2, '0')
  return `约 ${m} 分 ${s} 秒`
}

export function sizeLabel(width: number, height: number): string {
  return `${width} × ${height}`
}

export function framesLabel(frames: number): string {
  return `${frames} 帧`
}

export function progressLabel(done: number, total: number): string {
  return `${done}/${total}`
}

/* ── 结构化错误码（与 draw_studio/workflows/harness_errors.py 一一对应） ── */

export const HARNESS_ERROR_CODES = [
  'invalid_argument',
  'not_found',
  'revision_conflict',
  'shot_conflict',
  'busy',
  'running_locked',
  'draft_already_saved',
  'model_unconfigured',
  'model_error',
  'turn_stopped',
  'turn_timeout',
  'plugin_unavailable',
  'approval_required',
  'queue_full',
  'colab_unauthed',
  'media_invalid',
  'tool_limit_reached',
  'internal_error',
] as const

export type HarnessErrorCode = (typeof HARNESS_ERROR_CODES)[number]

/** 错误提示旁最多一个动作按钮。 */
export type ErrorAction = 'retry' | 'regenerate' | 'edit' | 'openModelSettings' | 'openCompute' | 'openRun'

export interface ErrorCopy {
  readonly text: string
  readonly action?: ErrorAction
}

export const HARNESS_ERROR_COPY: Readonly<Record<HarnessErrorCode, ErrorCopy>> = {
  invalid_argument: { text: '参数有误', action: 'edit' },
  not_found: { text: '内容已不存在' },
  revision_conflict: { text: '原内容已变', action: 'regenerate' },
  shot_conflict: { text: '镜头已被改动', action: 'regenerate' },
  busy: { text: '助手正忙，稍后再试', action: 'retry' },
  running_locked: { text: '工作流正在运行，停下后再改' },
  draft_already_saved: { text: '草稿已存为运行记录', action: 'openRun' },
  model_unconfigured: { text: '还没选对话模型', action: 'openModelSettings' },
  model_error: { text: '模型这次没有回应', action: 'retry' },
  turn_stopped: { text: '已停止' },
  turn_timeout: { text: '响应超时', action: 'retry' },
  plugin_unavailable: { text: '插件暂不可用' },
  approval_required: { text: '等你确认后再执行' },
  queue_full: { text: '队列已满，稍后再提交' },
  colab_unauthed: { text: '还没连接算力', action: 'openCompute' },
  media_invalid: { text: '素材不可用' },
  tool_limit_reached: { text: '一次做不完，分几次说', action: 'edit' },
  internal_error: { text: '出了点问题，再试一次', action: 'retry' },
}

export const ERROR_ACTION_LABELS: Readonly<Record<ErrorAction, string>> = {
  retry: '重试',
  regenerate: '重新生成',
  edit: '重新编辑',
  openModelSettings: '去设置',
  openCompute: '去连接',
  openRun: '打开记录',
}

export function isHarnessErrorCode(value: unknown): value is HarnessErrorCode {
  return typeof value === 'string' && (HARNESS_ERROR_CODES as readonly string[]).includes(value)
}

/**
 * 按错误码取文案。未知错误码一律落到 internal_error，不回显服务端原文。
 * shot_conflict 若带冲突镜号，改用具体镜号。
 */
export function errorCopy(code: unknown, conflictShots?: readonly number[]): ErrorCopy {
  const key: HarnessErrorCode = isHarnessErrorCode(code) ? code : 'internal_error'
  const base = HARNESS_ERROR_COPY[key]
  if (key === 'shot_conflict' && conflictShots && conflictShots.length > 0) {
    return { ...base, text: `${shotList(conflictShots)}已被改动` }
  }
  return base
}

/* ── 工具徽章（26 个静态创作工具 + 插件工具） ── */

export const STATIC_TOOLS = [
  'studio_read_context',
  'studio_get_catalog',
  'studio_list_templates',
  'studio_manage_template',
  'studio_list_runs',
  'studio_create_draft',
  'studio_read_workflow',
  'studio_list_nodes',
  'studio_edit_workflow',
  'studio_validate_workflow',
  'studio_manage_run_assets',
  'studio_read_shots',
  'studio_rewrite_prompt',
  'studio_apply_shot_edits',
  'studio_undo_change',
  'studio_request_run',
  'studio_run_status',
  'studio_find_assets',
  'studio_inspect_asset',
  'studio_edit_media',
  'studio_prepare_mask',
  'studio_references',
  'studio_library_actions',
  'studio_presets',
  'studio_generation',
  'studio_jobs',
] as const

export type StaticToolName = (typeof STATIC_TOOLS)[number]

export const PLUGIN_TOOLS = ['studio_shot_timing'] as const

export type PluginToolName = (typeof PLUGIN_TOOLS)[number]

export type ToolName = StaticToolName | PluginToolName

/** 工具徽章默认标签，2–6 字动词短语。 */
export const TOOL_LABELS: Readonly<Record<ToolName, string>> = {
  studio_read_context: '查看工作台',
  studio_get_catalog: '查看模型参数',
  studio_list_templates: '浏览模板',
  studio_manage_template: '整理模板',
  studio_list_runs: '查看运行记录',
  studio_create_draft: '新建草稿',
  studio_read_workflow: '读取工作流',
  studio_list_nodes: '查看节点',
  studio_edit_workflow: '修改工作流',
  studio_validate_workflow: '检查工作流',
  studio_manage_run_assets: '整理素材',
  studio_read_shots: '读取分镜',
  studio_rewrite_prompt: '改写提示词',
  studio_apply_shot_edits: '应用修改',
  studio_undo_change: '撤销修改',
  studio_request_run: '准备运行',
  studio_run_status: '查看进度',
  studio_find_assets: '查找作品',
  studio_inspect_asset: '查看作品信息',
  studio_edit_media: '编辑素材',
  studio_prepare_mask: '准备选区',
  studio_references: '调整参考图',
  studio_library_actions: '整理作品',
  studio_presets: '管理预设',
  studio_generation: '准备生成',
  studio_jobs: '查看任务',
  studio_shot_timing: '计算片长',
}

/** 带 op 的工具按 op 显示更具体的标签；缺省回落到 TOOL_LABELS。 */
export const TOOL_OP_LABELS = {
  studio_manage_template: { save: '保存模板', delete: '删除模板' },
  studio_manage_run_assets: { list: '查看素材', bind_rounds: '绑定素材', remove: '移除素材' },
  studio_run_status: { watch: '查看进度', cancel: '停止运行' },
  studio_edit_media: { crop: '裁剪图片', extract_frame: '截取画面', clip_video: '剪辑片段' },
  studio_references: { read: '查看参考图', use_round: '设为参考', remove: '移除参考', clear: '清空参考' },
  studio_library_actions: { star: '收藏作品', trash: '移到回收站', list_trash: '查看回收站', restore: '恢复作品' },
  studio_presets: { list: '查看预设', save: '保存预设', delete: '删除预设', parse_comfy_link: '解析模型链接' },
  studio_generation: { edit_composer: '调整参数', prepare: '检查参数', submit_image: '提交生图', submit_video: '提交视频' },
  studio_jobs: { list: '查看队列', read: '查看任务', cancel: '取消任务', retry: '重试任务' },
} as const satisfies { readonly [K in ToolName]?: Readonly<Record<string, string>> }

const OP_LABEL_INDEX: Readonly<Record<string, Readonly<Record<string, string>> | undefined>> = TOOL_OP_LABELS

/** 未登记的插件工具 */
export const UNKNOWN_TOOL_LABEL = '使用插件'

export function isToolName(value: string): value is ToolName {
  return Object.hasOwn(TOOL_LABELS, value)
}

/** 徽章标签：优先 op 级标签，其次工具标签，未知工具显示「使用插件」。不显示工具 ID。 */
export function toolLabel(name: string, op?: string): string {
  const byOp = op ? OP_LABEL_INDEX[name]?.[op] : undefined
  if (byOp) return byOp
  return isToolName(name) ? TOOL_LABELS[name] : UNKNOWN_TOOL_LABEL
}

/* ── 插件展示名（按包 ID 覆盖服务端名称与描述） ── */

export const PLUGIN_COPY: Readonly<Record<string, { readonly name: string; readonly description: string }>> = {
  'studio-shot-timing': { name: '镜头计时尺', description: '按镜头数和帧数算出片长' },
}

/* ── 界面文案 ── */

export const PROPOSAL_FIELD_LABELS: Readonly<Record<ProposalField, string>> = {
  keyframe_prompt: '关键帧提示词',
  video_prompt: '视频提示词',
  prompt: '提示词',
}

export const AGENT_COPY = {
  board: {
    title: '节点图',
    canvas: '节点画布',
    variables: '变量',
    zoomIn: '放大',
    zoomOut: '缩小',
    zoomReset: '恢复 100%',
    zoomValue: (scale: number) => `${Math.round(scale * 100)}%`,
    selectNode: (name: string) => `选择节点 ${name}`,
    nodeOff: '已停用',
    nodeDetail: {
      scenes: (n: number) => `${n} 个镜头`,
      size: sizeLabel,
    },
    nodeTypes: {
      asset_input: '素材',
      llm_script: '分镜',
      web_asset_fetch: '找图',
      image_gen: '关键帧',
      h3_prompt: '提示词',
      video_gen: '视频',
      video_stitch: '剪辑',
    } satisfies Readonly<Record<StepTypeKey, string>>,
    hint: '点选节点编辑，拖动调整位置',
    emptyHint: '在下方添加步骤，或让助手来搭',
    library: '模板与运行记录',
    saveDraft: '保存草稿',
    editNode: '编辑节点',
    askAgent: '问助手',
    refs: '参考图',
    refAlt: (stepName: string) => `${stepName} 的参考图`,
  },

  vars: {
    title: '变量',
    empty: '还没有变量',
    add: '添加变量',
    edit: (name: string) => `编辑 ${name}`,
    remove: (name: string) => `删除 ${name}`,
    copyRef: (name: string) => `复制 ${name} 的引用`,
    nameLabel: '变量名',
    typeLabel: '类型',
    valueLabel: '值',
    namePlaceholder: '名称，如 style',
    valuePlaceholder: '值',
    types: { string: '文本', number: '数字', boolean: '开关' },
    booleanValues: { true: '开', false: '关' },
    save: '保存',
    cancel: '取消',
    errors: {
      name: '以字母或下划线开头，只含字母、数字和下划线',
      taken: '已有同名变量',
      tooMany: '最多 32 个变量',
      reserved: '有步骤占用了 vars 这个名字，先给它改名',
      number: '请输入数字',
    },
  },

  agent: {
    launcher: '助手',
    launcherBusy: '助手正在处理',
    launcherUnread: '助手有新回复',
    title: '助手',
    moveAside: '移到另一侧',
    moveUp: '移到上方',
    moveDown: '移到下方',
    collapse: '收起',
    tabs: { aria: '助手视图', chat: '对话', plugins: '插件' },
    context: {
      aria: '当前对象',
      clear: '改为整个工作流',
      shot: shotLabel,
    },
    workspace: {
      image: '生图',
      video: '视频',
    },
    empty: {
      workflow: '想怎么改这条工作流？',
      step: '这一步想怎么改？',
      image: '想怎么调整这张图？',
      video: '想怎么调整这段视频？',
    },
    suggestions: {
      workflow: [
        { label: '检查缺少的输入', prompt: '检查工作流里缺少哪些上游输入' },
        { label: '加一个风格变量', prompt: '添加文本变量 style，值为胶片质感，并在分镜指令里引用它' },
        { label: '搭一条三镜头短片', prompt: '搭一条三镜头短片流程：分镜、关键帧、视频、剪辑' },
      ] satisfies readonly Suggestion[],
      image: [
        { label: '润色提示词', prompt: '润色当前提示词，补全构图和光影细节' },
        { label: '调整画幅尺寸', prompt: '把当前画幅改成 16:9 横图' },
        { label: '挑一张参考图', prompt: '从作品库里找最近的图片作为参考' },
      ] satisfies readonly Suggestion[],
      video: [
        { label: '润色视频提示词', prompt: '润色当前视频提示词，补全运镜和声音细节' },
        { label: '调整视频帧数', prompt: '把当前视频改成约 7 秒的帧数' },
        { label: '查看参考素材', prompt: '查看当前参考图和参考视频设置' },
      ] satisfies readonly Suggestion[],
      step: { label: '检查这一步的输入', prompt: '检查这个节点的输入和参数' } satisfies Suggestion,
      sceneCount: (n: number): Suggestion => ({ label: `改成 ${n} 个镜头`, prompt: `把这个分镜改成 ${n} 个镜头` }),
      polish: { label: '逐镜润色提示词', prompt: '逐镜润色这一步的提示词，保持人物和场景一致' } satisfies Suggestion,
      timing: { label: '算一下片长', prompt: '算一下现在的片长' } satisfies Suggestion,
    },
    composer: {
      aria: '给助手的话',
      placeholder: '说说想怎么改',
      placeholderStep: '这一步想怎么改',
      send: '发送',
      stop: '停止',
    },
    status: {
      working: '处理中',
      stopping: '正在停止',
      stopped: '已停止',
      jumpLatest: '回到最新',
      historyAria: '对话记录',
    },
    tools: {
      failedAria: (label: string) => `${label}失败`,
      more: (n: number) => `+${n}`,
      repeat: (n: number) => `×${n}`,
    },
    applied: {
      workflow: '已更新工作流',
      sceneCount: (from: number, to: number) => `镜头数 ${from} → ${to}`,
      shots: (nums: readonly number[]) => glue('已更新', shotList(nums)),
    },
    run: {
      start: '运行',
      resume: '继续运行',
      step: (stepName: string) => `运行「${stepName}」`,
      from: (stepName: string) => `从「${stepName}」开始运行`,
    },
    stale: {
      text: '工作流刚有改动，这次修改没有套用',
      resend: '重新发送',
      dismiss: '不用了',
    },
    unsaved: '修改还没保存好，稍后再发',
  },

  plugins: {
    loading: '读取中',
    loadFailed: '插件列表没加载出来',
    retry: '重试',
    state: { enabled: '已启用', disabled: '已停用' },
    install: '安装',
    installing: '安装中',
    enable: '启用',
    disable: '停用',
    remove: '卸载',
    removeAria: (name: string) => `卸载${name}`,
    tryTiming: '算片长',
    builtins: '内置能力',
  },

  proposal: {
    field: PROPOSAL_FIELD_LABELS,
    /** 「第 3 镜 · 关键帧提示词」；无镜号时只显示字段名。 */
    title: (shots: readonly number[], field: ProposalField): string => {
      const fieldLabel = PROPOSAL_FIELD_LABELS[field]
      return shots.length ? `${shotList(shots)} · ${fieldLabel}` : fieldLabel
    },
    before: '原文',
    after: '改写',
    expand: '展开',
    collapse: '收起',
    moreShots: (n: number) => `还有 ${n} 镜`,
    refsAria: (n: number) => `参考了 ${n} 张图`,
    refAlt: (assetLabel: string) => `参考 ${assetLabel}`,
    moreRefs: (n: number) => `+${n}`,
    apply: '采用',
    applyShots: (n: number) => `采用 ${n} 镜`,
    reject: '放弃',
    undo: '撤销',
    dismiss: '关闭',
    regenerate: '重新生成',
    state: {
      pending: '',
      applying: '应用中',
      applied: '已应用',
      undoing: '撤销中',
      undone: '已撤销',
      rejected: '已放弃',
      expired: '已过期',
    } satisfies Readonly<Record<ProposalState, string>>,
  },

  conflict: {
    changed: '原内容已变',
    shots: (nums: readonly number[]) => `${shotList(nums)}已被改动`,
    partial: (applied: number, nums: readonly number[]) => `已应用 ${applied} 镜，${shotList(nums)}原内容已变`,
    regenerate: '重新生成',
    keep: '保留现稿',
  },

  operation: {
    title: {
      image: (n: number) => `生成 ${n} 张图`,
      video: (n: number) => `生成 ${n} 段视频`,
    } satisfies Readonly<Record<OperationKind, (n: number) => string>>,
    state: {
      awaiting_approval: '待确认',
      queued: '排队中',
      running: '生成中',
      partial: '部分完成',
      done: '已完成',
      failed: '失败',
      canceled: '已取消',
      unknown: '同步中',
    } satisfies Readonly<Record<OperationState, string>>,
    confirm: '开始生成',
    cancel: '取消',
    stop: '停止',
    retryFailed: (n: number) => `重试 ${n} 项`,
    retryItem: '重试这一项',
    view: '查看作品',
    item: (n: number) => `第 ${n} 项`,
    moreItems: (n: number) => `还有 ${n} 项`,
    progress: progressLabel,
    size: sizeLabel,
    frames: framesLabel,
    count: (n: number, kind: OperationKind) => (kind === 'image' ? `${n} 张` : `${n} 段`),
    needsCompute: '还没连接算力',
    connect: '去连接',
  },

  stepAi: {
    trigger: 'AI 改写',
    triggerAria: (n: number) => `AI 改写${shotLabel(n)}`,
    rewriteAll: '全部改写',
    placeholder: '怎么改？比如：更有电影感',
    submit: '生成',
    generating: '生成中',
    cancel: '取消',
    /** 用户没填要求时发送的默认指令 */
    defaultInstruction: '润色这段提示词，保持原意',
  },

  toast: {
    applied: '已应用',
    appliedShots: (nums: readonly number[]) => glue('已应用到', shotList(nums)),
    undo: '撤销',
    undone: '已撤销',
    undoBlocked: '已有新改动，不能撤销',
    queued: '已加入队列',
    operationDone: (n: number, kind: OperationKind) => (kind === 'image' ? `${n} 张图已生成` : `${n} 段视频已生成`),
    operationFailed: (n: number) => `${n} 项没生成出来`,
    workflowUpdated: '已更新工作流',
    saved: '已保存',
    historyFailed: '对话记录没加载出来',
    refCopied: '已复制引用',
    copyFailed: '复制失败',
    pluginInstalled: (name: string) => `已安装${name}`,
    pluginEnabled: (name: string) => `已启用${name}`,
    pluginDisabled: (name: string) => `已停用${name}`,
    pluginRemoved: (name: string) => `已卸载${name}`,
  },
} as const

/* ── 禁用词（CDP 终验脚本按 ui-motion-spec.md §5.4 的范围扫描；命中即不通过） ── */

/** 防御性、免责式话术。适用于界面文字与模型回复。 */
export const BANNED_PHRASES = [
  '无法证明', '没有证据', '估算', '剪辑前', '仅在', '仅供参考', '版本匹配', '本轮', '本次',
  '工具调用', '调用', '已暂存', '由编辑器采用', '按工具定义', '请按', '可能会产生费用', '可能产生', '费用',
  '无法确认', '请注意', '温馨提示', '抱歉', '作为 AI', '作为AI', '我将', '为您', '您', '根据您的', '以下是',
  '需要注意的是', '理论上', '不保证', '尽力', '系统检测到', '是否确认', '成功地', '操作已完成',
] as const

/** 句式黑名单：「不是…而是…」等对照式辩解。适用于界面文字与模型回复。 */
export const BANNED_PATTERNS: readonly RegExp[] = [
  /不是[^。！？\n]{0,40}而是/,
  /并非[^。！？\n]{0,40}而是/,
  /(?:由于|因为)[^。！？\n]{0,40}(?:无法|不能)保证/,
]

/** 内部契约与实现细节。只扫界面固定文字（不含用户输入、提示词正文与模型回复）。 */
export const BANNED_INTERNAL_TERMS = [
  'dsh', 'DSH', 'PID', 'pid', 'CAS', 'idempotency', 'proposal_id', 'operation_id', 'undo_id', 'mask_id', 'shot_id',
  'turn_id', 'run_id', 'step_id', 'round_id', 'job_id', 'schema', 'Schema', 'native', 'session', 'Harness', 'harness',
  'revision', 'readset', 'writeset', 'generation', 'token', 'Token', 'JSON', 'NDJSON', 'API', 'DeepSeek', 'pnpm',
  'node_modules', 'profile', 'studio_', '{{', '}}', 'vars.', 'LLM', 'Prompt', 'prompt',
] as const

/** 模型回复里同样不得出现的内部词（回复可以合理提到变量写法等，所以范围更窄）。 */
export const BANNED_IN_ANSWERS = [
  'dsh', 'PID', 'CAS', 'idempotency', 'schema', 'native session', 'studio_', '_id', 'proposal', 'operation', 'Harness',
] as const

export type CopySurface = 'chrome' | 'answer'

/** 返回文本中命中的禁用词或句式，供终验脚本与开发期断言使用。 */
export function findBannedTerms(text: string, surface: CopySurface = 'chrome'): string[] {
  const terms: readonly string[] = surface === 'chrome'
    ? [...BANNED_PHRASES, ...BANNED_INTERNAL_TERMS]
    : [...BANNED_PHRASES, ...BANNED_IN_ANSWERS]
  const hits = terms.filter(term => text.includes(term))
  for (const pattern of BANNED_PATTERNS) {
    const match = pattern.exec(text)
    if (match) hits.push(match[0])
  }
  return hits
}

export const STEP_OUTPUT_COPY = {
  label: '产出',
  styleBible: (text: string) => `风格基调：${text}`,
  stitched: (count: number, seconds: number, id: string) => `已合成 ${count} 段，约 ${seconds} 秒，成片 ${id}。`,
  assets: '已登记素材，供后续步骤引用。',
} as const
