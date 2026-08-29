import type {
  UserCommunicationAdminModifyPayload,
  UserCommunicationDeleteResult,
  UserCommunicationKind,
  UserCommunicationResultMany,
  UserCommunicationResultOne,
  UserCommunicationSubmitResult,
} from '~/types/api'
import { ApiError } from '~/composables/useApi'

function resolveBaseUrl(): string {
  const config = useRuntimeConfig()
  if (import.meta.client && import.meta.dev) {
    return ''
  }
  return (config.public.apiBase as string) || ''
}

function prefixFor(kind: UserCommunicationKind) {
  return kind === 'bug_report' ? 'bug-report' : 'suggestion'
}

export function useUserCommunicationApi() {
  const { apiFetch } = useApi()

  async function uploadMultipart(path: string, form: FormData): Promise<UserCommunicationSubmitResult> {
    const base = resolveBaseUrl()
    const url = new URL(
      path.startsWith('http') ? path : `${base}${path}`,
      import.meta.client ? window.location.origin : 'http://localhost:3000',
    )
    const response = await fetch(url.toString(), {
      method: 'POST',
      body: form,
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      let message = `Request failed (${response.status})`
      if (data && typeof data === 'object') {
        const detail = (data as { detail?: unknown; failure_reason?: string }).detail
        const failure = (data as { failure_reason?: string }).failure_reason
        if (typeof detail === 'string') message = detail
        else if (Array.isArray(detail)) message = detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ')
        else if (failure) message = failure
      }
      throw new ApiError(message, response.status, data)
    }
    return data as UserCommunicationSubmitResult
  }

  async function submitBug(fields: {
    summary: string
    what_happened: string
    expected_happened?: string
    steps_to_reproduce?: string
    impact?: string
    file?: File | null
  }) {
    const form = new FormData()
    form.append('summary', fields.summary)
    form.append('what_happened', fields.what_happened)
    if (fields.expected_happened) form.append('expected_happened', fields.expected_happened)
    if (fields.steps_to_reproduce) form.append('steps_to_reproduce', fields.steps_to_reproduce)
    if (fields.impact) form.append('impact', fields.impact)
    if (fields.file) form.append('file', fields.file)
    return uploadMultipart('/ws/user-comm/bug-report-submit', form)
  }

  async function submitSuggestion(fields: {
    suggestion: string
    accomplish_goal?: string
    product_area?: string
    importance?: string
    file?: File | null
  }) {
    const form = new FormData()
    form.append('suggestion', fields.suggestion)
    if (fields.accomplish_goal) form.append('accomplish_goal', fields.accomplish_goal)
    if (fields.product_area) form.append('product_area', fields.product_area)
    if (fields.importance) form.append('importance', fields.importance)
    if (fields.file) form.append('file', fields.file)
    return uploadMultipart('/ws/user-comm/suggestion-submit', form)
  }

  async function retrieve(kind: UserCommunicationKind) {
    return apiFetch<UserCommunicationResultMany>(`/ws/user-comm/${prefixFor(kind)}-retrieve`, {
      method: 'POST',
    })
  }

  async function adminRetrieve(kind: UserCommunicationKind, offset = 0, limit = 25) {
    return apiFetch<UserCommunicationResultMany>(`/ws/user-comm/${prefixFor(kind)}-admin-retrieve`, {
      method: 'POST',
      body: { offset, limit },
    })
  }

  async function adminModify(kind: UserCommunicationKind, payload: UserCommunicationAdminModifyPayload) {
    return apiFetch<UserCommunicationResultOne>(`/ws/user-comm/${prefixFor(kind)}-admin-modify`, {
      method: 'POST',
      body: payload,
    })
  }

  async function remove(kind: UserCommunicationKind, id: number) {
    return apiFetch<UserCommunicationDeleteResult>(`/ws/user-comm/${prefixFor(kind)}-delete`, {
      method: 'POST',
      body: { id },
    })
  }

  function attachmentUrl(kind: UserCommunicationKind, id: number) {
    const base = resolveBaseUrl()
    return `${base}/ws/user-comm/${prefixFor(kind)}-attachment/${id}`
  }

  return {
    submitBug,
    submitSuggestion,
    retrieve,
    adminRetrieve,
    adminModify,
    remove,
    attachmentUrl,
  }
}
