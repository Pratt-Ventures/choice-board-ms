<template>
  <div>
    <div class="mb-4">
      <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/applications">
        Applications
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <template v-if="app">
      <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-1">
        <div class="d-flex align-center ga-3">
          <v-chip color="primary" variant="tonal" class="mono font-weight-bold">
            {{ app.application_tag }}
          </v-chip>
          <v-chip size="x-small" :color="app.disabled ? 'error' : 'success'" variant="tonal">
            {{ app.disabled ? 'disabled' : 'live' }}
          </v-chip>
        </div>
        <v-btn
          v-if="isAdmin"
          color="primary"
          variant="tonal"
          prepend-icon="mdi-content-save"
          :loading="saving"
          @click="save"
        >
          Save changes
        </v-btn>
      </div>
      <div class="text-body-2 text-medium-emphasis mb-5">
        {{ app.application_description || 'Application configuration for this product tag.' }}
      </div>

      <v-row dense>
        <v-col cols="12" md="7">
          <div class="section-label mb-2">Configuration</div>
          <v-card rounded="lg" variant="flat" class="pa-5 mb-4">
            <v-text-field
              :model-value="app.application_tag"
              label="Application tag"
              readonly
              class="mb-2 mono"
              hint="Tag cannot be changed after create"
              persistent-hint
            />
            <v-text-field
              v-model="form.application_description"
              label="Description"
              class="mb-2"
              :disabled="!isAdmin"
            />
            <v-switch
              v-model="form.disabled"
              label="Disable application"
              :disabled="!isAdmin"
              color="error"
            />
          </v-card>
        </v-col>

        <v-col cols="12" md="5">
          <div class="section-label mb-2">Details</div>
          <v-card rounded="lg" variant="flat" class="mb-4">
            <v-list density="compact" class="py-0">
              <v-list-item>
                <v-list-item-title class="text-caption text-medium-emphasis">Application ID</v-list-item-title>
                <template #append>
                  <span class="mono text-caption">{{ app.id }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title class="text-caption text-medium-emphasis">Created</v-list-item-title>
                <template #append>
                  <span class="text-caption">{{ formatDate(app.create_date) }}</span>
                </template>
              </v-list-item>
              <v-list-item>
                <v-list-item-title class="text-caption text-medium-emphasis">Last modified</v-list-item-title>
                <template #append>
                  <span class="text-caption">{{ formatDate(app.modify_date) }}</span>
                </template>
              </v-list-item>
            </v-list>
          </v-card>

          <v-btn
            v-if="isAdmin"
            color="error"
            variant="outlined"
            block
            prepend-icon="mdi-delete-outline"
            :loading="deleting"
            @click="confirmDelete = true"
          >
            Delete application
          </v-btn>
        </v-col>
      </v-row>
    </template>

    <v-dialog v-model="confirmDelete" max-width="420">
      <v-card class="pc-dialog-card">
        <v-card-title class="pa-6 pb-2 text-h6 font-weight-bold font-display">Delete application?</v-card-title>
        <v-card-text class="px-6 pt-2">
          Soft-deletes <strong>{{ app?.application_tag }}</strong>.
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="confirmDelete = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" :loading="deleting" @click="remove">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type {
  CustomerApplication,
  CustomerApplicationDeleteResult,
  CustomerApplicationResultOne,
  CustomerApplicationResultOneId,
} from '~/types/api'

const route = useRoute()
const { apiFetch } = useApi()
const { isAdmin, requireAdmin } = useAuth()
const { formatDate } = useFormat()
const snackbar = useSnackbar()

const app = ref<CustomerApplication | null>(null)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const confirmDelete = ref(false)
const form = reactive({
  application_description: '',
  disabled: false,
})

async function load() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await apiFetch<CustomerApplicationResultOne>('/ws/custapps/customer-application-get-by-id', {
      query: { retrieve_by_id: id },
    })
    if (res.failure_reason || !res.customer_app_info) {
      throw new Error(res.failure_reason || 'Application not found')
    }
    app.value = res.customer_app_info
    form.application_description = res.customer_app_info.application_description || ''
    form.disabled = !!res.customer_app_info.disabled
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Failed to load application')
  }
  finally {
    loading.value = false
  }
}

async function save() {
  if (!requireAdmin() || !app.value) return
  saving.value = true
  try {
    const res = await apiFetch<CustomerApplicationResultOneId>('/ws/custapps/customer-application-update', {
      method: 'POST',
      body: {
        application_tag: app.value.application_tag,
        application_description: form.application_description || null,
        disabled: form.disabled,
      },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Application saved')
    await load()
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Save failed')
  }
  finally {
    saving.value = false
  }
}

async function remove() {
  if (!requireAdmin() || !app.value) return
  deleting.value = true
  try {
    const res = await apiFetch<CustomerApplicationDeleteResult>('/ws/custapps/customer-application-delete', {
      method: 'DELETE',
      body: {
        application_id: app.value.id,
        application_tag: app.value.application_tag,
      },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Application deleted')
    await navigateTo('/applications')
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Delete failed')
  }
  finally {
    deleting.value = false
    confirmDelete.value = false
  }
}

onMounted(load)
</script>
