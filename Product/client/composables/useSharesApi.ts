import type {
  WsResultPackage,
  ShareLink,
  CreateShareLinkResponse,
  SendShareInvitationResponse,
  ShareActivityResultsSingle,
  ShareActivityResultsMulti,
  ShareAccessPayload,
} from '~/types/api'

export type ShareType = 'vote' | 'vote_view' | 'report' | 'not_set'
export type ShareAccessMode =
  | 'open_access'
  | 'email_any_unverified'
  | 'email_any_verified'
  | 'email_matching'
  | 'email_matching_verified'
  | 'recipient_email_verified'
  | 'password_only'
  | 'password_with_email_any_unverified'
  | 'password_with_email_any_verified'
  | 'password_with_email_matching'
  | 'password_with_email_matching_verified'
  | 'password_with_recipient_email_verified'
  | 'not_specified'

export function useSharesApi() {
  const { apiFetch } = useApi()

  async function createShareLink(body: {
    shared_type: ShareType
    shared_entity_db_id: number
    link_auto_send?: boolean
    shared_with_company_name?: string | null
    shared_with_person_name?: string | null
    shared_with_email?: string | null
    share_link_name?: string | null
    share_link_expiration?: number
    access_mode: ShareAccessMode
    share_password?: string | null
    share_password_in_email?: boolean
    cookie_duration?: number
  }) {
    return apiFetch<CreateShareLinkResponse>('/ws/create-share-link', {
      method: 'POST',
      body,
    })
  }

  async function extendOrDisable(body: {
    share_id?: number | null
    magic_token?: string | null
    share_link_enabled?: boolean | null
    share_link_expiration?: number | null
  }) {
    return apiFetch<WsResultPackage & { link_id?: number | null }>('/ws/extend-or-disable-share-link', {
      method: 'POST',
      body,
    })
  }

  async function sendInvitation(body: {
    share_id?: number | null
    magic_token?: string | null
  }) {
    return apiFetch<SendShareInvitationResponse>('/ws/send-share-invitation', {
      method: 'POST',
      body,
    })
  }

  async function activityForProject(projectId: number) {
    return apiFetch<ShareActivityResultsSingle>('/ws/get-share-activity-single-project', {
      query: { project_id: projectId },
    })
  }

  async function activityForProjects(projectIds: number[]) {
    return apiFetch<ShareActivityResultsMulti>('/ws/get-share-activity-multiple-projects', {
      method: 'POST',
      body: projectIds,
    })
  }

  async function extAccess(token: string, kind: 'vote' | 'vote_view' | 'report', body: Record<string, unknown> = {}) {
    const kindPath = kind === 'vote_view' ? 'vote-view' : kind
    return apiFetch<ShareAccessPayload>(`/ext-ws/share/${encodeURIComponent(token)}/${kindPath}`, {
      method: 'POST',
      body,
    })
  }

  async function extNextGroup(token: string, body: Record<string, unknown> = {}) {
    return apiFetch<ShareAccessPayload>(`/ext-ws/share/${encodeURIComponent(token)}/vote/next-group`, {
      method: 'POST',
      body,
    })
  }

  async function extCompleteGroup(token: string, body: Record<string, unknown>) {
    return apiFetch<ShareAccessPayload>(`/ext-ws/share/${encodeURIComponent(token)}/vote/complete-group`, {
      method: 'POST',
      body,
    })
  }

  async function extSaveGroup(token: string, body: Record<string, unknown>) {
    return apiFetch<ShareAccessPayload>(`/ext-ws/share/${encodeURIComponent(token)}/vote/save-group`, {
      method: 'POST',
      body,
    })
  }

  async function extComplete(token: string, body: Record<string, unknown> = {}) {
    return apiFetch<ShareAccessPayload>(`/ext-ws/share/${encodeURIComponent(token)}/vote/complete`, {
      method: 'POST',
      body,
    })
  }

  async function extLogout(token: string) {
    return apiFetch<void>(`/ext-ws/share/${encodeURIComponent(token)}/logout`)
  }

  return {
    createShareLink,
    extendOrDisable,
    sendInvitation,
    activityForProject,
    activityForProjects,
    extAccess,
    extNextGroup,
    extCompleteGroup,
    extSaveGroup,
    extComplete,
    extLogout,
  }
}

export type { ShareLink }
