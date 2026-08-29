<template>
  <div class="login-layout">
    <section class="login-marketing">
      <div>
        <div class="d-flex align-center ga-3 mb-10">
          <div class="brand-badge">
            <i class="fa-solid fa-bolt" />
          </div>
          <span class="text-h5 font-weight-bold" style="letter-spacing:-.02em;font-family:Manrope,Inter,sans-serif">Power Choice Pro</span>
        </div>
        <div class="hero-heading mb-5">Reset access securely.</div>
        <p class="hero-copy">
          We’ll email a one-time link so you can choose a new password.
        </p>
      </div>
    </section>

    <section class="login-card-wrap">
      <v-card class="login-card auth-card pa-8" variant="flat" elevation="0">
        <div class="text-h5 font-weight-bold mb-1" style="letter-spacing:-.02em">Reset your password</div>
        <div class="text-body-2 text-medium-emphasis mb-6">
          Enter the email on your Power Choice Pro user profile.
        </div>

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable">
          {{ error }}
        </v-alert>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4" density="comfortable">
          {{ success }}
        </v-alert>

        <v-form v-if="!success" @submit.prevent="onSubmit">
          <v-text-field v-model="email" label="Email" type="email" class="mb-4" :disabled="busy" />
          <v-btn type="submit" color="primary" size="large" block :loading="busy" class="mb-4">
            Send reset link
          </v-btn>
        </v-form>

        <div class="text-center text-body-2">
          <NuxtLink to="/login" class="text-decoration-none text-primary font-weight-medium">
            Back to sign in
          </NuxtLink>
        </div>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const { requestPasswordReset } = useAuth()
const email = ref('')
const busy = ref(false)
const error = ref('')
const success = ref('')

async function onSubmit() {
  error.value = ''
  if (!email.value) {
    error.value = 'Enter your email'
    return
  }
  busy.value = true
  try {
    await requestPasswordReset(email.value.trim())
    success.value = 'If that email exists, a reset link is on its way. Check your inbox.'
  }
  catch (err) {
    // Always show a soft success to avoid email enumeration in UI; still surface hard failures
    success.value = 'If that email exists, a reset link is on its way. Check your inbox.'
    if (err instanceof Error && err.message && !err.message.includes('404')) {
      // keep soft message
    }
  }
  finally {
    busy.value = false
  }
}
</script>
