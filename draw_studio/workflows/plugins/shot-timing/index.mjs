export const name = 'studio-shot-timing'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register({
    name: 'studio_shot_timing',
    description: '按当前分镜数、视频节点的帧数和 24 fps 计算片长。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    async execute(_args, exec) {
      const response = await fetch(new URL('/context', process.env.STUDIO_TOOL_URL), {
        method: 'POST', signal: exec.signal, redirect: 'error',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + process.env.STUDIO_TOOL_TOKEN },
        body: '{}',
      })
      if (!response.ok) throw Error('读取当前工作流失败')
      const { steps, selected_step } = await response.json()
      const enabled = steps.filter(s => s.enabled)
      const selected = enabled.find(s => s.id === selected_step)
      const videos = enabled.filter(s => s.type === 'video_gen')
      const video = selected?.type === 'video_gen' ? selected : videos.find(s => s.config.scenes_from === selected_step) || videos[0]
      if (!video) return '还没有启用的视频节点。'
      const script = enabled.find(s => s.type === 'llm_script' && s.id === video.config.scenes_from)
      if (!script) return '给视频节点连上分镜，就能算片长。'
      const count = script.config.scene_count, frames = video.config.num_frames
      if (!Number.isSafeInteger(count) || !Number.isSafeInteger(frames) || count <= 0 || frames <= 0) return '镜头数或帧数有误。'
      return JSON.stringify({ video_node: video.name, shots: count, frames_per_shot: frames, fps: 24,
        seconds_per_shot: +(frames / 24).toFixed(2), total_seconds: +(count * frames / 24).toFixed(2) })
    },
  })
}
