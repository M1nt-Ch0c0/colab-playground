export const cx = (...a: (string | false | null | undefined | 0)[]) => a.filter(Boolean).join(' ')

export function requestId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
}

let skew = 0
export const setClockSkew = (serverTime: number) => { skew = serverTime - Date.now() / 1000 }
export const now = () => Date.now() / 1000 + skew

export function fmtBytes(n: number | null | undefined): string {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, v = n
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${u[i]}`
}

export function dur(sec: number | null | undefined): string {
  if (sec == null || !isFinite(sec)) return '—'
  const s = Math.max(0, Math.round(sec))
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60), r = s % 60
  if (m < 60) return r ? `${m} 分 ${r} 秒` : `${m} 分`
  const h = Math.floor(m / 60)
  return `${h} 小时 ${m % 60} 分`
}

export function clock(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const m = Math.floor(s / 60), r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

export function ago(ts: number | null | undefined): string {
  if (!ts) return ''
  const d = now() - ts
  if (d < 45) return '刚刚'
  if (d < 3600) return `${Math.round(d / 60)} 分钟前`
  if (d < 86400) return `${Math.round(d / 3600)} 小时前`
  if (d < 86400 * 30) return `${Math.round(d / 86400)} 天前`
  const dt = new Date(ts * 1000)
  return `${dt.getFullYear()}/${dt.getMonth() + 1}/${dt.getDate()}`
}

export function dateLabel(ts: number): string {
  const d = new Date(ts * 1000)
  const t = new Date(now() * 1000)
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  if (same(d, t)) return '今天'
  const y = new Date(t); y.setDate(t.getDate() - 1)
  if (same(d, y)) return '昨天'
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`
}

export const rid = (id: string) => `#${+id}`

const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a)
export function ratio(w: number, h: number): string {
  const g = gcd(w, h) || 1
  const a = w / g, b = h / g
  return a > 30 || b > 30 ? (w / h).toFixed(2) : `${a}:${b}`
}
export const mp = (w: number, h: number) => ((w * h) / 1e6).toFixed(2)

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
export const snap = (v: number, step: number) => Math.round(v / step) * step

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
export const modKey = isMac ? '⌘' : 'Ctrl'

// 浏览器本地状态的 key。旧版用 cs.*，自用数据只存在这一个 origin 里，
// 首次读取时把旧值搬到新 key，旧 key 保留不删，方便回退。
export const LS_KEYS = {
  theme: 'colabreel.theme',
  draft: 'colabreel.draft',
  phist: 'colabreel.phist',
  libopen: 'colabreel.libopen',
  grab: 'colabreel.grab',
  rounds: 'colabreel.rounds',
  pollpx: 'colabreel.pollpx',
} as const

const LS_LEGACY: Record<string, string> = {
  [LS_KEYS.theme]: 'cs.theme',
  [LS_KEYS.draft]: 'cs.draft',
  [LS_KEYS.phist]: 'cs.phist',
  [LS_KEYS.libopen]: 'cs.libopen',
  [LS_KEYS.grab]: 'cs.grab',
  [LS_KEYS.rounds]: 'cs.rounds',
  [LS_KEYS.pollpx]: 'cs.pollpx',
}

export function migrateLocalStorage() {
  try {
    for (const [next, prev] of Object.entries(LS_LEGACY)) {
      if (localStorage.getItem(next) != null) continue
      const old = localStorage.getItem(prev)
      if (old != null) localStorage.setItem(next, old)
    }
  } catch { /* 私密窗口或被禁用 */ }
}

export function lsGet<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v ? (JSON.parse(v) as T) : fallback } catch { return fallback }
}
export function lsSet(key: string, v: unknown) {
  try { localStorage.setItem(key, JSON.stringify(v)) } catch { /* 私密窗口或被禁用 */ }
}

export async function copyText(t: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(t); return true } catch { return false }
}

/** 解析 HF 链接，仅用于前端即时预览；以后端 /api/comfy/parse-link 为准 */
export function parseHfLink(raw: string): { repo: string; file: string; fmt: string } | null {
  const s = raw.trim()
  if (!s) return null
  let m = s.match(/huggingface\.co\/([^/]+\/[^/]+)\/(?:blob|resolve)\/[^/]+\/(.+?)(?:\?|$)/)
  if (m) return { repo: m[1], file: m[2], fmt: fmtOf(m[2]) }
  m = s.match(/^([\w.-]+\/[\w.-]+)\s*::\s*(.+)$/)
  if (m) return { repo: m[1], file: m[2], fmt: fmtOf(m[2]) }
  if (/^https?:\/\//.test(s)) { const f = s.split('?')[0].split('/').pop() || ''; return { repo: '直链', file: f, fmt: fmtOf(f) } }
  return null
}
function fmtOf(f: string) {
  const l = f.toLowerCase()
  if (l.endsWith('.gguf')) return 'GGUF'
  if (l.includes('nvfp4')) return 'NVFP4'
  if (l.includes('fp8')) return 'FP8'
  if (l.includes('bf16')) return 'BF16'
  if (l.includes('fp16')) return 'FP16'
  return l.endsWith('.safetensors') ? 'safetensors' : '文件'
}
