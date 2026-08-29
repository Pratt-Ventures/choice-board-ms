<template>
  <v-card class="glass-card share-gate">
    <v-card-text class="pa-6">
      <div class="eyebrow">Secure access</div>
      <div class="text-h5 font-weight-bold mb-2">{{ title }}</div>
      <div class="text-body-2 text-medium-emphasis mb-4">{{ subtitle }}</div>
      <div v-if="remainingTimeCopy" class="text-body-2 text-medium-emphasis mb-4">{{ remainingTimeCopy }}</div>

      <v-alert v-if="message" :type="messageType" variant="tonal" class="mb-4">{{ message }}</v-alert>

      <template v-if="showSpinner">
        <v-progress-linear indeterminate color="primary" class="mb-2" />
        <div class="text-body-2 text-medium-emphasis">Checking access…</div>
      </template>
      <template v-else>
        <div v-if="verifiedHint" class="text-body-2 text-medium-emphasis mb-4">{{ verifiedHint }}</div>

        <v-text-field
          v-if="needsDisplayName"
          v-model="form.display_name"
          label="Your name"
          autocomplete="name"
          class="mb-2"
        />
        <v-text-field
          v-if="needsEmail"
          v-model="form.verification_email"
          label="Email"
          type="email"
          autocomplete="email"
          class="mb-2"
        />
        <v-text-field
          v-if="needsPassword"
          v-model="form.verification_password"
          label="Password"
          type="password"
          autocomplete="current-password"
          class="mb-2"
        />
        <v-text-field
          v-if="needsMagic"
          v-model="form.verification_magic_email_key"
          label="Access code"
          autocomplete="one-time-code"
          autofocus
          class="mb-2"
        />

        <template v-if="isVerifiedMode && view === 'request'">
          <v-btn
            color="primary"
            variant="flat"
            block
            :loading="loading"
            @click="sendCode"
          >
            Email Access Code
          </v-btn>
          <div class="text-center mt-3">
            <v-btn
              variant="text"
              size="small"
              class="text-medium-emphasis text-decoration-underline"
              @click="showEnterCode"
            >
              already have a code
            </v-btn>
          </div>
        </template>
        <template v-else>
          <v-btn color="primary" variant="flat" block :loading="loading" @click="continueUnlock">
            Continue
          </v-btn>
          <div v-if="isVerifiedMode || initialKey" class="text-center mt-3">
            <v-btn
              variant="text"
              size="small"
              class="text-medium-emphasis text-decoration-underline"
              :loading="loading"
              @click="sendCode"
            >
              send/resend code to email
            </v-btn>
          </div>
        </template>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { ShareAccessPayload } from '~/types/api'
import { projectRemainingTimeCopy } from '~/utils/projectEndTime'

const props = defineProps<{
  title?: string
  subtitle?: string
  endTime?: string | null
  denial?: ShareAccessPayload | null
  loading?: boolean
  message?: string
  messageType?: 'error' | 'info' | 'success' | 'warning'
  initialKey?: string
}>()

const remainingTimeCopy = computed(() => projectRemainingTimeCopy(props.endTime || props.denial?.project?.end_time))

const emit = defineEmits<{ submit: [payload: Record<string, unknown>] }>()

const form = reactive({
  display_name: '',
  verification_email: '',
  verification_password: '',
  verification_magic_email_key: '',
  authorize_verification_email: false,
})

const view = ref<'request' | 'enter'>('request')

const needsPassword = computed(() =>
  !!props.denial?.verification_password_needed
  || !!props.denial?.verification_password_not_supplied
  || !!props.denial?.verification_password_incorrect,
)

const recipientOnFileModes = new Set([
  'recipient_email_verified',
  'password_with_recipient_email_verified',
])

const needsEmail = computed(() => {
  if (recipientOnFileModes.has(String(props.denial?.access_mode || ''))) return false
  return !!props.denial?.verification_email_needed
    || !!props.denial?.verification_email_not_supplied
    || !!props.denial?.verification_original_email_needed
})

const isVerifiedMode = computed(() =>
  !!props.denial?.verification_email_send_link_mode
  || !!props.denial?.sent_magic_access_message
  || !!props.denial?.verification_email_magic_link_needed
  || !!props.denial?.verification_magic_link_incorrect
  || !!props.denial?.verification_magic_link_expired
  || !!props.denial?.verification_magic_link_used,
)

const needsMagic = computed(() =>
  view.value === 'enter' && (isVerifiedMode.value || !!props.initialKey),
)

const needsDisplayName = computed(() =>
  needsEmail.value || needsPassword.value || isVerifiedMode.value || !props.denial,
)

const showSpinner = computed(() => !!props.loading && !props.denial && !props.initialKey)

const verifiedHint = computed(() => {
  if (!isVerifiedMode.value) return ''
  if (view.value === 'enter') return 'Enter the access code from your email.'
  if (needsEmail.value) return 'We will send a one-time access code to your email.'
  return 'We will send a one-time access code to the email on file.'
})

function applyInitialKey(key?: string) {
  const value = String(key || '').trim()
  if (!value) return
  if (!form.verification_magic_email_key) form.verification_magic_email_key = value
  view.value = 'enter'
}

watch(() => props.initialKey, (key) => applyInitialKey(key), { immediate: true })

watch(() => props.denial, (denial) => {
  if (!denial) return
  if (
    denial.sent_magic_access_message
    || denial.verification_email_magic_link_needed
    || denial.verification_magic_link_incorrect
    || denial.verification_magic_link_expired
    || denial.verification_magic_link_used
  ) {
    view.value = 'enter'
  }
})

function showEnterCode() {
  view.value = 'enter'
}

function postedEmail() {
  return needsEmail.value ? form.verification_email : ''
}

function sendCode() {
  view.value = 'enter'
  emit('submit', {
    display_name: form.display_name,
    verification_email: postedEmail(),
    verification_password: form.verification_password,
    verification_magic_email_key: '',
    authorize_verification_email: true,
  })
}

function continueUnlock() {
  emit('submit', {
    display_name: form.display_name,
    verification_email: postedEmail(),
    verification_password: form.verification_password,
    verification_magic_email_key: form.verification_magic_email_key,
    authorize_verification_email: false,
  })
}
</script>
