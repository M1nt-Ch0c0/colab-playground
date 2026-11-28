import { ChevronRight, CircleAlert, Download, Play, Timer, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { AgentPluginAction, AgentPlugins as Inventory } from '../../api/types'
import { useStore } from '../../store/store'
import { AGENT_COPY as C, PLUGIN_COPY, errorCopy, toolLabel } from './agentCopy'

const toastText = {
  install: C.toast.pluginInstalled, enable: C.toast.pluginEnabled,
  disable: C.toast.pluginDisabled, remove: C.toast.pluginRemoved,
}

export function AgentPlugins({ data, loadFailed, retry, changed, tryTiming, disabled }: {
  data: Inventory | null; loadFailed: boolean; retry: () => void; changed: (data: Inventory) => void;
  tryTiming: () => void; disabled: boolean;
}) {
  const toast = useStore(s => s.toast)
  const [pending, setPending] = useState<AgentPluginAction | null>(null)
  const [error, setError] = useState('')
  const plugin = data?.plugin
  const copy = plugin && PLUGIN_COPY[plugin.id]
  const name = copy?.name ?? plugin?.name ?? ''

  async function change(action: AgentPluginAction) {
    if (!plugin || pending || disabled) return
    setPending(action)
    setError('')
    try {
      changed(await api.wf.changePlugin(plugin.id, action))
      toast(toastText[action](name), 'ok')
    } catch (failure) {
      setError(errorCopy(failure instanceof ApiError ? failure.code : undefined).text)
    } finally {
      setPending(null)
    }
  }

  const tools = Object.keys(data?.builtin_tools ?? {})
  const locked = !!pending || disabled
  return <div className="agent-plugins">
    {loadFailed && <div className="agent-error" role="alert"><CircleAlert size={14} />
      <span>{C.plugins.loadFailed}</span><button className="mini-link" onClick={retry}>{C.plugins.retry}</button>
    </div>}
    {!plugin && !loadFailed && <span className="agent-working"><span className="spinner" />{C.plugins.loading}</span>}
    {plugin && <article className="agent-package">
      <div className="package-heading">
        <span className="package-icon"><Timer size={20} /></span><b>{name}</b><span className="grow" />
        {plugin.installed && <span className={plugin.enabled ? 'tag ok' : 'tag'}>{C.plugins.state[plugin.enabled ? 'enabled' : 'disabled']}</span>}
      </div>
      {copy && <p>{copy.description}</p>}
      <div className="package-actions">
        {!plugin.installed ? <button className="btn sm primary" disabled={locked} onClick={() => void change('install')}>
          {pending ? <span className="spinner" /> : <Download size={14} />}{pending ? C.plugins.installing : C.plugins.install}
        </button> : <>
          {plugin.enabled && <button className="btn sm primary" disabled={locked} onClick={tryTiming}>
            <Play size={13} />{C.plugins.tryTiming}
          </button>}
          <button className="btn sm" disabled={locked} onClick={() => void change(plugin.enabled ? 'disable' : 'enable')}>
            {(pending === 'disable' || pending === 'enable') && <span className="spinner" />}
            {plugin.enabled ? C.plugins.disable : C.plugins.enable}
          </button>
          <span className="grow" />
          <button className="iconbtn sm" aria-label={C.plugins.removeAria(name)} disabled={locked} onClick={() => void change('remove')}>
            {pending === 'remove' ? <span className="spinner" /> : <Trash2 size={14} />}
          </button>
        </>}
      </div>
      {error && <div className="agent-error" role="alert"><CircleAlert size={14} /><span>{error}</span></div>}
    </article>}
    {!!data && <details className="agent-builtins">
      <summary><ChevronRight size={14} />{C.plugins.builtins}<span className="tabular">{tools.length}</span></summary>
      <ul>{tools.map(id => <li key={id}>{toolLabel(id)}</li>)}</ul>
    </details>}
  </div>
}
