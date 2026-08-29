import type {
  WsResultPackage,
  VoteParticipant,
  ProjectReportResult,
  ParticipantBundleResult,
  ProjectVoteBundleResult,
} from '~/types/api'

export type GroupPackage = {
  client_group_id: string
  group_token?: string
  pass_index: number
  group_type: string
  criterion_id?: number | null
  sort_algorithm: string
  item_ids_initial: number[]
  rank_order: number[]
  pairings: Array<{
    winner_id: number
    loser_id: number
    response: string
    decision_seconds: number
    presented_left_id?: number | null
    presented_right_id?: number | null
    effective_rule?: string
  }>
  algorithm_version?: string
  event_timestamp?: string | null
}

export type SortSessionResult = WsResultPackage & {
  participant_info?: VoteParticipant | null
  groups?: unknown[]
  next_group?: Record<string, unknown> | null
  progress?: Record<string, unknown>
  session_complete?: boolean
  project_settings?: Record<string, unknown>
  group_info?: unknown
}

export function useVotesApi() {
  const { apiFetch } = useApi()

  async function getMyVote(projectId: number, requestNext = true) {
    return apiFetch<ParticipantBundleResult & SortSessionResult>('/ws/project-votes/my-vote', {
      query: {
        project_id: projectId,
        request_next: requestNext,
      },
    })
  }

  async function nextGroup(projectId: number) {
    return apiFetch<SortSessionResult>('/ws/project-votes/next-group', {
      method: 'POST',
      body: { project_id: projectId },
    })
  }

  async function completeGroup(projectId: number, priorGroup: GroupPackage | null = null) {
    return apiFetch<SortSessionResult>('/ws/project-votes/complete-group', {
      method: 'POST',
      body: { project_id: projectId, prior_group: priorGroup },
    })
  }

  async function saveGroup(projectId: number, priorGroup: GroupPackage) {
    return apiFetch<SortSessionResult>('/ws/project-votes/save-group', {
      method: 'POST',
      body: { project_id: projectId, prior_group: priorGroup },
    })
  }

  async function markComplete(projectId: number, isComplete = true) {
    return apiFetch<WsResultPackage & {
      participant_info?: VoteParticipant | null
      votes_captured?: number
      groups_captured?: number
      submitter_summary?: Record<string, unknown> | null
      personal_vote?: Record<string, unknown> | null
    }>(
      '/ws/project-votes/mark-complete',
      { method: 'POST', body: { project_id: projectId, is_complete: isComplete } },
    )
  }

  async function listParticipants(projectId: number) {
    return apiFetch<WsResultPackage & { participant_info_list?: VoteParticipant[] | null }>(
      '/ws/project-votes/participants',
      { query: { project_id: projectId } },
    )
  }

  async function participantDetail(projectId: number, participantId: number) {
    return apiFetch<ParticipantBundleResult>('/ws/project-votes/participant-detail', {
      query: { project_id: projectId, participant_id: participantId },
    })
  }

  async function projectReport(projectId: number, includeParticipants = true) {
    return apiFetch<ProjectReportResult>('/ws/project-votes/project-report', {
      method: 'POST',
      body: { project_id: projectId, include_participants: includeParticipants },
    })
  }

  async function projectBundle(projectId: number) {
    return apiFetch<ProjectVoteBundleResult>('/ws/project-votes/project-bundle', {
      query: { project_id: projectId },
    })
  }

  async function runAiBaseline(projectId: number, models?: string[]) {
    return apiFetch<WsResultPackage & {
      job?: {
        id?: number | null
        project_id?: number | null
        model_key?: string
        status?: string
        pair_count?: number
        skip_count?: number
        group_count?: number
        error_summary?: string | null
        participant_complete?: boolean
        display_name?: string | null
      } | null
      jobs?: Array<{
        id?: number | null
        project_id?: number | null
        model_key?: string
        status?: string
        pair_count?: number
        skip_count?: number
        group_count?: number
        error_summary?: string | null
        participant_complete?: boolean
        display_name?: string | null
      }>
      already_complete?: boolean
    }>('/ws/project-votes/ai-baseline-run', {
      method: 'POST',
      body: { project_id: projectId, models },
    })
  }

  async function aiBaselineStatus(projectId: number) {
    return apiFetch<WsResultPackage & {
      job?: {
        id?: number | null
        project_id?: number | null
        status?: string
        pair_count?: number
        skip_count?: number
        group_count?: number
        error_summary?: string | null
        participant_complete?: boolean
      } | null
      already_complete?: boolean
    }>('/ws/project-votes/ai-baseline-status', {
      query: { project_id: projectId },
    })
  }

  async function pivotDetail(body: {
    project_id: number
    primary_axis: 'alternatives' | 'factors' | 'participants'
    row_id?: number | null
    alternative_id?: number | null
    factor_id?: number | null
    participant_id?: number | null
  }) {
    return apiFetch<WsResultPackage & { project_id?: number, detail?: Record<string, unknown> }>(
      '/ws/project-votes/report-pivot-detail',
      { method: 'POST', body },
    )
  }

  return {
    getMyVote,
    nextGroup,
    completeGroup,
    saveGroup,
    markComplete,
    listParticipants,
    participantDetail,
    projectReport,
    projectBundle,
    runAiBaseline,
    aiBaselineStatus,
    pivotDetail,
  }
}
