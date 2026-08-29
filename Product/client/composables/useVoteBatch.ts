import type { ProbeCandidate, ObservationResponse, ObservationType } from '~/utils/ranking'
import { IDLE_FLUSH_MS } from '~/utils/ranking'

export interface PendingVote {
  observation_type: ObservationType
  criterion_id: number | null
  item_ids: number[]
  response: ObservationResponse
  winner_id: number | null
  predicted_id: number | null
  predicted_probability: number | null
  client_event_id: string
  algorithm_version: string
}

/**
 * Buffers completed votes and flushes on next-group, pause, complete, or idle >90s.
 * Dedupes by client_event_id (scenario_id from the probe).
 */
export function useVoteBatch(options: {
  flush: (votes: PendingVote[], requestNextCount: number) => Promise<void>
  idleMs?: number
}) {
  const pending = ref<PendingVote[]>([])
  const flushedIds = ref<Set<string>>(new Set())
  const flushing = ref(false)
  const paused = ref(false)
  let idleTimer: ReturnType<typeof setTimeout> | null = null
  const idleMs = options.idleMs ?? IDLE_FLUSH_MS

  function clearIdle() {
    if (idleTimer) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
  }

  function resetIdle() {
    clearIdle()
    if (paused.value || !pending.value.length) return
    idleTimer = setTimeout(() => {
      void flush(0)
    }, idleMs)
  }

  function eventIdFor(probe: ProbeCandidate) {
    return probe.scenarioId || `obs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  }

  function enqueue(
    probe: ProbeCandidate,
    response: number | 'tie' | 'unsure',
  ): PendingVote | null {
    const clientEventId = eventIdFor(probe)
    if (flushedIds.value.has(clientEventId)) return null
    if (pending.value.some(v => v.client_event_id === clientEventId)) return null
    const isWinner = typeof response === 'number'
    const vote: PendingVote = {
      observation_type: probe.type,
      criterion_id: probe.criterion?.id ?? null,
      item_ids: probe.items.map(i => i.id),
      response: isWinner ? 'winner' : response,
      winner_id: isWinner ? response : null,
      predicted_id: probe.predictedId,
      predicted_probability: probe.probability ?? probe.predictedProbability ?? null,
      client_event_id: clientEventId,
      algorithm_version: '0.6',
    }
    pending.value = [...pending.value, vote]
    resetIdle()
    return vote
  }

  async function flush(requestNextCount = 0) {
    if (flushing.value) return
    const batch = pending.value.filter(v => !flushedIds.value.has(v.client_event_id))
    if (!batch.length && requestNextCount <= 0) {
      clearIdle()
      return
    }
    flushing.value = true
    clearIdle()
    try {
      // Mark ids before await to prevent duplicate sends on overlapping flushes
      const nextFlushed = new Set(flushedIds.value)
      for (const v of batch) nextFlushed.add(v.client_event_id)
      flushedIds.value = nextFlushed
      pending.value = pending.value.filter(v => !nextFlushed.has(v.client_event_id))
      await options.flush(batch, requestNextCount)
    }
    catch (e) {
      // Allow retry of failed batch
      for (const v of batch) flushedIds.value.delete(v.client_event_id)
      pending.value = [...batch, ...pending.value]
      throw e
    }
    finally {
      flushing.value = false
      if (pending.value.length) resetIdle()
    }
  }

  function setPaused(value: boolean) {
    paused.value = value
    if (value) clearIdle()
    else resetIdle()
  }

  function dispose() {
    clearIdle()
  }

  return {
    pending,
    flushing,
    paused,
    enqueue,
    flush,
    setPaused,
    dispose,
    resetIdle,
  }
}
