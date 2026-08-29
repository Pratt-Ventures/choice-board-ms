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
        <div class="hero-heading mb-5">Better structure. Better input. Better decisions.</div>
        <p class="hero-copy">
          Create a workspace, structure your first project, and invite people to focused comparisons.
        </p>
      </div>
      <div class="quote-card">
        <div class="text-body-2" style="opacity: .9">
          After signup, activate your account from the email we send — then bind Stripe and issue API keys.
        </div>
      </div>
    </section>

    <section class="login-card-wrap">
      <v-card class="login-card auth-card pa-8" variant="flat" elevation="0">
        <div class="text-h5 font-weight-bold mb-1" style="letter-spacing:-.02em">Create your account</div>
        <div class="text-body-2 text-medium-emphasis mb-6">
          Start verifying subscriptions in minutes. You’ll be the first admin.
        </div>

        <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="comfortable">
          {{ error }}
        </v-alert>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4" density="comfortable">
          {{ success }}
        </v-alert>

        <v-form v-if="!success" @submit.prevent="onSubmit">
          <v-text-field v-model="form.customer_name" label="Company / workspace name" class="mb-1" :disabled="busy" />
          <v-text-field v-model="form.admin_name" label="Your name" class="mb-1" :disabled="busy" />
          <v-text-field v-model="form.admin_email" label="Work email" type="email" class="mb-1" :disabled="busy" />
          <v-text-field v-model="form.admin_phone" label="Phone (optional)" class="mb-1" :disabled="busy" />
          <v-text-field
            v-model="form.admin_password"
            label="Password"
            :type="showPassword ? 'text' : 'password'"
            class="mb-1"
            :disabled="busy"
            :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="showPassword = !showPassword"
          />
          <v-text-field
            v-model="form.trial_activation_code"
            label="Trial code (optional)"
            class="mb-3"
            :disabled="busy"
            hint="If you have a trial activation code, enter it here"
            persistent-hint
          />

          <v-btn type="submit" color="primary" size="large" block :loading="busy" class="mb-4">
            Create account
          </v-btn>
        </v-form>

        <div class="text-center text-body-2" style="color: var(--powerchoice-muted)">
          Already have an account?
          <NuxtLink to="/login" class="text-decoration-none text-primary font-weight-medium">
            Sign in
          </NuxtLink>
        </div>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const { signup } = useAuth()
const snackbar = useSnackbar()

const form = reactive({
  customer_name: '',
  admin_name: '',
  admin_email: '',
  admin_phone: '',
  admin_password: '',
  trial_activation_code: '',
})
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')
const success = ref('')

async function onSubmit() {
  error.value = ''
  if (!form.customer_name || !form.admin_name || !form.admin_email || !form.admin_password) {
    error.value = 'Fill in company name, your name, email, and password'
    return
  }
  busy.value = true
  try {
    const result = await signup({
      customer_name: form.customer_name.trim(),
      admin_name: form.admin_name.trim(),
      admin_email: form.admin_email.trim(),
      admin_phone: form.admin_phone.trim() || null,
      admin_password: form.admin_password,
      trial_activation_code: form.trial_activation_code.trim() || null,
    })
    if (result.failure_reason) {
      error.value = result.failure_reason
      return
    }
    success.value = 'Account created. Check your email for an activation link, then sign in.'
    snackbar.success('Account created — check your email')
  }
  catch (err) {
    error.value = err instanceof Error ? err.message : 'Signup failed'
  }
  finally {
    busy.value = false
  }
}
</script>
