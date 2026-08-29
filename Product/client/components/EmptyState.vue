<template>
  <div class="text-center py-12 px-4">
    <v-icon :icon="icon" size="48" color="primary" class="mb-3" style="opacity: 0.75" />
    <div class="text-h6 font-weight-bold mb-1">{{ title }}</div>
    <div class="text-body-2 mb-5" style="color: var(--powerchoice-muted); max-width: 420px; margin: 0 auto">
      {{ description }}
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  icon?: string
  title: string
  description: string
}>(), {
  icon: 'mdi-inbox-outline',
})
</script>
