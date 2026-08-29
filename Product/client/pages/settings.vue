<template>
  <div>
    <div class="eyebrow">Preferences</div>
    <div class="page-title mb-2">Settings</div>
    <div class="page-subtitle mb-6">
      Customer-level defaults for Results. Comparison sort settings live on each project (min/max passes).
    </div>

    <v-row v-if="showTwoFactorBox">
      <v-col cols="12">
        <v-card class="glass-card mb-5">
          <v-card-text class="pa-6">
            <div class="text-h6 font-weight-bold mb-1">Two-factor authentication</div>
            <div class="text-caption text-medium-emphasis mb-4">
              A supplemental login code is emailed to you when you sign in.
            </div>
            <v-alert v-if="twoFactorLockedOn" type="info" variant="tonal" class="mb-4">
              Your account is 2FA enabled, linked to your email.
            </v-alert>
            <v-switch
              v-if="showUserTwoFactorToggle"
              :model-value="userUse2fa"
              label="Require a login code for my account"
              color="primary"
              :disabled="savingUser2fa"
              hide-details
              class="mb-4"
              @update:model-value="persistUser2fa"
            />
            <v-switch
              v-if="showCustomerTwoFactorToggle"
              :model-value="customerUse2fa"
              label="Require 2FA for all workspace users"
              color="primary"
              :disabled="savingCustomer2fa"
              hint="When on, every user in this workspace must complete email 2FA at sign-in."
              persistent-hint
              @update:model-value="persistCustomer2fa"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row v-if="aiFeaturesEnabled && isAdmin">
      <v-col cols="12">
        <v-card class="glass-card mb-5">
          <v-card-text class="pa-6">
            <div class="text-h6 font-weight-bold mb-1">AI provider</div>
            <div class="text-caption text-medium-emphasis mb-4">
              Bring your own key for this workspace. Keys are stored encrypted on the server and are never shown in plaintext after save.
              If these fields are empty, the system default provider is used when one is configured.
            </div>
            <v-row>
              <v-col cols="12" md="4">
                <v-select
                  v-model="aiProvider"
                  :items="aiProviderItems"
                  item-title="title"
                  item-value="value"
                  label="Provider"
                  density="compact"
                  clearable
                  hint="OpenCode Go, OpenCode Zen, or OpenRouter"
                  persistent-hint
                />
              </v-col>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="aiKeyInput"
                  :type="showAiKey ? 'text' : 'password'"
                  label="Authorization key"
                  density="compact"
                  autocomplete="new-password"
                  :placeholder="aiKeyConfigured ? 'Key is set — leave blank to keep, or enter a new key' : 'Paste provider key'"
                  hint="Blank on save clears the key. Unchanged encoded value is left as stored."
                  persistent-hint
                >
                  <template #append-inner>
                    <v-btn icon variant="text" size="small" @click="showAiKey = !showAiKey">
                      <i :class="showAiKey ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye'" />
                    </v-btn>
                  </template>
                </v-text-field>
              </v-col>
              <v-col cols="12" md="8">
                <v-select
                  v-model="aiModel"
                  :items="aiModelItems"
                  item-title="title"
                  item-value="value"
                  label="Default model"
                  density="compact"
                  :disabled="!aiModelItems.length"
                  hint="Test the connection to load available models, then choose a default."
                  persistent-hint
                />
              </v-col>
              <v-col cols="12" class="d-flex flex-wrap ga-2">
                <v-btn variant="tonal" color="primary" :loading="testingAi" :disabled="!aiProvider" @click="testAiConnection">
                  <i class="fa-solid fa-plug mr-2" /> Test connection
                </v-btn>
                <v-btn color="primary" variant="flat" :loading="savingAi" @click="persistAiSettings">
                  Save AI settings
                </v-btn>
                <v-btn v-if="aiKeyConfigured || aiKeyInput" variant="text" @click="clearAiKey">
                  Clear key
                </v-btn>
              </v-col>
            </v-row>
            <v-alert v-if="aiTestMessage" :type="aiTestOk ? 'success' : 'warning'" variant="tonal" class="mt-4" density="compact">
              {{ aiTestMessage }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card v-if="isAdmin" class="glass-card mb-5">
          <v-card-text class="pa-6">
            <div class="text-h6 font-weight-bold mb-1">Customer Results defaults</div>
            <div class="text-caption text-medium-emphasis mb-4">
              Applies to multi-participant Results for this workspace.
            </div>
            <v-select
              v-model="coherence_method"
              :items="[
                { title: 'Spearman ρ (default)', value: 'spearman' },
                { title: 'Kendall τ', value: 'kendall' },
              ]"
              item-title="title"
              item-value="value"
              label="Participant agreement metric"
              class="mb-4"
              hint="Optional legacy label for agreement displays."
              persistent-hint
            />
            <v-btn color="primary" variant="flat" :loading="savingCustomer" @click="persistCustomer">
              Save customer defaults
            </v-btn>
          </v-card-text>
        </v-card>
        <v-alert v-else type="info" variant="tonal" class="mb-5">
          Only workspace admins can change customer defaults.
        </v-alert>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="glass-card mb-5">
          <v-card-text class="pa-6">
            <div class="text-h6 font-weight-bold mb-1">Appearance</div>
            <div class="text-caption text-medium-emphasis mb-4">
              Switch between light and dark interface themes. Your choice is saved on this device.
            </div>
            <v-btn-toggle
              :model-value="mode"
              mandatory
              color="primary"
              divided
              class="theme-toggle"
              @update:model-value="onAppearanceChange"
            >
              <v-btn value="light">
                <i class="fa-solid fa-sun mr-2" />
                Light
              </v-btn>
              <v-btn value="dark">
                <i class="fa-solid fa-moon mr-2" />
                Dark
              </v-btn>
            </v-btn-toggle>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import type { ThemeMode } from '~/composables/useThemeMode'

import type { SetUse2FAResult } from '~/types/api'

const snackbar = useSnackbar()
const { apiFetch } = useApi()
const { isAdmin, isSystemAdmin, context, refreshContext, aiFeaturesEnabled } = useAuth()
const { mode, setMode } = useThemeMode()

const coherence_method = ref<'spearman' | 'kendall'>('spearman')
const savingCustomer = ref(false)
const savingUser2fa = ref(false)
const savingCustomer2fa = ref(false)
const userUse2fa = ref(false)
const customerUse2fa = ref(false)

const settingsFlags = computed(() => (context.value?.settings || {}) as Record<string, unknown>)
const twoFactorEnabled = computed(() => !!settingsFlags.value.TWO_FACTOR_AUTH_ENABLED)
const twoFactorOptional = computed(() => !!settingsFlags.value.TWO_FACTOR_AUTH_OPTIONAL)
const customerTwoFactorControllable = computed(() => !!settingsFlags.value.TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE)
const roleLocked = computed(() => isAdmin.value || isSystemAdmin.value)
const showUserTwoFactorToggle = computed(() => twoFactorOptional.value && !roleLocked.value)
const twoFactorLockedOn = computed(() => twoFactorEnabled.value && !showUserTwoFactorToggle.value)
const showCustomerTwoFactorToggle = computed(() => customerTwoFactorControllable.value)
const showTwoFactorBox = computed(() => twoFactorEnabled.value || twoFactorOptional.value || customerTwoFactorControllable.value)

const aiProvider = ref<string | null>(null)
const aiModel = ref<string | null>(null)
const aiKeyInput = ref('')
const aiStoredKey = ref('')
const aiKeyConfigured = ref(false)
const showAiKey = ref(false)
const savingAi = ref(false)
const testingAi = ref(false)
const aiTestOk = ref(false)
const aiTestMessage = ref('')
const aiModels = ref<Array<{ id: string, name: string }>>([])
const aiProviderItems = [
  { title: 'OpenCode Go', value: 'opencode_go' },
  { title: 'OpenCode Zen', value: 'opencode_zen' },
  { title: 'OpenRouter', value: 'openrouter' },
]
const aiModelItems = computed(() => {
  const rows = aiModels.value.map(m => ({ title: m.name || m.id, value: m.id }))
  if (aiModel.value && !rows.some(r => r.value === aiModel.value)) {
    rows.unshift({ title: aiModel.value, value: aiModel.value })
  }
  return rows
})

async function loadAiSettings() {
  if (!aiFeaturesEnabled.value || !isAdmin.value) return
  try {
    const res = await apiFetch<{
      failure_reason?: string
      ai_provider?: string | null
      ai_model?: string | null
      ai_api_key?: string | null
      key_configured?: boolean
    }>('/ws/core/customer-ai-settings')
    if (res.failure_reason) return
    aiProvider.value = res.ai_provider || null
    aiModel.value = res.ai_model || null
    aiStoredKey.value = res.ai_api_key || ''
    aiKeyConfigured.value = !!res.key_configured
    aiKeyInput.value = ''
  }
  catch {
    /* settings page still works without AI */
  }
}

function clearAiKey() {
  aiKeyInput.value = ''
  aiStoredKey.value = ''
  aiKeyConfigured.value = false
}

async function testAiConnection() {
  if (!aiProvider.value) return
  testingAi.value = true
  aiTestMessage.value = ''
  try {
    const res = await apiFetch<{
      failure_reason?: string
      ok?: boolean
      models?: Array<{ id: string, name: string }>
    }>('/ws/core/test-customer-ai-connection', {
      method: 'POST',
      body: {
        ai_provider: aiProvider.value,
        ai_api_key: aiKeyInput.value || aiStoredKey.value,
        ai_model: aiModel.value,
      },
    })
    if (res.failure_reason || !res.ok) {
      aiTestOk.value = false
      aiTestMessage.value = res.failure_reason || 'Provider authorization failed'
      return
    }
    aiModels.value = res.models || []
    aiTestOk.value = true
    aiTestMessage.value = `Connected. ${aiModels.value.length} models available.`
    if (aiModel.value && !aiModels.value.some(m => m.id === aiModel.value) && aiModels.value.length) {
      aiModel.value = aiModels.value[0].id
    }
  }
  catch (e: unknown) {
    aiTestOk.value = false
    aiTestMessage.value = e instanceof Error ? e.message : 'Could not test connection'
  }
  finally {
    testingAi.value = false
  }
}

async function persistAiSettings() {
  savingAi.value = true
  try {
    const keyToSend = aiKeyInput.value !== '' ? aiKeyInput.value : aiStoredKey.value
    const res = await apiFetch<{ failure_reason?: string, key_configured?: boolean, ai_api_key?: string | null }>(
      '/ws/core/customer-ai-settings',
      {
        method: 'POST',
        body: {
          ai_provider: aiProvider.value,
          ai_model: aiModel.value,
          ai_api_key: keyToSend,
        },
      },
    )
    if (res.failure_reason) throw new Error(res.failure_reason)
    aiStoredKey.value = res.ai_api_key || ''
    aiKeyConfigured.value = !!res.key_configured
    aiKeyInput.value = ''
    await refreshContext()
    snackbar.success('AI provider settings saved')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not save AI settings')
  }
  finally {
    savingAi.value = false
  }
}

onMounted(() => {
  const s = context.value?.settings as Record<string, unknown> | undefined
  if (s?.coherence_method) {
    const m = String(s.coherence_method).toLowerCase()
    coherence_method.value = m === 'kendall' ? 'kendall' : 'spearman'
  }
  userUse2fa.value = !!context.value?.user_record?.use_2fa
  customerUse2fa.value = !!context.value?.customer_record?.use_2fa
  loadAiSettings()
})

function onAppearanceChange(value: unknown) {
  if (value === 'light' || value === 'dark') setMode(value as ThemeMode)
}

async function persistUser2fa(value: boolean | null) {
  const enabled = !!value
  savingUser2fa.value = true
  try {
    const res = await apiFetch<SetUse2FAResult>('/ws/user/set-use-2fa', {
      method: 'POST',
      body: { enabled },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    await refreshContext()
    userUse2fa.value = !!context.value?.user_record?.use_2fa
    snackbar.success(enabled ? 'Login codes enabled for your account' : 'Login codes turned off for your account')
  }
  catch (e: unknown) {
    userUse2fa.value = !!context.value?.user_record?.use_2fa
    snackbar.error(e instanceof Error ? e.message : 'Could not update 2FA')
  }
  finally {
    savingUser2fa.value = false
  }
}

async function persistCustomer2fa(value: boolean | null) {
  const enabled = !!value
  savingCustomer2fa.value = true
  try {
    const res = await apiFetch<SetUse2FAResult>('/ws/customer/set-use-2fa', {
      method: 'POST',
      body: { enabled },
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    await refreshContext()
    customerUse2fa.value = !!context.value?.customer_record?.use_2fa
    snackbar.success(enabled ? 'Workspace 2FA requirement enabled' : 'Workspace 2FA requirement turned off')
  }
  catch (e: unknown) {
    customerUse2fa.value = !!context.value?.customer_record?.use_2fa
    snackbar.error(e instanceof Error ? e.message : 'Could not update workspace 2FA')
  }
  finally {
    savingCustomer2fa.value = false
  }
}

async function persistCustomer() {
  savingCustomer.value = true
  try {
    const res = await apiFetch<{ failure_reason?: string, settings?: Record<string, unknown> }>(
      '/ws/core/update-customer-vote-settings',
      {
        method: 'POST',
        body: { coherence_method: coherence_method.value },
      },
    )
    if (res.failure_reason) throw new Error(res.failure_reason)
    await refreshContext()
    snackbar.success('Customer defaults saved')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not save customer settings')
  }
  finally {
    savingCustomer.value = false
  }
}
</script>
