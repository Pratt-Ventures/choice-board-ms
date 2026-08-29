<template>
  <v-app>
    <v-app-bar flat height="64" color="surface" class="topbar">
      <div class="d-flex align-center ga-3 px-4 flex-grow-1" style="min-width:0">
        <div
          v-if="branding?.has_customer_image && customerImageSrc"
          class="share-brand-logo"
        >
          <img :src="customerImageSrc" alt="" class="share-brand-logo__img" />
        </div>
        <div
          v-else
          class="brand-badge"
          style="width:36px;height:36px;border-radius:11px;flex-shrink:0"
        >
          <i class="fa-solid fa-bolt" style="font-size:14px" />
        </div>
        <div style="min-width:0">
          <div class="brand-wordmark text-truncate" style="font-size:1rem">
            {{ displayCompanyName }}
          </div>
          <div class="text-caption text-medium-emphasis text-truncate">
            {{ branding?.project_title || 'Secure participation' }}
          </div>
        </div>
      </div>
      <v-spacer />
      <v-chip size="small" variant="tonal" color="primary" class="mr-4">{{ shareKindLabel }}</v-chip>
    </v-app-bar>
    <v-main>
      <div class="page-container">
        <VersionBanner
          v-if="versionCheck.showBanner.value"
          :server-version="versionCheck.serverVersion.value"
          :client-version="versionCheck.clientVersion.value"
          @dismiss="versionCheck.dismiss()"
          @reload="versionCheck.reload()"
        />
        <slot />
      </div>
    </v-main>
    <AppSnackbar />
  </v-app>
</template>

<script setup lang="ts">
import type { BrandingMeta } from '~/types/api'

const route = useRoute()
const brandingApi = useBrandingApi()
const shareSession = useShareSession()
const versionCheck = useVersionCheck()

const branding = ref<BrandingMeta | null>(null)

const shareToken = computed(() => {
  const t = route.params.token
  return typeof t === 'string' ? t : Array.isArray(t) ? t[0] : ''
})

const shareKindLabel = computed(() => {
  if (route.path.includes('/vote_view')) return 'Compare and See Only Your Results'
  if (route.path.includes('/report')) return 'See Full Results'
  if (route.path.includes('/vote')) return 'Comparing'
  return 'Share'
})

const displayCompanyName = computed(() => {
  const name = branding.value?.customer_name?.trim()
  return name || 'Power Choice Pro'
})

const customerImageSrc = computed(() => {
  // Binary images require authenticated share session cookie
  if (!shareSession.unlocked.value || !shareToken.value || !branding.value?.has_customer_image) return ''
  return brandingApi.shareCustomerImageUrl(
    shareToken.value,
    branding.value.customer_image_modify_date || Date.now(),
  )
})

async function loadBranding() {
  if (!shareToken.value) return
  shareSession.reset()
  try {
    const res = await brandingApi.shareBranding(shareToken.value)
    if (!res.failure_reason && res.branding) {
      branding.value = res.branding
    }
  }
  catch {
    // keep product default branding
  }
}

watch(shareToken, () => { loadBranding() }, { immediate: true })
</script>

<style scoped>
.share-brand-logo {
  width: 60px;
  height: 60px;
  border-radius: 11px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(var(--v-theme-surface-variant), 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}
.share-brand-logo__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
</style>
