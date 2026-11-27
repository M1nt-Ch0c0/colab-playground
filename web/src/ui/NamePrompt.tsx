import { useState } from 'react'
import { Modal } from './Overlay'

/** 替代 window.prompt：输入一个名称后提交 */
export function NamePrompt({ title, placeholder, initial = '', onClose, onSubmit }: { title: string; placeholder?: string; initial?: string; onClose: () => void; onSubmit: (name: string) => void }) {
  const [v, setV] = useState(initial)
  const submit = () => { const n = v.trim(); if (n) onSubmit(n) }
  return (
    <Modal title={title} onClose={onClose}
      foot={<><button className="btn" onClick={onClose}>取消</button><button className="btn primary" disabled={!v.trim()} onClick={submit}>保存</button></>}>
      <input id="name-prompt" type="text" autoFocus value={v} maxLength={60} placeholder={placeholder}
        onChange={e => setV(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') submit() }} />
    </Modal>
  )
}
