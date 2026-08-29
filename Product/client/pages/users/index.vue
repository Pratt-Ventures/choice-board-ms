<template>
  <div>
    <div class="d-flex flex-wrap justify-space-between align-center ga-3 mb-4">
      <div>
        <div class="text-h5 font-weight-bold" style="letter-spacing: -.02em">Team &amp; Access</div>
        <div class="text-body-2 text-medium-emphasis">
          Users on this customer account. Admins manage projects and users — members are read-only.
        </div>
      </div>
      <v-btn
        v-if="isAdmin"
        color="primary"
        variant="flat"
        prepend-icon="mdi-account-plus-outline"
        @click="openCreate"
      >
        Invite user
      </v-btn>
    </div>

    <v-card class="panel" variant="flat">
      <div class="pa-4 d-flex justify-end">
        <v-btn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">
          Refresh
        </v-btn>
      </div>
      <v-divider />

      <v-table v-if="users.length" class="data-table" density="comfortable">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Access</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>
              <div class="d-flex align-center ga-3 py-1">
                <v-avatar
                  size="32"
                  :color="user.access_disabled ? 'medium-emphasis' : 'primary'"
                  variant="tonal"
                >
                  <span class="text-caption font-weight-bold">{{ initials(user.name) }}</span>
                </v-avatar>
                <div>
                  <div class="text-body-2 font-weight-medium">{{ user.name }}</div>
                  <div class="text-caption text-medium-emphasis">
                    {{ user.email }}<span v-if="user.phone"> · {{ user.phone }}</span>
                  </div>
                </div>
              </div>
            </td>
            <td>
              <div class="d-flex flex-column align-start ga-1">
                <v-chip size="small" :color="user.customer_admin ? 'primary' : 'default'" variant="tonal">
                  <v-icon start size="12">
                    {{ user.customer_admin ? 'mdi-shield-crown-outline' : 'mdi-account-outline' }}
                  </v-icon>
                  {{ user.customer_admin ? 'Admin' : 'Member' }}
                </v-chip>
                <v-chip
                  v-if="powerLabel(user.power_user_mode)"
                  size="x-small"
                  color="secondary"
                  variant="tonal"
                >
                  {{ powerLabel(user.power_user_mode) }}
                </v-chip>
                <v-chip
                  v-if="sysAdminLabel(user.system_user_mode)"
                  size="x-small"
                  color="warning"
                  variant="tonal"
                >
                  {{ sysAdminLabel(user.system_user_mode) }}
                </v-chip>
              </div>
            </td>
            <td>
              <v-chip
                size="small"
                :color="user.access_disabled ? 'error' : 'success'"
                variant="tonal"
              >
                {{ user.access_disabled ? 'Disabled' : 'Enabled' }}
              </v-chip>
            </td>
            <td class="text-right">
              <v-btn
                size="small"
                variant="text"
                color="primary"
                :disabled="!isAdmin && user.id !== context?.user_id"
                @click="openEdit(user)"
              >
                Edit
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>

      <EmptyState
        v-else-if="!loading"
        title="No users"
        description="Invite teammates so they can manage applications and review subscribers."
      />
      <div v-else class="pa-8 text-center">
        <v-progress-circular indeterminate color="primary" />
      </div>
    </v-card>

    <v-dialog v-model="dialog" max-width="520">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">
            {{ editingId ? 'Edit user' : 'Add user' }}
          </span>
          <v-btn icon variant="text" size="small" @click="dialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <v-text-field v-model="form.name" label="Name" variant="outlined" class="mb-2" />
          <v-text-field
            v-model="form.email"
            label="Email"
            type="email"
            variant="outlined"
            class="mb-2"
            :disabled="!!editingId"
          />
          <v-text-field v-model="form.phone" label="Phone" variant="outlined" class="mb-2" />
          <v-text-field
            v-model="form.password"
            :label="editingId ? 'New password (optional)' : 'Password'"
            type="password"
            variant="outlined"
            class="mb-2"
          />
          <v-switch
            v-if="isAdmin"
            v-model="form.customer_admin"
            label="Customer admin"
            class="mb-2"
          />
          <v-select
            v-if="isAdmin"
            v-model="form.power_user_mode"
            :items="powerOptions"
            item-title="title"
            item-value="value"
            label="Power user"
            variant="outlined"
            hint="Off (0), power (1), or power+ (2) within this customer"
            persistent-hint
            class="mb-2"
          />
          <div v-if="editingSystemLabel" class="text-caption text-medium-emphasis mt-2">
            System role: <strong>{{ editingSystemLabel }}</strong> (display only)
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-btn
            v-if="editingId && isAdmin"
            color="error"
            variant="text"
            :loading="removing"
            @click="remove"
          >
            Delete
          </v-btn>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="save">
            {{ editingId ? 'Save' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type {
  UserRecord,
  UserResultMany,
  UserResultOne,
  UserResultOneId,
} from '~/types/api'

const { apiFetch } = useApi()
const { isAdmin, requireAdmin, context } = useAuth()
const { initials } = useFormat()
const snackbar = useSnackbar()

const users = ref<UserRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const removing = ref(false)
const dialog = ref(false)
const editingId = ref<number | null>(null)
const editingSystemMode = ref(0)

const powerOptions = [
  { title: 'Off (0)', value: 0 },
  { title: 'Power (1)', value: 1 },
  { title: 'Power+ (2)', value: 2 },
]

const form = reactive({
  name: '',
  email: '',
  phone: '',
  password: '',
  customer_admin: false,
  power_user_mode: 0,
})

const editingSystemLabel = computed(() => sysAdminLabel(editingSystemMode.value))

function powerLabel(mode?: number | null) {
  if (mode === 1) return 'power'
  if (mode === 2) return 'power+'
  return ''
}

function sysAdminLabel(mode?: number | null) {
  if (mode == null || mode <= 0) return ''
  if (mode >= 2) return 'System Admin'
  return 'System User'
}

function resetForm() {
  form.name = ''
  form.email = ''
  form.phone = ''
  form.password = ''
  form.customer_admin = false
  form.power_user_mode = 0
  editingId.value = null
  editingSystemMode.value = 0
}

function openCreate() {
  if (!requireAdmin()) return
  resetForm()
  dialog.value = true
}

function openEdit(user: UserRecord) {
  editingId.value = user.id
  form.name = user.name
  form.email = user.email
  form.phone = user.phone || ''
  form.password = ''
  form.customer_admin = !!user.customer_admin
  form.power_user_mode = Number(user.power_user_mode || 0)
  editingSystemMode.value = Number(user.system_user_mode || 0)
  dialog.value = true
}

async function load() {
  loading.value = true
  try {
    const res = await apiFetch<UserResultMany>('/ws/user-all-account-users')
    if (res.failure_reason) throw new Error(res.failure_reason)
    users.value = res.user_info_list || []
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Failed to load users')
  }
  finally {
    loading.value = false
  }
}

async function save() {
  if (!form.name || !form.email) {
    snackbar.error('Name and email are required')
    return
  }
  if (!editingId.value && !form.password) {
    snackbar.error('Password is required for new users')
    return
  }
  if (!editingId.value && !requireAdmin()) return

  saving.value = true
  try {
    if (editingId.value) {
      const res = await apiFetch<UserResultOneId>('/ws/user-update', {
        method: 'POST',
        body: {
          id: editingId.value,
          name: form.name,
          email: form.email,
          phone: form.phone || null,
          customer_admin: isAdmin.value ? form.customer_admin : undefined,
          power_user_mode: isAdmin.value ? form.power_user_mode : undefined,
          password: form.password || null,
        },
      })
      if (res.failure_reason) throw new Error(res.failure_reason)
      snackbar.success('User updated')
    }
    else {
      const res = await apiFetch<UserResultOne>('/ws/user/user-create', {
        method: 'POST',
        body: {
          name: form.name,
          email: form.email,
          phone: form.phone || null,
          customer_admin: form.customer_admin,
          power_user_mode: form.power_user_mode,
          password: form.password,
        },
        query: { send_welcome_email: true },
      })
      if (res.failure_reason) throw new Error(res.failure_reason)
      snackbar.success('User created')
    }
    dialog.value = false
    resetForm()
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
  if (!requireAdmin() || !editingId.value) return
  removing.value = true
  try {
    const res = await apiFetch<{ failure_reason?: string }>('/ws/user/delete-user', {
      method: 'DELETE',
      body: { user_id: editingId.value },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('User deleted')
    dialog.value = false
    resetForm()
    await load()
  }
  catch (err) {
    snackbar.error(err instanceof Error ? err.message : 'Delete failed')
  }
  finally {
    removing.value = false
  }
}

onMounted(load)
</script>
