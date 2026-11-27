// 工作流工作区：左侧模板与运行记录，中间是纵向步骤轨道，每步可展开配置与产出。
import { AnimatePresence, motion } from 'motion/react'
import { ArrowDown, ArrowUp, ChevronDown, Copy, Pause, Play, Plus, RotateCcw, Save, Square, Trash2, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api, media } from '../../api/client'
import type { RunStatus, StepState, StepStatus, WfDef, WfRun, WfStep } from '../../api/types'
import { ago, cx, rid } from '../../lib/util'
import { useStore } from '../../store/store'
import { Toggle, useConfirm } from '../../ui/Overlay'
import { NamePrompt } from '../../ui/NamePrompt'

const RUN_ZH: Record<RunStatus, string> = { draft: '草稿', running: '运行中', paused: '待审核', done: '已完成', error: '失败', canceled: '已终止' }
const RUN_TAG: Record<RunStatus, string> = { draft: '', running: 'run', paused: 'warn', done: 'ok', error: 'bad', canceled: '' }
const STEP_ZH: Record<StepStatus, string> = { pending: '等待', running: '执行中', done: '完成', error: '失败', skipped: '跳过', canceled: '终止' }
const UPSTREAM: Record<string, string[]> = {
  scenes_from: ['llm_script'], keyframe_from: ['image_gen'], prompts_from: ['h3_prompt'], clips_from: ['video_gen'],
}
const LABELS: Record<string, string> = {
  role: '资产角色', note: '备注', scene_count: '镜头数', output_format: '输出格式', instruction: '指令', url: '目标网页', search_query: '搜索词',
  max_images: '最多张数', scenes_from: '分镜来源', ref_sources: '引用上游参考图', prompt_template: '提示词模板', model: '模型', gpu: '首选 GPU',
  gpu_pool: '候补 GPU（按选择顺序）', poll_rounds: '轮询轮数', poll_all_proxies: '每轮使用全部代理', auto_offload: '自动显存卸载',
  width: '宽', height: '高', steps: '步数', cfg: 'CFG', max_scenes: '最多镜头', keyframe_from: '关键帧来源', workflow: '视频模式',
  num_frames: '帧数', prompts_from: '提示词来源', offload_mode: '显存卸载', clips_from: '片段来源', transition: '转场', fade_s: '转场秒数',
  target_width: '成片宽', target_height: '成片高', fps: '帧率', clip_round_ids: '追加作品编号', round_ids: '画廊作品编号',
}
const HIDDEN = new Set(['asset_files'])

export function WorkflowWorkspace() {
  const data = useStore(s => s.wfData)
  const run = useStore(s => s.wfRun)
  const loadWf = useStore(s => s.loadWf)
  const setRun = useStore(s => s.setWfRun)
  // 点模板只是本地草稿，点「运行」才真正建运行记录
  const [draft, setDraft] = useState<WfDef | null>(null)
  const selection = useRef(0)
  const openTpl = (d: WfDef) => { selection.current++; setRun(null); setDraft(d) }
  const activeStatus = useStore(s => s.status?.workflow_active?.status)
  const activeId = useStore(s => s.status?.workflow_active?.id)
  const toast = useStore(s => s.toast)

  const openRun = async (id: string) => {
    const version = ++selection.current
    try {
      const r = await api.wf.run(id)
      if (selection.current === version) { setDraft(null); setRun(r.run) }
    } catch (e) { toast(e instanceof Error ? e.message : '打开记录失败', 'err') }
  }
  useEffect(() => {
    const version = selection.current
    loadWf().then(() => {
      const state = useStore.getState()
      const id = state.status?.workflow_active?.id || state.wfData?.runs[0]?.id
      if (id && !state.wfRun && selection.current === version) void openRun(id)
    })
    return () => { selection.current++ }
  }, [loadWf]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!run || run.status !== 'running') return
    let fetching = false
    let active = true
    const id = setInterval(async () => {
      if (fetching) return
      fetching = true
      try {
        const r = await api.wf.run(run.id)
        if (!active || useStore.getState().wfRun?.id !== run.id) return
        setRun(r.run)
        if (r.run.status !== 'running') {
          loadWf()
          if (r.run.status === 'done') toast('工作流完成，成片已存入作品库', 'ok')
          else if (r.run.status === 'paused') toast(r.run.pause_reason || '已暂停，检查后继续', '')
          else if (r.run.status === 'error') toast(r.run.error || '工作流失败', 'err')
        }
      } catch (e) { if (active) toast(e instanceof Error ? e.message : '读取工作流失败', 'err') }
      finally { fetching = false }
    }, 1200)
    return () => { active = false; clearInterval(id) }
  }, [run?.id, run?.status]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!run || activeId !== run.id || activeStatus === run.status || run.status === 'running') return
    let active = true
    api.wf.run(run.id).then(r => { if (active) setRun(r.run) })
      .catch(e => { if (active) toast(e.message, 'err') })
    return () => { active = false }
  }, [activeId, activeStatus, run?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="wf">
      <WfSidebar draft={draft} onOpen={openTpl} openRun={openRun} />
      <div className="wf-main">
        {!data ? <div className="empty"><span className="spinner" /></div>
          : run ? <RunCanvas key={run.id} run={run} /> : draft ? <DraftCanvas key={draft.id || 'blank'} tpl={draft} /> : (
            <div className="empty"><b>先挑一个模板</b><span>点左边的模板可以先看步骤、改主题，点「运行」才开始。</span></div>
          )}
      </div>
    </div>
  )
}

type DraftFiles = { files: File[]; change: (next: File[]) => void }
type RunAction = (fn: () => Promise<{ run: WfRun }>, msg?: string) => void

function LocalImage({ file, remove }: { file: File; remove: () => void }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])
  return <figure className="ref-tile">{url && <img src={url} alt={file.name} />}
    <button className="ref-x" aria-label={`移除 ${file.name}`} onClick={remove}><X size={12} /></button></figure>
}

function templateSteps(steps: WfStep[]): WfStep[] {
  // Uploaded filenames belong to a run. Gallery round IDs can be reused across runs.
  return steps.map(s => s.type === 'asset_input' ? { ...s, config: { ...s.config, asset_files: [] } } : s)
}

/** 未落库的模板草稿：编辑主题和步骤，点运行时才创建运行记录 */
function DraftCanvas({ tpl }: { tpl: WfDef }) {
  const data = useStore(s => s.wfData)!
  const setRun = useStore(s => s.setWfRun)
  const loadWf = useStore(s => s.loadWf)
  const toast = useStore(s => s.toast)
  const [wf, setWf] = useState(() => ({ ...tpl, steps: templateSteps(tpl.steps) }))
  const [files, setFiles] = useState<Record<string, File[]>>({})
  const [requestId] = useState(() => Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join(''))
  const attempted = useRef(false)
  const [topic, setTopic] = useState('')
  const [starting, setStarting] = useState(false)
  const setSteps = (steps: WfStep[]) => setWf({ ...wf, steps })
  const addStep = (type: WfStep['type']) => {
    const cat = data.step_catalog.find(c => c.type === type)!
    let id = type.replace(/_.*/, ''); let n = 1
    while (wf.steps.some(s => s.id === id)) id = `${type.replace(/_.*/, '')}_${++n}`
    setSteps([...wf.steps, { id, type, name: `${wf.steps.length + 1}. ${cat.label}`, enabled: true, pause_after: false, config: structuredClone(cat.default_config) }])
  }
  const start = async () => {
    setStarting(true)
    try {
      const retry = attempted.current
      attempted.current = true
      const { run } = await api.wf.createRun({ workflow: wf, topic, request_id: requestId })
      if (run.status !== 'draft') { setRun(run); await loadWf(); return }
      // An interrupted upload can be retried on this same run, including after a lost response.
      if (retry) await api.wf.update(run.id, { topic, workflow: wf })
      const selectedFiles = new Set<string>()
      for (const step of wf.steps) {
        for (const file of files[step.id] || []) {
          const upload = await api.wf.uploadAsset(run.id, file, step.id)
          selectedFiles.add(upload.filename)
        }
      }
      if (retry) {
        // A previous partial submit may contain a file removed from the local draft.
        for (const step of run.workflow.steps.filter(s => s.type === 'asset_input')) {
          for (const filename of step.config.asset_files || []) {
            if (!selectedFiles.has(filename)) await api.wf.deleteAsset(run.id, filename)
          }
        }
      }
      setRun((await api.wf.start(run.id, undefined, true)).run)
      await loadWf()
      toast(`「${wf.name}」已开始运行`, 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '启动失败', 'err') }
    finally { setStarting(false) }
  }
  return (
    <div className="run" inert={starting}>
      <div className="run-head glass">
        <div className="row between">
          <div className="run-title"><h2>{wf.name}</h2><span className="tag">模板</span><span className="dim tabular">{wf.steps.length} 步</span></div>
          <span className="grow" />
          <button className="btn sm primary" disabled={starting || !wf.steps.some(s => s.enabled)} onClick={start}>{starting ? <span className="spinner" /> : <Play size={13} />}{starting ? '启动中' : '运行'}</button>
        </div>
        <p className="dim">{wf.description}</p>
        <textarea rows={2} value={topic} placeholder="写下这条流水线的主题，例如：雨夜霓虹街头的 3 镜头短片" onChange={e => setTopic(e.target.value)} />
      </div>
      <ol className="rail">
        {wf.steps.map((step, i) => (
          <StepCard key={step.id} draft={wf} step={step} idx={i}
            local={{ files: files[step.id] || [], change: next => setFiles(all => ({ ...all, [step.id]: next })) }}
            onChange={next => setSteps(wf.steps.map(x => x.id === step.id ? next : x))}
            onMove={d => { const j = i + d; if (j < 0 || j >= wf.steps.length) return; const a = [...wf.steps]; [a[i], a[j]] = [a[j], a[i]]; setSteps(a) }}
            onRemove={() => {
              setSteps(wf.steps.filter(x => x.id !== step.id))
              setFiles(all => { const next = { ...all }; delete next[step.id]; return next })
            }} />
        ))}
      </ol>
      <div className="add-step glass">
        <span className="lbl">添加步骤</span>
        <div className="chips">{data.step_catalog.map(c => <button key={c.type} className="chip" title={c.hint} onClick={() => addStep(c.type)}><span>{c.icon}</span>{c.label}</button>)}</div>
      </div>
    </div>
  )
}

function WfSidebar({ draft, onOpen, openRun }: { draft: WfDef | null; onOpen: (d: WfDef) => void; openRun: (id: string) => void }) {
  const data = useStore(s => s.wfData)
  const run = useStore(s => s.wfRun)
  const setRun = useStore(s => s.setWfRun)
  const loadWf = useStore(s => s.loadWf)
  const toast = useStore(s => s.toast)
  const ask = useConfirm(s => s.ask)
  if (!data) return <aside className="wf-side glass" />
  const blank = (): WfDef => ({
    id: '', builtin: false, name: '我的自定义流水线', description: '自由组合策划、找图、生图、视频与剪辑',
    steps: [
      { id: 'script', type: 'llm_script', name: '1. AI 分镜脚本', enabled: true, pause_after: true, config: { scene_count: 3, output_format: 'storyboard' } },
      { id: 'keyframes', type: 'image_gen', name: '2. 关键帧生图', enabled: true, pause_after: true, config: { scenes_from: 'script', ref_sources: [] } },
    ],
  })
  const delRun = async (id: string) => {
    if (!(await ask({ title: '删除这条运行记录？', body: '已生成的作品仍保留在作品库。', ok: '删除', danger: true }))) return
    try { await api.wf.deleteRun(id); if (run?.id === id) setRun(null); await loadWf() } catch (e) { toast(e instanceof Error ? e.message : '删除失败', 'err') }
  }
  const delTpl = async (id: string) => {
    if (!(await ask({ title: '删除这个模板？', ok: '删除', danger: true }))) return
    await api.wf.deleteTemplate(id); loadWf()
  }
  return (
    <aside className="wf-side glass">
      <div className="wf-side-h"><h2>模板</h2><span className={cx('tag', data.ffmpeg_available ? 'ok' : 'warn')}>FFmpeg {data.ffmpeg_available ? '就绪' : '未安装'}</span></div>
      <div className="wf-list">
        {[...data.builtin, ...data.custom].map(t => (
          <div key={t.id} className={cx('wf-item', !run && draft?.id === t.id && 'on')} role="button" tabIndex={0} onClick={() => onOpen(structuredClone(t))} onKeyDown={e => { if (e.key === 'Enter') onOpen(structuredClone(t)) }}>
            <div className="wt"><b>{t.name}</b>{t.builtin ? <span className="tag">内置</span> : <button className="iconbtn sm" onClick={e => { e.stopPropagation(); delTpl(t.id) }} aria-label="删除模板"><X size={12} /></button>}</div>
            <p>{t.description}</p>
            <small className="dim">{t.steps.length} 步 · 点开后点运行</small>
          </div>
        ))}
        <button className="btn sm ghost" onClick={() => onOpen(blank())}><Plus size={13} />空白工作流</button>
      </div>
      <div className="wf-side-h"><h2>运行记录</h2><span className="dim">{data.runs.length}</span></div>
      <div className="wf-list">
        {!data.runs.length && <span className="dim help">暂无</span>}
        {data.runs.map(r => (
          <div key={r.id} className={cx('wf-item', run?.id === r.id && 'on')} role="button" tabIndex={0} onClick={() => openRun(r.id)} onKeyDown={e => { if (e.key === 'Enter') openRun(r.id) }}>
            <div className="wt"><b>{r.workflow_name}</b><span className={cx('tag', RUN_TAG[r.status])}>{RUN_ZH[r.status]}</span>
              <button className="iconbtn sm" onClick={e => { e.stopPropagation(); delRun(r.id) }} aria-label="删除记录"><X size={12} /></button></div>
            <p>{r.topic || '（未填主题）'}</p>
            <div className="mini-prog"><i style={{ width: `${r.total_steps ? r.done_steps / r.total_steps * 100 : 0}%` }} /></div>
            <small className="dim">{r.done_steps}/{r.total_steps} 步{r.final_round_id ? ` · 成片 ${rid(r.final_round_id)}` : ''} · {ago(r.updated_at)}</small>
          </div>
        ))}
      </div>
    </aside>
  )
}

function RunCanvas({ run }: { run: WfRun }) {
  const data = useStore(s => s.wfData)!
  const setRun = useStore(s => s.setWfRun)
  const loadWf = useStore(s => s.loadWf)
  const toast = useStore(s => s.toast)
  const [topic, setTopic] = useState(run.topic)
  const [savingTpl, setSavingTpl] = useState(false)
  const [logOpen, setLogOpen] = useState(false)
  const timer = useRef(0)
  const pending = useRef<Pick<WfRun, 'topic' | 'workflow'> | null>(null)
  const writing = useRef<Promise<unknown> | null>(null)
  const [acting, setActing] = useState(false)
  const running = run.status === 'running'
  useEffect(() => { if (!running) setTopic(run.topic) }, [run.topic]) // eslint-disable-line react-hooks/exhaustive-deps

  const flush = async () => {
    clearTimeout(timer.current)
    if (writing.current) await writing.current
    const change = pending.current
    if (!change) return
    const write = api.wf.update(run.id, change)
    writing.current = write
    try {
      await write
      if (pending.current === change) pending.current = null
    } finally {
      if (writing.current === write) writing.current = null
    }
  }
  const save = (next: Partial<Pick<WfRun, 'topic' | 'workflow'>>) => {
    const merged = { ...run, ...next }
    pending.current = { topic: merged.topic, workflow: merged.workflow }
    setRun(merged)
    clearTimeout(timer.current)
    timer.current = window.setTimeout(() => { flush().catch(e => toast(e.message, 'err')) }, 450)
  }
  const setSteps = (steps: WfStep[]) => save({ workflow: { ...run.workflow, steps } })
  const act: RunAction = async (fn, msg) => {
    setActing(true)
    try {
      await flush()
      const r = await fn()
      if (useStore.getState().wfRun?.id === run.id) setRun(r.run)
      await loadWf()
      if (msg) toast(msg, 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '操作失败', 'err') }
    finally { setActing(false) }
  }
  const addStep = (type: WfStep['type']) => {
    const cat = data.step_catalog.find(c => c.type === type)!
    let id = type.replace(/_.*/, ''); let n = 1
    while (run.workflow.steps.some(s => s.id === id)) id = `${type.replace(/_.*/, '')}_${++n}`
    setSteps([...run.workflow.steps, { id, type, name: `${run.workflow.steps.length + 1}. ${cat.label}`, enabled: true, pause_after: false, config: structuredClone(cat.default_config) }])
  }
  const saveTpl = async (name: string) => {
    try { await api.wf.saveTemplate({ name, description: run.workflow.description, steps: templateSteps(run.workflow.steps) }); toast('已存为模板', 'ok'); loadWf() }
    catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
    setSavingTpl(false)
  }
  const done = run.workflow.steps.filter(s => ['done', 'skipped'].includes(run.step_states[s.id]?.status)).length
  const finalRid = [...run.workflow.steps].reverse().map(s => run.step_states[s.id]?.output?.final_round_id).find(Boolean) as string | undefined

  return (
    <div className="run" inert={acting}>
      <div className="run-head glass">
        <div className="row between">
          <div className="run-title"><h2>{run.workflow.name}</h2><span className={cx('tag', RUN_TAG[run.status])}>{RUN_ZH[run.status]}</span><span className="dim tabular">{done}/{run.workflow.steps.length} 步</span></div>
          <span className="grow" />
          <button className="btn sm ghost" onClick={() => setLogOpen(v => !v)}>日志 {run.logs.length}</button>
          <button className="btn sm ghost" onClick={() => setSavingTpl(true)} disabled={running}><Save size={13} />存为模板</button>
          {running ? <button className="btn sm danger" onClick={() => act(() => api.wf.cancel(run.id), '已终止')}><Square size={13} />终止</button>
            : run.status === 'paused' ? <button className="btn sm primary" onClick={() => act(() => api.wf.resume(run.id))}><Play size={13} />继续</button>
            : <button className="btn sm primary" onClick={() => act(() => api.wf.start(run.id, run.status === 'draft' ? undefined : run.workflow.steps[0]?.id), '开始执行')}><Play size={13} />{run.status === 'draft' ? '运行' : '从头再跑'}</button>}
        </div>
        <p className="dim">{run.workflow.description}</p>
        <textarea rows={2} value={topic} disabled={running} placeholder="写下这条流水线的主题，例如：雨夜霓虹街头的 3 镜头短片"
          onChange={e => { setTopic(e.target.value); save({ topic: e.target.value }) }} />
        <div className="run-prog"><i style={{ width: `${done / Math.max(1, run.workflow.steps.length) * 100}%` }} /></div>
        {run.status === 'paused' && run.pause_reason && <div className="warnbox"><Pause size={14} />{run.pause_reason}</div>}
        {run.status === 'error' && run.error && <div className="warnbox bad">{run.error}</div>}
        {finalRid && <FinalCut id={finalRid} />}
        <AnimatePresence>{logOpen && <motion.pre className="logbox sm" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>{run.logs.join('\n')}</motion.pre>}</AnimatePresence>
      </div>

      <ol className="rail">
        {run.workflow.steps.map((s, i) => (
          <StepCard key={s.id} run={run} step={s} idx={i} state={run.step_states[s.id]} onChange={st => setSteps(run.workflow.steps.map(x => x.id === s.id ? st : x))}
            onMove={d => { const a = [...run.workflow.steps]; const j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; setSteps(a) }}
            onRemove={() => setSteps(run.workflow.steps.filter(x => x.id !== s.id))}
            onAct={act} />
        ))}
      </ol>
      {!running && (
        <div className="add-step glass">
          <span className="lbl">添加步骤</span>
          <div className="chips">{data.step_catalog.map(c => <button key={c.type} className="chip" title={c.hint} onClick={() => addStep(c.type)}><span>{c.icon}</span>{c.label}</button>)}</div>
        </div>
      )}
      {savingTpl && <NamePrompt title="存为模板" initial={run.workflow.name} onClose={() => setSavingTpl(false)} onSubmit={saveTpl} />}
    </div>
  )
}

function FinalCut({ id }: { id: string }) {
  const r = useStore(s => s.rounds.find(x => x.id === id))
  const setWs = useStore(s => s.setWorkspace)
  const setViewing = useStore(s => s.setViewing)
  if (!r) return null
  return (
    <div className="final-cut">
      <img src={media.thumb(r)} alt="" />
      <div><b>成片 {rid(id)}</b><span className="dim">{r.duration_s ? `${r.duration_s} 秒 · ` : ''}{r.width}×{r.height}</span></div>
      <span className="grow" />
      <button className="btn sm" onClick={() => { setWs('video'); setViewing(id) }}>在舞台查看</button>
    </div>
  )
}

function StepCard({ run, step, idx, state, onChange, onMove, onRemove, onAct, draft, local }: {
  run?: WfRun; step: WfStep; idx: number; state?: StepState
  onChange: (s: WfStep) => void; onMove: (d: number) => void; onRemove: () => void
  onAct?: RunAction; local?: DraftFiles
  draft?: { steps: WfStep[] }
}) {
  const catIcon = useStore(s => s.wfData?.step_catalog.find(c => c.type === step.type)?.icon)
  const catLabel = useStore(s => s.wfData?.step_catalog.find(c => c.type === step.type)?.label)
  const st = state?.status || 'pending'
  const [open, setOpen] = useState(st === 'error' || run?.current_step_id === step.id)
  const running = run?.status === 'running'
  const hasOut = state && Object.keys(state.output || {}).length > 0
  const steps = run?.workflow.steps || draft?.steps || []
  useEffect(() => { if (run?.current_step_id === step.id) setOpen(true) }, [run?.current_step_id, step.id])
  return (
    <motion.li layout className={cx('step', `s-${st}`, !step.enabled && 'off')}>
      <span className="step-node">{st === 'running' ? <span className="spinner" /> : st === 'done' ? '✓' : idx + 1}</span>
      <div className="step-card glass">
        <div className="step-h" role="button" tabIndex={0} onClick={() => setOpen(v => !v)} onKeyDown={e => { if (e.key === 'Enter') setOpen(v => !v) }}>
          <span className="step-ic">{catIcon}</span>
          <div className="step-t"><b>{step.name}</b><small className="dim">{catLabel} · {step.id}{state?.progress ? ` · ${state.progress}` : ''}</small></div>
          <span className="grow" />
          {step.pause_after && <span className="tag">完成后暂停</span>}
          <span className={cx('tag', st === 'done' ? 'ok' : st === 'running' ? 'run' : st === 'error' ? 'bad' : '')}>{STEP_ZH[st]}</span>
          <ChevronDown size={15} className={cx('chev', open && 'up')} />
        </div>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div className="step-b" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}>
              <div className="step-inner">
                {state?.error && <div className="warnbox bad">{state.error}</div>}
                <div className="row wrap" inert={running}>
                  <input type="text" className="step-name" value={step.name} disabled={running} onChange={e => onChange({ ...step, name: e.target.value })} aria-label="步骤名" />
                  <Toggle on={step.enabled} onChange={v => onChange({ ...step, enabled: v })}>启用</Toggle>
                  <Toggle on={step.pause_after} onChange={v => onChange({ ...step, pause_after: v })}>完成后暂停</Toggle>
                </div>
                <StepConfig run={run} steps={steps} step={step} idx={idx} disabled={running} onChange={onChange} local={local} onAct={onAct} />
                {run && hasOut && <StepOutput run={run} step={step} state={state!} disabled={running} />}
                <div className="row wrap step-actions">
                  {run && <><button className="btn sm" disabled={running} onClick={() => onAct!(() => api.wf.retry(run.id, step.id, true), '只跑这一步')}><RotateCcw size={13} />只跑这一步</button>
                  <button className="btn sm" disabled={running} onClick={() => onAct!(() => api.wf.retry(run.id, step.id, false), '从这一步往后跑')}><Play size={13} />从这里往后跑</button></>}
                  <span className="grow" />
                  <button className="iconbtn sm" disabled={running || idx === 0} onClick={() => onMove(-1)} aria-label="上移"><ArrowUp size={14} /></button>
                  <button className="iconbtn sm" disabled={running || idx === steps.length - 1} onClick={() => onMove(1)} aria-label="下移"><ArrowDown size={14} /></button>
                  <button className="iconbtn sm" disabled={running} onClick={onRemove} aria-label="删除步骤"><Trash2 size={14} /></button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  )
}

function StepConfig({ run, steps, step, idx, disabled, onChange, local, onAct }: {
  run?: WfRun; steps: WfStep[]; step: WfStep; idx: number; disabled: boolean; onChange: (s: WfStep) => void
  local?: DraftFiles; onAct?: RunAction
}) {
  const cfg = useStore(s => s.cfg)
  const toast = useStore(s => s.toast)
  const open = useStore(s => s.openSheet)
  const fileRef = useRef<HTMLInputElement>(null)
  const prev = steps.slice(0, idx)
  const set = (k: string, v: unknown) => onChange({ ...step, config: { ...step.config, [k]: v } })
  const setPool = (pool: string[]) => onChange({ ...step, config: { ...step.config, gpu: pool[0], gpu_pool: pool } })
  const defaults = useStore(s => s.wfData?.step_catalog.find(c => c.type === step.type)?.default_config)
  const upload = (files: File[]) => {
    if (!files.length) return
    if (files.some(f => !['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > (cfg?.limits.upload_max_mb || 12) * 1048576)) {
      toast('请使用 12 MB 以内的 PNG、JPEG 或 WebP 图片', 'err')
      return
    }
    if (local) local.change([...local.files, ...files])
    else if (run && onAct) onAct(async () => {
      try {
        for (const file of files) await api.wf.uploadAsset(run.id, file, step.id)
      } catch (e) { toast(e instanceof Error ? e.message : '上传失败', 'err') }
      return api.wf.run(run.id)
    })
  }
  const field = (k: string, v: unknown) => {
    const label = LABELS[k] || k
    if (UPSTREAM[k]) return (
      <label className="field" key={k}><span className="fl">{label}</span>
        <select value={String(v || '')} disabled={disabled} onChange={e => set(k, e.target.value)}>
          <option value="">（无 / 手动）</option>
          {prev.filter(s => UPSTREAM[k].includes(s.type)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select></label>
    )
    if (k === 'ref_sources') return (
      <div className="field wide" key={k}><span className="fl">{label}</span>
        <div className="chips">{prev.filter(s => ['asset_input', 'web_asset_fetch', 'image_gen'].includes(s.type)).map(s => {
          const on = (v as string[] || []).includes(s.id)
          return <button key={s.id} disabled={disabled} className={cx('chip', on && 'on')} onClick={() => set(k, on ? (v as string[]).filter(x => x !== s.id) : [...(v as string[] || []), s.id])}>{s.name}</button>
        })}{!prev.length && <span className="dim">前面没有可引用的步骤</span>}</div></div>
    )
    if (k === 'model') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => set(k, e.target.value)}>{cfg?.image_models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}</select></label>
    if (k === 'gpu') return <label className="field" key={k}><span className="fl">{label}</span>
      <select value={String(v)} disabled={disabled} onChange={e => setPool([e.target.value])} title="切换首选 GPU 会重置候补列表">
        {cfg?.gpus.map(g => <option key={g.id} value={g.id}>{g.label}</option>)}
      </select></label>
    if (k === 'gpu_pool') {
      const primary = step.config.gpu
      const backups: string[] = Array.isArray(v) ? v.filter(id => id !== primary) : []
      return <div className="field wide" key={k}><span className="fl">{label}</span>
        <div className="chips" role="group" aria-label={label}>{cfg?.gpus.filter(g => g.id !== primary).map(g => {
          const pos = backups.indexOf(g.id)
          return <button type="button" key={g.id} className={cx('chip', pos >= 0 && 'on')} disabled={disabled}
            aria-label={g.label} aria-pressed={pos >= 0} onClick={() => setPool([primary, ...(pos >= 0 ? backups.filter(id => id !== g.id) : [...backups, g.id])])}>
            {g.label}{pos >= 0 && ` · ${pos + 1}`}
          </button>
        })}</div></div>
    }
    if (k === 'workflow') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => set(k, e.target.value)}>{cfg?.video_workflows.map(w => <option key={w.id} value={w.id}>{w.label}</option>)}</select></label>
    if (k === 'offload_mode') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => onChange({ ...step, config: { ...step.config, offload_mode: e.target.value, auto_offload: e.target.value !== 'none' } })}>{cfg?.video_offload_modes.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
    if (k === 'output_format') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => set(k, e.target.value)}><option value="storyboard">结构化分镜</option><option value="text">纯文本</option></select></label>
    if (k === 'transition') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => set(k, e.target.value)}><option value="fade">淡入淡出</option><option value="cut">硬切</option></select></label>
    if (k === 'role') return <label className="field" key={k}><span className="fl">{label}</span><select value={String(v)} disabled={disabled} onChange={e => set(k, e.target.value)}><option value="character">角色人设</option><option value="style">风格参考</option><option value="scene">场景参考</option></select></label>
    if (k === 'auto_offload' && step.config.offload_mode) return null
    if (typeof v === 'boolean' || typeof defaults?.[k] === 'boolean') return <div className="field" key={k}>
      <Toggle on={v === true} disabled={disabled} onChange={on => set(k, on)}>{label}</Toggle></div>
    if (Array.isArray(v)) return <label className="field" key={k}><span className="fl">{label}</span><input type="text" disabled={disabled} value={(v as string[]).join(', ')} placeholder="逗号分隔" onChange={e => set(k, e.target.value.split(/[,，\s]+/).filter(Boolean))} /></label>
    if (typeof v === 'number') return <label className="field" key={k}><span className="fl">{label}</span><input type="number" disabled={disabled} value={v} step={k === 'cfg' || k === 'fade_s' ? 0.05 : 1} onChange={e => set(k, +e.target.value)} /></label>
    const long = ['instruction', 'prompt_template', 'note'].includes(k)
    return long
      ? <label className="field wide" key={k}><span className="fl">{label}</span><textarea rows={2} disabled={disabled} value={String(v ?? '')} onChange={e => set(k, e.target.value)} /></label>
      : <label className="field" key={k}><span className="fl">{label}</span><input type="text" disabled={disabled} value={String(v ?? '')} onChange={e => set(k, e.target.value)} /></label>
  }
  return (
    <div className="step-cfg">
      {step.type === 'asset_input' && (
        <div className="field wide"><span className="fl">素材</span>
          <div className="asset-row">
            {run && (step.config.asset_files as string[] || []).map(f => (
              <figure key={f} className="ref-tile"><img src={media.assetThumb(run.id, f)} alt="" />
                {!disabled && <button className="ref-x" onClick={() => onAct?.(async () => {
                  await api.wf.deleteAsset(run.id, f)
                  return api.wf.run(run.id)
                })} aria-label="移除"><X size={12} /></button>}</figure>
            ))}
            {local?.files.map((file, i) => <LocalImage key={i} file={file} remove={() => local.change(local.files.filter((_, n) => n !== i))} />)}
            {!disabled && <button className="ref-add" onClick={() => fileRef.current?.click()}><Upload size={15} /><span>上传</span></button>}
            {!disabled && <button className="ref-add" onClick={() => open('picker', { onPick: (r: { id: string }) => set('round_ids', [...(step.config.round_ids || []), r.id]) })}><Copy size={15} /><span>从作品库</span></button>}
          </div>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={e => { if (e.target.files) upload([...e.target.files]); e.target.value = '' }} />
        </div>
      )}
      {Object.entries(step.config).filter(([k]) => !HIDDEN.has(k)).map(([k, v]) => field(k, v))}
    </div>
  )
}

function StepOutput({ run, step, state, disabled }: { run: WfRun; step: WfStep; state: StepState; disabled: boolean }) {
  const rounds = useStore(s => s.rounds)
  const setRun = useStore(s => s.setWfRun)
  const toast = useStore(s => s.toast)
  const out = state.output
  const saveOut = async (patch: Record<string, unknown>) => {
    try { const r = await api.wf.saveOutput(run.id, step.id, patch); setRun(r.run); toast('已保存修改', 'ok') } catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
  }
  const thumbs = (ids: string[]) => (
    <div className="out-grid">{ids.map(id => { const r = rounds.find(x => x.id === id); return r ? <figure key={id}><img src={media.thumb(r)} alt="" /><figcaption>{rid(id)}</figcaption></figure> : <figure key={id} className="missing"><figcaption>{rid(id)}</figcaption></figure> })}</div>
  )
  return (
    <div className="step-out">
      <span className="lbl">产出</span>
      {step.type === 'llm_script' && Array.isArray(out.scenes) && (
        <>
          {out.style_bible && <p className="help">风格基调：{out.style_bible}</p>}
          <div className="scenes">{(out.scenes as Record<string, string>[]).map((s, i) => (
            <div key={i} className="scene">
              <b>{i + 1}. {s.title}</b>
              <textarea rows={2} disabled={disabled} defaultValue={s.keyframe_prompt} onBlur={e => { if (e.target.value !== s.keyframe_prompt) { const scenes = [...out.scenes]; scenes[i] = { ...s, keyframe_prompt: e.target.value }; saveOut({ scenes }) } }} aria-label="关键帧提示词" />
              <small className="dim">{s.video_prompt} · {s.audio_notes}</small>
            </div>
          ))}</div>
        </>
      )}
      {step.type === 'llm_script' && out.format === 'text' && <pre className="logbox sm">{out.text}</pre>}
      {step.type === 'web_asset_fetch' && Array.isArray(out.images) && (
        <div className="out-grid">{(out.images as { filename: string; title: string }[]).map(im => <figure key={im.filename}><img src={media.assetThumb(run.id, im.filename)} alt="" /><figcaption>{im.title}</figcaption></figure>)}</div>
      )}
      {(step.type === 'image_gen' || step.type === 'video_gen') && Array.isArray(out.round_ids) && thumbs(out.round_ids)}
      {step.type === 'h3_prompt' && Array.isArray(out.items) && (
        <div className="scenes">{(out.items as { title: string; video_prompt: string }[]).map((it, i) => (
          <div key={i} className="scene"><b>{i + 1}. {it.title}</b>
            <textarea rows={3} disabled={disabled} defaultValue={it.video_prompt} onBlur={e => { if (e.target.value !== it.video_prompt) { const items = [...out.items]; items[i] = { ...it, video_prompt: e.target.value }; saveOut({ items }) } }} aria-label="视频提示词" /></div>
        ))}</div>
      )}
      {step.type === 'video_stitch' && out.final_round_id && <p className="help">已合成 {out.clip_count} 段，约 {out.duration_s} 秒，成片 {rid(out.final_round_id)}。</p>}
      {step.type === 'asset_input' && <p className="help">已登记素材，供后续步骤引用。</p>}
    </div>
  )
}
