<template>
  <v-card class="glass-card">
    <v-card-text class="pa-6">
      <div class="d-flex align-center ga-3 mb-5">
        <div class="submit-badge">
          <i :class="kind === 'bug' ? 'fa-solid fa-bug' : 'fa-solid fa-lightbulb'" />
        </div>
        <div>
          <div class="text-h6 font-weight-bold font-display">
            {{ kind === 'bug' ? 'Report a bug' : 'Submit a suggestion' }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ kind === 'bug'
              ? 'Tell us what went wrong so we can fix it.'
              : 'Tell us what would make the product more useful.' }}
          </div>
        </div>
      </div>

      <template v-if="kind === 'bug'">
        <v-text-field v-model="bug.summary" label="Summary *" variant="outlined" class="mb-2" />
        <v-textarea v-model="bug.what_happened" label="What happened? *" variant="outlined" rows="3" class="mb-2" auto-grow />
        <v-textarea v-model="bug.expected_happened" label="What did you expect to happen?" variant="outlined" rows="2" class="mb-2" auto-grow />
        <v-textarea v-model="bug.steps_to_reproduce" label="Steps to reproduce" variant="outlined" rows="3" class="mb-2" auto-grow />
        <v-select
          v-model="bug.impact"
          :items="impactItems"
          label="Impact"
          variant="outlined"
          class="mb-2"
          clearable
        />
      </template>
      <template v-else>
        <v-textarea v-model="idea.suggestion" label="Suggestion *" variant="outlined" rows="3" class="mb-2" auto-grow />
        <v-textarea v-model="idea.accomplish_goal" label="What would this help you accomplish?" variant="outlined" rows="2" class="mb-2" auto-grow />
        <v-select
          v-model="idea.product_area"
          :items="areaItems"
          label="Area of the product"
          variant="outlined"
          class="mb-2"
          clearable
        />
        <v-select
          v-model="idea.importance"
          :items="importanceItems"
          label="Importance"
          variant="outlined"
          class="mb-2"
          clearable
        />
      </template>

      <div class="attach-box" @paste="onPaste">
        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,.png,.jpg,.jpeg,.webp,.gif,.pdf"
          class="d-none"
          @change="onFileSelected"
        >
        <div class="d-flex align-center justify-space-between ga-3 flex-wrap">
          <div>
            <div class="text-body-2 font-weight-medium">
              {{ kind === 'bug' ? 'Attach screenshot or file' : 'Optional attachment' }}
            </div>
            <div class="text-caption text-medium-emphasis">
              Images or PDF, 8 MB max. You can also paste a screenshot.
            </div>
          </div>
          <v-btn variant="tonal" size="small" @click="pickFile">
            <i class="fa-solid fa-paperclip mr-2" /> Choose file
          </v-btn>
        </div>
        <div v-if="file" class="d-flex align-center justify-space-between mt-3">
          <span class="text-body-2 text-truncate">{{ file.name }}</span>
          <v-btn icon variant="text" size="x-small" @click="file = null">
            <i class="fa-solid fa-xmark" />
          </v-btn>
        </div>
      </div>
    </v-card-text>
    <v-card-actions class="px-6 pb-5 pt-0">
      <v-spacer />
      <v-btn variant="text" @click="emit('cancel')">Cancel</v-btn>
      <v-btn color="primary" variant="flat" :loading="saving" @click="save">
        Submit
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { quotaCopy } from '~/utils/submissionQuota'

const props = defineProps<{
  kind: 'bug' | 'suggestion'
}>()
const emit = defineEmits<{
  submitted: []
  cancel: []
}>()

const api = useUserCommunicationApi()
const snackbar = useSnackbar()
const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const saving = ref(false)

const bug = reactive({
  summary: '',
  what_happened: '',
  expected_happened: '',
  steps_to_reproduce: '',
  impact: null as string | null,
})
const idea = reactive({
  suggestion: '',
  accomplish_goal: '',
  product_area: null as string | null,
  importance: null as string | null,
})

const impactItems = [
  { title: 'Minor', value: 'minor' },
  { title: 'Moderate', value: 'moderate' },
  { title: 'Blocking', value: 'blocking' },
]
const importanceItems = [
  { title: 'Nice to have', value: 'nice_to_have' },
  { title: 'Important', value: 'important' },
  { title: 'Very important', value: 'very_important' },
]
const areaItems = [
  { title: 'Projects', value: 'projects' },
  { title: 'Sharing', value: 'sharing' },
  { title: 'Compare', value: 'compare' },
  { title: 'Results', value: 'results' },
  { title: 'Templates', value: 'templates' },
  { title: 'Team', value: 'team' },
  { title: 'Account', value: 'account' },
  { title: 'Other', value: 'other' },
]

function reset() {
  bug.summary = ''
  bug.what_happened = ''
  bug.expected_happened = ''
  bug.steps_to_reproduce = ''
  bug.impact = null
  idea.suggestion = ''
  idea.accomplish_goal = ''
  idea.product_area = null
  idea.importance = null
  file.value = null
}

function pickFile() {
  fileInput.value?.click()
}

function acceptFile(next: File | null) {
  if (!next) return
  if (next.size > 8 * 1_048_576) {
    snackbar.error('Attachment must be 8 MB or smaller')
    return
  }
  file.value = next
}

function onFileSelected(ev: Event) {
  const input = ev.target as HTMLInputElement
  const next = input.files?.[0] || null
  input.value = ''
  acceptFile(next)
}

function onPaste(ev: ClipboardEvent) {
  const items = ev.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const pasted = item.getAsFile()
      if (pasted) {
        ev.preventDefault()
        const named = new File([pasted], pasted.name || 'pasted-screenshot.png', { type: pasted.type })
        acceptFile(named)
      }
      return
    }
  }
}

async function save() {
  if (props.kind === 'bug') {
    if (!bug.summary.trim() || !bug.what_happened.trim()) {
      snackbar.error('Summary and what happened are required')
      return
    }
  }
  else if (!idea.suggestion.trim()) {
    snackbar.error('Suggestion is required')
    return
  }
  saving.value = true
  try {
    const res = props.kind === 'bug'
      ? await api.submitBug({
          summary: bug.summary.trim(),
          what_happened: bug.what_happened.trim(),
          expected_happened: bug.expected_happened.trim() || undefined,
          steps_to_reproduce: bug.steps_to_reproduce.trim() || undefined,
          impact: bug.impact || undefined,
          file: file.value,
        })
      : await api.submitSuggestion({
          suggestion: idea.suggestion.trim(),
          accomplish_goal: idea.accomplish_goal.trim() || undefined,
          product_area: idea.product_area || undefined,
          importance: idea.importance || undefined,
          file: file.value,
        })
    const quota = quotaCopy(res.submitted_in_window, res.max_per_day)
    if (!res.stored) {
      snackbar.error(res.failure_reason || 'The request was discarded due to daily submission limits.')
      return
    }
    if (res.limit_warning || res.failure_reason) {
      snackbar.info([res.failure_reason, quota].filter(Boolean).join(' '))
    }
    else {
      snackbar.success(quota || 'Submission received')
    }
    reset()
    emit('submitted')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Submit failed')
  }
  finally {
    saving.value = false
  }
}

watch(
  () => props.kind,
  () => reset(),
)
</script>

<style scoped>
.submit-badge {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: rgb(var(--v-theme-primary));
  color: white;
  font-size: 16px;
}
.attach-box {
  border: 1px dashed var(--pc-border);
  border-radius: 12px;
  padding: 14px 16px;
  background: rgba(var(--v-theme-on-surface), 0.03);
}
</style>
