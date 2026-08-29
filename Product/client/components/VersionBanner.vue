<template>
  <div
    v-if="visible"
    role="alert"
    aria-live="polite"
    class="version-banner"
  >
    <v-alert
      type="warning"
      variant="tonal"
      color="warning"
      density="comfortable"
      class="version-banner__alert"
      prominent
    >
      <div class="version-banner__content">
        <div class="version-banner__text">
          <strong>A new version is available</strong> — reload to update.
          <span
            v-if="serverVersion && clientVersion"
            class="version-banner__meta"
          >
            (client {{ clientVersion }} → server {{ serverVersion }})
          </span>
        </div>
        <div class="version-banner__actions">
          <v-btn
            color="warning"
            variant="flat"
            size="small"
            rounded="lg"
            class="mr-2"
            @click="onReload"
          >
            Reload
          </v-btn>
          <v-btn
            variant="text"
            size="small"
            rounded="lg"
            aria-label="Dismiss version update banner"
            @click="onDismiss"
          >
            Dismiss
          </v-btn>
        </div>
      </div>
    </v-alert>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    serverVersion?: string | null
    clientVersion?: string | null
    visible?: boolean
  }>(),
  {
    serverVersion: null,
    clientVersion: null,
    visible: true,
  },
)

const emit = defineEmits<{
  reload: []
  dismiss: []
}>()

function onReload() {
  emit('reload')
  if (!import.meta.client) return
  try {
    const doHardReload = () => {
      try {
        ;(window.location.reload as unknown as (b: boolean) => void)(true)
      } catch {
        window.location.reload()
      }
      setTimeout(() => {
        if (document.visibilityState !== 'hidden') window.location.href = window.location.href
      }, 400)
    }
    const bustHttpCacheThenReload = () => {
      let done = false
      const once = () => {
        if (done) return
        done = true
        doHardReload()
      }
      try {
        fetch(window.location.href, {
          cache: 'no-store',
          headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
        }).then(once, once)
        setTimeout(once, 700)
      } catch {
        once()
      }
    }
    const clearCachesThenBust = () => {
      if ('caches' in window && typeof (window as unknown as { caches?: { keys: () => Promise<string[]> } }).caches?.keys === 'function') {
        try {
          const cs = (window as unknown as { caches: { keys: () => Promise<string[]>; delete: (k: string) => Promise<boolean> } }).caches
          cs.keys()
            .then((keys) => Promise.all(keys.map((k) => cs.delete(k))))
            .then(bustHttpCacheThenReload, bustHttpCacheThenReload)
          return
        } catch {
          // fall through to bust
        }
      }
      bustHttpCacheThenReload()
    }
    clearCachesThenBust()
  } catch {
    window.location.reload()
  }
}

function onDismiss() {
  emit('dismiss')
}
</script>

<style scoped>
.version-banner {
  margin-bottom: 16px;
}
.version-banner__alert {
  border: 1.5px solid rgba(var(--v-theme-warning), 0.45);
}
.version-banner__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.version-banner__text {
  flex: 1 1 260px;
  min-width: 0;
  line-height: 1.35;
}
.version-banner__meta {
  opacity: 0.75;
  font-size: 0.85em;
  margin-left: 6px;
}
.version-banner__actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
</style>
