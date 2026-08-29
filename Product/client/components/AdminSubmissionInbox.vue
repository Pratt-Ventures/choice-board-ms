<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between ga-4 mb-6">
      <div>
        <div class="eyebrow">System Admin</div>
        <div class="page-title">{{ title }}</div>
        <div class="page-subtitle">{{ subtitle }}</div>
      </div>
      <v-btn variant="text" :loading="loading" @click="load">
        <i class="fa-solid fa-rotate mr-2" /> Refresh
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <v-card class="glass-card">
      <v-table v-if="rows.length" class="data-table" density="comfortable">
        <thead>
          <tr>
            <th>Submitted</th>
            <th>Workspace</th>
            <th>User</th>
            <th>{{ headlineLabel }}</th>
            <th>Acknowledged</th>
            <th>Response</th>
            <th>Resolution</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="text-body-2">{{ formatDate(row.create_date, true) }}</td>
            <td class="text-body-2">{{ row.customer_name || '—' }}</td>
            <td class="text-body-2">{{ row.user_name || '—' }}</td>
            <td class="text-body-2">{{ clip(headline(row)) }}</td>
            <td><LifecycleStamp :date="row.acknowledge_date" :note="row.acknowledge_note" empty="NA" /></td>
            <td><LifecycleStamp :date="row.response_date" :note="row.response_note" empty="NA" /></td>
            <td><LifecycleStamp :date="row.resolution_date" :note="row.resolution_note" empty="NA" /></td>
            <td class="text-right">
              <v-btn size="small" variant="text" color="primary" @click="openEdit(row)">
                Edit/Delete
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
      <div v-else-if="!loading" class="empty-state py-12">
        <i :class="['fa-solid fa-2x mb-3', kind === 'suggestion' ? 'fa-lightbulb' : 'fa-bug']" style="color:var(--pc-primary)" />
        <div class="text-body-1 font-weight-bold">{{ emptyTitle }}</div>
      </div>
    </v-card>

    <div v-if="totalCount > limit" class="d-flex align-center justify-space-between mt-4">
      <div class="text-caption text-medium-emphasis">
        {{ pageStart }}–{{ pageEnd }} of {{ totalCount }}
      </div>
      <div class="d-flex ga-2">
        <v-btn variant="tonal" size="small" :disabled="offset === 0" @click="prevPage">Previous</v-btn>
        <v-btn variant="tonal" size="small" :disabled="offset + limit >= totalCount" @click="nextPage">Next</v-btn>
      </div>
    </div>

    <AdminSubmissionDialog
      v-model="dialog"
      :kind="kind"
      :row="editing"
      @saved="load"
      @deleted="load"
    />
  </div>
</template>

<script setup lang="ts">
import type { UserCommunicationKind, UserCommunicationRow } from '~/types/api'

const props = defineProps<{
  kind: UserCommunicationKind
  title: string
  subtitle: string
}>()

const api = useUserCommunicationApi()
const snackbar = useSnackbar()
const { isSystemAdmin, userCommEnabled } = useAuth()
const { formatDate } = useFormat()

const loading = ref(false)
const rows = ref<UserCommunicationRow[]>([])
const totalCount = ref(0)
const offset = ref(0)
const limit = 25
const dialog = ref(false)
const editing = ref<UserCommunicationRow | null>(null)

const headlineLabel = computed(() => props.kind === 'suggestion' ? 'Suggestion' : 'Summary')
const emptyTitle = computed(() =>
  props.kind === 'suggestion' ? 'No active suggestions found' : 'No active bug reports found',
)
const pageStart = computed(() => (rows.value.length ? offset.value + 1 : 0))
const pageEnd = computed(() => offset.value + rows.value.length)

onMounted(() => {
  if (!isSystemAdmin.value || !userCommEnabled.value) {
    navigateTo('/projects')
    return
  }
  load()
})

function headline(row: UserCommunicationRow) {
  return props.kind === 'suggestion' ? (row.suggestion || '') : (row.summary || '')
}

function clip(text: string, max = 48) {
  const trimmed = text.replace(/\s+/g, ' ').trim()
  if (trimmed.length <= max) return trimmed || '—'
  return `${trimmed.slice(0, max).trimEnd()}…`
}

function openEdit(row: UserCommunicationRow) {
  editing.value = row
  dialog.value = true
}

function prevPage() {
  offset.value = Math.max(0, offset.value - limit)
  load()
}

function nextPage() {
  offset.value += limit
  load()
}

async function load() {
  loading.value = true
  try {
    const res = await api.adminRetrieve(props.kind, offset.value, limit)
    if (res.failure_reason) throw new Error(res.failure_reason)
    rows.value = res.items || []
    totalCount.value = res.total_count || 0
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not load submissions')
  }
  finally {
    loading.value = false
  }
}
</script>
