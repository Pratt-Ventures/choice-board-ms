<template>
  <div>
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
    <template v-else-if="project">
      <div class="d-flex flex-wrap justify-space-between ga-3 mb-4">
        <div>
          <div class="eyebrow">Comparing</div>
          <div class="page-title">{{ project.project_title || project.project_tag }}</div>
          <div class="page-subtitle">Pair comparisons only. Keyboard: 1 / 2 choose, E equal, N unsure, U undo.</div>
          <div v-if="remainingTimeCopy" class="text-body-2 text-medium-emphasis mt-2">{{ remainingTimeCopy }}</div>
          <v-alert
            v-if="project.private_participation"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            Individual participant choices are kept private.
          </v-alert>
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
        <div class="d-flex ga-2 flex-wrap">
          <v-btn v-if="!completeView && !paused && !maxCompleteView" variant="text" :disabled="!runner.canUndo.value || submitting || showGroupIntro" @click="onUndo">
            <i class="fa-solid fa-rotate-left mr-2" /> Undo
          </v-btn>
          <v-btn v-if="!completeView && !paused && !maxCompleteView" variant="tonal" @click="onPause">Pause</v-btn>
          <v-btn v-if="!completeView && !paused" color="primary" variant="flat" :disabled="submitting" @click="markComplete">
            Mark complete
          </v-btn>
          <v-btn variant="tonal" :to="`/projects/${project.id}/results`">
            <i class="fa-solid fa-chart-column mr-2" /> Results
          </v-btn>
          <v-btn icon variant="text" :to="`/projects/${project.id}`"><i class="fa-solid fa-xmark" /></v-btn>
        </div>
      </div>

      <div v-if="error" class="mb-4">
        <v-alert type="error" variant="tonal">{{ error }}</v-alert>
      </div>

      <div v-if="completeView" class="empty-state py-12">
        <i class="fa-solid fa-circle-check fa-3x mb-3" style="color:var(--pc-success)" />
        <div class="text-h5 font-weight-bold mb-2">Thank you for your input</div>
        <div class="text-body-1 mb-4">{{ votesCaptured }} comparison{{ votesCaptured === 1 ? '' : 's' }} captured.</div>
        <v-btn v-if="!inputClosed" color="primary" variant="tonal" class="mr-2" @click="resumeAfterComplete">Continue comparing</v-btn>
        <v-btn variant="text" :to="`/projects/${project.id}/results`">View results</v-btn>
      </div>

      <template v-else>
        <RankingConfidenceBar :confidence="ranking.confidence.value" class="mb-3" />

        <div v-if="paused" class="empty-state py-12">
          <i class="fa-solid fa-pause fa-3x mb-3" style="color:#5b6b7c" />
          <div class="text-h5 font-weight-bold mb-2">Comparisons paused</div>
          <v-btn color="primary" variant="flat" class="mt-4" @click="onResume">Continue comparing</v-btn>
        </div>

        <template v-else>
        <div v-if="project.disabled" class="mb-4">
          <v-alert type="warning" variant="tonal">This project is locked. New comparisons cannot be recorded.</v-alert>
        </div>
        <div v-else-if="collectionClosed" class="mb-4">
          <v-alert type="warning" variant="tonal">Input closed. New comparisons cannot be recorded.</v-alert>
        </div>

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
                  <span>Overall progress</span>
                  <strong v-if="pastMinTarget">Adding Optional Comparisons</strong>
                </div>
                <v-progress-linear :model-value="overallPct" height="9" rounded color="secondary" />
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <div v-if="fetching" class="probe-stage question-group-loading">
          <div class="question-group-timer" aria-hidden="true" />
          <div class="text-body-2 text-medium-emphasis">Preparing next comparison group…</div>
        </div>

        <div v-else-if="maxCompleteView" class="empty-state py-12">
          <i class="fa-solid fa-flag-checkered fa-3x mb-3" style="color:var(--pc-success)" />
          <div class="text-h5 font-weight-bold mb-2">Maximum comparisons completed</div>
          <div class="text-body-1 text-medium-emphasis mb-4">
            You've completed the maximum comparisons for this project.
          </div>
          <v-btn color="primary" variant="flat" class="mr-2" :disabled="submitting" @click="markComplete">Mark complete</v-btn>
          <v-btn
            v-if="heldNextGroup || !sessionComplete"
            variant="tonal"
            :disabled="submitting"
            @click="continuePastMax"
          >
            Continue comparing
          </v-btn>
          <v-btn variant="text" :to="`/projects/${project.id}/results`">View results</v-btn>
        </div>

        <div v-else-if="sessionComplete && !runner.group.value && !pendingGroup" class="empty-state py-12">
          <i class="fa-solid fa-flag-checkered fa-3x mb-3" style="color:var(--pc-success)" />
          <div class="text-h6 font-weight-bold mb-2">All planned comparison groups are done</div>
          <div class="text-body-2 text-medium-emphasis mb-4">You can mark complete or continue if more passes are available.</div>
          <v-btn color="primary" variant="flat" @click="markComplete">Mark complete</v-btn>
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

        <div v-else-if="runner.left.value && runner.right.value" class="probe-stage" :class="{ 'criteria-mode': isCriteria }">
          <CompareQuestionHeader
            :is-criteria="isCriteria"
            :pass-index="passIndex"
            :criterion="runner.group.value?.criterion"
            :criterion-id="runner.group.value?.criterion_id"
            variant="pair"
          />
          <v-row>
            <v-col cols="12" md="6">
              <div class="choice-card" :class="{ 'criteria-choice': isCriteria }" @click="runner.answer('winner', runner.left.value!.id)">
                <div class="text-caption text-medium-emphasis mb-1">Option 1</div>
                <div class="text-h6 font-weight-bold">{{ runner.left.value.title }}</div>
                <div v-if="runner.left.value.description" class="text-body-2 text-medium-emphasis mt-2">{{ runner.left.value.description }}</div>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div class="choice-card" :class="{ 'criteria-choice': isCriteria }" @click="runner.answer('winner', runner.right.value!.id)">
                <div class="text-caption text-medium-emphasis mb-1">Option 2</div>
                <div class="text-h6 font-weight-bold">{{ runner.right.value.title }}</div>
                <div v-if="runner.right.value.description" class="text-body-2 text-medium-emphasis mt-2">{{ runner.right.value.description }}</div>
              </div>
            </v-col>
          </v-row>
          <div class="d-flex flex-wrap ga-2 justify-center mt-4">
            <v-btn variant="text" :disabled="!runner.canUndo.value || submitting" @click="onUndo">
              <i class="fa-solid fa-rotate-left mr-2" /> Undo
            </v-btn>
            <v-btn variant="tonal" @click="runner.answer('tie')">About equal</v-btn>
            <v-btn variant="text" @click="runner.answer('unsure')">Not sure</v-btn>
            <v-btn variant="text" @click="runner.answer('skipped')">Skip</v-btn>
          </div>
        </div>

        <div v-else class="probe-stage question-group-loading">
          <div class="question-group-timer" aria-hidden="true" />
          <div class="text-body-2 text-medium-emphasis">Sorting…</div>
        </div>
        </template>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { SortGroupPayload } from '~/composables/useSortGroupRunner'
import { collectionEndingSoon, collectionIsClosed, projectRemainingTimeCopy } from '~/utils/projectEndTime'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const votes = useVotesApi()
const { loadProject, project, alternatives, factors } = useProjectWorkspace()
const runner = useSortGroupRunner()
const ranking = useRankingConfidence()
const remainingTimeCopy = computed(() => projectRemainingTimeCopy(project.value?.end_time))
const collectionClosed = computed(() => collectionIsClosed(project.value?.end_time))
const endingSoon = computed(() => collectionEndingSoon(project.value?.end_time))
const inputClosed = computed(() => !!project.value?.disabled || collectionClosed.value)

const loading = ref(true)
const fetching = ref(false)
const submitting = ref(false)
const error = ref('')
const completeView = ref(false)
const paused = ref(false)
const votesCaptured = ref(0)
const progress = ref<Record<string, unknown>>({})
const sessionComplete = ref(false)
const projectSettings = ref<Record<string, unknown>>({})
const pendingGroup = ref<SortGroupPayload | null>(null)
const showGroupIntro = ref(false)
const maxCompleteView = ref(false)
const maxCompleteAcknowledged = ref(false)
const heldNextGroup = ref<SortGroupPayload | null>(null)

const multiFactorMode = computed(() => {
  const n = (factors.value || []).filter((f: any) => !f.disabled).length
  return n >= 2
})

const displayGroup = computed(() => pendingGroup.value || runner.group.value)
const isCriteria = computed(() => String(runner.group.value?.group_type || '') === 'criteria')
const introIsCriteria = computed(() => String(displayGroup.value?.group_type || '') === 'criteria')
const passIndex = computed(() => Number(progress.value.pass_index || runner.group.value?.pass_index || 1))
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

function reachedMaxRecommended(res: Record<string, unknown>): boolean {
  if (maxCompleteAcknowledged.value) return false
  const p = (res.progress as Record<string, unknown>) || {}
  const maxP = Number(p.max_recommended_passes || projectSettings.value.max_recommended_passes || 0)
  const completed = Number(p.passes_completed || 0)
  if (!maxP || completed < maxP) return false
  const g = res.next_group as SortGroupPayload | null | undefined
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

async function applySession(res: Record<string, unknown>) {
  if (res.failure_reason) {
    error.value = String(res.failure_reason)
    return
  }
  error.value = ''
  progress.value = (res.progress as Record<string, unknown>) || {}
  ranking.seedFromProgress(progress.value)
  sessionComplete.value = Boolean(res.session_complete)
  projectSettings.value = (res.project_settings as Record<string, unknown>) || {}
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
  if (g) {
    beginGroup(g)
  } else {
    pendingGroup.value = null
    showGroupIntro.value = false
    runner.stop()
  }
}

async function bootstrap() {
  loading.value = true
  try {
    await loadProject(projectId.value, { myVote: false })
    ranking.setCatalog(
      (alternatives.value || []).filter((a: any) => !a.disabled).map((a: any) => Number(a.id)),
      (factors.value || []).filter((f: any) => !f.disabled).map((f: any) => Number(f.id)),
    )
    const res = await votes.getMyVote(projectId.value, true) as any
    await applySession(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to load compare session'
  } finally {
    loading.value = false
  }
}

async function submitCompletedGroup() {
  const pkg = runner.buildPackage()
  if (!pkg) return
  fetching.value = true
  submitting.value = true
  try {
    const res = await votes.completeGroup(projectId.value, pkg) as any
    await applySession(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to save group'
  } finally {
    fetching.value = false
    submitting.value = false
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
    await votes.saveGroup(projectId.value, pkg)
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

function onUndo() {
  runner.undo()
}

function onPause() {
  paused.value = true
  runner.setPaused(true)
}

function onResume() {
  paused.value = false
  runner.setPaused(false)
}

async function markComplete() {
  submitting.value = true
  try {
    const res = await votes.markComplete(projectId.value, true) as any
    votesCaptured.value = Number(res.votes_captured || 0)
    completeView.value = true
    maxCompleteView.value = false
    showGroupIntro.value = false
    pendingGroup.value = null
    heldNextGroup.value = null
    runner.stop()
  } catch (e: any) {
    error.value = e?.message || 'Failed to mark complete'
  } finally {
    submitting.value = false
  }
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
    const res = await votes.nextGroup(projectId.value) as any
    await applySession(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to continue comparisons'
  } finally {
    fetching.value = false
  }
}

async function resumeAfterComplete() {
  fetching.value = true
  try {
    await votes.markComplete(projectId.value, false)
    completeView.value = false
    maxCompleteAcknowledged.value = true
    const res = await votes.nextGroup(projectId.value) as any
    await applySession(res)
  } catch (e: any) {
    error.value = e?.message || 'Failed to resume comparisons'
  } finally {
    fetching.value = false
  }
}

function onKey(e: KeyboardEvent) {
  if (completeView.value || paused.value || maxCompleteView.value || showGroupIntro.value || !runner.left.value) return
  if (e.key === '1') runner.answer('winner', runner.left.value.id)
  else if (e.key === '2') runner.answer('winner', runner.right.value!.id)
  else if (e.key === 'e' || e.key === 'E') runner.answer('tie')
  else if (e.key === 'n' || e.key === 'N') runner.answer('unsure')
  else if (e.key === 'u' || e.key === 'U') onUndo()
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  bootstrap()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
