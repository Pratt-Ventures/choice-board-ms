import type {
  CustomerProject,
  CustomerProjectAlternative,
  CustomerProjectFactor,
  VoteParticipant,
} from '~/types/api'
import {
  type RankItem,
  defaultRankingSettings,
  mergeRankingSettings,
  type RankingSettings,
} from '~/utils/ranking'

const LOCAL_SETTINGS_KEY = 'power-choice:v1:ranking-settings'

function loadLocalRankingSettings(): Partial<RankingSettings> {
  if (!import.meta.client) return {}
  try {
    const raw = localStorage.getItem(LOCAL_SETTINGS_KEY)
    if (raw) return JSON.parse(raw)
  }
  catch { /* ignore */ }
  return {}
}

export function useProjectWorkspace() {
  const api = useProjectsApi()
  const votesApi = useVotesApi()
  const { context } = useAuth()

  const project = ref<CustomerProject | null>(null)
  const alternatives = ref<CustomerProjectAlternative[]>([])
  const factors = ref<CustomerProjectFactor[]>([])
  const myGroups = ref<Record<string, unknown>[]>([])
  const myObservations = ref<unknown[]>([]) // legacy empty
  const myParticipant = ref<VoteParticipant | null>(null)
  const allGroups = ref<Record<string, unknown>[]>([])
  const allObservations = ref<unknown[]>([])
  const participants = ref<VoteParticipant[]>([])
  const report = ref<Record<string, unknown> | null>(null)
  const loading = ref(false)
  const nextGroup = ref<Record<string, unknown> | null>(null)
  const nextQuestions = ref<unknown[]>([])
  const progress = ref<Record<string, unknown>>({})
  const settings = ref<RankingSettings>(mergeRankingSettings(
    loadLocalRankingSettings(),
    context.value?.settings as Record<string, unknown> | undefined,
  ))

  const altItems = computed<RankItem[]>(() =>
    alternatives.value
      .filter(a => !a.disabled)
      .map(a => ({
        id: a.id,
        title: a.alternative_title || `Option ${a.id}`,
        description: a.alternative_description,
      })),
  )

  const factorItems = computed<RankItem[]>(() =>
    factors.value
      .filter(f => !f.disabled)
      .map(f => ({
        id: f.id,
        title: f.factor_title || `Factor ${f.id}`,
        description: f.factor_description,
      })),
  )

  async function loadProject(projectId: number, opts: {
    bundle?: boolean
    myVote?: boolean
    requestNext?: boolean
  } = {}) {
    loading.value = true
    try {
      const [p, alts, facts] = await Promise.all([
        api.getProject(projectId),
        api.listAlternatives(projectId),
        api.listFactors(projectId),
      ])
      if (p.failure_reason || !p.customer_project_info) {
        throw new Error(p.failure_reason || 'Project not found')
      }
      project.value = p.customer_project_info
      alternatives.value = alts.alternative_info_list || []
      factors.value = facts.factor_info_list || []

      settings.value = mergeRankingSettings(
        loadLocalRankingSettings(),
        context.value?.settings as Record<string, unknown> | undefined,
      )

      if (opts.myVote !== false) {
        const mine = await votesApi.getMyVote(projectId, opts.requestNext !== false) as any
        myParticipant.value = mine.participant_info || null
        myGroups.value = mine.groups || []
        myObservations.value = []
        nextGroup.value = mine.next_group || null
        progress.value = mine.progress || {}
        nextQuestions.value = mine.next_group ? [mine.next_group] : []
      }

      if (opts.bundle) {
        const bundle = await votesApi.projectBundle(projectId) as any
        participants.value = bundle.participants || []
        allGroups.value = bundle.groups || []
        allObservations.value = []
        report.value = bundle.report || null
      }
      return project.value
    }
    finally {
      loading.value = false
    }
  }

  async function refreshMyVote(projectId: number, requestNext = true) {
    const mine = await votesApi.getMyVote(projectId, requestNext) as any
    myParticipant.value = mine.participant_info || null
    myGroups.value = mine.groups || []
    nextGroup.value = mine.next_group || null
    progress.value = mine.progress || {}
    nextQuestions.value = mine.next_group ? [mine.next_group] : []
  }

  async function refreshReport(projectId: number) {
    const res = await votesApi.projectReport(projectId, true)
    report.value = res.report || null
    return report.value
  }

  return {
    project,
    alternatives,
    factors,
    myGroups,
    myObservations,
    myParticipant,
    allGroups,
    allObservations,
    participants,
    report,
    loading,
    settings,
    nextGroup,
    nextQuestions,
    progress,
    altItems,
    factorItems,
    loadProject,
    refreshMyVote,
    refreshReport,
  }
}
