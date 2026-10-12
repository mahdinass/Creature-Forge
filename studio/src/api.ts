import type { CompileResult, Params, Phase0, PushInfo, RunPayload, Schema, Sketch } from './types'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getSchema = () => fetch('/api/schema').then((r) => j<Schema>(r))
export const getPhase0 = () => fetch('/api/experiments/phase0').then((r) => j<Phase0>(r))
export const getDefaultSketch = () => fetch('/api/sketch/default').then((r) => j<Sketch>(r))

export const simulate = (body: Params, seed: number, duration: number, push: PushInfo | null) =>
  fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body, seed, duration, push }),
  }).then((r) => j<RunPayload>(r))

export const compileSketch = (sketch: Sketch) =>
  fetch('/api/sketch/compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sketch),
  }).then((r) => j<CompileResult>(r))
