import { Globe, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/client'
import type { ProxyProfile, ProxyState } from '../../api/types'
import { cx } from '../../lib/util'
import { useStore } from '../../store/store'
import { useConfirm } from '../../ui/Overlay'

function applyState(proxy: ProxyState) {
  useStore.setState(s => s.status ? { status: { ...s.status, proxy } } : {})
}

function RouteForm({ initial, done }: { initial: ProxyProfile | null; done: () => void }) {
  const [label, setLabel] = useState(initial?.label || '')
  const [url, setUrl] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useStore(s => s.toast)
  return <form className="llm-form" onSubmit={async e => {
    e.preventDefault()
    setSaving(true)
    try {
      applyState(await api.proxy.save({ id: initial?.id, label: label.trim(), url: url.trim() || undefined }))
      toast('代理线路已保存', 'ok')
      done()
    } catch (error) { toast(error instanceof Error ? error.message : '保存失败', 'err') }
    finally { setSaving(false) }
  }}>
    <label className="field"><span className="fl">线路名称</span>
      <input id="proxy-label" value={label} onChange={e => setLabel(e.target.value)} maxLength={80} required /></label>
    <label className="field"><span className="fl">代理地址</span>
      <input id="proxy-url" type="password" autoComplete="new-password" spellCheck={false}
        placeholder={initial ? '留空保留已保存的地址与凭据' : 'http://host:port 或 socks5://host:port'}
        value={url} onChange={e => setUrl(e.target.value)} required={!initial} /></label>
    <div className="row end">
      <button type="button" className="btn sm ghost" disabled={saving} onClick={done}>取消</button>
      <button className="btn sm primary" disabled={saving || !label.trim() || (!initial && !url.trim())}>保存线路</button>
    </div>
  </form>
}

export function ProxyBox() {
  const px = useStore(s => s.status?.proxy)
  const refresh = useStore(s => s.refresh)
  const toast = useStore(s => s.toast)
  const ask = useConfirm(s => s.ask)
  const [editing, setEditing] = useState<ProxyProfile | 'new' | null>(null)
  const [busy, setBusy] = useState(false)
  if (!px) return null
  const perform = async (action: () => Promise<void>) => {
    setBusy(true)
    try { await action() }
    catch (e) { toast(e instanceof Error ? e.message : '线路操作失败', 'err') }
    finally { setBusy(false) }
  }
  const select = (id: string) => perform(async () => { applyState(await api.proxy.set(id)); toast('出口已切换', 'ok') })
  const test = (id: string) => perform(async () => {
    const r = await api.proxy.test(id)
    toast(r.ok ? `连通 · ${r.loc} ${r.colo} · ${r.ms}ms` : r.error, r.ok ? 'ok' : 'err')
    await refresh()
  })
  const remove = async (p: ProxyProfile) => {
    if (!(await ask({ title: `删除「${p.label}」？`, body: '将删除这条线路保存的地址与凭据。', ok: '删除', danger: true }))) return
    await perform(async () => { applyState(await api.proxy.remove(p.id)); toast('线路已删除', 'ok') })
  }
  return <section className="sect card" aria-label="出口线路">
    <h4><Globe size={14} />出口线路</h4>
    {!px.active && <p className="help">当前使用系统网络。</p>}
    <div className="llm-list">{px.profiles.map(p => {
      const active = px.active === p.id
      const probe = px.last_test?.profile === p.id ? px.last_test : null
      return <div key={p.id} className={cx('llm-row', active && 'on')}>
        <div className="llm-main"><div className="row"><b>{p.label}</b>{active && <span className="tag run">使用中</span>}</div>
          <small className="mono dim">{p.masked}</small>
          {probe && <small className={probe.ok ? 'dim' : 'bad-text'}>{probe.ok ? `${probe.loc} · ${probe.colo} · ${probe.ms}ms` : probe.error}</small>}
        </div>
        <div className="llm-acts">
          {!active && <button className="btn sm ghost" disabled={busy} onClick={() => select(p.id)}>使用</button>}
          <button className="btn sm ghost" disabled={busy} onClick={() => test(p.id)}>测试</button>
          <button className="iconbtn sm" title="编辑线路" disabled={busy} onClick={() => setEditing(p)}><Pencil size={14}/></button>
          <button className="iconbtn sm" title="删除线路" disabled={busy} onClick={() => remove(p)}><Trash2 size={14}/></button>
        </div></div>
    })}</div>
    {editing ? <RouteForm key={editing === 'new' ? 'new' : editing.id} initial={editing === 'new' ? null : editing}
      done={() => setEditing(null)} /> : <div className="row wrap">
      <button className="btn sm" disabled={busy} onClick={() => setEditing('new')}><Plus size={13}/>添加线路</button>
      {px.active && <button className="btn sm ghost" disabled={busy} onClick={() => select('')}>使用系统网络</button>}
    </div>}
  </section>
}
