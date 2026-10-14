import { describe, expect, it } from 'vitest'
import { j } from './api'

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
