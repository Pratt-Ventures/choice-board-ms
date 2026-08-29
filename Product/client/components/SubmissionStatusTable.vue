<template>
  <v-card class="glass-card">
    <v-card-text class="pa-0">
      <v-table v-if="rows.length" class="data-table" density="comfortable">
        <thead>
          <tr>
            <th>Submitted</th>
            <th>{{ headlineLabel }}</th>
            <th v-if="showSubmitter">Submitter</th>
            <th>Acknowledged</th>
            <th>Response</th>
            <th>Resolution</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="text-body-2">{{ formatDate(row.create_date, true) }}</td>
            <td class="text-body-2">{{ clip(headline(row)) }}</td>
            <td v-if="showSubmitter" class="text-body-2">{{ row.user_name || '—' }}</td>
            <td><LifecycleStamp :date="row.acknowledge_date" :note="row.acknowledge_note" /></td>
            <td><LifecycleStamp :date="row.response_date" :note="row.response_note" /></td>
            <td><LifecycleStamp :date="row.resolution_date" :note="row.resolution_note" /></td>
          </tr>
        </tbody>
      </v-table>
      <div v-else class="empty-state py-12">
        <i :class="['fa-solid fa-2x mb-3', emptyIcon]" style="color:var(--pc-primary)" />
        <div class="text-body-1 font-weight-bold">{{ emptyTitle }}</div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { UserCommunicationRow } from '~/types/api'

const props = defineProps<{
  rows: UserCommunicationRow[]
  kind: 'bug_report' | 'suggestion'
  showSubmitter?: boolean
}>()

const { formatDate } = useFormat()

const headlineLabel = computed(() => props.kind === 'suggestion' ? 'Suggestion' : 'Summary')
const emptyTitle = computed(() =>
  props.kind === 'suggestion' ? 'No suggestions on file' : 'No bug reports on file',
)
const emptyIcon = computed(() => props.kind === 'suggestion' ? 'fa-lightbulb' : 'fa-bug')

function headline(row: UserCommunicationRow) {
  return props.kind === 'suggestion' ? (row.suggestion || '') : (row.summary || '')
}

function clip(text: string, max = 48) {
  const trimmed = text.replace(/\s+/g, ' ').trim()
  if (trimmed.length <= max) return trimmed || '—'
  return `${trimmed.slice(0, max).trimEnd()}…`
}
</script>
