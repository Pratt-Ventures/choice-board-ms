<template>
  <div>
    <ShareAccessGate
      v-if="!unlocked"
      title="Join this decision"
      subtitle="Verify access to submit your comparisons on the shared project."
      :end-time="projectEndTime"
      :denial="denial"
      :loading="gateLoading"
      :message="gateMessage"
      :message-type="gateMessageType"
      :initial-key="routeMagicKey"
      @submit="access"
    />
    <template v-else>
      <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
      <template v-else>
        <div class="d-flex flex-wrap justify-space-between ga-3 mb-4">
          <div class="d-flex align-start ga-3" style="min-width:0">
            <div class="flex-grow-1" style="min-width:0">
              <div class="eyebrow">Comparing</div>
              <div class="d-flex align-center ga-3 flex-wrap">
                <div class="page-title mb-0">{{ projectTitle }}</div>
                <div v-if="projectImageSrc" class="share-project-logo">
                  <img :src="projectImageSrc" alt="" class="share-project-logo__img" />
                </div>
              </div>
              <div class="page-subtitle">Pair comparisons · Pass {{ passIndex }}</div>
              <div v-if="remainingTimeCopy" class="text-body-2 text-medium-emphasis mt-2">{{ remainingTimeCopy }}</div>
              <v-alert
                v-if="endingSoon && !inputClosed"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-3"
              >
                Comparison collection ends soon.
              </v-alert>
            </div>
          </div>
          <div class="d-flex ga-2 flex-wrap">
            <v-btn v-if="!completeView && !paused && !maxCompleteView" variant="text" :disabled="!runner.canUndo.value || showGroupIntro" @click="runner.undo()">Undo</v-btn>
            <v-btn v-if="!completeView && !paused && !maxCompleteView" variant="tonal" @click="onPause">Pause</v-btn>
            <v-btn v-if="!completeView" color="primary" variant="flat" :loading="submitting" @click="markComplete">Mark complete</v-btn>
          </div>
        </div>

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-alert v-if="projectDisabled" type="warning" variant="tonal" class="mb-4">
          This project is locked. New comparisons cannot be recorded.
        </v-alert>
        <v-alert v-else-if="collectionClosed" type="warning" variant="tonal" class="mb-4">
          Input closed. New comparisons cannot be recorded.
        </v-alert>

        <template v-if="completeView">
          <div class="empty-state py-8">
            <i class="fa-solid fa-circle-check fa-3x mb-3" style="color:var(--pc-success)" />
            <div class="text-h5 font-weight-bold mb-2">Thank you</div>
            <div class="text-body-1">{{ votesCaptured }} comparisons captured.</div>
            <div v-if="personalConfidenceLabel" class="text-body-2 text-medium-emphasis mt-2">
              Confidence: {{ personalConfidenceLabel }}
            </div>
          </div>
          <v-row v-if="personalOptions.length" class="mt-2">
            <v-col cols="12" :lg="showPersonalFactors ? 7 : 12">
              <v-card class="glass-card">
                <v-card-text class="pa-5">
                  <div class="text-h6 font-weight-bold mb-1">Your ranking</div>
                  <div class="text-caption text-medium-emphasis mb-4">
                    Decision factors contribute according to their ranked importance; Rank percentage is first vs last likelihood.
                  </div>
                  <div v-for="(item, index) in personalOptions" :key="item.id" class="rank-row mb-2">
                    <div class="d-flex align-center ga-3">
                      <div class="rank-number">{{ index + 1 }}</div>
                      <div class="flex-grow-1">
                        <div class="d-flex justify-space-between ga-3">
                          <strong>{{ item.title }}</strong>
                          <span class="font-weight-bold">{{ formatPercent(item.score) }}</span>
                        </div>
                        <v-progress-linear :model-value="scoreBarPercent(item.score)" height="8" rounded color="primary" class="mt-2" />
                        <div class="text-caption text-medium-emphasis mt-2 personal-rank-caption">
                          <RankRangeBar
                            :expected-rank="item.expected_rank"
                            :rank-sd="item.rank_sd"
                            :rank-ci95="item.rank_ci95"
                            :item-count="personalOptions.length"
                            density="comfortable"
                          >
                            <template #fallback>
                              <template v-if="formatRankCi(item.rank_ci95)">{{ formatRankCi(item.rank_ci95) }}</template>
                              <template v-else-if="formatExpectedRank(item.expected_rank)">
                                expected rank {{ formatExpectedRank(item.expected_rank) }}
                              </template>
                              <template v-if="personalRankingMode === 'rank_all' && formatExpectedRank(item.expected_rank) && formatRankCi(item.rank_ci95)">
                                · expected {{ formatExpectedRank(item.expected_rank) }}
                              </template>
                            </template>
                          </RankRangeBar>
                          <template v-if="optionChanceCaption(item, personalRankingMode, personalTopN)">
                            {{ optionChanceCaption(item, personalRankingMode, personalTopN) }}
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
            <v-col v-if="showPersonalFactors" cols="12" lg="5">
              <v-card class="glass-card">
                <v-card-text class="pa-5">
                  <div class="text-h6 font-weight-bold mb-1">What matters most</div>
                  <div class="text-caption text-medium-emphasis mb-4">
                    Importance, how much each factor separates options, and which factors actually move the outcome.
                  </div>
                  <div v-for="(criterion, index) in personalFactors" :key="criterion.id" class="rank-row mb-3">
                    <div class="d-flex align-center ga-3">
                      <div class="rank-number">{{ index + 1 }}</div>
                      <div class="flex-grow-1">
                        <div class="d-flex justify-space-between ga-3">
                          <strong>{{ criterion.title }}</strong>
                          <span class="font-weight-bold">{{ formatNullablePercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score) }}</span>
                        </div>
                        <v-progress-linear
                          :model-value="scoreBarPercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score ?? 0)"
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
                            :item-count="personalFactors.length"
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
                            :weight="criterion.normalizedWeight ?? criterion.weight ?? criterion.score"
                            :weight-ci95="criterion.weight_ci95"
                            density="comfortable"
                          >
                            <template #fallback>
                              <span>
                                Importance {{ formatNullablePercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score) }}
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
          </v-row>
        </template>

        <template v-else>
          <RankingConfidenceBar :confidence="ranking.confidence.value" class="mb-3" />

          <div v-if="paused" class="empty-state py-12">
            <div class="text-h5 font-weight-bold mb-2">Paused</div>
            <v-btn color="primary" class="mt-4" @click="onResume">Continue</v-btn>
          </div>

          <template v-else>
          <v-row class="mb-4" dense>
            <v-col cols="12" md="6">
              <v-card class="soft-card" rounded="lg">
                <v-card-text class="py-3">
                  <div class="d-flex justify-space-between text-caption mb-2">
                    <span>This group</span>
                    <strong>{{ groupDoneLabel }}</strong>
                  </div>
                  <v-progress-linear :model-value="inGroupPct" height="9" rounded color="primary" />
                </v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card class="soft-card" rounded="lg">
                <v-card-text class="py-3">
                  <div class="d-flex justify-space-between text-caption mb-2">
                    <span>Overall</span>
                    <strong v-if="pastMinTarget">Adding Optional Comparisons</strong>
                  </div>
                  <v-progress-linear :model-value="overallPct" height="9" rounded color="secondary" />
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>

          <div v-if="fetching" class="probe-stage question-group-loading">
            <div class="question-group-timer" />
            <div class="text-body-2">Preparing next group…</div>
          </div>

          <div v-else-if="maxCompleteView" class="empty-state py-12">
            <i class="fa-solid fa-flag-checkered fa-3x mb-3" style="color:var(--pc-success)" />
            <div class="text-h5 font-weight-bold mb-2">Maximum comparisons completed</div>
            <div class="text-body-1 text-medium-emphasis mb-4">
              You've completed the maximum comparisons for this project.
            </div>
            <v-btn color="primary" variant="flat" class="mr-2" :loading="submitting" @click="markComplete">Mark complete</v-btn>
            <v-btn
              v-if="heldNextGroup || !sessionComplete"
              variant="tonal"
              @click="continuePastMax"
            >
              Continue comparing
            </v-btn>
          </div>

          <div v-else-if="sessionComplete && !runner.group.value && !pendingGroup" class="empty-state py-12">
            <div class="text-h6 font-weight-bold">All groups complete</div>
            <v-btn color="primary" class="mt-4" @click="markComplete">Mark complete</v-btn>
          </div>

          <div v-else-if="showGroupIntro && displayGroup" class="probe-stage" :class="{ 'criteria-mode': introIsCriteria }">
            <CompareQuestionHeader
              :is-criteria="introIsCriteria"
              :pass-index="introPassIndex"
              :criterion="displayGroup?.criterion"
              :criterion-id="displayGroup?.criterion_id"
              variant="intro"
            />
            <div class="d-flex justify-center mt-6">
              <v-btn color="primary" variant="flat" size="large" @click="beginPendingGroup">
                {{ introIsCriteria ? 'Compare factors' : 'Compare based on this factor' }}
              </v-btn>
            </div>
          </div>

          <div v-else-if="runner.left.value && runner.right.value" class="probe-stage">
            <CompareQuestionHeader
              :is-criteria="isCriteria"
              :pass-index="passIndex"
              :criterion="runner.group.value?.criterion"
              :criterion-id="runner.group.value?.criterion_id"
              variant="pair"
            />
            <v-row>
              <v-col cols="12" md="6">
                <div class="choice-card" @click="runner.answer('winner', runner.left.value!.id)">
                  <div class="text-h6 font-weight-bold">{{ runner.left.value.title }}</div>
                  <div v-if="runner.left.value.description" class="text-body-2 text-medium-emphasis mt-2">{{ runner.left.value.description }}</div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="choice-card" @click="runner.answer('winner', runner.right.value!.id)">
                  <div class="text-h6 font-weight-bold">{{ runner.right.value.title }}</div>
                  <div v-if="runner.right.value.description" class="text-body-2 text-medium-emphasis mt-2">{{ runner.right.value.description }}</div>
                </div>
              </v-col>
            </v-row>
            <div class="d-flex flex-wrap ga-2 justify-center mt-4">
              <v-btn variant="text" :disabled="!runner.canUndo.value" @click="runner.undo()">
                <i class="fa-solid fa-rotate-left mr-2" /> Undo
              </v-btn>
              <v-btn variant="tonal" @click="runner.answer('tie')">About equal</v-btn>
              <v-btn variant="text" @click="runner.answer('unsure')">Not sure</v-btn>
              <v-btn variant="text" @click="runner.answer('skipped')">Skip</v-btn>
            </div>
          </div>

          <div v-else class="probe-stage question-group-loading">
            <div class="question-group-timer" />
            <div class="text-body-2">Sorting…</div>
          </div>
          </template>
        </template>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ShareAccessPayload } from '~/types/api'
import type { SortGroupPayload } from '~/composables/useSortGroupRunner'
import { collectionEndingSoon, collectionIsClosed, projectRemainingTimeCopy } from '~/utils/projectEndTime'
import { mergeShareGateCreds, shareGateDenialAlert } from '~/utils/shareGateCreds'
import { shareMagicKeyFromRoute } from '~/utils/shareRoute'
import {
  formatPercent,
  formatNullablePercent,
  formatRankCi,
  formatWeightCi,
  formatExpectedRank,
  scoreBarPercent,
  optionChanceCaption,
  personalRankingsFromSummary,
  metricLabel,
} from '~/utils/ranking'

const props = withDefaults(defineProps<{
  shareKind?: 'vote' | 'vote_view'
}>(), {
  shareKind: 'vote',
})

const route = useRoute()
const shares = useSharesApi()
const brandingApi = useBrandingApi()
const shareSession = useShareSession()
const runner = useSortGroupRunner()
const ranking = useRankingConfidence()

const token = computed(() => String(route.params.token || ''))
const routeMagicKey = computed(() => shareMagicKeyFromRoute(route))
const shareKind = computed(() => props.shareKind)

const unlocked = ref(false)
const gateCreds = ref<Record<string, unknown>>({})
const gateLoading = ref(false)
const denial = ref<ShareAccessPayload | null>(null)
const gateMessage = ref('')
const gateMessageType = ref<'error' | 'info' | 'success' | 'warning'>('info')
const loading = ref(false)
const fetching = ref(false)
const submitting = ref(false)
const error = ref('')
const projectTitle = ref('Project')
const projectImageSrc = ref('')
const projectEndTime = ref<string | null>(null)
const projectDisabled = ref(false)
const remainingTimeCopy = computed(() => projectRemainingTimeCopy(projectEndTime.value))
const collectionClosed = computed(() => collectionIsClosed(projectEndTime.value))
const endingSoon = computed(() => collectionEndingSoon(projectEndTime.value))
const inputClosed = computed(() => projectDisabled.value || collectionClosed.value)
const progress = ref<Record<string, unknown>>({})
const sessionComplete = ref(false)
const completeView = ref(false)
const paused = ref(false)
const votesCaptured = ref(0)
const submitterSummary = ref<Record<string, any> | null>(null)
const factorCount = ref(0)
const projectSettings = ref<Record<string, unknown>>({})
const pendingGroup = ref<SortGroupPayload | null>(null)
const showGroupIntro = ref(false)
const maxCompleteView = ref(false)
const maxCompleteAcknowledged = ref(false)
const heldNextGroup = ref<SortGroupPayload | null>(null)

const personalView = computed(() =>
  personalRankingsFromSummary(submitterSummary.value, projectSettings.value),
)
const personalOptions = computed(() => personalView.value.options)
const personalFactors = computed(() => personalView.value.factors)
const showPersonalFactors = computed(() => personalView.value.showFactors)
const personalRankingMode = computed(() => personalView.value.rankingMode)
const personalTopN = computed(() => personalView.value.topN)
const personalConfidenceLabel = computed(() => {
  const c = personalView.value.confidence
  if (c == null) return ''
  return metricLabel(c)
})

const multiFactorMode = computed(() => factorCount.value >= 2)
const displayGroup = computed(() => pendingGroup.value || runner.group.value)
const isCriteria = computed(() => String(runner.group.value?.group_type || '') === 'criteria')
const introIsCriteria = computed(() => String(displayGroup.value?.group_type || '') === 'criteria')
const passIndex = computed(() => Number(progress.value.pass_index || runner.group.value?.pass_index || displayGroup.value?.pass_index || 1))
const introPassIndex = computed(() => Number(displayGroup.value?.pass_index || passIndex.value))

const groupDoneCount = computed(() => (showGroupIntro.value ? 0 : runner.inGroupDone.value))
const groupTotalCount = computed(() => {
  if (showGroupIntro.value && pendingGroup.value) {
    return Number(pendingGroup.value.question_budget || pendingGroup.value.estimated_comparisons || 0)
  }
  return runner.inGroupTotal.value || 0
})
const groupDoneLabel = computed(() => `${groupDoneCount.value} / ${groupTotalCount.value || '—'}`)
const inGroupPct = computed(() => {
  const t = groupTotalCount.value || 0
  if (!t) return 0
  return Math.min(100, Math.round((100 * groupDoneCount.value) / t))
})

const comparisonsDone = computed(() => {
  return Number(progress.value.participant_comparisons_done || 0) + (showGroupIntro.value ? 0 : runner.inGroupDone.value)
})
const minTarget = computed(() => Number(progress.value.estimated_comparisons_at_min || 0))
const pastMinTarget = computed(() => {
  const minPasses = Number(progress.value.min_expected_passes || 0)
  const completed = Number(progress.value.passes_completed || 0)
  if (minPasses > 0 && completed >= minPasses) return true
  return minTarget.value > 0 && comparisonsDone.value >= minTarget.value
})
const overallPct = computed(() => {
  if (pastMinTarget.value) return 100
  const total = minTarget.value
  if (!total) return 0
  return Math.min(100, Math.round((100 * comparisonsDone.value) / total))
})

function reachedMaxRecommended(res: any): boolean {
  if (maxCompleteAcknowledged.value) return false
  const p = res.progress || {}
  const maxP = Number(p.max_recommended_passes || projectSettings.value.max_recommended_passes || 0)
  const completed = Number(p.passes_completed || 0)
  if (!maxP || completed < maxP) return false
  const g = res.next_group
  if (!g) return true
  return Number(g.pass_index || 0) > maxP
}

function beginGroup(g: SortGroupPayload) {
  heldNextGroup.value = null
  maxCompleteView.value = false
  lastFlushedCount.value = 0
  if (multiFactorMode.value) {
    pendingGroup.value = g
    showGroupIntro.value = true
    runner.stop()
  } else {
    pendingGroup.value = null
    showGroupIntro.value = false
    runner.startGroup(g)
  }
}

function beginPendingGroup() {
  const g = pendingGroup.value
  if (!g) return
  showGroupIntro.value = false
  pendingGroup.value = null
  runner.startGroup(g)
}

function applyPayload(res: any) {
  if (res.failure_reason) {
    error.value = String(res.failure_reason)
    return
  }
  error.value = ''
  if (res.project) {
    projectTitle.value = res.project.project_title || res.project.project_tag || 'Project'
    if (res.project.factor_count != null) factorCount.value = Number(res.project.factor_count)
    projectEndTime.value = res.project.end_time || null
    projectDisabled.value = !!res.project.disabled
    projectImageSrc.value = (res.project.has_project_branding_image && shareSession.unlocked.value)
      ? brandingApi.shareProjectImageUrl(token.value, Date.now())
      : ''
  }
  if (Array.isArray(res.factors)) factorCount.value = res.factors.length
  progress.value = res.progress || {}
  ranking.seedFromProgress(progress.value)
  sessionComplete.value = Boolean(res.session_complete)
  ranking.setCatalog(
    (res.alternatives || []).map((a: any) => Number(a.id)).filter(Boolean),
    (res.factors || []).map((f: any) => Number(f.id)).filter(Boolean),
  )
  projectSettings.value = res.project_settings || {}
  const g = res.next_group as SortGroupPayload | null | undefined

  if (reachedMaxRecommended(res)) {
    showGroupIntro.value = false
    pendingGroup.value = null
    runner.stop()
    heldNextGroup.value = g || null
    maxCompleteView.value = true
    return
  }

  maxCompleteView.value = false
  if (g) beginGroup(g)
  else {
    pendingGroup.value = null
    showGroupIntro.value = false
    runner.stop()
  }
}

function storeCredentials(form: Record<string, unknown>) {
  gateCreds.value = mergeShareGateCreds(gateCreds.value, form, routeMagicKey.value)
}

async function access(form: Record<string, unknown> = {}) {
  gateLoading.value = true
  storeCredentials(form)
  try {
    const res = await shares.extAccess(token.value, shareKind.value, {
      ...gateCreds.value,
      request_next: true,
      share_kind: shareKind.value,
    }) as any
    if (res.failure_reason && !res.project) {
      denial.value = res
      const alert = shareGateDenialAlert(res.failure_reason, !!res.sent_magic_access_message)
      gateMessage.value = alert.message
      gateMessageType.value = alert.type
      return
    }
    unlocked.value = true
    shareSession.markUnlocked(token.value)
    denial.value = null
    gateMessage.value = ''
    loading.value = true
    applyPayload(res)
    if (res.personal_vote?.is_complete && shareKind.value === 'vote_view') {
      completeView.value = true
      votesCaptured.value = Number(res.votes_captured || res.personal_vote?.comparison_count || 0)
      submitterSummary.value = res.submitter_summary || null
      showGroupIntro.value = false
      pendingGroup.value = null
      heldNextGroup.value = null
      maxCompleteView.value = false
      runner.stop()
    }
  } catch (e: any) {
    gateMessage.value = e?.message || 'Access failed'
    gateMessageType.value = 'error'
  } finally {
    gateLoading.value = false
    loading.value = false
  }
}

async function submitCompletedGroup() {
  const pkg = runner.buildPackage()
  if (!pkg) return
  fetching.value = true
  try {
    const res = await shares.extCompleteGroup(token.value, {
      ...gateCreds.value,
      share_kind: shareKind.value,
      prior_group: pkg,
    }) as any
    applyPayload(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to save group'
  } finally {
    fetching.value = false
  }
}

watch(
  () => runner.complete.value,
  async (done) => {
    if (done && runner.group.value) await submitCompletedGroup()
  },
)

const lastFlushedCount = ref(0)
let idleTimer: ReturnType<typeof setTimeout> | null = null

function flushThresholds() {
  return {
    count: Math.max(1, Number(projectSettings.value.partial_flush_count || 5)),
    idleMs: Math.max(5, Number(projectSettings.value.partial_idle_seconds || 90)) * 1000,
  }
}

async function flushPartial() {
  if (runner.complete.value || submitting.value) return
  const pkg = runner.buildPartialPackage()
  if (!pkg || !pkg.pairings.length) return
  if (pkg.pairings.length === lastFlushedCount.value) return
  try {
    await shares.extSaveGroup(token.value, {
      ...gateCreds.value,
      share_kind: shareKind.value,
      prior_group: pkg,
    })
    lastFlushedCount.value = pkg.pairings.length
  } catch { /* best-effort */ }
}

watch(
  () => [runner.group.value, runner.pairings.value, runner.inGroupDone.value] as const,
  () => ranking.setLive(runner.group.value, runner.pairings.value),
)

watch(
  () => runner.inGroupDone.value,
  (n) => {
    if (idleTimer) clearTimeout(idleTimer)
    if (!n || runner.complete.value) return
    const { count, idleMs } = flushThresholds()
    if (n - lastFlushedCount.value >= count) void flushPartial()
    idleTimer = setTimeout(() => { void flushPartial() }, idleMs)
  },
)

onBeforeUnmount(() => {
  if (idleTimer) clearTimeout(idleTimer)
})

function onPause() {
  paused.value = true
  runner.setPaused(true)
}
function onResume() {
  paused.value = false
  runner.setPaused(false)
}

async function continuePastMax() {
  maxCompleteAcknowledged.value = true
  maxCompleteView.value = false
  const held = heldNextGroup.value
  heldNextGroup.value = null
  if (held) {
    beginGroup(held)
    return
  }
  fetching.value = true
  try {
    const res = await shares.extNextGroup(token.value, {
      ...gateCreds.value,
      share_kind: shareKind.value,
    }) as any
    applyPayload(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to continue comparisons'
  } finally {
    fetching.value = false
  }
}

async function markComplete() {
  submitting.value = true
  try {
    const res = await shares.extComplete(token.value, {
      ...gateCreds.value,
      share_kind: shareKind.value,
      is_complete: true,
    }) as any
    votesCaptured.value = Number(res.votes_captured || 0)
    submitterSummary.value = res.submitter_summary || null
    if (res.project_settings) projectSettings.value = res.project_settings
    completeView.value = true
    maxCompleteView.value = false
    showGroupIntro.value = false
    pendingGroup.value = null
    heldNextGroup.value = null
    runner.stop()
  } catch (e: any) {
    error.value = e?.message || 'Failed to complete'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const initial: Record<string, unknown> = {}
  const routeKey = shareMagicKeyFromRoute(route)
  if (routeKey) initial.verification_magic_email_key = routeKey
  access(initial)
})
</script>

<style scoped>
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
</style>
