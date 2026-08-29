<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Workspace</div>
        <div class="page-title">{{ greeting }}</div>
        <div class="page-subtitle">
          Create, organize, and revisit every decision project.
        </div>
      </div>
      <div class="head-actions">
        <v-btn color="primary" variant="flat" @click="navigateTo('/projects/new')">
          <i class="fa-solid fa-plus mr-2" /> Create Project
        </v-btn>
      </div>
    </div>

    <div v-if="spotlight" class="welcome-banner">
      <div>
        <div class="eyebrow">Needs attention</div>
        <h2>{{ spotlight.project.project_title || spotlight.project.project_tag }}</h2>
        <p>{{ spotlightBlurb }}</p>
        <div class="welcome-actions">
          <v-btn
            color="white"
            variant="flat"
            class="text-primary"
            @click="navigateTo(spotlightHref)"
          >
            {{ spotlight.action }}
          </v-btn>
          <v-btn
            variant="text"
            style="color:#fff"
            @click="navigateTo(`/projects/${spotlight.project.id}`)"
          >
            Open project
          </v-btn>
        </div>
      </div>
      <div class="welcome-art" aria-hidden="true">
        <span /><span />
        <i class="fa-solid fa-chart-line" />
      </div>
    </div>

    <v-row class="mb-5" dense>
      <v-col v-for="m in summaryMetrics" :key="m.label" cols="6" md="3">
        <v-card class="metric-card">
          <v-card-text class="pa-5">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value">{{ m.value }}</div>
            <div v-if="m.detail" class="metric-detail">{{ m.detail }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <div class="d-flex flex-wrap ga-3 mb-4 align-center">
      <h2 class="text-h6 font-weight-bold mr-auto mb-0" style="font-family:Manrope,Inter,sans-serif">
        Your projects
      </h2>
      <v-text-field
        v-model="search"
        placeholder="Search projects"
        prepend-inner-icon="mdi-magnify"
        hide-details
        density="compact"
        style="max-width:320px"
        clearable
      />
      <v-btn-toggle v-model="viewMode" mandatory density="compact" color="primary" rounded="lg">
        <v-btn value="tiles" size="small" aria-label="Card view"><i class="fa-solid fa-table-cells-large" /></v-btn>
        <v-btn value="table" size="small" aria-label="Table view"><i class="fa-solid fa-list" /></v-btn>
      </v-btn-toggle>
      <v-btn variant="text" :loading="loading" @click="load"><i class="fa-solid fa-rotate mr-2" />Refresh</v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <div v-if="!loading && !filtered.length" class="empty-state py-16">
      <div class="brand-badge mx-auto mb-4" style="width:54px;height:54px">
        <i class="fa-solid fa-folder-open" />
      </div>
      <div class="text-h6 font-weight-bold" style="color:var(--pc-ink)">No projects yet</div>
      <div class="text-body-2 mt-2 mb-4" style="max-width:360px;margin-inline:auto">
        Start with a project name, add options, and invite people when you are ready.
      </div>
      <v-btn color="primary" @click="navigateTo('/projects/new')">
        <i class="fa-solid fa-plus mr-2" /> Create Project
      </v-btn>
    </div>

    <v-row v-else-if="viewMode === 'tiles'">
      <v-col v-for="row in filtered" :key="row.project.id" cols="12" md="6" lg="6">
        <v-card class="glass-card project-card">
          <v-card-text class="pa-5">
            <div class="d-flex justify-space-between ga-2 mb-2">
              <div class="d-flex flex-wrap ga-2">
                <span :class="['status', statusMeta(row).className]">{{ statusMeta(row).label }}</span>
                <span class="status status-ready">
                  {{ row.project.project_exclusive_mode ? 'Pick one' : 'Rank all' }}
                </span>
              </div>
              <v-menu>
                <template #activator="{ props }">
                  <v-btn v-bind="props" icon variant="text" size="small" aria-label="More actions">
                    <i class="fa-solid fa-ellipsis" />
                  </v-btn>
                </template>
                <v-list density="compact">
                  <v-list-item
                    v-for="item in projectMenuItems(row)"
                    :key="item.title"
                    :title="item.title"
                    :class="item.className"
                    @click="item.run()"
                  />
                </v-list>
              </v-menu>
            </div>

            <div class="project-card-title mt-2">
              {{ row.project.project_title || row.project.project_tag }}
            </div>
            <div class="text-body-2 text-medium-emphasis mt-1" style="min-height:40px">
              {{ row.project.project_description || 'No description yet.' }}
            </div>

            <div class="project-meta">
              <span><i class="fa-solid fa-shapes" />{{ row.altCount }} options</span>
              <span><i class="fa-solid fa-sliders" />{{ row.factorCount }} factors</span>
              <span><i class="fa-solid fa-user-group" />{{ row.participantCount }} participants</span>
              <span><i class="fa-solid fa-code-compare" />{{ row.obsCount }} responses</span>
            </div>

            <div class="mt-4">
              <div class="d-flex justify-space-between text-caption mb-2">
                <span>{{ row.obsCount > 0 ? 'Participation' : 'Setup readiness' }}</span>
                <strong>{{ row.metrics.completion }}%</strong>
              </div>
              <div class="stability-track">
                <span
                  class="bar-fill"
                  :class="{ success: row.metrics.completion >= 90 }"
                  :style="{ width: Math.min(100, row.metrics.completion) + '%' }"
                />
              </div>
              <div v-if="row.obsCount > 0" class="d-flex justify-space-between text-caption mt-2">
                <span>Stability: <span class="metric-state">{{ metricLabel(row.metrics.stability) }}</span></span>
                <span>Confidence: <span class="metric-state">{{ metricLabel(row.metrics.confidence) }}</span></span>
              </div>
            </div>

            <div class="d-flex flex-wrap ga-2 mt-5 align-center justify-space-between">
              <span class="text-caption text-medium-emphasis">
                {{ row.project.project_exclusive_mode ? 'Pick one' : 'Rank all' }}
                · {{ row.project.disabled || collectionIsClosed(row.project.end_time) ? 'Input closed' : 'Open' }}
              </span>
              <div class="d-flex flex-wrap ga-2">
                <v-btn
                  :color="primaryAction(row).color"
                  :variant="primaryAction(row).variant"
                  size="small"
                  @click="navigateTo(primaryAction(row).to)"
                >
                  {{ primaryAction(row).label }}
                  <i class="fa-solid fa-arrow-right ml-2" style="font-size:11px" />
                </v-btn>
                <v-btn variant="text" size="small" @click="navigateTo(`/projects/${row.project.id}`)">
                  Open
                </v-btn>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card v-else class="glass-card">
      <v-table class="data-table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Status</th>
            <th>Type</th>
            <th>Options</th>
            <th>Participants</th>
            <th>Progress</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.project.id" @click="navigateTo(`/projects/${row.project.id}`)">
            <td>
              <div class="font-weight-bold">{{ row.project.project_title || row.project.project_tag }}</div>
              <div class="text-caption text-medium-emphasis">{{ row.project.project_description || row.project.project_tag }}</div>
            </td>
            <td><span :class="['status', statusMeta(row).className]">{{ statusMeta(row).label }}</span></td>
            <td>{{ row.project.project_exclusive_mode ? 'Pick one' : 'Rank all' }}</td>
            <td>{{ row.altCount }}</td>
            <td>{{ row.participantCount }}</td>
            <td style="min-width:140px">
              <v-progress-linear :model-value="row.metrics.completion" height="8" rounded color="primary" />
            </td>
            <td class="text-right" @click.stop>
              <v-menu>
                <template #activator="{ props }">
                  <v-btn v-bind="props" icon variant="text" size="small" aria-label="More actions">
                    <i class="fa-solid fa-ellipsis" />
                  </v-btn>
                </template>
                <v-list density="compact">
                  <v-list-item
                    v-for="item in projectMenuItems(row)"
                    :key="item.title"
                    :title="item.title"
                    :class="item.className"
                    @click="item.run()"
                  />
                </v-list>
              </v-menu>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card class="pc-dialog-card">
        <v-card-title class="pa-6 pb-2 text-h6 font-weight-bold font-display">Delete project?</v-card-title>
        <v-card-text class="px-6 pt-2">
          This soft-deletes <strong>{{ pendingDelete?.project_title || pendingDelete?.project_tag }}</strong>.
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" :loading="deleting" @click="doDelete">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type { CustomerProject } from '~/types/api'
import { metricLabel, asMetricPercent } from '~/utils/ranking'
import { collectionIsClosed } from '~/utils/projectEndTime'

const api = useProjectsApi()
const snackbar = useSnackbar()
const { requireAdmin, userName } = useAuth()

const loading = ref(true)
const search = ref('')
const viewMode = ref<'tiles' | 'table'>('tiles')
const rows = ref<Array<{
  project: CustomerProject
  altCount: number
  factorCount: number
  obsCount: number
  participantCount: number
  metrics: { completion: number, stability: number, confidence: number }
}>>([])
const deleteDialog = ref(false)
const pendingDelete = ref<CustomerProject | null>(null)
const deleting = ref(false)

type ProjectRow = typeof rows.value[number]

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(r =>
    (r.project.project_title || '').toLowerCase().includes(q)
    || (r.project.project_tag || '').toLowerCase().includes(q)
    || (r.project.project_description || '').toLowerCase().includes(q),
  )
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  const first = (userName.value || '').trim().split(/\s+/)[0]
  const name = first || 'there'
  if (hour < 12) return `Good morning, ${name}.`
  if (hour < 18) return `Good afternoon, ${name}.`
  return `Good evening, ${name}.`
})

const summaryMetrics = computed(() => {
  const active = rows.value.filter(r => !r.project.disabled).length
  const withResponses = rows.value.filter(r => r.obsCount > 0).length
  const totalObs = rows.value.reduce((s, r) => s + r.obsCount, 0)
  const participants = rows.value.reduce((s, r) => s + r.participantCount, 0)
  return [
    { label: 'Active projects', value: active, detail: `${withResponses} collecting input` },
    { label: 'Responses', value: totalObs, detail: 'Comparisons recorded' },
    { label: 'With results', value: withResponses, detail: 'Projects with rankings' },
    { label: 'Participants', value: participants, detail: 'Across all projects' },
  ]
})

const spotlight = computed(() => {
  if (!rows.value.length) return null
  const ranked = [...rows.value].sort((a, b) => {
    const score = (r: ProjectRow) => {
      if (r.project.disabled) return 0
      if (r.altCount < 2) return 40
      if (r.obsCount === 0) return 30
      if (r.metrics.completion >= 80 && r.metrics.completion < 100) return 50
      return r.metrics.completion
    }
    return score(b) - score(a)
  })
  const row = ranked[0]
  const action = primaryAction(row)
  return { ...row, action: action.label }
})

const spotlightHref = computed(() => spotlight.value ? primaryAction(spotlight.value).to : '/projects')

const spotlightBlurb = computed(() => {
  if (!spotlight.value) return ''
  const r = spotlight.value
  if (r.altCount < 2) return 'Add at least two options before collecting input.'
  if (r.obsCount === 0) return 'The project is ready for comparisons. Invite people or start comparing yourself.'
  if (r.metrics.completion >= 80) {
    return `${r.participantCount || 'Several'} participants have responded. Preliminary results are available to review.`
  }
  return 'Continue collecting input or review the current ranking direction.'
})

function statusMeta(row: ProjectRow) {
  if (row.project.disabled || collectionIsClosed(row.project.end_time)) return { label: 'Input closed', className: 'status-closed' }
  if (row.altCount < 2) return { label: 'Needs attention', className: 'status-attention' }
  if (row.obsCount === 0) return { label: 'Ready', className: 'status-ready' }
  if (row.metrics.completion >= 95) return { label: 'Results available', className: 'status-results' }
  return { label: 'Collecting input', className: 'status-collecting' }
}

function primaryAction(row: ProjectRow) {
  const id = row.project.id
  if (row.altCount < 2) {
    return { label: 'Continue setup', to: `/projects/${id}/edit`, color: 'primary', variant: 'tonal' as const }
  }
  if (row.project.disabled || collectionIsClosed(row.project.end_time)) {
    return { label: 'View results', to: `/projects/${id}/results`, color: 'primary', variant: 'flat' as const }
  }
  if (row.obsCount === 0) {
    return { label: 'Start comparing', to: `/projects/${id}/probe`, color: 'primary', variant: 'flat' as const }
  }
  if (row.metrics.completion >= 80) {
    return { label: 'View results', to: `/projects/${id}/results`, color: 'primary', variant: 'flat' as const }
  }
  return { label: 'View preliminary results', to: `/projects/${id}/results`, color: 'primary', variant: 'flat' as const }
}

function projectMenuItems(row: ProjectRow) {
  const id = row.project.id
  const items: Array<{ title: string, className?: string, run: () => void }> = [
    { title: 'Open project', run: () => navigateTo(`/projects/${id}`) },
    { title: 'Edit Settings', run: () => navigateTo(`/projects/${id}/edit`) },
    { title: 'Make a copy', run: () => makeDuplicate(id) },
    { title: 'Invite people', run: () => navigateTo(`/projects/${id}/shares?invite=1`) },
  ]
  if (row.altCount >= 2 && !row.project.disabled && !collectionIsClosed(row.project.end_time)) {
    items.push({ title: 'Start comparing', run: () => navigateTo(`/projects/${id}/probe`) })
  }
  items.push(
    { title: 'View results', run: () => navigateTo(`/projects/${id}/results`) },
    { title: 'Delete', className: 'text-error', run: () => confirmDelete(row.project) },
  )
  return items
}

async function load() {
  loading.value = true
  try {
    const result = await api.listProjectsSummary()
    if (result.failure_reason) throw new Error(result.failure_reason)
    rows.value = (result.projects || []).map(item => ({
      project: item.project,
      altCount: item.alternative_count || 0,
      factorCount: item.factor_count || 0,
      obsCount: item.observation_count || 0,
      participantCount: item.participant_count || 0,
      metrics: {
        completion: asMetricPercent(item.metrics?.completion ?? 0),
        stability: asMetricPercent(item.metrics?.stability ?? 0),
        confidence: asMetricPercent(item.metrics?.confidence ?? 0),
      },
    }))
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Failed to load projects')
  }
  finally {
    loading.value = false
  }
}

function makeDuplicate(projectId: number) {
  if (!requireAdmin()) return
  navigateTo(`/projects/0/edit?from=${projectId}`)
}

function confirmDelete(project: CustomerProject) {
  if (!requireAdmin()) return
  pendingDelete.value = project
  deleteDialog.value = true
}

async function doDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    const res = await api.deleteProject(pendingDelete.value.id, pendingDelete.value.project_tag)
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Project deleted')
    deleteDialog.value = false
    await load()
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Delete failed')
  }
  finally {
    deleting.value = false
  }
}

onMounted(load)
</script>
