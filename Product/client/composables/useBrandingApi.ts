import type { BrandingImageResult, ShareBrandingMetaResult } from '~/types/api'
import { ApiError } from '~/composables/useApi'

function resolveBaseUrl(): string {
  const config = useRuntimeConfig()
  if (import.meta.client && import.meta.dev) {
    return ''
  }
  return (config.public.apiBase as string) || ''
}

export function useBrandingApi() {
  const { apiFetch } = useApi()

  async function customerMeta() {
    return apiFetch<BrandingImageResult>('/ws/branding/customer-meta')
  }

  async function projectMeta(projectId: number) {
    return apiFetch<BrandingImageResult>('/ws/branding/project-meta', {
      query: { project_id: projectId },
    })
  }

  function customerImageUrl(cacheKey?: string | number | null) {
    const base = resolveBaseUrl()
    const q = cacheKey ? `?v=${encodeURIComponent(String(cacheKey))}` : ''
    return `${base}/ws/branding/customer-image${q}`
  }

  function projectImageUrl(projectId: number, cacheKey?: string | number | null) {
    const base = resolveBaseUrl()
    const q = new URLSearchParams({ project_id: String(projectId) })
    if (cacheKey) q.set('v', String(cacheKey))
    return `${base}/ws/branding/project-image?${q.toString()}`
  }

  function shareCustomerImageUrl(token: string, cacheKey?: string | number | null) {
    const base = resolveBaseUrl()
    const q = cacheKey ? `?v=${encodeURIComponent(String(cacheKey))}` : ''
    return `${base}/ext-ws/share/${encodeURIComponent(token)}/customer-image${q}`
  }

  function shareProjectImageUrl(token: string, cacheKey?: string | number | null) {
    const base = resolveBaseUrl()
    const q = cacheKey ? `?v=${encodeURIComponent(String(cacheKey))}` : ''
    return `${base}/ext-ws/share/${encodeURIComponent(token)}/project-image${q}`
  }

  async function shareBranding(token: string) {
    return apiFetch<ShareBrandingMetaResult>(`/ext-ws/share/${encodeURIComponent(token)}/branding`)
  }

  async function uploadMultipart(path: string, form: FormData): Promise<BrandingImageResult> {
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
    return data as BrandingImageResult
  }

  async function uploadCustomerImage(file: File) {
    const form = new FormData()
    form.append('file', file)
    return uploadMultipart('/ws/branding/customer-image', form)
  }

  async function deleteCustomerImage() {
    return apiFetch<BrandingImageResult>('/ws/branding/customer-image', { method: 'DELETE' })
  }

  async function uploadProjectImage(projectId: number, file: File) {
    const form = new FormData()
    form.append('project_id', String(projectId))
    form.append('file', file)
    return uploadMultipart('/ws/branding/project-image', form)
  }

  async function deleteProjectImage(projectId: number) {
    return apiFetch<BrandingImageResult>('/ws/branding/project-image', {
      method: 'DELETE',
      query: { project_id: projectId },
    })
  }

  return {
    customerMeta,
    projectMeta,
    customerImageUrl,
    projectImageUrl,
    shareCustomerImageUrl,
    shareProjectImageUrl,
    shareBranding,
    uploadCustomerImage,
    deleteCustomerImage,
    uploadProjectImage,
    deleteProjectImage,
  }
}
