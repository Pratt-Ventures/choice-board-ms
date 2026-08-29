import type { DashboardEntriesView, RequestDashboardEntries } from '~/types/api'

export function useDashboardApi() {
  const { apiFetch } = useApi()

  async function fetchDashboard(request: RequestDashboardEntries = {}) {
    return apiFetch<DashboardEntriesView>('/ws/core/get-dashboard-information', {
      method: 'POST',
      body: {
        recent_limit: request.recent_limit ?? 14,
        application_tag: request.application_tag ?? null,
      },
    })
  }

  return { fetchDashboard }
}
