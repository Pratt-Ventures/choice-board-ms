<template>
  <v-dialog :model-value="modelValue" max-width="720" scrollable @update:model-value="emit('update:modelValue', $event)">
    <v-card v-if="draft" class="pc-dialog-card">
      <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
        <span class="text-h6 font-weight-bold font-display">
          {{ kind === 'suggestion' ? 'Suggestion' : 'Bug report' }}
        </span>
        <v-btn icon variant="text" size="small" @click="emit('update:modelValue', false)">
          <i class="fa-solid fa-xmark" />
        </v-btn>
      </v-card-title>
      <v-card-text class="px-6 pt-2">
        <div class="detail-grid mb-5">
          <div class="detail-row">
            <span class="text-caption text-medium-emphasis">Workspace</span>
            <span class="text-body-2 font-weight-medium">{{ draft.customer_name || '—' }}</span>
          </div>
          <div class="detail-row">
            <span class="text-caption text-medium-emphasis">User</span>
            <span class="text-body-2 font-weight-medium">{{ draft.user_name || '—' }}</span>
          </div>
          <div class="detail-row">
            <span class="text-caption text-medium-emphasis">Submitted</span>
            <span class="text-body-2">{{ formatDate(draft.create_date, true) }}</span>
          </div>
        </div>

        <template v-if="kind === 'bug_report'">
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Summary</div>
            <div class="text-body-2">{{ draft.summary || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">What happened</div>
            <div class="text-body-2">{{ draft.what_happened || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Expected</div>
            <div class="text-body-2">{{ draft.expected_happened || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Steps to reproduce</div>
            <div class="text-body-2">{{ draft.steps_to_reproduce || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Impact</div>
            <div class="text-body-2">{{ impactLabel(draft.impact) }}</div>
          </div>
        </template>
        <template v-else>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Suggestion</div>
            <div class="text-body-2">{{ draft.suggestion || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">What this would help accomplish</div>
            <div class="text-body-2">{{ draft.accomplish_goal || '—' }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Area</div>
            <div class="text-body-2">{{ areaLabel(draft.product_area) }}</div>
          </div>
          <div class="field-block">
            <div class="text-caption text-medium-emphasis">Importance</div>
            <div class="text-body-2">{{ importanceLabel(draft.importance) }}</div>
          </div>
        </template>

        <div v-if="draft.has_attachment" class="mb-5">
          <v-btn variant="tonal" size="small" :href="attachmentHref" target="_blank" rel="noopener">
            <i class="fa-solid fa-download mr-2" />
            {{ draft.attachment_filename || 'Download attachment' }}
          </v-btn>
        </div>

        <div class="text-subtitle-2 font-weight-bold mb-3">Lifecycle</div>
        <div v-for="slot in slots" :key="slot.key" class="lifecycle-block mb-4">
          <div class="d-flex flex-wrap align-center justify-space-between ga-2 mb-2">
            <div>
              <div class="text-body-2 font-weight-medium">{{ slot.label }}</div>
              <div class="text-caption text-medium-emphasis">
                {{ dateValue(slot.dateKey) ? formatDate(dateValue(slot.dateKey), true) : 'Not set' }}
              </div>
            </div>
            <div class="d-flex ga-2">
              <v-btn size="small" variant="tonal" @click="setDate(slot.actionKey)">Set now</v-btn>
              <v-btn size="small" variant="text" @click="clearDate(slot.actionKey)">Clear</v-btn>
            </div>
          </div>
          <v-textarea v-model="notes[slot.noteKey]" :label="`${slot.label} note`" variant="outlined" rows="2" auto-grow hide-details />
        </div>
      </v-card-text>
      <v-card-actions class="px-6 pb-5 pt-0">
        <v-btn color="error" variant="text" @click="confirmOpen = true">Delete</v-btn>
        <v-spacer />
        <v-btn variant="text" @click="emit('update:modelValue', false)">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" @click="save">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="confirmOpen" max-width="420">
    <v-card class="pc-dialog-card">
      <v-card-title class="pa-6 pb-2 text-h6 font-weight-bold font-display">Delete this submission?</v-card-title>
      <v-card-text class="px-6 pt-2">
        This soft-deletes the {{ kind === 'suggestion' ? 'suggestion' : 'bug report' }}.
      </v-card-text>
      <v-card-actions class="px-6 pb-5 pt-0">
        <v-spacer />
        <v-btn variant="text" @click="confirmOpen = false">Cancel</v-btn>
        <v-btn color="error" variant="flat" :loading="deleting" @click="doDelete">Delete</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { UserCommunicationAdminModifyPayload, UserCommunicationKind, UserCommunicationRow } from '~/types/api'

const props = defineProps<{
  modelValue: boolean
  kind: UserCommunicationKind
  row: UserCommunicationRow | null
}>()
const emit = defineEmits<{
  'update:modelValue': [boolean]
  saved: []
  deleted: []
}>()

const api = useUserCommunicationApi()
const snackbar = useSnackbar()
const { formatDate } = useFormat()

const draft = ref<UserCommunicationRow | null>(null)
const notes = reactive({
  acknowledge_note: '',
  response_note: '',
  resolution_note: '',
})
const dateActions = reactive<Record<'acknowledge_date_action' | 'response_date_action' | 'resolution_date_action', 'set' | 'clear' | null>>({
  acknowledge_date_action: null,
  response_date_action: null,
  resolution_date_action: null,
})
const saving = ref(false)
const deleting = ref(false)
const confirmOpen = ref(false)

const slots = [
  { key: 'ack', label: 'Acknowledge', dateKey: 'acknowledge_date', noteKey: 'acknowledge_note', actionKey: 'acknowledge_date_action' },
  { key: 'resp', label: 'Response', dateKey: 'response_date', noteKey: 'response_note', actionKey: 'response_date_action' },
  { key: 'res', label: 'Resolution', dateKey: 'resolution_date', noteKey: 'resolution_note', actionKey: 'resolution_date_action' },
] as const

const attachmentHref = computed(() => {
  if (!draft.value) return ''
  return api.attachmentUrl(props.kind, draft.value.id)
})

watch(
  () => [props.modelValue, props.row] as const,
  ([open, row]) => {
    if (!open || !row) return
    draft.value = { ...row }
    notes.acknowledge_note = row.acknowledge_note || ''
    notes.response_note = row.response_note || ''
    notes.resolution_note = row.resolution_note || ''
    dateActions.acknowledge_date_action = null
    dateActions.response_date_action = null
    dateActions.resolution_date_action = null
  },
)

function dateValue(key: 'acknowledge_date' | 'response_date' | 'resolution_date') {
  return draft.value?.[key] || null
}

function setDate(actionKey: keyof typeof dateActions) {
  dateActions[actionKey] = 'set'
  if (!draft.value) return
  if (actionKey === 'acknowledge_date_action') draft.value.acknowledge_date = new Date().toISOString()
  if (actionKey === 'response_date_action') draft.value.response_date = new Date().toISOString()
  if (actionKey === 'resolution_date_action') draft.value.resolution_date = new Date().toISOString()
}

function clearDate(actionKey: keyof typeof dateActions) {
  dateActions[actionKey] = 'clear'
  if (!draft.value) return
  if (actionKey === 'acknowledge_date_action') draft.value.acknowledge_date = null
  if (actionKey === 'response_date_action') draft.value.response_date = null
  if (actionKey === 'resolution_date_action') draft.value.resolution_date = null
}

function impactLabel(value?: string | null) {
  return ({ minor: 'Minor', moderate: 'Moderate', blocking: 'Blocking' } as Record<string, string>)[value || ''] || value || '—'
}
function importanceLabel(value?: string | null) {
  return ({ nice_to_have: 'Nice to have', important: 'Important', very_important: 'Very important' } as Record<string, string>)[value || ''] || value || '—'
}
function areaLabel(value?: string | null) {
  return ({
    projects: 'Projects',
    sharing: 'Sharing',
    compare: 'Compare',
    results: 'Results',
    templates: 'Templates',
    team: 'Team',
    account: 'Account',
    other: 'Other',
  } as Record<string, string>)[value || ''] || value || '—'
}

async function save() {
  if (!draft.value) return
  saving.value = true
  try {
    const payload: UserCommunicationAdminModifyPayload = {
      id: draft.value.id,
      acknowledge_date_action: dateActions.acknowledge_date_action,
      response_date_action: dateActions.response_date_action,
      resolution_date_action: dateActions.resolution_date_action,
      acknowledge_note: notes.acknowledge_note,
      response_note: notes.response_note,
      resolution_note: notes.resolution_note,
    }
    const res = await api.adminModify(props.kind, payload)
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Saved')
    emit('update:modelValue', false)
    emit('saved')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Save failed')
  }
  finally {
    saving.value = false
  }
}

async function doDelete() {
  if (!draft.value) return
  deleting.value = true
  try {
    const res = await api.remove(props.kind, draft.value.id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Deleted')
    confirmOpen.value = false
    emit('update:modelValue', false)
    emit('deleted')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Delete failed')
  }
  finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.detail-grid,
.field-block,
.lifecycle-block {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
}
.field-block {
  margin-bottom: 10px;
}
</style>
