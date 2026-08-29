<template>
  <v-dialog :model-value="modelValue" max-width="420" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="pc-dialog-card">
      <v-card-text class="pa-6">
        <div class="d-flex align-center justify-space-between mb-4">
          <div class="d-flex align-center ga-3">
            <div class="about-badge">
              <i class="fa-solid fa-bolt" />
            </div>
            <div>
              <div class="text-h6 font-weight-bold" style="letter-spacing:-.01em;font-family:Manrope,Inter,sans-serif">
                Power Choice Pro
              </div>
              <div class="text-caption text-medium-emphasis">Decision workspace</div>
            </div>
          </div>
          <v-btn icon variant="text" size="small" @click="emit('update:modelValue', false)">
            <i class="fa-solid fa-xmark" />
          </v-btn>
        </div>

        <div class="about-row">
          <span class="text-caption text-medium-emphasis">Version</span>
          <span class="text-body-2 font-weight-bold">{{ versionLabel }}</span>
        </div>
        <div v-if="service" class="about-row mt-2">
          <span class="text-caption text-medium-emphasis">Service</span>
          <span class="text-body-2">{{ service }}</span>
        </div>
      </v-card-text>
      <v-card-actions class="px-6 pb-5 pt-0">
        <v-spacer />
        <v-btn color="primary" variant="tonal" rounded="lg" @click="emit('update:modelValue', false)">
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const { apiFetch } = useApi()
const version = ref<string | null>(null)
const service = ref<string | null>(null)
const loading = ref(false)

const versionLabel = computed(() => {
  if (loading.value && !version.value) return '…'
  return version.value || 'Unavailable'
})

async function loadVersion() {
  if (loading.value) return
  loading.value = true
  try {
    const body = await apiFetch<{ version?: string; service?: string }>('/status')
    version.value = body.version || null
    service.value = body.service || null
  } catch {
    version.value = null
    service.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) loadVersion()
  },
)
</script>

<style scoped>
.about-badge {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: rgb(var(--v-theme-primary));
  color: white;
  font-size: 18px;
}
.about-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
