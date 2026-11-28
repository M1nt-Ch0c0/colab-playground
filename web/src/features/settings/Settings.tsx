// 设置抽屉：Colab 账号、抢卡、出口代理、空闲释放、HF Token、存储与外观。
import { Bot, Cpu, HardDrive, KeyRound, LogOut, Palette, Pencil, Plus, Power, RefreshCw, Settings as Gear, Timer, Trash2, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { LlmKind, LlmProvider } from '../../api/types'
import { LS_KEYS, ago, cx, fmtBytes, lsSet } from '../../lib/util'
import { useStore } from '../../store/store'
import { Drawer, Seg, Toggle, useConfirm } from '../../ui/Overlay'

import { ProxyBox } from './ProxyBox'

const IDLE = [0, 5, 10, 20, 30, 60]

export function SettingsSheet() {
  const close = useStore(s => s.closeSheet)
  return (
    <Drawer title="设置" icon={<Gear size={16} />} onClose={close}>
      <ColabAccount />
      <GrabBox />
      <IdleBox />
      <ProxyBox />
      <LlmBox />
      <HfBox />
      <StorageBox />
      <AppearanceBox />
    </Drawer>
  )
}

function ColabAccount() {
  const c = useStore(s => s.status?.colab)
  const toast = useStore(s => s.toast)
  const refresh = useStore(s => s.refresh)
  const ask = useConfirm(s => s.ask)
  const [url, setUrl] = useState(''); const [code, setCode] = useState(''); const [busy, setBusy] = useState(false)
  if (!c) return null
  const start = async () => {
    try { const r = await api.colab.authStart(); setUrl(r.auth_url); window.open(r.auth_url, '_blank', 'noopener') }
    catch (e) { toast(e instanceof Error ? e.message : '无法开始授权', 'err') }
  }
  const complete = async () => {
    setBusy(true)
    try { await api.colab.authComplete(code.trim()); setUrl(''); setCode(''); toast('Colab 已连接', 'ok'); refresh() }
    catch (e) { toast(e instanceof Error ? e.message : '授权失败', 'err') }
    setBusy(false)
  }
  const logout = async () => {
    if (!(await ask({ title: '断开 Google Colab？', body: '会清除本机保存的授权。正在运行的实例不会被释放。', ok: '断开', danger: true }))) return
    await api.colab.logout(); refresh()
  }
  return (
    <section className="sect card">
      <h4><Zap size={14} />Google Colab</h4>
      {c.authed ? (
        <>
          <div className="kv">
            <span>账号</span><span>{c.email || '已授权'}</span>
            <span>余额</span><span className="tabular">{c.balance == null ? '—' : `${Number(c.balance).toFixed(1)} CU`}</span>
            <span>消耗</span><span className="tabular">{c.rate_per_hour ? `${Number(c.rate_per_hour).toFixed(1)} CU / 小时` : '当前不计费'}</span>
          </div>
          {c.error && <div className="warnbox">{c.error}</div>}
          <div className="row"><span className="grow" /><button className="btn sm ghost" onClick={logout}><LogOut size={13} />断开</button></div>
        </>
      ) : (
        <>
          <p className="help">连接后才能申请 GPU。授权在新窗口完成，把页面显示的授权码粘贴回来。</p>
          {!url ? <button className="btn primary" onClick={start}>连接 Google 账号</button> : (
            <div className="row"><input type="text" value={code} placeholder="粘贴授权码" onChange={e => setCode(e.target.value)} /><button className="btn primary" disabled={!code.trim() || busy} onClick={complete}>完成</button></div>
          )}
        </>
      )}
    </section>
  )
}

function GrabBox() {
  const st = useStore(s => s.status)
  const cfg = useStore(s => s.cfg)
  const pool = useStore(s => s.grabPool)
  const rounds = useStore(s => s.pollRounds)
  const allPx = useStore(s => s.pollAllProxies)
  const toast = useStore(s => s.toast)
  const refresh = useStore(s => s.refresh)
  const ask = useConfirm(s => s.ask)
  if (!st || !cfg) return null
  const c = st.colab
  const lim = cfg.limits
  const grabbing = st.phase === 'starting' && !st.current
  const setPool = (p: string[]) => { lsSet(LS_KEYS.grab, p); useStore.setState({ grabPool: p }) }
  const toggle = (id: string) => setPool(pool.includes(id) ? pool.filter(x => x !== id) : [...pool, id])
  const move = (id: string, d: number) => { const i = pool.indexOf(id); const j = i + d; if (i < 0 || j < 0 || j >= pool.length) return; const p = [...pool]; [p[i], p[j]] = [p[j], p[i]]; setPool(p) }
  const grab = async () => {
    try { await api.colab.grab({ gpu_pool: pool, poll_rounds: rounds, poll_all_proxies: allPx }); toast(`开始抢卡：${pool.join(' → ')}`, 'ok'); refresh() }
    catch (e) { toast(e instanceof Error ? e.message : '抢卡失败', 'err') }
  }
  const release = async () => {
    if (!(await ask({ title: '释放全部算力？', body: '会停止当前任务、清空队列并关闭所有 Colab 实例，停止计费。', ok: '释放', danger: true }))) return
    await api.release(); toast('正在释放', 'ok'); refresh()
  }
  return (
    <section className="sect card">
      <h4><Cpu size={14} />算力</h4>
      {c.sessions.length > 0 ? (
        <div className="sess-list">{c.sessions.map(s => (
          <div key={s.name} className="sess"><i className="dot ok" /><b>{s.gpu}</b><span className="dim">{s.shape}</span><span className="grow" /><span className="dim mono">{s.name}</span></div>
        ))}</div>
      ) : <p className="help">当前没有持有任何实例。</p>}
      <div className="lbl">抢卡顺序 <span className="dim">按顺序尝试，抢到第一张就停</span></div>
      <div className="grab-list">
        {cfg.gpus.map(g => {
          const on = pool.includes(g.id)
          const h = c.gpu_health[g.id]
          const eligible = !c.eligible_gpus.length || c.eligible_gpus.includes(g.id)
          return (
            <div key={g.id} className={cx('grab-row', on && 'on', !eligible && 'off')}>
              <button className={cx('check', on && 'on')} disabled={!eligible} onClick={() => toggle(g.id)} aria-label={`选择 ${g.label}`} />
              <span className="gpu-main"><b>{g.label}</b><small>{g.hint}</small></span>
              {h && <span className={cx('tag', h.status === 'ok' ? 'ok' : h.status === 'unavailable' ? 'warn' : 'bad')} title={ago(h.at)}>{h.status === 'ok' ? '可用' : h.status === 'unavailable' ? '无库存' : '出错'}</span>}
              {!eligible && <span className="tag">账号不可用</span>}
              {on && <span className="ord tabular">{pool.indexOf(g.id) + 1}</span>}
              {on && <span className="ord-btns"><button onClick={() => move(g.id, -1)} aria-label="上移">↑</button><button onClick={() => move(g.id, 1)} aria-label="下移">↓</button></span>}
            </div>
          )
        })}
      </div>
      <div className="row wrap">
        <span className="lbl">轮询</span>
        <input type="number" className="inl" min={lim.poll_rounds_min} max={lim.poll_rounds_max} value={rounds} onChange={e => { const v = Math.max(lim.poll_rounds_min, Math.min(lim.poll_rounds_max, +e.target.value || 1)); lsSet(LS_KEYS.rounds, v); useStore.setState({ pollRounds: v }) }} />
        <span className="dim">轮</span>
        <Toggle on={allPx} onChange={v => { lsSet(LS_KEYS.pollpx, v); useStore.setState({ pollAllProxies: v }) }}>每轮换遍所有出口</Toggle>
      </div>
      <div className="row">
        <button className="btn primary grow-btn" disabled={!c.authed || !pool.length || grabbing || !!st.current} onClick={grab}>{grabbing ? <><span className="spinner" />正在抢卡</> : '开始抢卡'}</button>
        <button className="btn danger" disabled={!c.any_running && st.phase !== 'starting'} onClick={release}><Power size={14} />释放全部</button>
      </div>
    </section>
  )
}

function IdleBox() {
  const st = useStore(s => s.status)
  const toast = useStore(s => s.toast)
  const refresh = useStore(s => s.refresh)
  if (!st) return null
  const set = async (m: number) => { try { await api.setIdle(m); toast(m ? `空闲 ${m} 分钟后释放` : '已设为一直持有', 'ok'); refresh() } catch (e) { toast(e instanceof Error ? e.message : '设置失败', 'err') } }
  return (
    <section className="sect card">
      <h4><Timer size={14} />空闲释放</h4>
      <div className="chips">{IDLE.map(m => <button key={m} className={cx('chip', st.idle_minutes === m && 'on')} onClick={() => set(m)}>{m ? `${m} 分钟` : '一直持有'}</button>)}</div>
      <p className="help">没有任务时开始倒计时，到点自动关掉实例。选「一直持有」要记得手动释放，否则持续计费。</p>
    </section>
  )
}

const KINDS: { id: LlmKind; label: string; base: string; keyHint: string }[] = [
  { id: 'openai', label: 'OpenAI', base: 'https://api.openai.com/v1', keyHint: 'sk-…，兼容 OpenAI 协议的网关也选这个' },
  { id: 'anthropic', label: 'Anthropic', base: 'https://api.anthropic.com', keyHint: 'sk-ant-…' },
  { id: 'gemini', label: 'Gemini', base: 'https://generativelanguage.googleapis.com', keyHint: 'AIza…' },
]
const kindLabel = (k: LlmKind) => KINDS.find(x => x.id === k)?.label || k

function LlmBox() {
  const llm = useStore(s => s.llm)
  const load = useStore(s => s.loadLlm)
  const toast = useStore(s => s.toast)
  const focus = useStore(s => s.sheetArgs.focus)
  const ask = useConfirm(s => s.ask)
  const [editing, setEditing] = useState<LlmProvider | 'new' | null>(null)
  const [busy, setBusy] = useState('')
  const ref = useRef<HTMLElement>(null)
  useEffect(() => { load() }, [load])
  useEffect(() => { if (focus === 'llm') ref.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [focus])
  const providers = llm?.providers || []

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    try { await fn() } catch (e) { toast(e instanceof Error ? e.message : '操作失败', 'err') }
    setBusy('')
  }
  const fetchModels = (p: LlmProvider) => run('m' + p.id, async () => {
    const st = await api.llm.fetchModels(p.id)
    useStore.setState({ llm: st })
    const n = st.providers.find(x => x.id === p.id)?.models.length || 0
    toast(`「${p.name}」拉到 ${n} 个模型`, 'ok')
  })
  const test = (p: LlmProvider) => run('t' + p.id, async () => {
    const r = await api.llm.test(p.id, llm?.active?.provider_id === p.id ? llm.active.model : undefined)
    toast(r.ok ? `连通 · ${r.model} · ${r.ms}ms` : `连不上：${r.error}`, r.ok ? 'ok' : 'err')
  })
  const remove = async (p: LlmProvider) => {
    if (!(await ask({ title: `删除「${p.name}」？`, body: '服务器上保存的 API Key 会一起删除。', ok: '删除', danger: true }))) return
    run('d' + p.id, async () => { useStore.setState({ llm: await api.llm.remove(p.id) }); toast('已删除', 'ok') })
  }

  return (
    <section className="sect card" ref={ref}>
      <h4><Bot size={14} />改写模型</h4>
      <p className="help">「AI 改写为提示词」用这里的模型。Key 只存在服务器上，页面不回显。</p>
      {providers.length > 0 && (
        <div className="llm-list">
          {providers.map(p => {
            const active = llm?.active?.provider_id === p.id
            return (
              <div key={p.id} className={cx('llm-row', active && 'on')}>
                <div className="llm-main">
                  <div className="row"><b>{p.name}</b><span className="tag">{kindLabel(p.kind)}</span>{active && <span className="tag run">使用中 · {llm!.active!.model}</span>}</div>
                  <small className="mono dim">{p.base_url}</small>
                  <small className="dim">{p.key_set ? `Key ${p.key_masked}` : '未填 Key'} · {p.models.length ? `${p.models.length} 个模型${p.models_fetched_at ? ` · ${ago(p.models_fetched_at)}拉取` : ''}` : '还没拉取模型'}</small>
                </div>
                <div className="llm-acts">
                  <button className="iconbtn sm" title="拉取模型列表" disabled={!!busy || !p.key_set} onClick={() => fetchModels(p)}>{busy === 'm' + p.id ? <span className="spinner" /> : <RefreshCw size={14} />}</button>
                  <button className="btn sm ghost" disabled={!!busy || !p.key_set || !p.models.length} onClick={() => test(p)}>{busy === 't' + p.id ? <span className="spinner" /> : '测试'}</button>
                  <button className="iconbtn sm" title="编辑" onClick={() => setEditing(p)}><Pencil size={14} /></button>
                  <button className="iconbtn sm" title="删除" disabled={!!busy} onClick={() => remove(p)}><Trash2 size={14} /></button>
                </div>
              </div>
            )
          })}
        </div>
      )}
      {editing ? (
        <LlmForm key={editing === 'new' ? 'new' : editing.id} initial={editing === 'new' ? null : editing} onDone={() => setEditing(null)} />
      ) : (
        <button className="btn sm" onClick={() => setEditing('new')}><Plus size={13} />添加服务商</button>
      )}
    </section>
  )
}

function LlmForm({ initial, onDone }: { initial: LlmProvider | null; onDone: () => void }) {
  const toast = useStore(s => s.toast)
  const [kind, setKind] = useState<LlmKind>(initial?.kind || 'openai')
  const [name, setName] = useState(initial?.name || '')
  const [base, setBase] = useState(initial?.base_url || KINDS[0].base)
  const [key, setKey] = useState('')
  const [models, setModels] = useState((initial?.models || []).join(', '))
  const [enhanced, setEnhanced] = useState(initial?.enhanced_rewrite || false)
  const [saving, setSaving] = useState(false)
  const meta = KINDS.find(k => k.id === kind)!
  // 切换类型时，如果 BASE_URL 还是上一个类型的默认值，就跟着换
  const switchKind = (k: LlmKind) => {
    if (!base.trim() || KINDS.some(x => x.base === base.trim())) setBase(KINDS.find(x => x.id === k)!.base)
    setKind(k)
  }
  const save = async () => {
    setSaving(true)
    try {
      const list = models.split(/[,，\s]+/).map(m => m.trim()).filter(Boolean)
      const st = await api.llm.save({ id: initial?.id, kind, name: name.trim() || meta.label, base_url: base.trim(), api_key: key.trim() || undefined, models: list, enhanced_rewrite: enhanced })
      useStore.setState({ llm: st })
      toast(initial ? '已保存' : `已添加「${name.trim() || meta.label}」`, 'ok')
      onDone()
    } catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') }
    setSaving(false)
  }
  return (
    <div className="llm-form">
      <Seg ariaLabel="服务商类型" value={kind} onChange={switchKind} options={KINDS.map(k => ({ id: k.id, label: k.label }))} />
      <label className="field"><span className="fl">名称</span><input id="llm-name" type="text" value={name} placeholder={meta.label} onChange={e => setName(e.target.value)} /></label>
      <label className="field"><span className="fl">BASE_URL</span><input id="llm-base" type="text" value={base} placeholder={meta.base} onChange={e => setBase(e.target.value)} spellCheck={false} /></label>
      <label className="field"><span className="fl">API_KEY{initial?.key_set && <span className="dim">已保存 {initial.key_masked}，留空不改</span>}</span>
        <input id="llm-key" type="password" value={key} placeholder={meta.keyHint} autoComplete="off" onChange={e => setKey(e.target.value)} spellCheck={false} /></label>
      <label className="field"><span className="fl">模型<span className="dim">留空则保存后点刷新按钮拉取；也可以手填，逗号分隔</span></span>
        <input id="llm-models" type="text" value={models} placeholder="填写服务商返回的模型 ID，多个用逗号分隔" onChange={e => setModels(e.target.value)} spellCheck={false} /></label>
      <Toggle on={enhanced} onChange={setEnhanced}>增强改写（破甲）</Toggle>
      <small className="dim">{initial?.legacy_template
        ? '此服务商沿用旧版破甲模板。关闭时使用标准改写。'
        : '加强画面细节和输出格式，适用于创作台改写和工作流 H3 提示词。'}</small>
      <div className="row end">
        <button className="btn sm ghost" onClick={onDone}>取消</button>
        <button className="btn sm primary" disabled={saving || !base.trim() || (!initial && !key.trim())} onClick={save}>{saving ? <span className="spinner" /> : null}{initial ? '保存' : '添加'}</button>
      </div>
    </div>
  )
}

function HfBox() {
  const set = useStore(s => s.status?.colab.hf_token_set)
  const toast = useStore(s => s.toast)
  const refresh = useStore(s => s.refresh)
  const [v, setV] = useState('')
  const save = async (t: string) => { try { await api.colab.hfToken(t); toast(t ? 'HF Token 已保存' : 'HF Token 已清除', 'ok'); setV(''); refresh() } catch (e) { toast(e instanceof Error ? e.message : '保存失败', 'err') } }
  return (
    <section className="sect card">
      <h4><KeyRound size={14} />Hugging Face Token</h4>
      <p className="help">下载受限模型（如 FLUX.2）需要。只保存在服务器上，页面不回显。{set ? <span className="tag ok">已设置</span> : <span className="tag">未设置</span>}</p>
      <div className="row"><input type="password" value={v} placeholder="hf_..." autoComplete="off" onChange={e => setV(e.target.value)} /><button className="btn sm" disabled={!v.trim()} onClick={() => save(v.trim())}>保存</button>{set && <button className="btn sm ghost" onClick={() => save('')}>清除</button>}</div>
    </section>
  )
}

function StorageBox() {
  const storage = useStore(s => s.storage)
  const rev = useStore(s => s.roundsRev)
  const open = useStore(s => s.openSheet)
  useEffect(() => { api.storage().then(s => useStore.setState({ storage: s })).catch(() => {}) }, [rev])
  if (!storage) return null
  const used = storage.disk_total_bytes - storage.disk_free_bytes
  const pct = storage.disk_total_bytes ? used / storage.disk_total_bytes * 100 : 0
  return (
    <section className="sect card">
      <h4><HardDrive size={14} />存储</h4>
      <div className="kv">
        <span>作品</span><span className="tabular">{storage.rounds.count} 个 · {fmtBytes(storage.rounds.bytes)}（图片 {storage.rounds.images} · 视频 {storage.rounds.videos}）</span>
        <span>回收站</span><span className="tabular">{storage.trash.count} 个 · {fmtBytes(storage.trash.bytes)}</span>
        <span>磁盘</span><span className="tabular">剩余 {fmtBytes(storage.disk_free_bytes)} / {fmtBytes(storage.disk_total_bytes)}</span>
      </div>
      <div className="bar thin"><i style={{ width: `${pct}%` }} /></div>
      <div className="row"><button className="btn sm" onClick={() => open('cleanup')}>清理旧作品</button><button className="btn sm ghost" onClick={() => open('trash')}>回收站</button></div>
    </section>
  )
}

function AppearanceBox() {
  const theme = useStore(s => s.theme)
  const setTheme = useStore(s => s.setTheme)
  return (
    <section className="sect card">
      <h4><Palette size={14} />外观</h4>
      <Seg ariaLabel="主题" value={theme} onChange={setTheme} options={[{ id: 'system', label: '跟随系统' }, { id: 'light', label: '亮色' }, { id: 'dark', label: '暗色' }]} />
    </section>
  )
}
