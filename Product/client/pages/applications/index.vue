<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-5">
      <div>
        <div class="text-h5 font-weight-bold" style="letter-spacing: -.02em">Applications</div>
        <div class="text-body-2 text-medium-emphasis">
          Product tags used to scope API keys and toolkit access within your workspace.
        </div>
      </div>
      <v-btn
        v-if="isAdmin"
        color="primary"
        variant="flat"
        prepend-icon="mdi-plus"
        @click="dialog = true"
      >
        New application
      </v-btn>
    </div>

    <div class="d-flex flex-wrap ga-3 align-center mb-4">
      <v-text-field
        v-model="search"
        prepend-inner-icon="mdi-magnify"
        label="Search tags or descriptions"
        hide-details
        density="compact"
        style="max-width: 360px"
        clearable
      />
      <v-spacer />
      <v-btn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">
        Refresh
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <v-row v-if="filtered.length" dense>
      <v-col v-for="app in filtered" :key="app.id" cols="12" sm="6" xl="4">
        <v-card rounded="lg" variant="flat" class="app-card" @click="navigateTo(`/applications/${app.id}`)">
          <v-card-text>
            <div class="d-flex align-center justify-space-between">
              <v-chip size="small" color="primary" variant="tonal" class="mono font-weight-bold">
                {{ app.application_tag }}
              </v-chip>
              <v-chip size="x-small" :color="app.disabled ? 'error' : 'success'" variant="tonal">
                {{ app.disabled ? 'disabled' : 'live' }}
              </v-chip>
            </div>
            <div class="text-body-2 mt-3" style="min-height: 40px">
              {{ app.application_description || 'No description yet' }}
            </div>
            <v-divider class="my-3" />
            <div class="d-flex align-center text-caption text-medium-emphasis">
              <span>Created {{ formatDate(app.create_date) }}</span>
              <v-spacer />
              <v-icon size="16">mdi-chevron-right</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <EmptyState
      v-else-if="!loading"
      title="No applications"
      description="Create an application tag to bind API keys and toolkit calls."
    >
      <v-btn v-if="isAdmin" color="primary" @click="dialog = true">Add application</v-btn>
    </EmptyState>

    <v-dialog v-model="dialog" max-width="560">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">New application</span>
          <v-btn icon variant="text" size="small" @click="dialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <v-alert type="info" variant="tonal" density="comfortable" class="mb-4">
            Tag must be unique in your workspace.
          </v-alert>
          <v-text-field
            v-model="form.application_tag"
            label="Application tag"
            variant="outlined"
            hint="Lowercase identifier — letters, digits, dot, dash, underscore"
            persistent-hint
            class="mono mb-1"
          />
          <v-textarea
            v-model="form.application_description"
            label="Description"
            variant="outlined"
            rows="2"
            class="mt-3"
          />
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="create">
            Create application
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type {
  CustomerApplication,
  CustomerApplicationResultOne,
} from '~/types/api'

const { apiFetch } = useApi()
const { isAdmin, requireAdmin } = useAuth()
const { formatDate } = useFormat()
const snackbar = useSnackbar()

const apps = ref<CustomerApplication[]>([])
const loading = ref(false)
const saving = ref(false)
const search = ref('')
const dialog = ref(false)
const form = reactive({
  application_tag: '',
  application_description: '',
})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return apps.value
  return apps.value.filter(a =>
    a.application_tag.toLowerCase().includes(q)
    || (a.application_description || '').toLowerCase().includes(q),
  )
})

async function load() {
  loading.value = true
  try {
    const appRes = await apiFetch<{ customer_app_info_list?: CustomerApplication[], failure_reason?: string }>(
      '/ws/custapps/customer-applications-get-all',
    )
    if (appRes.failure_reason) throw new Error(appRes.failure_reason)
    apps.value = appRes.customer_app_info_list || []
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Failed to load applications')
  }
  finally {
    loading.value = false
  }
}

async function create() {
  if (!requireAdmin()) return
  const tag = form.application_tag.trim().toLowerCase()
  if (!tag) {
    snackbar.error('Application tag is required')
    return
  }
  saving.value = true
  try {
    const res = await apiFetch<CustomerApplicationResultOne>('/ws/custapps/customer-application-create', {
      method: 'POST',
      body: {
        application_tag: tag,
        application_description: form.application_description.trim() || null,
        disabled: false,
      },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Application created')
    dialog.value = false
    form.application_tag = ''
    form.application_description = ''
    await load()
    if (res.customer_app_info?.id) {
      await navigateTo(`/applications/${res.customer_app_info.id}`)
    }
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Create failed')
  }
  finally {
    saving.value = false
  }
}

onMounted(load)
</script>
