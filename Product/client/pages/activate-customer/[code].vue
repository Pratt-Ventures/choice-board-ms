<template>
  <div class="login-layout">
    <section class="login-marketing">
      <div>
        <div class="d-flex align-center ga-3 mb-10">
          <div class="brand-badge"><i class="fa-solid fa-bolt" /></div>
          <div class="text-h6 font-weight-bold" style="font-family:Manrope,Inter,sans-serif">Power Choice Pro</div>
        </div>
        <h1 class="hero-heading">Activate your workspace.</h1>
        <p class="hero-copy">
          Confirming this link unlocks sign-in for your admin account.
        </p>
      </div>
    </section>

    <section class="login-card-wrap">
      <v-card class="login-card pa-8" variant="flat">
        <div class="eyebrow">Activation</div>
        <h2 class="text-h4 font-weight-bold mb-4" style="letter-spacing: -.03em; color: var(--powerchoice-navy)">
          Confirming account…
        </h2>

        <v-progress-linear v-if="busy" indeterminate color="primary" class="mb-4" />
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4">{{ success }}</v-alert>

        <v-btn v-if="success || error" color="primary" block to="/login">
          Go to sign in
        </v-btn>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'auth' })

const route = useRoute()
const { confirmSignup } = useAuth()
const snackbar = useSnackbar()

const busy = ref(true)
const error = ref('')
const success = ref('')

onMounted(async () => {
  const code = String(route.params.code || '')
  if (!code) {
    error.value = 'Missing activation code'
    busy.value = false
    return
  }
  try {
    const result = await confirmSignup(code)
    if (result.failure_reason) {
      error.value = result.failure_reason
      return
    }
    success.value = 'Account activated. You can sign in now.'
    snackbar.success('Account activated')
  }
  catch (err) {
    error.value = err instanceof Error ? err.message : 'Activation failed'
  }
  finally {
    busy.value = false
  }
})
</script>
