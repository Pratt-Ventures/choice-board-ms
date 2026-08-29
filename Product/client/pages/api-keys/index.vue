<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold" style="letter-spacing: -.02em">API Keys</div>
        <div class="text-body-2 text-medium-emphasis">
          Key sets for signed toolkit API requests — no session management required.
        </div>
      </div>
      <v-btn
        v-if="isAdmin"
        color="primary"
        variant="flat"
        prepend-icon="mdi-key-plus"
        @click="openCreate"
      >
        New API key
      </v-btn>
    </div>

    <v-alert color="info" variant="tonal" icon="mdi-information-outline" density="compact" class="mb-4">
      A key's <b>requestor identifier</b> is returned once at creation and <b>cannot be reconstructed by the server later</b>.
      Store the key ID, shared secret and requestor ID together securely.
    </v-alert>

    <v-card class="panel" variant="flat">
      <div class="pa-4 d-flex justify-end">
        <v-btn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">
          Refresh
        </v-btn>
      </div>
      <v-divider />

      <v-table v-if="keys.length" class="data-table" density="comfortable">
        <thead>
          <tr>
            <th>Description</th>
            <th>App</th>
            <th>Key id</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="key in keys" :key="key.id" @click="selected = key">
            <td class="font-weight-medium">{{ key.description || 'Untitled key' }}</td>
            <td><span class="tag-code">{{ key.application_tag }}</span></td>
            <td class="masked-secret">{{ maskSecret(key.authentication_key_id) }}</td>
            <td>
              <v-chip size="small" :color="key.active_status ? 'success' : 'error'" variant="tonal">
                {{ key.active_status ? 'Active' : 'Disabled' }}
              </v-chip>
            </td>
            <td class="text-right">
              <v-btn size="small" variant="text" color="primary" @click.stop="selected = key">
                Details
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <EmptyState
        v-else-if="!loading"
        title="No API keys"
        description="Create a key bound to an application tag to call /api/api-check and related endpoints."
      >
        <v-btn v-if="isAdmin" color="primary" @click="openCreate">Create key</v-btn>
      </EmptyState>
      <div v-else class="pa-8 text-center">
        <v-progress-circular indeterminate color="primary" />
      </div>
    </v-card>

    <!-- Create dialog -->
    <v-dialog v-model="createDialog" max-width="560">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Create API key</span>
          <v-btn icon variant="text" size="small" @click="createDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <v-select
            v-model="createForm.application_tag"
            :items="appTags"
            label="Application tag"
            variant="outlined"
            class="mb-2"
          />
          <v-text-field v-model="createForm.description" label="Description" variant="outlined" class="mb-2" />
          <v-text-field v-model="createForm.webhook_endpoint" label="Webhook endpoint (optional)" variant="outlined" class="mb-2" />
          <v-switch v-model="createForm.include_cb_test" label="Include reciprocal callback key (test)" />
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="createDialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="create">Create</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- One-time secrets after create -->
    <v-dialog v-model="createdSecretsDialog" max-width="640" persistent>
      <v-card class="pc-dialog-card">
        <v-card-title class="pa-6 pb-2 text-h6 font-weight-bold font-display">Save these credentials now</v-card-title>
        <v-card-text class="px-6 pt-2">
          <div class="security-note mb-4">
            The request authentication value (<code>rq-…</code>) is returned only once and cannot be reconstructed later.
            Store it securely before closing this dialog.
          </div>
          <SecretField
            label="Request authentication (X-api-request-authentication)"
            :value="createdSecrets?.api_configuration_request_authentication"
          />
          <div class="my-4" />
          <SecretField
            label="Shared secret"
            :value="createdSecrets?.api_configuration_info?.shared_secret"
          />
          <div class="my-4" />
          <SecretField
            label="Key id (stored)"
            :value="createdSecrets?.api_configuration_info?.authentication_key_id"
          />
          <div class="my-4" />
          <SecretField
            label="Callback authentication"
            :value="createdSecrets?.api_callback_authentication"
          />
          <div v-if="createdSecrets?.api_reciprocal_callback_key" class="my-4">
            <SecretField
              label="Reciprocal callback key (test)"
              :value="createdSecrets.api_reciprocal_callback_key"
            />
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn color="primary" variant="flat" @click="createdSecretsDialog = false">I’ve saved them</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Detail drawer -->
    <v-navigation-drawer
      v-model="detailOpen"
      location="right"
      temporary
      width="420"
    >
      <div v-if="selected" class="pa-5">
        <div class="d-flex align-center justify-space-between mb-4">
          <div class="section-title">Key details</div>
          <v-btn icon variant="text" @click="selected = null">
            <v-icon icon="mdi-close" />
          </v-btn>
        </div>

        <div class="mb-3">
          <div class="detail-label">Description</div>
          <v-text-field
            v-model="editForm.description"
            density="compact"
            hide-details
            :disabled="!isAdmin"
          />
        </div>
        <div class="mb-3">
          <div class="detail-label">Application</div>
          <span class="tag-code">{{ selected.application_tag }}</span>
        </div>
        <SecretField class="mb-3" label="Key id" :value="selected.authentication_key_id" />
        <SecretField class="mb-3" label="Shared secret" :value="selected.shared_secret" />
        <div class="mb-3">
          <div class="detail-label">Webhook</div>
          <v-text-field
            v-model="editForm.webhook_endpoint"
            density="compact"
            hide-details
            :disabled="!isAdmin"
          />
        </div>
        <v-switch
          v-model="editForm.active_status"
          label="Active"
          :disabled="!isAdmin"
        />

        <div class="d-flex ga-2 mt-4">
          <v-btn
            v-if="isAdmin"
            color="primary"
            :loading="saving"
            @click="saveSelected"
          >
            Save
          </v-btn>
          <v-btn
            v-if="isAdmin"
            color="error"
            variant="outlined"
            :loading="removing"
            @click="removeSelected"
          >
            Remove
          </v-btn>
        </div>
      </div>
    </v-navigation-drawer>
  </div>
</template>

<script setup lang="ts">
import type {
  ApiAccessConfiguration,
  ApiAccessConfigurationResultMany,
  ApiAccessConfigurationResultOne,
  ApiAccessConfigurationResultOneId,
  CustomerApplication,
} from '~/types/api'

const { apiFetch } = useApi()
const { isAdmin, requireAdmin } = useAuth()
const { maskSecret } = useFormat()
const snackbar = useSnackbar()

const keys = ref<ApiAccessConfiguration[]>([])
const apps = ref<CustomerApplication[]>([])
const loading = ref(false)
const saving = ref(false)
const removing = ref(false)
const createDialog = ref(false)
const createdSecretsDialog = ref(false)
const createdSecrets = ref<ApiAccessConfigurationResultOne | null>(null)
const selected = ref<ApiAccessConfiguration | null>(null)

const createForm = reactive({
  application_tag: '',
  description: '',
  webhook_endpoint: '',
  include_cb_test: false,
})

const editForm = reactive({
  description: '',
  webhook_endpoint: '',
  active_status: true,
})

const appTags = computed(() => apps.value.map(a => a.application_tag))
const detailOpen = computed({
  get: () => !!selected.value,
  set: (v: boolean) => { if (!v) selected.value = null },
})

watch(selected, (key) => {
  if (!key) return
  editForm.description = key.description || ''
  editForm.webhook_endpoint = key.webhook_endpoint || ''
  editForm.active_status = !!key.active_status
})

function openCreate() {
  if (!requireAdmin()) return
  createDialog.value = true
}

async function load() {
  loading.value = true
  try {
    const [keyRes, appRes] = await Promise.all([
      apiFetch<ApiAccessConfigurationResultMany>('/ws/api-keys/get-api-access-configurations', {
        method: 'POST',
        body: {},
      }),
      apiFetch<{ customer_app_info_list?: CustomerApplication[] }>('/ws/custapps/customer-applications-get-all'),
    ])
    if (keyRes.failure_reason) throw new Error(keyRes.failure_reason)
    keys.value = keyRes.api_configuration_list || []
    apps.value = appRes.customer_app_info_list || []
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Failed to load API keys')
  }
  finally {
    loading.value = false
  }
}

async function create() {
  if (!requireAdmin()) return
  if (!createForm.application_tag) {
    snackbar.error('Select an application tag')
    return
  }
  saving.value = true
  try {
    const res = await apiFetch<ApiAccessConfigurationResultOne>('/ws/api-keys/create-api-access-configuration', {
      method: 'POST',
      body: {
        application_tag: createForm.application_tag,
        description: createForm.description || '',
        active_status: true,
        webhook_endpoint: createForm.webhook_endpoint || null,
        include_cb_test: createForm.include_cb_test,
      },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    createdSecrets.value = res
    createDialog.value = false
    createdSecretsDialog.value = true
    createForm.description = ''
    createForm.webhook_endpoint = ''
    createForm.include_cb_test = false
    await load()
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Create failed')
  }
  finally {
    saving.value = false
  }
}

async function saveSelected() {
  if (!requireAdmin() || !selected.value?.authentication_key_id) return
  saving.value = true
  try {
    const res = await apiFetch<ApiAccessConfigurationResultOne>('/ws/api-keys/modify-api-access-configuration', {
      method: 'POST',
      body: {
        authentication_key_id: selected.value.authentication_key_id,
        description: editForm.description,
        active_status: editForm.active_status,
        webhook_endpoint: editForm.webhook_endpoint,
      },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('API key updated')
    selected.value = res.api_configuration_info || selected.value
    await load()
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Update failed')
  }
  finally {
    saving.value = false
  }
}

async function removeSelected() {
  if (!requireAdmin() || !selected.value?.authentication_key_id) return
  removing.value = true
  try {
    const res = await apiFetch<ApiAccessConfigurationResultOneId>('/ws/api-keys/remove-api-access-configuration', {
      method: 'POST',
      body: { authentication_key_id: selected.value.authentication_key_id },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('API key removed')
    selected.value = null
    await load()
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Remove failed')
  }
  finally {
    removing.value = false
  }
}

onMounted(load)
</script>
