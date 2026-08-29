<template>
  <div>
    <div v-if="!unlocked">
      <ShareAccessGate
        title="Open full results"
        subtitle="Full project rankings, participant views, and agreement metrics."
        :denial="denial"
        :loading="loading"
        :message="gateMessage"
        :message-type="gateMessageType"
        :initial-key="routeMagicKey"
        @submit="access"
      />
    </div>
    <template v-else>
      <div class="eyebrow">See Full Results</div>
      <div class="d-flex align-center ga-3 flex-wrap mb-1">
        <div class="page-title mb-0">{{ project?.project_title || 'Project results' }}</div>
        <div v-if="projectImageSrc" class="share-project-logo">
          <img :src="projectImageSrc" alt="" class="share-project-logo__img" />
        </div>
      </div>
      <div class="page-subtitle mb-5">{{ project?.project_description }}</div>
      <v-alert
        v-if="project?.private_participation"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-5"
      >
        Private participation is on. Individual names are hidden; people appear as unique participant 1, 2, … in this view.
      </v-alert>

      <v-row dense class="mb-5">
        <v-col cols="6" md="3" v-for="m in cards" :key="m.label">
          <v-card class="glass-card"><v-card-text class="pa-5">
            <div class="text-caption text-medium-emphasis">{{ m.label }}</div>
            <div class="text-h4 font-weight-bold">{{ m.value }}</div>
          </v-card-text></v-card>
        </v-col>
      </v-row>

      <v-card class="glass-card mb-5" v-if="leader">
        <v-card-text class="pa-6">
          <v-chip color="primary" variant="flat" class="mb-3">
            {{ heroHeadline }}
          </v-chip>
          <div class="text-h3 font-weight-bold">{{ leader.title }}</div>
          <div class="leader-basis mt-2">Weighted by what matters most</div>
          <div class="text-h6 mt-2">Score {{ formatPercent(leader.score || 0) }}</div>
          <div v-if="polarizingCaption(leader)" class="text-caption text-medium-emphasis mt-2">
            {{ polarizingCaption(leader) }}
          </div>
          <div class="overall-violin-row text-caption text-medium-emphasis">
            <span class="violin-label">Rank</span>
            <RankRangeBar
              :expected-rank="leader.expected_rank"
              :rank-sd="leader.rank_sd"
              :rank-ci95="leader.rank_ci95"
              :item-count="rankings.length"
              density="comfortable"
            >
              <template #fallback>
                <template v-if="formatRankCi(leader.rank_ci95)">{{ formatRankCi(leader.rank_ci95) }}</template>
                <template v-else-if="formatExpectedRank(leader.expected_rank)">
                  expected rank {{ formatExpectedRank(leader.expected_rank) }}
                </template>
                <template v-if="rankingMode === 'rank_all' && formatExpectedRank(leader.expected_rank) && formatRankCi(leader.rank_ci95)">
                  <template v-if="formatRankCi(leader.rank_ci95)"> · </template>
                  expected {{ formatExpectedRank(leader.expected_rank) }}
                </template>
              </template>
            </RankRangeBar>
            <template v-if="optionChanceCaption(leader, rankingMode, reportTopN)">
              {{ optionChanceCaption(leader, rankingMode, reportTopN) }}
            </template>
          </div>
          <template v-if="factorWeights.length > 1">
            <div class="overall-violin-row text-caption text-medium-emphasis" style="margin-top: 10px">
              <span class="violin-label">Top factor — Rank</span>
              <RankRangeBar
                :expected-rank="factorWeights[0].expected_rank"
                :rank-sd="factorWeights[0].rank_sd"
                :rank-ci95="factorWeights[0].rank_ci95"
                :item-count="factorWeights.length"
                density="comfortable"
              >
                <template #fallback>
                  <span v-if="formatRankCi(factorWeights[0].rank_ci95)">{{ formatRankCi(factorWeights[0].rank_ci95) }}</span>
                  <span v-else-if="formatExpectedRank(factorWeights[0].expected_rank)">expected rank {{ formatExpectedRank(factorWeights[0].expected_rank) }}</span>
                  <span v-else>Rank 1 · {{ factorWeights[0].title }}</span>
                </template>
              </RankRangeBar>
            </div>
            <div class="overall-violin-row text-caption text-medium-emphasis" style="margin-top: 10px">
              <span class="violin-label">Importance</span>
              <WeightRangeBar
                :weight="factorWeights[0].normalizedWeight ?? factorWeights[0].score"
                :weight-ci95="factorWeights[0].weight_ci95"
                density="comfortable"
              >
                <template #fallback>
                  <span>
                    Importance {{ formatNullablePercent(factorWeights[0].normalizedWeight ?? factorWeights[0].score) }}
                    <template v-if="formatWeightCi(factorWeights[0].weight_ci95)">
                      ({{ formatWeightCi(factorWeights[0].weight_ci95) }})
                    </template>
                  </span>
                </template>
              </WeightRangeBar>
            </div>
          </template>
        </v-card-text>
      </v-card>

      <v-row>
        <v-col cols="12" md="7">
          <v-card class="glass-card">
            <v-card-text class="pa-5">
              <div class="text-h6 font-weight-bold mb-4">Overall ranking</div>
              <div v-for="(item, index) in rankings" :key="item.id" class="rank-row mb-2">
                <div class="d-flex align-center ga-3">
                  <div class="rank-number">{{ index + 1 }}</div>
                  <div class="flex-grow-1">
                    <div class="d-flex justify-space-between">
                      <strong>{{ item.title }}</strong>
                      <span>{{ formatPercent(item.score || 0) }}</span>
                    </div>
                    <v-progress-linear :model-value="scoreBarPercent(item.score || 0)" height="8" rounded color="primary" class="mt-2" />
                    <div class="text-caption text-medium-emphasis mt-2 personal-rank-caption">
                      <RankRangeBar
                        :expected-rank="item.expected_rank"
                        :rank-sd="item.rank_sd"
                        :rank-ci95="item.rank_ci95"
                        :item-count="rankings.length"
                        density="comfortable"
                      >
                        <template #fallback>
                          <template v-if="formatRankCi(item.rank_ci95)">{{ formatRankCi(item.rank_ci95) }}</template>
                          <template v-if="rankingMode === 'rank_all' && formatExpectedRank(item.expected_rank)">
                            <template v-if="formatRankCi(item.rank_ci95)"> · </template>
                            expected {{ formatExpectedRank(item.expected_rank) }}
                          </template>
                        </template>
                      </RankRangeBar>
                      <template v-if="optionChanceCaption(item, rankingMode, reportTopN)">
                        {{ optionChanceCaption(item, rankingMode, reportTopN) }}
                      </template>
                    </div>
                    <div v-if="polarizingCaption(item)" class="text-caption mt-1">
                      {{ polarizingCaption(item) }}
                    </div>
                  </div>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="factorWeights.length > 1" class="glass-card mt-5">
            <v-card-text class="pa-5">
              <div class="text-h6 font-weight-bold mb-1">What matters most</div>
              <div class="text-caption text-medium-emphasis mb-4">
                Importance, how much each factor separates options, and which factors actually move the outcome.
              </div>
              <div v-for="(criterion, index) in factorWeights" :key="criterion.id" class="rank-row mb-3">
                <div class="d-flex align-center ga-3">
                  <div class="rank-number">{{ index + 1 }}</div>
                  <div class="flex-grow-1">
                    <div class="d-flex justify-space-between">
                      <strong>{{ criterion.title }}</strong>
                      <span>{{ formatNullablePercent(criterion.normalizedWeight ?? criterion.score) }}</span>
                    </div>
                    <v-progress-linear
                      :model-value="scoreBarPercent(criterion.normalizedWeight ?? criterion.score ?? 0)"
                      height="8"
                      rounded
                      color="deep-purple"
                      class="mt-2"
                    />
                    <div class="text-caption text-medium-emphasis mt-2 factor-violin-row">
                      <span class="violin-label">Rank</span>
                      <RankRangeBar
                        :expected-rank="criterion.expected_rank"
                        :rank-sd="criterion.rank_sd"
                        :rank-ci95="criterion.rank_ci95"
                        :item-count="factorWeights.length"
                        density="comfortable"
                      >
                        <template #fallback>
                          <span v-if="formatRankCi(criterion.rank_ci95)">{{ formatRankCi(criterion.rank_ci95) }}</span>
                          <span v-else-if="formatExpectedRank(criterion.expected_rank)">expected rank {{ formatExpectedRank(criterion.expected_rank) }}</span>
                          <span v-else>Rank {{ criterion.rank ?? index + 1 }}</span>
                        </template>
                      </RankRangeBar>
                    </div>
                    <div class="text-caption text-medium-emphasis mt-1 factor-violin-row">
                      <span class="violin-label">Importance</span>
                      <WeightRangeBar
                        :weight="criterion.normalizedWeight ?? criterion.score"
                        :weight-ci95="criterion.weight_ci95"
                        density="comfortable"
                      >
                        <template #fallback>
                          <span>
                            Importance {{ formatNullablePercent(criterion.normalizedWeight ?? criterion.score) }}
                            <template v-if="formatWeightCi(criterion.weight_ci95)">
                              ({{ formatWeightCi(criterion.weight_ci95) }})
                            </template>
                          </span>
                        </template>
                      </WeightRangeBar>
                    </div>
                    <div class="d-flex flex-wrap ga-4 text-caption text-medium-emphasis mt-2">
                      <span>Differentiation {{ formatNullablePercent(criterion.discrimination) }}</span>
                      <span>Decision leverage {{ formatNullablePercent(criterion.leverage) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="5">
          <v-card class="glass-card">
            <v-card-text class="pa-5">
              <div class="text-h6 font-weight-bold mb-2">Dispersion</div>
              <div class="text-body-2 mb-1">Index: {{ Math.round((dispersion.dispersion_index || 0) * 100) }}%</div>
              <div class="text-body-2 mb-1">Clustering: {{ Math.round((dispersion.clustering_index || 0) * 100) }}%</div>
              <div class="text-body-2 mb-4">Distinct leaders: {{ dispersion.unique_leaders || 0 }}</div>
              <div class="text-h6 font-weight-bold mb-2">Participants</div>
              <div v-for="p in participants" :key="p.id" class="rank-row mb-2">
                <strong>{{ p.display_name || p.email || `unique participant ${p.id}` }}</strong>
                <div class="text-caption">
                  {{ p.comparison_count ?? p.observation_count ?? p.data_points ?? 0 }} comparisons · prefers {{ p.leader?.title || p.ranking?.[0]?.title || '—' }}
                  <template v-if="p.coherence != null"> · align {{ Math.round(Number(p.coherence) * 100) }}%</template>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ShareAccessPayload } from '~/types/api'
import {
  formatPercent,
  formatNullablePercent,
  formatRankCi,
  formatWeightCi,
  formatExpectedRank,
  scoreBarPercent,
  mapServerRanking,
  normalizeRankingMode,
  headlineOptionLabel,
  optionChanceCaption,
  polarizingCaption,
  insightMetricChips,
} from '~/utils/ranking'
import { mergeShareGateCreds, shareGateDenialAlert } from '~/utils/shareGateCreds'
import { shareMagicKeyFromRoute } from '~/utils/shareRoute'

definePageMeta({ layout: 'share' })

const route = useRoute()
const shares = useSharesApi()
const brandingApi = useBrandingApi()
const shareSession = useShareSession()

const token = computed(() => String(route.params.token))
const routeMagicKey = computed(() => shareMagicKeyFromRoute(route))
const loading = ref(false)
const unlocked = ref(false)
const gateCreds = ref<Record<string, unknown>>({})
const denial = ref<ShareAccessPayload | null>(null)
const gateMessage = ref('')
const gateMessageType = ref<'error' | 'info' | 'success' | 'warning'>('info')
const project = ref<ShareAccessPayload['project']>(null)
const report = ref<Record<string, any>>({})

const projectImageSrc = computed(() => {
  if (!shareSession.unlocked.value || !project.value?.has_project_branding_image) return ''
  return brandingApi.shareProjectImageUrl(token.value, Date.now())
})

const rankings = computed(() => {
  const mapped = mapServerRanking(
    report.value?.option_ranking
    || report.value?.results?.importance_adjusted
    || report.value?.alternative_ranking,
  )
  return mapped || []
})
const leader = computed(() => rankings.value[0] || report.value?.results?.leader || null)
const dispersion = computed(() => report.value?.dispersion || {})
const participants = computed(() => report.value?.participants || [])
const factorWeights = computed(() => {
  const mapped = mapServerRanking(
    report.value?.factor_ranking || report.value?.results?.criterion_weights,
  )
  return mapped || []
})
const rankingMode = computed(() =>
  normalizeRankingMode(report.value?.ranking_mode, project.value?.project_exclusive_mode),
)
const reportTopN = computed(() => Number(report.value?.top_n) || 1)
const heroHeadline = computed(() => headlineOptionLabel(rankingMode.value))
const cards = computed(() => {
  const chips = insightMetricChips(report.value)
  return [
    { label: 'Participants', value: report.value?.unique_participants || 0 },
    ...chips.map(c => ({ label: c.label, value: c.display })),
  ]
})

function storeCredentials(form: Record<string, unknown>) {
  gateCreds.value = mergeShareGateCreds(gateCreds.value, form, routeMagicKey.value)
}

async function access(form: Record<string, unknown> = {}) {
  loading.value = true
  storeCredentials(form)
  try {
    const payload = await shares.extAccess(token.value, 'report', gateCreds.value)
    if (payload.failure_reason && !payload.project) {
      denial.value = payload
      const alert = shareGateDenialAlert(payload.failure_reason, !!payload.sent_magic_access_message)
      gateMessage.value = alert.message
      gateMessageType.value = alert.type
      return
    }
    unlocked.value = true
    shareSession.markUnlocked(token.value)
    project.value = payload.project
    report.value = payload.report || {}
  }
  catch (e: unknown) {
    gateMessage.value = e instanceof Error ? e.message : 'Access failed'
    gateMessageType.value = 'error'
  }
  finally {
    loading.value = false
  }
}

onMounted(() => {
  const initial: Record<string, unknown> = {}
  if (routeMagicKey.value) initial.verification_magic_email_key = routeMagicKey.value
  access(initial)
})
</script>

<style scoped>
.share-project-logo {
  width: 90px;
  height: 90px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(var(--v-theme-surface-variant), 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.share-project-logo__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.personal-rank-caption {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  row-gap: 8px;
  line-height: 1.3;
  padding-right: 4px;
}
.factor-violin-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  row-gap: 12px;
  margin-bottom: 4px;
  padding-right: 4px;
}
.factor-violin-row .violin-label {
  min-width: 80px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pc-muted);
  line-height: 1.2;
}
.factor-violin-row + .factor-violin-row {
  margin-top: 10px !important;
}
.overall-violin-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  row-gap: 12px;
  margin-top: 16px;
  padding-right: 4px;
}
.overall-violin-row .violin-label {
  min-width: 80px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pc-muted);
  line-height: 1.2;
}
@media (max-width: 480px) {
  .factor-violin-row,
  .overall-violin-row,
  .personal-rank-caption {
    gap: 8px 12px;
  }
  .factor-violin-row .violin-label,
  .overall-violin-row .violin-label {
    min-width: 72px;
  }
}
</style>
