import type { SortGroupPayload } from '~/composables/useSortGroupRunner'
import {
  computeRankingConfidence,
  emptyRankingConfidence,
  evidenceFromLiveGroup,
  mergeLiveEvidence,
  type RankingConfidence,
  type RankingEvidenceGroup,
  type RankingEvidencePairing,
} from '~/utils/rankingConfidence'

export function useRankingConfidence() {
  const evidence = ref<RankingEvidenceGroup[]>([])
  const optionIds = ref<number[]>([])
  const factorIds = ref<number[]>([])
  const live = ref<RankingEvidenceGroup | null>(null)

  function seedFromProgress(progress: Record<string, unknown> | null | undefined) {
    if (!progress) return
    if (Array.isArray(progress.ranking_evidence)) {
      evidence.value = progress.ranking_evidence as RankingEvidenceGroup[]
    }
    if (Array.isArray(progress.ranking_option_ids) && progress.ranking_option_ids.length) {
      optionIds.value = progress.ranking_option_ids.map(Number).filter(n => Number.isFinite(n))
    }
    if (Array.isArray(progress.ranking_factor_ids) && progress.ranking_factor_ids.length) {
      factorIds.value = progress.ranking_factor_ids.map(Number).filter(n => Number.isFinite(n))
    }
  }

  function setCatalog(options: number[], factors: number[]) {
    if (options.length) optionIds.value = options.filter(n => Number.isFinite(n) && n)
    if (factors.length) factorIds.value = factors.filter(n => Number.isFinite(n) && n)
  }

  function setLive(group: SortGroupPayload | null | undefined, pairings: RankingEvidencePairing[] | undefined) {
    live.value = evidenceFromLiveGroup(group, pairings)
  }

  const confidence = computed<RankingConfidence>(() => computeRankingConfidence({
    evidence: mergeLiveEvidence(evidence.value, live.value),
    optionIds: optionIds.value,
    factorIds: factorIds.value,
  }))

  return {
    seedFromProgress,
    setCatalog,
    setLive,
    confidence,
    empty: emptyRankingConfidence(),
  }
}
