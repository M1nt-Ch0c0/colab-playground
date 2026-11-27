// 程序化生成的示例图片：渐变 + 几何图形 + 噪点，不依赖外部资源。
// 每张图带固定种子，刷新后保持一致，方便截图验收。

function mulberry(seed: number) {
  let s = seed >>> 0
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296 }
}

interface ArtOpts { w: number; h: number; seed: number; label?: string; video?: boolean }

export function makeArt({ w, h, seed, label, video }: ArtOpts): string {
  const c = document.createElement('canvas')
  const scale = Math.min(1, 720 / Math.max(w, h))
  c.width = Math.round(w * scale); c.height = Math.round(h * scale)
  const g = c.getContext('2d')!
  const rnd = mulberry(seed * 997 + 17)
  const hue = Math.floor(rnd() * 360)
  const hue2 = (hue + 40 + Math.floor(rnd() * 80)) % 360
  const bg = g.createLinearGradient(0, 0, c.width, c.height)
  bg.addColorStop(0, `hsl(${hue} 46% 42%)`)
  bg.addColorStop(0.55, `hsl(${(hue + 18) % 360} 40% 30%)`)
  bg.addColorStop(1, `hsl(${hue2} 38% 22%)`)
  g.fillStyle = bg; g.fillRect(0, 0, c.width, c.height)

  g.globalAlpha = 0.55
  for (let i = 0; i < 3; i++) {
    const cx = rnd() * c.width, cy = rnd() * c.height
    const rad = g.createRadialGradient(cx, cy, 0, cx, cy, Math.max(c.width, c.height) * 0.6)
    rad.addColorStop(0, `hsla(${(hue + i * 30) % 360} 70% 70% / .55)`)
    rad.addColorStop(1, 'transparent')
    g.fillStyle = rad; g.fillRect(0, 0, c.width, c.height)
  }
  g.globalAlpha = 1

  g.strokeStyle = 'rgba(255,255,255,.35)'; g.lineWidth = Math.max(2, c.width / 220)
  const n = 4 + Math.floor(rnd() * 4)
  for (let k = 0; k < n; k++) {
    g.beginPath()
    const x0 = rnd() * c.width * 0.3, y0 = rnd() * c.height
    g.moveTo(x0, y0)
    for (let s = 0; s < 3; s++) g.quadraticCurveTo(rnd() * c.width, rnd() * c.height, rnd() * c.width, rnd() * c.height)
    g.stroke()
  }
  if (rnd() > 0.4) {
    g.globalAlpha = 0.8
    g.fillStyle = `hsla(${hue2} 30% 92% / .75)`
    const bx = c.width * (0.15 + rnd() * 0.4), by = c.height * (0.25 + rnd() * 0.35)
    g.beginPath(); g.ellipse(bx, by, c.width * 0.13, c.height * 0.22, rnd() * 0.4, 0, Math.PI * 2); g.fill()
    g.globalAlpha = 1
  }
  if (video) {
    g.fillStyle = 'rgba(0,0,0,.45)'; g.beginPath()
    const r = Math.min(c.width, c.height) * 0.09
    g.arc(c.width / 2, c.height / 2, r, 0, Math.PI * 2); g.fill()
    g.fillStyle = '#fff'; g.beginPath()
    g.moveTo(c.width / 2 - r * 0.3, c.height / 2 - r * 0.45)
    g.lineTo(c.width / 2 + r * 0.5, c.height / 2)
    g.lineTo(c.width / 2 - r * 0.3, c.height / 2 + r * 0.45); g.closePath(); g.fill()
  }
  if (label) {
    g.font = `600 ${Math.round(c.width / 28)}px ui-sans-serif`
    g.fillStyle = 'rgba(255,255,255,.85)'
    g.fillText(label, 14, c.height - 16)
  }
  return c.toDataURL('image/jpeg', 0.72)
}

export function makeThumb(src: string, max = 240): Promise<string> {
  return new Promise(resolve => {
    const img = new Image()
    img.onload = () => {
      const k = max / Math.max(img.width, img.height)
      const c = document.createElement('canvas')
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k)
      c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height)
      resolve(c.toDataURL('image/jpeg', 0.7))
    }
    img.src = src
  })
}
