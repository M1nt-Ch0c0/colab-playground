// Cordis adapter loaded with the studio's private profile.
import { timingSafeEqual } from 'node:crypto'
import { createServer, request } from 'node:http'

export const name = 'studio-workflow-tools'
export const inject = ['tools', 'agents']

function postToStudio(path, body, signal) {
  const payload = JSON.stringify(body)
  return new Promise((resolve, reject) => {
    const req = request(new URL(path, process.env.STUDIO_TOOL_URL), {
      method: 'POST', signal, headers: {
        Authorization: 'Bearer ' + process.env.STUDIO_TOOL_TOKEN,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    }, res => {
      const chunks = []
      res.on('data', part => chunks.push(part))
      res.on('error', reject)
      res.on('end', () => {
        try {
          const value = JSON.parse(Buffer.concat(chunks).toString('utf8'))
          if (res.statusCode !== 200) throw Error(JSON.stringify(value))
          resolve(value)
        } catch (error) { reject(error) }
      })
    })
    req.on('error', reject)
    req.end(payload)
  })
}

export async function apply(ctx, config) {
  // Loopback control server for ToolBridge.interrupt() (agent_bridge.py).
  // POST /stop contract: 204 = running turn cancelled (keep process/session/plugins alive),
  // 200 {"state":"idle"} = already idle, 409 = unconfirmed (bridge closes process),
  // 403 = bad path/method/token.
  const token = Buffer.from('Bearer ' + process.env.STUDIO_TOOL_TOKEN)
  const control = createServer((req, res) => {
    const received = Buffer.from(req.headers.authorization ?? '')
    if (req.url !== '/stop' || req.method !== 'POST' ||
        received.length !== token.length || !timingSafeEqual(received, token)) {
      res.writeHead(403).end()
      return
    }
    try {
      const agent = ctx.agents.get(process.env.STUDIO_SESSION_ID)
      if (agent?.status === 'idle') {
        res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"state":"idle"}')
      } else if (agent?.status === 'running') {
        agent.cancel({ kind: 'user' })
        res.writeHead(204).end()
      } else {
        res.writeHead(409).end()
      }
    } catch { res.writeHead(409).end() }
  })
  ctx.on('dispose', () => { control.closeAllConnections(); control.close() })
  await new Promise((resolve, reject) => {
    control.once('error', reject)
    control.listen(0, '127.0.0.1', resolve)
  })
  await postToStudio('/ready', { port: control.address().port, pid: process.pid })

  for (const tool of config.tools) {
    ctx.tools.register({
      ...tool,
      output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
      async execute(args, exec) {
        return JSON.stringify(await postToStudio('/tool', { name: tool.name, args }, exec.signal))
      },
    })
  }
}
