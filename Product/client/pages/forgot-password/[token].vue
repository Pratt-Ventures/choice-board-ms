<template>
  <div class="login-layout">
    <section class="login-marketing">
      <div>
        <div class="d-flex align-center ga-3 mb-10">
          <div class="brand-badge"><i class="fa-solid fa-bolt" /></div>
          <div class="text-h6 font-weight-bold" style="font-family:Manrope,Inter,sans-serif">Power Choice Pro</div>
        </div>
        <h1 class="hero-heading">Choose a new password.</h1>
        <p class="hero-copy">
          This link is single-use. After you save, sign in with the new password.
        </p>
      </div>
    </section>

    <section class="login-card-wrap">
      <v-card class="login-card pa-8" variant="flat">
        <div class="eyebrow">Account recovery</div>
        <h2 class="text-h4 font-weight-bold mb-1" style="letter-spacing: -.03em; color: var(--powerchoice-navy)">
          Set new password
        </h2>

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable">
          {{ error }}
        </v-alert>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4" density="comfortable">
          {{ success }}
        </v-alert>

        <v-form v-if="!success" @submit.prevent="onSubmit">
          <v-text-field
            v-model="password"
            label="New password"
            type="password"
            class="mb-1"
            :disabled="busy"
          />
          <v-text-field
            v-model="confirm"
            label="Confirm password"
            type="password"
            class="mb-4"
            :disabled="busy"
          />
          <v-btn type="submit" color="primary" size="large" block :loading="busy" class="mb-4">
            Update password
          </v-btn>
        </v-form>

        <div class="text-center text-body-2">
          <NuxtLink to="/login" class="text-decoration-none font-weight-bold" style="color: var(--powerchoice-blue)">
            Back to sign in
          </NuxtLink>
        </div>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const route = useRoute()
const { changePasswordViaToken } = useAuth()
const snackbar = useSnackbar()

const token = computed(() => String(route.params.token || ''))
const password = ref('')
const confirm = ref('')
const busy = ref(false)
const error = ref('')
const success = ref('')

async function onSubmit() {
  error.value = ''
  if (!password.value || password.value.length < 8) {
    error.value = 'Password must be at least 8 characters'
    return
  }
  if (password.value !== confirm.value) {
    error.value = 'Passwords do not match'
    return
  }
  busy.value = true
  try {
    const ok = await changePasswordViaToken(token.value, password.value)
    if (!ok) {
      error.value = 'Password reset failed. The link may be expired.'
      return
    }
    success.value = 'Password updated. You can sign in now.'
    snackbar.success('Password updated')
  }
  catch (err) {
    error.value = err instanceof Error ? err.message : 'Password reset failed'
  }
  finally {
    busy.value = false
  }
}
</script>
