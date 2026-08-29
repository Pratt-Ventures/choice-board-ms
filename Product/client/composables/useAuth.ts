import type {
  CustomerUserCreateResult,
  Login2FAChallenge,
  LoginResponse,
  UserCustomerContextView,
} from '~/types/api'
import { ApiError } from '~/composables/useApi'

export interface CustomerSelfRegPayload {
  customer_name: string
  admin_name: string
  admin_email: string
  admin_phone?: string | null
  admin_password: string
  trial_activation_code?: string | null
  invitation_code?: string | null
}

const context = ref<UserCustomerContextView | null>(null)
const loading = ref(false)
const initialized = ref(false)

export function useAuth() {
  const { apiFetch } = useApi()
  const snackbar = useSnackbar()

  const isAuthenticated = computed(() => !!context.value?.user_id)
  const isAdmin = computed(() => !!context.value?.is_customer_admin)
  const isSystemAdmin = computed(() => (context.value?.user_record?.system_user_mode ?? 0) >= 2)
  const userCommEnabled = computed(() =>
    !!(context.value?.settings as Record<string, unknown> | undefined)?.enable_user_communication,
  )
  const aiFeaturesEnabled = computed(() =>
    !!(context.value?.settings as Record<string, unknown> | undefined)?.ai_features_enabled,
  )
  const aiProvidersConfigured = computed(() =>
    !!(context.value?.settings as Record<string, unknown> | undefined)?.ai_providers_configured,
  )
  const userName = computed(() => context.value?.name || '')
  const customerName = computed(() => context.value?.customer_name || '')
  const trialDays = computed(() => context.value?.trial_expiration_days ?? null)
  const stripeCallbackPrefix = computed(() => context.value?.stripe_callback_prefix || '')

  async function login(email: string, password: string, twoFactorCode?: string) {
    loading.value = true
    try {
      const result = await apiFetch<UserCustomerContextView & Login2FAChallenge>('/auth-ws/login-and-get-context', {
        method: 'POST',
        body: {
          email,
          password,
          two_factor_code: twoFactorCode || undefined,
        },
      })
      if (result.two_factor_required) {
        return result
      }
      if (result.failure_reason) {
        throw new ApiError(result.failure_reason, 400, result)
      }
      context.value = result
      initialized.value = true
      return result
    }
    finally {
      loading.value = false
    }
  }

  async function loginPlain(email: string, password: string, twoFactorCode?: string) {
    loading.value = true
    try {
      const result = await apiFetch<LoginResponse>('/auth-ws/login', {
        method: 'POST',
        body: {
          email,
          password,
          two_factor_code: twoFactorCode || undefined,
        },
      })
      if (result.two_factor_required) {
        return result
      }
      await refreshContext()
      return result
    }
    finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await apiFetch<{ message?: string }>('/auth-ws/logout', { method: 'GET' })
    }
    catch {
      // still clear local session
    }
    context.value = null
    initialized.value = true
    await navigateTo('/login')
  }

  async function refreshContext(includeAccountStatus = false) {
    loading.value = true
    try {
      const result = await apiFetch<UserCustomerContextView>('/ws/core/get-user-customer-context', {
        method: 'POST',
        body: { include_account_status: includeAccountStatus },
      })
      if (result.failure_reason) {
        context.value = null
        return null
      }
      context.value = result
      return result
    }
    catch {
      context.value = null
      return null
    }
    finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function ensureSession() {
    if (initialized.value) return isAuthenticated.value
    await refreshContext()
    return isAuthenticated.value
  }

  async function signup(payload: CustomerSelfRegPayload) {
    return apiFetch<CustomerUserCreateResult>('/auth-ws/initial-signup', {
      method: 'POST',
      body: payload,
    })
  }

  async function confirmSignup(activationCode: string) {
    return apiFetch<CustomerUserCreateResult>(`/auth-ws/signup-confirm/${encodeURIComponent(activationCode)}`, {
      method: 'GET',
    })
  }

  async function requestPasswordReset(email: string) {
    return apiFetch<string>('/auth-ws/password-reset-request', {
      method: 'POST',
      body: { email },
    })
  }

  async function changePasswordViaToken(token: string, newPassword: string, email?: string) {
    return apiFetch<boolean>('/auth-ws/change-password-via-token', {
      method: 'POST',
      body: {
        token,
        new_password: newPassword,
        email: email || undefined,
      },
    })
  }

  function requireAdmin() {
    if (!isAdmin.value) {
      snackbar.error('Admin access required for this action')
      return false
    }
    return true
  }

  function requireSystemAdmin() {
    if (!isSystemAdmin.value) {
      snackbar.error('System admin access required for this action')
      return false
    }
    return true
  }

  return {
    context,
    loading,
    initialized,
    isAuthenticated,
    isAdmin,
    isSystemAdmin,
    userCommEnabled,
    aiFeaturesEnabled,
    aiProvidersConfigured,
    userName,
    customerName,
    trialDays,
    stripeCallbackPrefix,
    login,
    loginPlain,
    logout,
    refreshContext,
    ensureSession,
    signup,
    confirmSignup,
    requestPasswordReset,
    changePasswordViaToken,
    requireAdmin,
    requireSystemAdmin,
  }
}
