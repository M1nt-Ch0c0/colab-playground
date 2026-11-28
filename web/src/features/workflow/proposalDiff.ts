type Segment = { text: string; changed: boolean }
type Match = [number, number]

function lengths(left: string[], start: number, end: number, right: string[], a: number, b: number, reverse: boolean) {
  const width = b - a
  const best = new Uint16Array(width + 1)
  for (let i = 0; i < end - start; i++) {
    let previous = 0
    const char = left[reverse ? end - 1 - i : start + i]
    for (let j = 1; j <= width; j++) {
      const above = best[j]
      best[j] = char === right[reverse ? b - j : a + j - 1] ? previous + 1 : Math.max(above, best[j - 1])
      previous = above
    }
  }
  return best
}

function common(left: string[], right: string[], from: number, to: number, a: number, b: number, matches: Match[]) {
  while (from < to && a < b && left[from] === right[a]) matches.push([from++, a++])
  const end = to
  while (from < to && a < b && left[to - 1] === right[b - 1]) { to--; b-- }
  if (to - from === 1) {
    const char = left[from]
    for (let j = a; j < b; j++) {
      if (right[j] === char) { matches.push([from, j]); break }
    }
  } else if (from < to && a < b) {
    const mid = Math.floor((from + to) / 2)
    const head = lengths(left, from, mid, right, a, b, false)
    const tail = lengths(left, mid, to, right, a, b, true)
    const width = b - a
    let split = 0
    for (let k = 1; k <= width; k++) {
      if (head[k] + tail[width - k] > head[split] + tail[width - split]) split = k
    }
    if (head[split] + tail[width - split] > 0) {
      common(left, right, from, mid, a, a + split, matches)
      common(left, right, mid, to, a + split, b, matches)
    }
  }
  for (let i = to; i < end; i++) matches.push([i, b + i - to])
}

function segments(chars: string[], positions: number[]): Segment[] {
  const same = new Set(positions)
  const result: Segment[] = []
  chars.forEach((char, i) => {
    const changed = !same.has(i)
    const previous = result.at(-1)
    if (previous?.changed === changed) previous.text += char
    else result.push({ text: char, changed })
  })
  return result
}

export function proposalDiff(before: string, after: string): { before: Segment[]; after: Segment[] } {
  const plain = { before: [{ text: before, changed: false }], after: [{ text: after, changed: false }] }
  if (!before || !after || before === after) return plain
  const left = Array.from(before), right = Array.from(after)
  const available = new Map<string, number>()
  for (const char of left) available.set(char, (available.get(char) ?? 0) + 1)
  let overlap = 0
  for (const char of right) {
    const count = available.get(char) ?? 0
    if (count) { overlap++; available.set(char, count - 1) }
  }
  const total = left.length + right.length
  if ((total - 2 * overlap) / total > .6) return plain

  const matches: Match[] = []
  common(left, right, 0, left.length, 0, right.length, matches)
  const joined = matches.filter(([x, y], index) => {
    const adjacent = (pair?: Match) => pair && Math.abs(pair[0] - x) === 1 && Math.abs(pair[1] - y) === 1
    return (x === 0 && y === 0) || (x === left.length - 1 && y === right.length - 1)
      || adjacent(matches[index - 1]) || adjacent(matches[index + 1])
  })
  if ((total - 2 * joined.length) / total > .6) return plain
  return { before: segments(left, joined.map(pair => pair[0])), after: segments(right, joined.map(pair => pair[1])) }
}
