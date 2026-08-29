<template>
  <div class="login-layout">
    <section class="login-marketing">
      <div style="position:relative;max-width:560px">
        <div class="d-flex align-center ga-3 mb-10">
          <div class="brand-badge">
            <i class="fa-solid fa-bolt" />
          </div>
          <div>
            <span class="text-h5 font-weight-bold" style="letter-spacing:-.02em;font-family:Manrope,Inter,sans-serif">
              Power Choice Pro
            </span>
            <div class="text-caption" style="opacity:.75;letter-spacing:.1em;text-transform:uppercase;font-weight:700">
              Decision workspace
            </div>
          </div>
        </div>
        <div class="hero-heading mb-5">
          Turn complex choices into confident action.
        </div>
        <p class="hero-copy mb-10">
          Structure options, invite the right people, and share a result that is clear enough to act on and explain.
        </p>
        <div class="d-flex flex-column ga-5">
          <div class="feature-row">
            <div class="feature-ic"><i class="fa-solid fa-diagram-project" /></div>
            <div>
              <div class="font-weight-bold">Structure the decision</div>
              <div class="text-body-2" style="opacity:.8">Projects, options, and factors — without the statistical theater.</div>
            </div>
          </div>
          <div class="feature-row">
            <div class="feature-ic"><i class="fa-solid fa-user-group" /></div>
            <div>
              <div class="font-weight-bold">Collect meaningful input</div>
              <div class="text-body-2" style="opacity:.8">Focused comparisons with autosave, resume, and share links.</div>
            </div>
          </div>
          <div class="feature-row">
            <div class="feature-ic"><i class="fa-solid fa-chart-line" /></div>
            <div>
              <div class="font-weight-bold">Explain the result</div>
              <div class="text-body-2" style="opacity:.8">Recommendations, rankings, confidence, and participation context.</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="login-card-wrap">
      <v-card class="login-card auth-card pa-8" variant="flat" elevation="0">
        <div class="text-h5 font-weight-bold mb-1" style="letter-spacing:-.02em;font-family:Manrope,Inter,sans-serif">
          Welcome back
        </div>
        <div class="text-body-2 text-medium-emphasis mb-6">Sign in to your Power Choice Pro account.</div>

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="compact">
          {{ error }}
        </v-alert>
        <v-alert v-else-if="twoFactorMessage" type="info" variant="tonal" class="mb-4" density="compact">
          {{ twoFactorMessage }}
        </v-alert>

        <v-form @submit.prevent="onSubmit">
          <v-text-field
            v-model="email"
            label="Email"
            type="email"
            autocomplete="username"
            prepend-inner-icon="mdi-email-outline"
            class="mb-3"
            :disabled="busy || twoFactorRequired"
          />
          <v-text-field
            v-if="!twoFactorRequired"
            v-model="password"
            label="Password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            prepend-inner-icon="mdi-lock-outline"
            :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
            :disabled="busy"
            class="mb-1"
            @click:append-inner="showPassword = !showPassword"
          />
          <v-text-field
            v-else
            v-model="twoFactorCode"
            label="Login code"
            autocomplete="one-time-code"
            prepend-inner-icon="mdi-shield-key-outline"
            class="mb-1"
            :disabled="busy"
          />

          <div class="d-flex justify-end mb-5">
            <button
              v-if="twoFactorRequired"
              type="button"
              class="text-body-2 text-decoration-none text-primary font-weight-medium"
              :disabled="busy"
              @click="onResend"
            >
              Resend code
            </button>
            <NuxtLink v-else to="/forgot-password" class="text-body-2 text-decoration-none text-primary font-weight-medium">
              Forgot password?
            </NuxtLink>
          </div>

          <v-btn
            type="submit"
            color="primary"
            size="large"
            block
            :loading="busy"
          >
            {{ twoFactorRequired ? 'Verify and sign in' : 'Sign in' }}
          </v-btn>
        </v-form>

        <div class="text-center text-body-2 mt-6">
          New to Power Choice Pro?
          <NuxtLink to="/signup" class="text-decoration-none text-primary font-weight-medium">
            Create an account
          </NuxtLink>
        </div>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const route = useRoute()
const { login, loading } = useAuth()
const snackbar = useSnackbar()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref('')
const twoFactorRequired = ref(false)
const twoFactorCode = ref('')
const twoFactorMessage = ref('')
const busy = computed(() => loading.value)

function applyChallenge(result: { two_factor_required?: boolean, message?: string, failure_reason?: string, validity_minutes?: number }) {
  twoFactorRequired.value = true
  twoFactorCode.value = ''
  const sent = result.failure_reason || result.message || 'A supplemental login code has been sent to your email'
  const mins = result.validity_minutes
  twoFactorMessage.value = mins ? `${sent} Valid for ${mins} minutes.` : sent
}

async function completeLogin(code?: string) {
  error.value = ''
  const result = await login(email.value.trim(), password.value, code)
  if (result && 'two_factor_required' in result && result.two_factor_required) {
    applyChallenge(result)
    return
  }
  snackbar.success('Signed in')
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/projects'
  await navigateTo(redirect)
}

async function onSubmit() {
  if (!email.value || !password.value) {
    error.value = 'Enter email and password'
    return
  }
  if (twoFactorRequired.value && !twoFactorCode.value.trim()) {
    error.value = 'Enter the login code sent to your email'
    return
  }
  try {
    await completeLogin(twoFactorRequired.value ? twoFactorCode.value.trim() : undefined)
  }
  catch (err) {
    error.value = err instanceof Error ? err.message : 'Sign-in failed'
  }
}

async function onResend() {
  try {
    await completeLogin()
  }
  catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not resend the login code'
  }
}
</script>
