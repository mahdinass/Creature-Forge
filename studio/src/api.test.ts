import { describe, expect, it } from 'vitest'
import { fj, forgeArmReplayUrl, forgeReplayUrl, ForgeApiError, j } from './api'

const resp = (body: string, type: string, status = 200) =>
  new Response(body, { status, headers: { 'Content-Type': type } })

describe('api json parsing', () => {
  it('turns an HTML fallback page into an actionable error, not a JSON parse exception', async () => {
    await expect(j(resp('<!doctype html><html></html>', 'text/html; charset=utf-8'))).rejects.toThrow(/instead of JSON.*start_studio/s)
  })
  it('surfaces structured error detail', async () => {
    await expect(j(resp('{"detail":"No such trial"}', 'application/json', 404))).rejects.toThrow('No such trial')
  })
  it('returns parsed data', async () => {
    expect(await j(resp('{"a":1}', 'application/json'))).toEqual({ a: 1 })
  })
})

describe('forge api client', () => {
  it('keeps the HTTP status on errors so a 503 can be shown as "not available yet"', async () => {
    const err = (await fj(resp('{"detail":"investigations not yet available"}', 'application/json', 503)).catch((e: unknown) => e)) as ForgeApiError
    expect(err).toBeInstanceOf(ForgeApiError)
    expect(err.status).toBe(503)
    expect(err.message).toBe('investigations not yet available')
  })
  it('keeps the status for a non-JSON answer too', async () => {
    const err = (await fj(resp('<html></html>', 'text/html', 200)).catch((e: unknown) => e)) as ForgeApiError
    expect(err).toBeInstanceOf(ForgeApiError)
    expect(err.message).toMatch(/instead of JSON/)
  })
  it('passes parsed data through', async () => {
    expect(await fj(resp('{"job_id":"j-1","run_id":"r-2"}', 'application/json'))).toEqual({ job_id: 'j-1', run_id: 'r-2' })
  })
  it('builds the replay query for a stand run without push parameters', () => {
    expect(forgeReplayUrl({ runId: 'r-12345678', seed: 100001 })).toBe('/api/forge/replay?run_id=r-12345678&seed=100001')
  })
  it('adds direction and force for a push replay', () => {
    const u = forgeReplayUrl({ runId: 'r-12345678', seed: 7, direction: -1, force: 25 })
    expect(u).toContain('direction=-1')
    expect(u).toContain('force=25')
  })
  it('builds the arm replay query', () => {
    expect(forgeArmReplayUrl('i-1', 'ai:P1', 9)).toBe('/api/forge/replay?investigation_id=i-1&arm=ai%3AP1&seed=9')
  })
})
