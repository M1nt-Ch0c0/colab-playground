// 实时日志抽屉。后端日志里的 \r 行表示进度刷新，这里合并成同一行。
import { Copy, ScrollText, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useStore } from '../../store/store'
import { Drawer } from '../../ui/Overlay'

export function LogsSheet() {
  const close = useStore(s => s.closeSheet)
  const logs = useStore(s => s.logs)
  const toast = useStore(s => s.toast)
  const [q, setQ] = useState('')
  const [follow, setFollow] = useState(true)
  const box = useRef<HTMLPreElement>(null)
  const lines = useMemo(() => {
    const out: string[] = []
    for (const l of logs) {
      const progress = l.includes('\r')
      const clean = l.replace(/\r/g, '')
      if (progress && out.length && out[out.length - 1].includes('​')) out[out.length - 1] = clean + '​'
      else out.push(progress ? clean + '​' : clean)
    }
    const k = q.trim().toLowerCase()
    return (k ? out.filter(l => l.toLowerCase().includes(k)) : out).map(l => l.replace('​', ''))
  }, [logs, q])
  useEffect(() => { if (follow && box.current) box.current.scrollTop = box.current.scrollHeight }, [lines, follow])
  const copy = async () => { try { await navigator.clipboard.writeText(lines.join('\n')); toast('日志已复制', 'ok') } catch { toast('复制失败', 'err') } }
  return (
    <Drawer title="实时日志" icon={<ScrollText size={16} />} onClose={close}>
      <div className="row">
        <input type="search" value={q} placeholder="过滤" onChange={e => setQ(e.target.value)} />
        <button className="iconbtn" onClick={copy} title="复制"><Copy size={15} /></button>
        <button className="iconbtn" onClick={() => useStore.setState({ logs: [] })} title="清空本地显示"><Trash2 size={15} /></button>
      </div>
      <pre ref={box} className="logbox" onScroll={e => { const el = e.currentTarget; setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 30) }}>
        {lines.length ? lines.map((l, i) => <div key={i} className={/失败|错误|error|Traceback/i.test(l) ? 'bad-text' : /完成|就绪|抢到/.test(l) ? 'ok-text' : ''}>{l}</div>) : <span className="dim">还没有日志</span>}
      </pre>
    </Drawer>
  )
}
