// 创作台左侧：参数全部在这里，生成按钮钉在底部。
import { useMemo, useRef, useState } from 'react'
import { ChevronDown, Dices, Film, ImagePlus, Link2, Lock, Minus, Plus, RefreshCw, Save, Sparkles, Trash2, Wand2, X } from 'lucide-react'
import { api, media } from '../../api/client'
import type { ComfyPreset, LlmKind, Lora, StudioPreset } from '../../api/types'
import { cx, mp, parseHfLink, ratio, rid } from '../../lib/util'
import { comfyDraftFields, comfyPayload, useStore } from '../../store/store'
import { Field, Seg, Slider, Toggle } from '../../ui/Overlay'
import { NamePrompt } from '../../ui/NamePrompt'
import type { Draft } from '../../store/store'

const IMAGE_SIZES: [string, number, number][] = [['1:1', 1024, 1024], ['2:3', 768, 1152], ['3:2', 1152, 768], ['3:4', 896, 1152], ['4:3', 1152, 896], ['9:16', 768, 1344], ['16:9', 1344, 768], ['2:3 高清', 1024, 1536], ['3:2 高清', 1536, 1024]]
const VIDEO_SIZES: [string, number, number][] = [['16:9 横', 1280, 768], ['9:16 竖', 768, 1280], ['1:1', 768, 768], ['预览', 512, 768]]
const FRAMES: [number, string][] = [[124, '5 秒'], [175, '7 秒'], [243, '10 秒'], [345, '14 秒']]
const REF_TASKS: [Draft['videoTask'], string][] = [
  ['images', '参考图'], ['edit', '翻修原片'], ['continue', '续拍下一段'], ['motion', '白模 + 人设'],
]

export function Composer() {
  const ws = useStore(s => s.workspace)
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const cfg = useStore(s => s.cfg)
  const status = useStore(s => s.status)
  const gen = useStore(s => s.generate)
  const toast = useStore(s => s.toast)
  const open = useStore(s => s.openSheet)
  const video = ws === 'video'
  const mask = !video && draft.editMask
  const videoTask = video && draft.workflow === 'ref2va' && draft.videoTask !== 'images' ? draft.videoTask : undefined
  const optionalImages = videoTask === 'edit' || videoTask === 'continue'
  const useImages = !optionalImages || draft.videoUseImages
  const lim = cfg?.limits
  const [rewriting, setRewriting] = useState(false)
  const [savingPreset, setSavingPreset] = useState(false)
  const [histOpen, setHistOpen] = useState(false)
  const hist = useStore(s => s.promptHist)

  const held = (status?.colab.sessions || []).map(s => s.gpu.toUpperCase())
  const busy = !!status?.current
  const grabbing = status?.phase === 'starting' && !status.current

  const rewrite = async () => {
    if (!draft.idea.trim()) { toast('先写一句想法', 'err'); return }
    setRewriting(true)
    try {
      const refs = status?.references
      const keyframes = video && draft.workflow === 'fl2va'
      const hasFirst = draft.useFirstFrame && !!refs?.first.set
      const editing = !video && (!!mask || draft.useRef || draft.chain)
      const active = useStore.getState().llm?.active
      const r = await api.rewrite({
        provider_id: active?.provider_id, model: active?.model,
        text: draft.idea.trim(), mode: video ? 'video' : 'image', workflow: draft.workflow, num_frames: draft.frames,
        video_task: videoTask,
        edit_source_id: mask ? mask.source_id : undefined,
        editing, chain: !video && draft.chain, has_image: keyframes ? hasFirst : undefined,
        has_last_image: keyframes && !!refs?.last.set,
        ref_count: keyframes ? Number(hasFirst) + Number(!!refs?.last.set)
          : video ? (draft.workflow === 't2va' || !useImages ? 0 : (refs?.items.length || 0)) : (editing ? (draft.chain || mask ? 1 : (refs?.items.length || 0)) : 0),
      })
      patch({ prompt: r.prompt }); toast('已写入提示词', 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '改写失败', 'err') }
    setRewriting(false)
  }

  const savePreset = async (name: string) => {
    try {
      const r = await api.presets.save({
        name, mode: video ? 'video' : 'image', gpu: draft.gpu, width: draft.width, height: draft.height,
        steps: draft.steps, cfg: draft.cfg, loras: draft.loras.filter(l => l.repo_id),
        ...(video ? { workflow: draft.workflow, video_task: videoTask, num_frames: draft.frames, offload_mode: draft.offload } : draft.engine === 'comfyui' ? {
          engine: draft.engine, comfy: comfyPayload(draft),
        } : { engine: draft.engine, model: draft.model }),
      })
      if (status) useStore.setState({ status: { ...status, studio_presets: r.custom } })
      toast(`已保存预设「${name}」`, 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
    setSavingPreset(false)
  }

  return (
    <aside className="composer">
      <div className="composer-scroll">
        <PresetBar video={video} onSave={() => setSavingPreset(true)} />

        <section className="block">
          <h2>{video ? '视频工作流' : '引擎与模型'}</h2>
          {video ? <VideoMode /> : <ImageEngine />}
        </section>

        {videoTask && <VideoRefBoard />}
        {(!video || draft.workflow !== 't2va') && <section className="block">
          {optionalImages ? <Toggle on={draft.videoUseImages} onChange={v => patch({ videoUseImages: v })}>附加参考图</Toggle>
            : <h2>{mask ? '局部改图' : video && draft.workflow === 'fl2va' ? '首帧与尾帧' : videoTask === 'motion' ? '人设图' : '参考图'}</h2>}
          {useImages && <RefBoard video={video} />}
        </section>}

        <section className="block">
          <div className="block-h"><h2>提示词</h2><span className="dim kbd-hint">⌘/Ctrl + Enter</span></div>
          <Field label="一句话想法">
            <textarea rows={2} value={draft.idea} placeholder="例如：雨夜霓虹街头，撑透明雨伞的人回头微笑" onChange={e => patch({ idea: e.target.value })} />
          </Field>
          <div className="rewrite-row">
            <button className="btn rewrite" onClick={rewrite} disabled={rewriting}>{rewriting ? <span className="spinner" /> : <Wand2 size={14} />}{rewriting ? '改写中' : 'AI 改写为提示词'}</button>
            <ModelPicker />
          </div>
          <Field label={<span>提示词<button type="button" className="mini-link" onClick={() => patch({ prompt: draft.prompt + '{日落|雨夜|清晨}' })} title="多张生成时按种子抽取不同变体">{'{a|b|c}'}</button><button type="button" className="mini-link" onClick={() => setHistOpen(v => !v)}>历史</button></span>}>
            <textarea rows={4} value={draft.prompt} placeholder="写中文或英文提示词，支持 {日落|雨夜|清晨} 抽签" maxLength={lim?.prompt_max}
              onChange={e => patch({ prompt: e.target.value })} />
          </Field>
          {histOpen && (
            <div className="hist-pop">
              {hist.length ? hist.map((h, i) => <button key={i} onClick={() => { patch({ prompt: h }); setHistOpen(false) }}>{h.slice(0, 90)}</button>) : <span className="dim">还没有历史记录</span>}
            </div>
          )}
          <div className="counter">{draft.prompt.length} / {lim?.prompt_max ?? 12000}</div>
          <details className="neg">
            <summary>负面提示词</summary>
            <textarea rows={2} value={draft.negative} maxLength={lim?.negative_max} onChange={e => patch({ negative: e.target.value })} />
          </details>
        </section>

        <section className="block">
          <div className="block-h"><h2>{mask ? '采样' : '画幅与采样'}</h2>{!mask && <span className="mp-badge">{mp(draft.width, draft.height)} MP · {ratio(draft.width, draft.height)}</span>}</div>
          {!mask && <>
          <div className="chips">
            {(video ? VIDEO_SIZES : IMAGE_SIZES).map(([l, w, h]) => (
              <button key={l} className={cx('chip', draft.width === w && draft.height === h && 'on')} onClick={() => patch({ width: w, height: h })}>
                <i className="ar" style={{ width: Math.round(w / Math.max(w, h) * 13), height: Math.round(h / Math.max(w, h) * 13) }} />{l}
              </button>
            ))}
          </div>
          <div className="wh">
            <span>宽</span><Slider min={lim?.size_min ?? 512} max={lim?.size_max ?? 1536} step={lim?.size_step ?? 64} value={draft.width} onChange={v => patch({ width: v })} />
            <span>高</span><Slider min={lim?.size_min ?? 512} max={lim?.size_max ?? 1536} step={lim?.size_step ?? 64} value={draft.height} onChange={v => patch({ height: v })} />
          </div>
          <div className="row between">
            <span className="help">推荐约 {video ? '0.98 MP（1280×768 档）' : '1.05 MP（1024×1024 档）'}</span>
            <span className="row">
              <button className="btn sm ghost" onClick={() => patch({ width: draft.height, height: draft.width })}>交换宽高</button>
              <button className="btn sm" title="保持当前比例，把总像素对齐到推荐值" onClick={() => {
                const area = video ? 1280 * 768 : 1024 * 1024
                const lo = lim?.size_min ?? 512, hi = lim?.size_max ?? 1536, st = lim?.size_step ?? 64
                const fit = (v: number) => Math.min(hi, Math.max(lo, Math.round(v / st) * st))
                const r = draft.width / draft.height
                const w = fit(Math.sqrt(area * r)), h = fit(Math.sqrt(area / r))
                patch({ width: w, height: h }); toast(`已按当前比例调整为 ${w}×${h}`, 'ok')
              }}>最佳像素</button>
            </span>
          </div>
          </>}
          <Field label="采样步数" hint={video ? '视频推荐 30' : '常规 28–40，Turbo 可设 4–8'}>
            <Slider min={lim?.steps_min ?? 2} max={lim?.steps_max ?? 60} value={draft.steps} onChange={v => patch({ steps: v })} />
          </Field>
          <Field label="CFG" hint="提示词遵循强度，Turbo 通常 1.0">
            <Slider min={lim?.cfg_min ?? 1} max={lim?.cfg_max ?? 12} step={0.5} value={draft.cfg} onChange={v => patch({ cfg: v })} />
          </Field>
          <Field label="种子">
            <div className="row">
              <input type="number" value={draft.seed} placeholder="-1 随机" onChange={e => patch({ seed: e.target.value })} />
              <button className="iconbtn" title="随机固定一个种子" onClick={() => patch({ seed: String(Math.floor(Math.random() * 9_000_000)) })}><Dices size={15} /></button>
              <button className="iconbtn" title="用上一个作品的种子" onClick={() => { const s = useStore.getState().rounds[0]?.seed; if (s != null) patch({ seed: String(s) }); else toast('还没有作品', 'err') }}><Lock size={15} /></button>
              <button className="iconbtn" title="恢复为随机" onClick={() => patch({ seed: '-1' })}><RefreshCw size={15} /></button>
            </div>
          </Field>
          {video && (
            <Field label="显存卸载" hint="40G 及以下显存建议逐层">
              <select value={draft.offload} onChange={e => patch({ offload: e.target.value as Draft['offload'] })}>
                {(cfg?.video_offload_modes || []).map(o => <option key={o.id} value={o.id}>{o.label} · {o.hint}</option>)}
              </select>
            </Field>
          )}
        </section>

        <LoraBlock />

        <section className="block">
          <div className="block-h"><h2>算力</h2><button className="btn sm ghost" onClick={() => open('settings')}>抢卡</button></div>
          <GpuPicker held={held} />
        </section>
      </div>

      <div className="go-bar glass">
        <div className="stepper" title="一次生成几张，种子依次 +1">
          <button onClick={() => patch({ count: Math.max(1, draft.count - 1) })} disabled={draft.count <= 1}><Minus size={14} /></button>
          <span>{draft.count}</span>
          <button onClick={() => patch({ count: Math.min(lim?.count_max ?? 4, draft.count + 1) })} disabled={draft.count >= (lim?.count_max ?? 4)}><Plus size={14} /></button>
        </div>
        <button className="btn primary go" onClick={gen} disabled={grabbing}><Sparkles size={16} />{busy ? '加入队列' : '开始生成'}</button>
      </div>
      {savingPreset && <NamePrompt title="保存为预设" placeholder="例如：人像 2:3 精细" onClose={() => setSavingPreset(false)} onSubmit={savePreset} />}
    </aside>
  )
}

const KIND_LABEL: Record<LlmKind, string> = { openai: 'OpenAI', anthropic: 'Anthropic', gemini: 'Gemini' }

/** 改写用的模型。选项来自设置里配置的服务商，每家列出拉取到的模型 */
function ModelPicker() {
  const llm = useStore(s => s.llm)
  const open = useStore(s => s.openSheet)
  const toast = useStore(s => s.toast)
  if (!llm) return null
  const usable = llm.providers.filter(p => p.key_set && p.models.length)
  if (!usable.length) return <button className="btn sm ghost model-pick empty" onClick={() => open('settings', { focus: 'llm' })}>配置改写模型</button>
  const value = llm.active ? `${llm.active.provider_id}::${llm.active.model}` : ''
  const choose = async (v: string) => {
    if (v === '__settings') { open('settings', { focus: 'llm' }); return }
    const [pid, ...rest] = v.split('::')
    try { useStore.setState({ llm: await api.llm.setActive(pid, rest.join('::')) }) }
    catch (e) { toast(e instanceof Error ? e.message : '切换失败', 'err') }
  }
  return (
    <select className="model-pick" value={value} onChange={e => choose(e.target.value)} aria-label="改写用的模型" title="改写用的模型">
      {!value && <option value="">选择模型</option>}
      {usable.map(p => (
        <optgroup key={p.id} label={`${p.name} · ${KIND_LABEL[p.kind]}`}>
          {p.models.map(m => <option key={m} value={`${p.id}::${m}`}>{m}</option>)}
        </optgroup>
      ))}
      <option value="__settings">管理模型…</option>
    </select>
  )
}

function PresetBar({ video, onSave }: { video: boolean; onSave: () => void }) {
  const cfg = useStore(s => s.cfg)
  const status = useStore(s => s.status)
  const apply = useStore(s => s.applyPreset)
  const toast = useStore(s => s.toast)
  const mode = video ? 'video' : 'image'
  const all = useMemo(() => [...(status?.studio_presets || []), ...(cfg?.studio_presets.builtin || [])].filter(p => p.mode === mode), [status, cfg, mode])
  const del = async (id: string) => {
    try { const r = await api.presets.delete(id); if (status) useStore.setState({ status: { ...status, studio_presets: r.custom } }); toast('已删除预设', 'ok') }
    catch (e) { toast(e instanceof Error ? e.message : '删除失败', 'err') }
  }
  return (
    <div className="preset-bar">
      <select defaultValue="" onChange={e => { const p = all.find(x => x.id === e.target.value); if (p) apply(p); e.target.value = '' }} aria-label="参数预设">
        <option value="">参数预设</option>
        {(status?.studio_presets || []).filter(p => p.mode === mode).length > 0 && <optgroup label="我的预设">{(status?.studio_presets || []).filter(p => p.mode === mode).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>}
        <optgroup label="推荐">{(cfg?.studio_presets.builtin || []).filter(p => p.mode === mode).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>
      </select>
      <button className="btn sm" onClick={onSave}><Save size={13} />存预设</button>
      <PresetDelete presets={(status?.studio_presets || []).filter(p => p.mode === mode)} onDelete={del} />
    </div>
  )
}
function PresetDelete({ presets, onDelete }: { presets: StudioPreset[]; onDelete: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  if (!presets.length) return null
  return (
    <div className="pop-wrap">
      <button className="iconbtn sm" title="删除自定义预设" onClick={() => setOpen(v => !v)}><Trash2 size={14} /></button>
      {open && <div className="pop">{presets.map(p => <button key={p.id} onClick={() => { onDelete(p.id); setOpen(false) }}>删除「{p.name}」</button>)}</div>}
    </div>
  )
}

function ImageEngine() {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const cfg = useStore(s => s.cfg)
  const status = useStore(s => s.status)
  const toast = useStore(s => s.toast)
  if (!cfg) return null
  const saveModel = async () => {
    const m = draft.model.trim(); if (!m) return
    try { const r = await api.recentModels.add(m); if (status) useStore.setState({ status: { ...status, recent_models: r.recent_models } }); toast('已加入最近使用', 'ok') }
    catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
  }
  const removeModel = async (m: string) => {
    const r = await api.recentModels.remove(m)
    if (status) useStore.setState({ status: { ...status, recent_models: r.recent_models } })
  }
  return (
    <>
      <Seg ariaLabel="生图引擎" value={draft.engine} onChange={v => patch({ engine: v })} options={[{ id: 'diffusers', label: 'Diffusers' }, { id: 'comfyui', label: 'ComfyUI' }]} />
      {draft.engine === 'diffusers' ? (
        <>
          <Field label="生图模型">
            <div className="row">
              <input type="text" list="model-suggest" value={draft.model} placeholder="内置名或 owner/repo" onChange={e => patch({ model: e.target.value })} />
              <button className="btn sm" onClick={saveModel}>保存</button>
            </div>
          </Field>
          <datalist id="model-suggest">{cfg.image_models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}{(status?.recent_models || []).map(m => <option key={m} value={m} />)}</datalist>
          <p className="help">{cfg.image_models.find(m => m.id === draft.model)?.hint || '可直接填任意 Hugging Face Diffusers 仓库'}</p>
          {(status?.recent_models || []).length > 0 && (
            <div className="chips">{status!.recent_models.map(m => (
              <span key={m} className={cx('chip', draft.model === m && 'on')}><button onClick={() => patch({ model: m })}>{m.split('/').pop()}</button><button className="x" onClick={() => removeModel(m)} aria-label="移除"><X size={11} /></button></span>
            ))}</div>
          )}
          <details className="fold"><summary>内置预设</summary>
            <div className="chips">{cfg.image_models.map(m => <button key={m.id} className={cx('chip', draft.model === m.id && 'on')} onClick={() => patch({ model: m.id })} title={m.hint}>{m.label}</button>)}</div>
          </details>
          {draft.model === 'qwen-2.1-q5' && (
            <details className="fold" open><summary>自定义 GGUF 权重（留空用默认 Q5_K_M）</summary>
              <div className="g2">
                <input type="text" value={draft.ggufRepo} placeholder="仓库，默认 unsloth/Qwen-Image-2.1-GGUF" onChange={e => patch({ ggufRepo: e.target.value })} />
                <input type="text" value={draft.ggufFile} placeholder="文件名，默认 qwen-image-2.1-Q5_K_M.gguf" onChange={e => patch({ ggufFile: e.target.value })} />
              </div>
            </details>
          )}
        </>
      ) : <ComfyBox />}
    </>
  )
}

function ComfyBox() {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const cfg = useStore(s => s.cfg)!
  const status = useStore(s => s.status)
  const toast = useStore(s => s.toast)
  const [saving, setSaving] = useState(false)
  const apply = (p: ComfyPreset) => patch({ ...comfyDraftFields(p), steps: p.steps, cfg: p.cfg, width: p.width, height: p.height, loras: p.loras || [] })
  const onTemplate = (id: string) => {
    const t = cfg.comfy.templates.find(x => x.id === id); if (!t) return
    patch({ comfyTemplate: id, comfySampler: t.defaults.sampler, comfyScheduler: t.defaults.scheduler, comfyClipType: undefined, comfyDenoise: undefined })
  }
  const save = async (name: string) => {
    try {
      const r = await api.comfy.savePreset({ name, ...comfyPayload(draft), steps: draft.steps, cfg: draft.cfg, width: draft.width, height: draft.height, loras: draft.loras })
      if (status) useStore.setState({ status: { ...status, comfy_presets: r.presets } })
      toast('已保存组合方案', 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
    setSaving(false)
  }
  const del = async (id: string) => {
    const r = await api.comfy.deletePreset(id)
    if (status) useStore.setState({ status: { ...status, comfy_presets: r.presets } })
  }
  const link = (key: 'comfyDiff' | 'comfyTe' | 'comfyVae', label: string, ph: string) => {
    const v = draft[key]
    const spec = parseHfLink(v)
    return (
      <Field label={label}>
        <div className="row">
          <input type="text" value={v} placeholder={ph} onChange={e => patch({ [key]: e.target.value })} />
          {v && <button className="iconbtn" onClick={() => patch({ [key]: '' })} aria-label="清空"><X size={14} /></button>}
        </div>
        {spec && <span className="link-meta">{spec.repo} · {spec.file.split('/').pop()} · {spec.fmt}</span>}
      </Field>
    )
  }
  return (
    <>
      <div className="row between"><span className="dim">常用组合方案</span><button className="btn sm" onClick={() => setSaving(true)}>保存当前组合</button></div>
      {(status?.comfy_presets || []).length > 0 && (
        <div className="chips">{status!.comfy_presets.map(p => <span key={p.id} className="chip"><button onClick={() => apply(p)}>{p.name}</button><button className="x" onClick={() => del(p.id)} aria-label="删除"><X size={11} /></button></span>)}</div>
      )}
      <details className="fold" open><summary>内置推荐组合</summary>
        <div className="chips">{cfg.comfy.builtin_presets.map(p => <button key={p.id} className="chip" onClick={() => apply(p)}>{p.name}</button>)}</div>
      </details>
      <Field label="架构模板"><select value={draft.comfyTemplate} onChange={e => onTemplate(e.target.value)}>{cfg.comfy.templates.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</select></Field>
      {link('comfyDiff', '扩散模型（Diffusion / UNET）', '粘贴 HF 文件链接，支持 safetensors / NVFP4 / FP8 / GGUF')}
      {link('comfyTe', '文本编码器（Text Encoder / CLIP）', '粘贴 HF 文件链接')}
      {link('comfyVae', 'VAE', '粘贴 HF 文件链接')}
      <div className="g2">
        <Field label="采样器"><select value={draft.comfySampler} onChange={e => patch({ comfySampler: e.target.value })}>{cfg.comfy.samplers.map(s => <option key={s}>{s}</option>)}</select></Field>
        <Field label="调度器"><select value={draft.comfyScheduler} onChange={e => patch({ comfyScheduler: e.target.value })}>{cfg.comfy.schedulers.map(s => <option key={s}>{s}</option>)}</select></Field>
      </div>
      <div className="chips">
        <button className="chip" onClick={() => patch({ steps: 35, cfg: 5, comfySampler: 'euler', comfyScheduler: 'simple' })}>35 步精细 · CFG 5</button>
        <button className="chip" onClick={() => patch({ steps: 8, cfg: 1, comfySampler: 'euler', comfyScheduler: 'simple' })}>8 步 Turbo · CFG 1</button>
      </div>
      {saving && <NamePrompt title="保存 ComfyUI 组合方案" placeholder="例如：Omni BF16 + Turbo 8步" onClose={() => setSaving(false)} onSubmit={save} />}
    </>
  )
}

function VideoMode() {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const cfg = useStore(s => s.cfg)
  return (
    <>
      <div className="chips">{(cfg?.video_workflows || []).map(w => <button key={w.id} className={cx('chip', draft.workflow === w.id && 'on')} onClick={() => patch({ workflow: w.id })}>{w.label}</button>)}</div>
      {draft.workflow === 'ref2va' && <div className="chips" role="group" aria-label="参考用途">
        {REF_TASKS.map(([key, label]) => <button key={key} aria-pressed={draft.videoTask === key}
          className={cx('chip', draft.videoTask === key && 'on')} onClick={() => patch({ videoTask: key })}>{label}</button>)}
      </div>}
      <Field label="时长">
        <div className="chips">{FRAMES.map(([n, l]) => <button key={n} className={cx('chip', draft.frames === n && 'on')} onClick={() => patch({ frames: n })}>{l}<span className="dim">{n}f</span></button>)}</div>
        {!FRAMES.some(([n]) => n === draft.frames) && <span className="dim">当前 {draft.frames} 帧 · 约 {(draft.frames / 24).toFixed(1)} 秒</span>}
      </Field>
      <p className="help">{draft.workflow === 'ref2va' && draft.videoTask === 'continue'
        ? '时长指新生成的下一段。原片和续拍片段会分别保存在作品库。'
        : 'MiniMax-H3，24 fps，帧数自动对齐到 17 × n + 5。'}</p>
    </>
  )
}

function VideoRefBoard() {
  const clip = useStore(s => s.status?.references.video)
  const task = useStore(s => s.draft.videoTask)
  const frames = useStore(s => s.draft.frames)
  const maxFrames = useStore(s => s.cfg?.limits.frames_max ?? 345)
  const windowSeconds = (5 + 17 * Math.ceil((Math.min(frames, maxFrames) - 5) / 17)) / 24
  const maxMB = useStore(s => s.cfg?.limits.video_upload_max_mb ?? 64)
  const open = useStore(s => s.openSheet)
  const busy = useStore(s => s.videoRefBusy)
  const update = useStore(s => s.setVideoRef)
  const input = useRef<HTMLInputElement>(null)
  return <section className="block" aria-label="参考视频" aria-busy={busy}
    onDragOver={e => e.preventDefault()} onDrop={e => {
      e.preventDefault()
      const source = e.dataTransfer.getData('text/x-round') || e.dataTransfer.files[0]
      if (source && !busy) void update(source)
    }}>
    <div className="block-h"><h2>{task === 'motion' ? '白模视频' : '参考视频'}</h2>
      {clip && <span className="dim">{clip.source.startsWith('round:') ? rid(clip.source.slice(6)) : '已上传'} · {+clip.duration_s.toFixed(2)} 秒</span>}
    </div>
    {clip && (__MOCK__ && clip.source.startsWith('round:')
      ? <img className="ref-video" src={media.videoRef(clip.id)} alt="参考视频封面" />
      : <video className="ref-video" src={media.videoRef(clip.id)} controls playsInline preload="metadata" aria-label="参考视频预览" />)}
    <div className="row wrap">
      <button className="btn sm" disabled={busy} onClick={() => input.current?.click()}><Film size={14} />{busy ? '处理中…' : clip ? '更换视频' : '上传视频'}</button>
      <button className="btn sm ghost" disabled={busy} onClick={() => open('picker', { slot: 'video' })}>从作品库选视频</button>
      {clip && <button className="iconbtn sm" aria-label="移除参考视频" disabled={busy} onClick={() => update(null)}><X size={14} /></button>}
    </div>
    <input ref={input} type="file" accept="video/mp4,.mp4" hidden onChange={e => {
      const file = e.target.files?.[0]; e.target.value = ''; if (file) void update(file)
    }} />
    <p className="help">MP4 · 2–15 秒 · 最大 {maxMB} MB{task === 'motion' ? '。动作、节奏和运镜取自白模，角色外观取自第一张人设图。' : ''}</p>
    {clip && clip.duration_s > windowSeconds && <p className="help">{task === 'continue'
      ? `续拍会参考原片最后 ${windowSeconds.toFixed(1)} 秒。`
      : `本次生成会参考原片前 ${windowSeconds.toFixed(1)} 秒。`}</p>}
  </section>
}

function RefBoard({ video }: { video: boolean }) {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const refs = useStore(s => s.status?.references ?? null)
  const toast = useStore(s => s.toast)
  const open = useStore(s => s.openSheet)
  const fileRef = useRef<HTMLInputElement>(null)
  const characterFile = useRef<HTMLInputElement>(null)
  const [slot, setSlot] = useState<'first' | 'last'>('first')
  const source = useStore(s => s.rounds.find(r => r.id === draft.editMask?.source_id))
  if (!video && draft.editMask) return <div className="mask-source">
    {source ? <img src={media.thumb(source)} alt="局部改图原图" /> : <span className="dim">原图已移除</span>}
    <div><b>{rid(draft.editMask.source_id)}</b>{source && <span className="dim"> · {source.width}×{source.height}</span>}
      <div className="row wrap"><button className="btn sm" disabled={!source} onClick={() => open('mask', { id: source?.id })}>调整选区</button>
        <button className="btn sm ghost" onClick={() => patch({ editMask: null })}>退出局部改图</button></div>
    </div>
  </div>
  if (!refs) return null
  const keyframes = video && draft.workflow === 'fl2va'
  const character = video && draft.workflow === 'ref2va' && draft.videoTask === 'motion'
  const needs = video ? draft.videoTask === 'images' || draft.videoTask === 'motion' : draft.useRef && !draft.chain
  const upload = async (files: FileList | File[], target: 'first' | 'last', append: boolean) => {
    for (const f of keyframes ? [...files].slice(0, 1) : [...files]) {
      if (!/^image\/(png|jpeg|webp)$/.test(f.type)) { toast('只支持 PNG / JPEG / WebP', 'err'); return }
      if (f.size > 12 * 1048576) { toast('图片超过 12MB', 'err'); return }
      try { const r = await api.uploadRef(f, target, append); const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: r.references } }); append = true }
      catch (e) { toast(e instanceof Error ? e.message : '上传失败', 'err'); return }
    }
    if (target === 'first' && !video) patch({ useRef: true, chain: false })
    if (target === 'first' && keyframes) patch({ useFirstFrame: true })
    toast(target === 'last' ? '尾帧已上传' : keyframes ? '首帧已上传' : '参考图已上传', 'ok')
  }
  const remove = async (id: string) => {
    const r = await api.removeRef(id); const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: r.references } })
  }
  const clearLast = async () => { const r = await api.clearSlot('last'); const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: r.references } }) }
  const onDrop = (e: React.DragEvent, target: 'first' | 'last') => {
    e.preventDefault()
    const rid = e.dataTransfer.getData('text/x-round')
    const append = target === 'first' && !keyframes
    if (rid) { api.useRound(rid, target, append).then(r => {
      const st = useStore.getState().status
      if (st) useStore.setState({ status: { ...st, references: r.references } })
      if (!video) patch({ useRef: true, chain: false })
      if (keyframes && target === 'first') patch({ useFirstFrame: true })
    }).catch(err => toast(err.message, 'err')) }
    else if (e.dataTransfer.files.length) upload(e.dataTransfer.files, target, append)
  }
  if (keyframes) return <div>
    {(['first', 'last'] as const).map(target => {
      const first = target === 'first'
      const label = first ? '首帧' : '尾帧'
      const selected = refs[target].set && (!first || draft.useFirstFrame)
      return <div key={target} className="last-frame" onDrop={e => onDrop(e, target)} onDragOver={e => e.preventDefault()}>
        <span className="dim">{label}</span>
        {selected && <figure className="ref-tile"><img src={media.slot(target, refs[target].updated_at)} alt={label} />
          <button className="ref-x" aria-label={first ? '本次不用首帧' : '移除尾帧'} onClick={() => first ? patch({ useFirstFrame: false }) : clearLast().catch(e => toast(e.message, 'err'))}><X size={12} /></button></figure>}
        {first && !selected && refs.first.set && <button className="btn sm" onClick={() => patch({ useFirstFrame: true })}>使用现有首帧</button>}
        <button className="btn sm" onClick={() => { setSlot(target); fileRef.current?.click() }}>{selected ? '更换' : '上传'}{label}</button>
        <button className="btn sm ghost" onClick={() => open('picker', { slot: target, keyframe: first })}>从作品库选{label}</button>
      </div>
    })}
    <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e => { if (e.target.files?.length) void upload(e.target.files, slot, false); e.target.value = '' }} />
  </div>
  return (
    <div onDragOver={e => e.preventDefault()}>
      {!video && (
        <div className="row wrap">
          <Toggle on={draft.useRef} onChange={v => patch({ useRef: v, chain: v ? false : draft.chain })}>用参考图改图</Toggle>
          <Toggle on={draft.chain} onChange={v => patch({ chain: v, useRef: v ? false : draft.useRef })} title="自动取最新作品当参考图">接着改</Toggle>
        </div>
      )}
      <div className="ref-grid">
        {refs.items.map((it, i) => (
          <figure key={it.id} className="ref-tile">
            <img src={media.ref(it.id, it.updated_at)} alt={character && i === 0 ? '人设图' : '参考图'} />
            {character && i === 0 && <figcaption className="tile-id">人设图</figcaption>}
            <button className="ref-x" onClick={() => remove(it.id)} aria-label="移除"><X size={12} /></button>
          </figure>
        ))}
        {refs.items.length < refs.max && (video || !draft.chain) && (
          <button className="ref-add" onClick={() => { setSlot('first'); fileRef.current?.click() }} onDrop={e => onDrop(e, 'first')} onDragOver={e => e.preventDefault()}>
            <ImagePlus size={16} /><span>{refs.items.length ? '再加一张' : character ? '上传人设图' : '上传、拖入或粘贴'}</span>
          </button>
        )}
      </div>
      <div className="row wrap">
        {character && <>
          <button className="btn sm ghost" onClick={() => open('picker', { slot: 'first', character: true })}>从作品库选人设图</button>
          {refs.first.set && <button className="btn sm ghost" onClick={() => characterFile.current?.click()}>上传替换人设图</button>}
          <input ref={characterFile} type="file" aria-label="上传替换人设图" accept="image/png,image/jpeg,image/webp" hidden onChange={e => {
            if (e.target.files?.length) void upload(e.target.files, 'first', false)
            e.target.value = ''
          }} />
        </>}
        {(!character || (refs.first.set && refs.items.length < refs.max)) && <button className="btn sm ghost" onClick={() => open('picker', { slot: 'first' })}>
          {character ? '从作品库追加参考图' : '从作品库挑选'}</button>}
        {!video && <button className="btn sm ghost" onClick={() => open('picker', { onPick: (r: { id: string }) => open('mask', { id: r.id }) })}>选图局部修改</button>}
        {refs.items.length > 0 && <button className="btn sm ghost" onClick={async () => { const r = await api.clearSlot('first'); const st = useStore.getState().status; if (st) useStore.setState({ status: { ...st, references: r.references } }); patch({ useRef: false }) }}>清空全部</button>}
        <span className="dim">{refs.items.length}/{refs.max}</span>
      </div>
      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={e => { if (e.target.files) upload(e.target.files, 'first', refs.items.length > 0); e.target.value = '' }} />
      {needs && !refs.first.set && <p className="help warn-text">{video && draft.videoTask === 'motion' ? '请添加一张人设图' : '当前设置需要参考图'}</p>}
    </div>
  )
}

function LoraBlock() {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const toast = useStore(s => s.toast)
  const rows = draft.loras.length ? draft.loras : [{ repo_id: '', weight_name: '', scale: 1 }]
  const set = (i: number, p: Partial<Lora>) => patch({ loras: rows.map((r, j) => j === i ? { ...r, ...p } : r) })
  // 删到只剩一行时清空它，而不是让区块消失
  const remove = (i: number) => patch({ loras: rows.length > 1 ? rows.filter((_, j) => j !== i) : [] })
  const scan = async (i: number) => {
    const repo = rows[i].repo_id.trim()
    const m = repo.match(/huggingface\.co\/([^/]+\/[^/]+)/)
    const id = m ? m[1] : repo
    try {
      const r = await api.listLoras(id)
      if (r.files.length) set(i, { repo_id: id, weight_name: r.files[0] })
      toast(`找到 ${r.files.length} 个权重`, 'ok')
    } catch (e) { toast(e instanceof Error ? e.message : '扫描失败', 'err') }
  }
  const used = rows.filter(r => r.repo_id.trim()).length
  return (
    <details className="block fold-block">
      <summary><Link2 size={14} />LoRA 挂载<span className="dim">{used ? `已挂 ${used} 个` : '未启用'}</span><ChevronDown size={14} className="chev" /></summary>
      {rows.slice(0, 4).map((r, i) => (
        <div className="lora" key={i}>
          <div className="row">
            <input type="text" value={r.repo_id} placeholder={`LoRA ${i + 1} · owner/repo 或文件链接`} onChange={e => set(i, { repo_id: e.target.value })} />
            <button className="btn sm" onClick={() => scan(i)}>扫描</button>
            <button className="iconbtn sm" onClick={() => remove(i)} title={rows.length > 1 ? '移除这个 LoRA' : '清空'} aria-label="移除 LoRA" disabled={rows.length === 1 && !r.repo_id && !r.weight_name}><Trash2 size={14} /></button>
          </div>
          <div className="row">
            <input type="text" value={r.weight_name} placeholder="权重文件 .safetensors" onChange={e => set(i, { weight_name: e.target.value })} />
            <Slider min={0} max={2.5} step={0.05} value={r.scale} onChange={v => set(i, { scale: v })} />
          </div>
        </div>
      ))}
      {rows.length < 4 && <button className="btn sm ghost" onClick={() => patch({ loras: [...rows, { repo_id: '', weight_name: '', scale: 1 }] })}><Plus size={13} />再加一个</button>}
      <p className="help">填 Hugging Face 仓库 ID 或直接粘贴 .safetensors 链接。MiniMax-H3 会自动转换 ComfyUI 格式的 LoRA。</p>
    </details>
  )
}

function GpuPicker({ held }: { held: string[] }) {
  const draft = useStore(s => s.draft)
  const patch = useStore(s => s.patchDraft)
  const cfg = useStore(s => s.cfg)
  const status = useStore(s => s.status)
  const open = useStore(s => s.openSheet)
  if (!status?.colab.authed) return <p className="help">还没连接 Google Colab。<button className="mini-link" onClick={() => open('settings')}>去设置连接</button></p>
  if (!held.length) return <p className="help">还没有持有的算力。<button className="mini-link" onClick={() => open('settings')}>去设置抢卡</button></p>
  const current = held.includes(draft.gpu) ? draft.gpu : held[0]
  return (
    <div className="gpu-list">
      {held.map(id => {
        const meta = cfg?.gpus.find(g => g.id === id)
        const sess = status.colab.sessions.find(s => s.gpu.toUpperCase() === id)
        return (
          <button key={id} className={cx('gpu-item', current === id && 'on')} onClick={() => patch({ gpu: id })}>
            <span className={cx('radio', current === id && 'on')} />
            <span className="gpu-main"><b>{meta?.label || id}</b><small>{[sess?.shape, sess?.endpoint].filter(Boolean).join(' · ')}</small></span>
            <span className="tag run">持有中</span>
          </button>
        )
      })}
      <p className="help">{held.length > 1 ? '点选这次生成用哪张卡。要申请新卡，去设置里抢卡。' : '生成会直接复用这张卡。'}</p>
    </div>
  )
}
