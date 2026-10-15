import { useEffect, useReducer } from 'react'
import { getForgeJob } from '../api'
import { initialPoll, POLL_MS, pollReducer, shouldKeepPolling, type PollState } from './forgeLogic'

/** Polls GET /api/forge/jobs/{id}?since= every second until the job reaches a terminal state (or the network keeps failing). */
export function useJobPoll(jobId: string | null): PollState {
  const [state, dispatch] = useReducer(pollReducer, initialPoll)
  useEffect(() => {
    dispatch({ type: 'reset' })
    if (!jobId) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let since = 0
    let failures = 0
    const tick = async () => {
      try {
        const poll = await getForgeJob(jobId, since)
        if (!alive) return
        failures = 0
        since = poll.events.reduce((m, e) => Math.max(m, e.i), since)
        dispatch({ type: 'data', poll })
        if (poll.job.status === 'done' || poll.job.status === 'failed' || poll.job.status === 'cancelled') return
      } catch (e) {
        if (!alive) return
        failures += 1
        dispatch({ type: 'error', message: (e as Error).message })
        if (!shouldKeepPolling({ ...initialPoll, failures })) return
      }
      timer = setTimeout(() => void tick(), POLL_MS)
    }
    void tick()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [jobId])
  return state
}
