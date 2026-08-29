<template>
  <div>
    <div class="page-head">
      <div>
        <div class="eyebrow">Library</div>
        <div class="page-title">Templates</div>
        <div class="page-subtitle">Reusable project, option, and factor starters. Import copies content into a project — no ongoing link.</div>
      </div>
      <v-btn color="primary" variant="flat" @click="openNew">
        <i class="fa-solid fa-plus mr-2" /> New Template
      </v-btn>
    </div>

    <div class="template-note mb-5">
      <i class="fa-solid fa-copy mt-1" />
      <div>
        Applying a template copies its settings into the project. Later changes to the template do not change existing projects, and project edits do not alter the original template.
      </div>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <v-row>
      <v-col v-for="t in templates" :key="t.id" cols="12" md="6" lg="4">
        <v-card class="glass-card project-card">
          <v-card-text class="pa-5">
            <div class="d-flex justify-space-between mb-2">
              <div class="brand-badge" style="width:38px;height:38px;border-radius:12px">
                <i class="fa-solid fa-layer-group" style="font-size:14px" />
              </div>
              <span :class="['status', t.enable_global_share ? 'status-ready' : 'status-draft']">
                {{ t.enable_global_share ? 'Shared' : 'Your template' }}
              </span>
            </div>
            <div class="project-card-title mt-3">{{ t.factor_template_title || `Template ${t.id}` }}</div>
            <div class="text-body-2 text-medium-emphasis mt-2" style="min-height:40px">
              {{ t.factor_template_description || 'No description' }}
            </div>
            <div class="d-flex flex-wrap ga-1 mt-3">
              <v-chip v-if="t.use_with_projects" size="x-small" variant="tonal" color="primary">Project</v-chip>
              <v-chip v-if="t.use_with_options" size="x-small" variant="tonal">Options</v-chip>
              <v-chip v-if="t.use_with_factors" size="x-small" variant="tonal">Factors</v-chip>
              <v-chip v-if="!t.use_with_projects && !t.use_with_options && !t.use_with_factors" size="x-small" variant="outlined">Not offered</v-chip>
            </div>
            <div class="d-flex flex-wrap ga-1 mt-2">
              <span
                v-for="(e, i) in (t.factor_template_entries || []).slice(0, 4)"
                :key="'f' + i"
                class="factor-tag"
              >
                {{ e.factor_title }}
              </span>
              <span
                v-for="(e, i) in (t.option_template_entries || []).slice(0, 3)"
                :key="'o' + i"
                class="factor-tag"
              >
                {{ e.alternative_title }}
              </span>
            </div>
            <div class="d-flex ga-2 mt-4">
              <v-btn size="small" variant="tonal" :disabled="!canEdit(t)" @click="edit(t)">Edit</v-btn>
              <v-btn size="small" variant="text" color="error" :disabled="!canEdit(t)" @click="remove(t.id)">Delete</v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog v-model="dialog" max-width="720" scrollable content-class="pc-template-dialog">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">{{ editor.id ? 'Edit template' : 'New template' }}</span>
          <v-btn icon variant="text" size="small" @click="dialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2 pc-dialog-scroll-body">
          <v-text-field v-model="editor.title" label="Template name" variant="outlined" class="mb-2" />
          <v-textarea v-model="editor.description" label="Description" variant="outlined" rows="2" class="mb-3" />

          <div class="text-subtitle-2 mb-2">Offer for import on</div>
          <div class="d-flex flex-wrap ga-4 mb-4">
            <v-checkbox v-model="editor.use_with_projects" label="Project" density="compact" hide-details color="primary" />
            <v-checkbox v-model="editor.use_with_options" label="Options" density="compact" hide-details color="primary" />
            <v-checkbox v-model="editor.use_with_factors" label="Factors" density="compact" hide-details color="primary" />
          </div>

          <div class="text-subtitle-2 mb-2">Project settings (when used on Project page)</div>
          <v-btn-toggle v-model="editor.mode" mandatory color="primary" divided class="mb-3">
            <v-btn value="exclusive" size="small">Choose one winner</v-btn>
            <v-btn value="rank" size="small">Rank all options</v-btn>
          </v-btn-toggle>
          <v-switch
            v-model="editor.private_participation"
            label="Private participation"
            color="primary"
            density="compact"
            class="mb-4"
            hide-details
          />

          <div class="d-flex justify-space-between mb-2">
            <div class="text-subtitle-2">Options</div>
            <v-btn size="small" variant="text" @click="editor.options.push({ alternative_title: '', alternative_description: '' })">Add</v-btn>
          </div>
          <div v-for="(e, idx) in editor.options" :key="'opt' + idx" class="rank-row mb-2">
            <div class="d-flex ga-2">
              <div class="flex-grow-1">
                <v-text-field v-model="e.alternative_title" label="Option" density="compact" hide-details class="mb-2" />
                <v-text-field v-model="e.alternative_description" label="Description" density="compact" hide-details />
              </div>
              <v-btn icon variant="text" @click="editor.options.splice(idx, 1)"><i class="fa-solid fa-trash" /></v-btn>
            </div>
          </div>

          <div class="d-flex justify-space-between mb-2 mt-4">
            <div class="text-subtitle-2">Factors</div>
            <v-btn size="small" variant="text" @click="editor.entries.push({ factor_title: '', factor_description: '', comparison_question: '' })">Add</v-btn>
          </div>
          <div v-for="(e, idx) in editor.entries" :key="'fac' + idx" class="rank-row mb-2">
            <div class="d-flex ga-2">
              <div class="flex-grow-1">
                <v-text-field v-model="e.factor_title" label="Factor" density="compact" hide-details class="mb-2" />
                <v-text-field v-model="e.factor_description" label="Description" density="compact" hide-details class="mb-2" />
                <v-text-field
                  v-model="e.comparison_question"
                  label="Comparison question"
                  placeholder="Which option has lower Engineering Cost?"
                  hint="Optional. Used only during pairwise option comparisons."
                  persistent-hint
                  counter="200"
                  maxlength="200"
                  density="compact"
                />
              </div>
              <v-btn icon variant="text" @click="editor.entries.splice(idx, 1)"><i class="fa-solid fa-trash" /></v-btn>
            </div>
          </div>

          <v-switch
            v-if="isSystemAdmin"
            v-model="editor.enable_global_share"
            label="Globally shared"
            color="primary"
            class="mt-4"
            hint="Visible to all workspaces. System admin only."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="save">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type { FactorTemplate, FactorTemplateEntry, OptionTemplateEntry } from '~/types/api'

const api = useProjectsApi()
const snackbar = useSnackbar()
const { requireAdmin, isSystemAdmin, context } = useAuth()

const templates = ref<FactorTemplate[]>([])
const loading = ref(true)
const dialog = ref(false)
const saving = ref(false)
const editor = reactive({
  id: 0 as number | null,
  title: '',
  description: '',
  entries: [{ factor_title: '', factor_description: '', comparison_question: '' }] as FactorTemplateEntry[],
  options: [] as OptionTemplateEntry[],
  use_with_projects: false,
  use_with_options: false,
  use_with_factors: true,
  mode: 'exclusive' as 'exclusive' | 'rank',
  private_participation: false,
  enable_global_share: false,
})

function canEdit(t: FactorTemplate) {
  if (isSystemAdmin.value) return true
  return t.customer_id === context.value?.customer_id && !t.enable_global_share
}

function resetEditor() {
  editor.id = null
  editor.title = ''
  editor.description = ''
  editor.entries = [{ factor_title: '', factor_description: '', comparison_question: '' }]
  editor.options = []
  editor.use_with_projects = false
  editor.use_with_options = false
  editor.use_with_factors = true
  editor.mode = 'exclusive'
  editor.private_participation = false
  editor.enable_global_share = false
}

async function load() {
  loading.value = true
  try {
    const res = await api.listTemplates(true)
    templates.value = res.factor_template_info_list || []
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Failed to load templates')
  }
  finally {
    loading.value = false
  }
}

function openNew() {
  if (!requireAdmin()) return
  resetEditor()
  dialog.value = true
}

function edit(t: FactorTemplate) {
  if (!requireAdmin()) return
  if (!canEdit(t)) {
    snackbar.error('You can view this shared template but not edit it')
    return
  }
  editor.id = t.id
  editor.title = t.factor_template_title || ''
  editor.description = t.factor_template_description || ''
  editor.entries = (t.factor_template_entries || []).map(e => ({
    ...e,
    comparison_question: e.comparison_question || '',
  }))
  if (!editor.entries.length) editor.entries = [{ factor_title: '', factor_description: '', comparison_question: '' }]
  editor.options = (t.option_template_entries || []).map(e => ({ ...e }))
  editor.use_with_projects = !!t.use_with_projects
  editor.use_with_options = !!t.use_with_options
  editor.use_with_factors = t.use_with_factors !== false
  editor.mode = t.project_exclusive_mode ? 'exclusive' : 'rank'
  editor.private_participation = !!t.private_participation
  editor.enable_global_share = !!t.enable_global_share
  dialog.value = true
}

async function save() {
  const entries = editor.entries.filter(e => (e.factor_title || '').trim())
  const options = editor.options.filter(e => (e.alternative_title || '').trim())
  if (!editor.title.trim()) {
    snackbar.error('Template name is required')
    return
  }
  if (!editor.use_with_projects && !editor.use_with_options && !editor.use_with_factors) {
    snackbar.error('Select at least one place to offer this template, or it will not appear for import')
  }
  if (!entries.length && !options.length && !editor.use_with_projects) {
    snackbar.error('Add at least one factor or option, or enable project scope with settings')
    return
  }
  saving.value = true
  try {
    const payload = {
      factor_template_title: editor.title.trim(),
      factor_template_description: editor.description.trim(),
      factor_template_entries: entries,
      option_template_entries: options,
      use_with_projects: editor.use_with_projects,
      use_with_options: editor.use_with_options,
      use_with_factors: editor.use_with_factors,
      project_exclusive_mode: editor.mode === 'exclusive',
      private_participation: editor.private_participation,
      ...(isSystemAdmin.value ? { enable_global_share: editor.enable_global_share } : {}),
    }
    if (editor.id) {
      const res = await api.updateTemplate({
        factor_template_id: editor.id,
        ...payload,
      })
      if (res.failure_reason) throw new Error(res.failure_reason)
    }
    else {
      const res = await api.createTemplate(payload)
      if (res.failure_reason) throw new Error(res.failure_reason)
    }
    snackbar.success('Template saved')
    dialog.value = false
    await load()
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Save failed')
  }
  finally {
    saving.value = false
  }
}

async function remove(id: number) {
  if (!requireAdmin()) return
  try {
    const res = await api.deleteTemplate(id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.info('Template deleted')
    await load()
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Delete failed')
  }
}

onMounted(load)
</script>
