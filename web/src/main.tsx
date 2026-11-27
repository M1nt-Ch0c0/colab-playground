import '@fontsource-variable/geist'
import './styles/app.css'
import './styles/layout.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { installMock, mockMedia } from './api/client'

async function start() {
  if (__MOCK__) {
    const m = await import('./mock/server')
    m.boot()
    installMock(async (method, path, body, q) => {
      await new Promise(r => setTimeout(r, 60 + Math.random() * 120))
      const res = await m.handle(method, path, body, q)
      return structuredClone(res)
    })
    mockMedia.round = id => m.mediaOf(id)
    mockMedia.thumb = id => m.mediaOf(id)
    mockMedia.ref = key => m.mediaOf(key)
  }
  createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
}
start()
