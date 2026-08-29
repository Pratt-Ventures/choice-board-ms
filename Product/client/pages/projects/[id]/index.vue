<template>
  <div>
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
    <template v-else-if="project">
      <div class="page-head">
        <div class="page-head-top">
          <v-btn
            variant="text"
            color="primary"
            class="px-0"
            :to="'/projects'"
          >
            <i class="fa-solid fa-arrow-left mr-2" /> Projects
          </v-btn>
          <div class="head-actions">
            <v-btn variant="text" :to="`/projects/${project.id}/edit`">
              <i class="fa-solid fa-sliders mr-2" /> Project settings
            </v-btn>
            <v-btn variant="text" @click="makeDuplicate">
              <i class="fa-solid fa-copy mr-2" /> Make a copy
            </v-btn>
            <v-btn variant="outlined" :to="`/projects/${project.id}/shares`">
              <i class="fa-solid fa-user-plus mr-2" /> Invite people
            </v-btn>
            <v-btn
              v-if="!inputClosed"
              color="primary"
              variant="flat"
              :to="`/projects/${project.id}/probe`"
            >
              <i class="fa-solid fa-check-to-slot mr-2" /> Start comparing
            </v-btn>
            <v-btn variant="tonal" :to="`/projects/${project.id}/results`">
              <i class="fa-solid fa-chart-column mr-2" /> View results
            </v-btn>
            <v-btn
              v-if="canRunAiAgents && !inputClosed"
              variant="tonal"
              color="primary"
              :loading="runningAi"
              :disabled="activeAlts.length < 2 || runningAi"
              @click="runAiBaseline"
            >
              <i class="fa-solid fa-robot mr-2" /> Run AI agents
            </v-btn>
          </div>
        </div>
        <div>
          <div class="page-title">{{ project.project_title || project.project_tag }}</div>
          <div class="page-subtitle">{{ project.project_description || 'No description yet.' }}</div>
          <div class="d-flex flex-wrap ga-2 mt-3">
            <span :class="['status', inputClosed ? 'status-closed' : (myObservationCount > 0 ? 'status-collecting' : 'status-ready')]">
              {{ inputClosed ? 'Input closed' : (myObservationCount > 0 ? 'Collecting input' : 'Ready') }}
            </span>
            <span class="status status-ready">
              {{ project.project_exclusive_mode ? 'Pick one' : 'Rank all' }}
            </span>
            <span v-if="remainingTimeCopy" class="status status-ready">{{ remainingTimeCopy }}</span>
          </div>
        </div>
      </div>

      <div class="summary-hero mb-5" style="display:grid;grid-template-columns:1.1fr .9fr;gap:18px">
        <v-card class="glass-card">
          <v-card-text class="pa-6">
            <div class="eyebrow">Project summary</div>
            <div class="text-h5 font-weight-bold mt-1" style="font-family:Manrope,Inter,sans-serif">
              {{ project.project_exclusive_mode ? 'Pick one' : 'Rank all' }} project
            </div>
            <div class="d-flex flex-wrap ga-2 mt-5">
              <div class="metric-pill"><strong>{{ activeAlts.length }}</strong><span>Options</span></div>
              <div class="metric-pill"><strong>{{ activeFactors.length }}</strong><span>Factors</span></div>
              <div class="metric-pill"><strong>{{ myObservationCount }}</strong><span>Your comparisons</span></div>
              <div class="metric-pill"><strong>{{ participantCount }}</strong><span>Participants</span></div>
              <div class="metric-pill" title="Estimated comparisons for one participant completing the minimum target groups across all factors plus the factor group">
                <strong>{{ targetComparisonsEst }}</strong><span>Target comparisons est</span>
              </div>
              <div class="metric-pill" title="Estimated comparisons for one participant at the recommended maximum number of passes">
                <strong>{{ maxComparisonsEst }}</strong><span>Max comparisons est</span>
              </div>
              <div class="metric-pill" title="Participants who have recorded at least one comparison">
                <strong>{{ activeParticipantCount }}</strong><span>Active participants</span>
              </div>
              <div
                v-if="aiAgentCounts.requested > 0"
                class="metric-pill"
                title="requested / queued or in progress / completed"
              >
                <strong>{{ aiAgentCounts.requested }}/{{ aiAgentCounts.in_flight }}/{{ aiAgentCounts.completed }}</strong>
                <span>AI agents</span>
              </div>
            </div>
          </v-card-text>
        </v-card>
        <v-card class="glass-card result-hero">
          <v-card-text class="pa-6">
            <div class="eyebrow">Recommended next action</div>
            <div class="text-h6 font-weight-bold mt-2" style="font-family:Manrope,Inter,sans-serif">
              {{ nextAction.title }}
            </div>
            <p class="text-body-2 text-medium-emphasis mt-2 mb-4">{{ nextAction.detail }}</p>
            <v-btn color="primary" variant="flat" :to="nextAction.to">
              {{ nextAction.label }}
              <i class="fa-solid fa-arrow-right ml-2" style="font-size:11px" />
            </v-btn>
          </v-card-text>
        </v-card>
      </div>

      <v-card v-if="showHumanParticipants" class="glass-card mb-5">
        <v-card-text class="pa-5">
          <div class="text-h6 font-weight-bold mb-3" style="font-family:Manrope,Inter,sans-serif">Active Participants</div>
          <template v-if="humanActive.length">
            <div class="eyebrow mb-2">Active</div>
            <div v-for="row in humanActive" :key="`active-${row.participant_id || row.label}`" class="rank-row mb-2">
              <div class="d-flex justify-space-between align-center ga-3">
                <strong>{{ row.label }}</strong>
                <span class="text-caption text-medium-emphasis">{{ responseCopy(row.comparison_count) }}</span>
              </div>
            </div>
          </template>
          <template v-if="humanPending.length">
            <div class="eyebrow mt-4 mb-2">Pending</div>
            <div v-for="row in humanPending" :key="`pending-${row.share_id || row.participant_id || row.label}`" class="rank-row mb-2">
              <div class="d-flex justify-space-between align-center ga-3">
                <strong>{{ row.label }}</strong>
                <span class="text-caption text-medium-emphasis">{{ daysCopy(row.days_pending) }}</span>
              </div>
            </div>
          </template>
          <template v-if="humanAnonymous.length">
            <div class="eyebrow mt-4 mb-2">Open shares</div>
            <div v-for="row in humanAnonymous" :key="`anon-${row.share_id || row.label}`" class="rank-row mb-2">
              <div class="d-flex justify-space-between align-center ga-3">
                <strong>{{ row.label }}</strong>
                <span class="text-caption text-medium-emphasis">{{ activatedCopy(row.activated) }}</span>
              </div>
            </div>
          </template>
        </v-card-text>
      </v-card>

      <v-card v-if="aiAgentCounts.requested > 0" class="glass-card mb-5">
        <v-card-text class="pa-5">
          <div class="text-h6 font-weight-bold mb-3" style="font-family:Manrope,Inter,sans-serif">AI participants</div>
          <div v-for="row in aiParticipants" :key="row.model_key" class="rank-row mb-2">
            <div class="d-flex justify-space-between align-center ga-3">
              <div class="min-w-0">
                <strong>{{ row.display_name }}</strong>
                <div class="text-caption text-medium-emphasis">
                  {{ pairCopy(row.pairs_answered) }}
                  <template v-if="row.pairs_remaining > 0"> · {{ row.pairs_remaining }} remaining</template>
                </div>
              </div>
              <v-chip size="small" variant="tonal" :color="aiStatusColor(row.status)">{{ aiStatusLabel(row.status) }}</v-chip>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <v-row>
        <v-col cols="12" md="6">
          <v-card class="glass-card">
            <v-card-text class="pa-5">
              <div class="d-flex justify-space-between align-center mb-3">
                <div class="text-h6 font-weight-bold" style="font-family:Manrope,Inter,sans-serif">Options</div>
                <v-btn size="small" variant="text" color="primary" :to="`/projects/${project.id}/edit`">Edit</v-btn>
              </div>
              <div v-if="!activeAlts.length" class="text-medium-emphasis">
                Add at least two options before starting comparisons.
              </div>
              <div v-for="a in activeAlts" :key="a.id" class="rank-row mb-2">
                <strong>{{ a.title }}</strong>
                <div class="text-caption text-medium-emphasis">{{ a.description }}</div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card class="glass-card">
            <v-card-text class="pa-5">
              <div class="d-flex justify-space-between align-center mb-3">
                <div class="text-h6 font-weight-bold" style="font-family:Manrope,Inter,sans-serif">Factors</div>
                <v-btn size="small" variant="text" color="primary" :to="`/projects/${project.id}/edit`">Edit</v-btn>
              </div>
              <div v-if="!activeFactors.length" class="template-note">
                <i class="fa-solid fa-circle-check mt-1" />
                <div>
                  <b>Overall only</b><br>
                  Participants will compare options as a whole without separate factor prompts.
                </div>
              </div>
              <div v-for="f in activeFactors" :key="f.id" class="rank-row mb-2">
                <strong>{{ f.title }}</strong>
                <div class="text-caption text-medium-emphasis">{{ f.description }}</div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import type {
  AiAgentCounts,
  AiParticipantStatusItem,
  AnonymousShareItem,
  CustomerProject,
  HumanParticipantActiveItem,
  HumanParticipantPendingItem,
  ProjectPageContentItem,
  ProjectListMetrics,
  ProjectPageSummaryResult,
} from '~/types/api'
import { metricLabel } from '~/utils/ranking'
import { collectionIsClosed, projectRemainingTimeCopy } from '~/utils/projectEndTime'

const route = useRoute()
const snackbar = useSnackbar()
const api = useProjectsApi()
const votesApi = useVotesApi()
const { requireAdmin, isAdmin, aiFeaturesEnabled } = useAuth()
const runningAi = ref(false)

async function runAiBaseline() {
  if (!requireAdmin() || !project.value) return
  if (activeAlts.value.length < 2) {
    snackbar.error('Save at least two options before running AI agents')
    return
  }
  runningAi.value = true
  try {
    const res = await votesApi.runAiBaseline(project.value.id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    if (res.already_complete) snackbar.success('AI agents have already finished')
    else snackbar.success('AI agents started. Results appear when they finish.')
    await loadSummary(true)
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not start AI agents')
  }
  finally {
    runningAi.value = false
  }
}

const loading = ref(true)
const project = ref<CustomerProject | null>(null)
const alternatives = ref<ProjectPageContentItem[]>([])
const factors = ref<ProjectPageContentItem[]>([])
const myObservationCount = ref(0)
const participantCount = ref(0)
const targetComparisonsEst = ref(0)
const maxComparisonsEst = ref(0)
const activeParticipantCount = ref(0)
const aiAgentCounts = ref<AiAgentCounts>({ requested: 0, in_flight: 0, completed: 0 })
const humanActive = ref<HumanParticipantActiveItem[]>([])
const humanPending = ref<HumanParticipantPendingItem[]>([])
const humanAnonymous = ref<AnonymousShareItem[]>([])
const aiParticipants = ref<AiParticipantStatusItem[]>([])
const myMetrics = ref<ProjectListMetrics>({})
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
let pollBusy = false

const activeAlts = computed(() => alternatives.value.filter(a => !a.disabled))
const activeFactors = computed(() => factors.value.filter(f => !f.disabled))
const remainingTimeCopy = computed(() => projectRemainingTimeCopy(project.value?.end_time))
const inputClosed = computed(() => !!project.value?.disabled || collectionIsClosed(project.value?.end_time))
const canRunAiAgents = computed(() =>
  !!aiFeaturesEnabled.value
  && isAdmin.value
  && !!project.value?.include_ai_agents
  && (project.value?.ai_voter_models || []).length > 0,
)
const showHumanParticipants = computed(() =>
  humanActive.value.length > 0 || humanPending.value.length > 0 || humanAnonymous.value.length > 0,
)

function responseCopy(n: number) {
  return n === 1 ? '1 response' : `${n} responses`
}
function daysCopy(n: number) {
  return n === 1 ? '1 day' : `${n} days`
}
function activatedCopy(n: number) {
  return n === 1 ? '1 activated' : `${n} activated`
}
function pairCopy(n: number) {
  return n === 1 ? '1 pair answered' : `${n} pairs answered`
}
function aiStatusLabel(status: string) {
  if (status === 'in_progress') return 'in progress'
  return status || 'queued'
}
function aiStatusColor(status: string) {
  if (status === 'complete') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'in_progress') return 'primary'
  return undefined
}

function applySummary(res: ProjectPageSummaryResult) {
  project.value = res.project || null
  alternatives.value = res.alternatives || []
  factors.value = res.factors || []
  myObservationCount.value = res.my_observation_count || 0
  participantCount.value = res.participant_count || 0
  targetComparisonsEst.value = res.target_comparisons_est || 0
  maxComparisonsEst.value = res.max_comparisons_est || 0
  activeParticipantCount.value = res.active_participant_count || 0
  aiAgentCounts.value = res.ai_agent_counts || { requested: 0, in_flight: 0, completed: 0 }
  humanActive.value = res.human_participants?.active || []
  humanPending.value = res.human_participants?.pending || []
  humanAnonymous.value = res.human_participants?.anonymous_shares || []
  aiParticipants.value = res.ai_participants || []
  myMetrics.value = res.my_metrics || {}
}

function syncAiPoll() {
  const need = (aiAgentCounts.value?.in_flight || 0) > 0
  if (need && !pollTimer.value) {
    pollTimer.value = setInterval(() => { void loadSummary(true) }, 4000)
  }
  else if (!need && pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function loadSummary(silent = false) {
  if (pollBusy) return
  pollBusy = true
  if (!silent) loading.value = true
  try {
    const res = await api.getProjectPageSummary(Number(route.params.id))
    if (res.failure_reason || !res.project) throw new Error(res.failure_reason || 'Project not found')
    applySummary(res)
  }
  catch (e: unknown) {
    if (!silent) snackbar.error(e instanceof Error ? e.message : 'Failed to load project')
  }
  finally {
    pollBusy = false
    if (!silent) loading.value = false
    syncAiPoll()
  }
}

const nextAction = computed(() => {
  const id = project.value?.id
  if (!id) return { title: '', detail: '', label: '', to: '/projects' }
  if (activeAlts.value.length < 2) {
    return {
      title: 'Complete project setup',
      detail: 'Add at least two realistic options before collecting input.',
      label: 'Continue setup',
      to: `/projects/${id}/edit`,
    }
  }
  if (inputClosed.value) {
    return {
      title: 'Review current results',
      detail: 'Comparison collection is closed. Results remain available.',
      label: 'View results',
      to: `/projects/${id}/results`,
    }
  }
  if (myObservationCount.value === 0 && participantCount.value === 0) {
    return {
      title: 'Begin collecting input',
      detail: 'Invite people or start comparing yourself.',
      label: 'Start comparing',
      to: `/projects/${id}/probe`,
    }
  }
  return {
    title: 'Review current results',
    detail: `Confidence is ${metricLabel(Number(myMetrics.value.confidence ?? 0))}. Open results to explain the outcome.`,
    label: 'View results',
    to: `/projects/${id}/results`,
  }
})

function makeDuplicate() {
  if (!requireAdmin() || !project.value) return
  navigateTo(`/projects/0/edit?from=${project.value.id}`)
}

onMounted(() => {
  void loadSummary()
})
onUnmounted(() => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
})
</script>

<style scoped>
@media (max-width: 960px) {
  .summary-hero {
    grid-template-columns: 1fr !important;
  }
}
</style>
