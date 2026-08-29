<template>
  <div>
    <div class="detail-label">{{ label }}</div>
    <div class="d-flex align-center ga-2">
      <code class="masked-secret">{{ revealed ? value : masked }}</code>
      <v-btn
        v-if="value"
        icon
        size="x-small"
        variant="text"
        :aria-label="revealed ? 'Hide' : 'Reveal'"
        @click="revealed = !revealed"
      >
        <v-icon :icon="revealed ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" size="18" />
      </v-btn>
      <v-btn
        v-if="value"
        icon
        size="x-small"
        variant="text"
        aria-label="Copy"
        @click="copyText(value, label)"
      >
        <v-icon icon="mdi-content-copy" size="18" />
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string
  value?: string | null
  visibleChars?: number
}>()

const { maskSecret, copyText } = useFormat()
const revealed = ref(false)
const masked = computed(() => maskSecret(props.value, props.visibleChars ?? 4))
</script>
