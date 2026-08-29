<template>
  <v-card class="metric-card" rounded="lg" variant="flat">
    <v-card-text>
      <div class="d-flex justify-space-between align-start">
        <div class="stat-icon" :style="{ background: tint }">
          <v-icon :color="color" size="20" :icon="icon" />
        </div>
        <v-chip
          v-if="delta"
          size="x-small"
          :color="deltaDir === 'down' ? 'error' : 'success'"
          variant="tonal"
        >
          <v-icon start size="11">
            {{ deltaDir === 'down' ? 'mdi-arrow-down' : 'mdi-arrow-up' }}
          </v-icon>
          {{ delta }}
        </v-chip>
        <v-chip v-else-if="chip" size="x-small" :color="chipColor" variant="tonal">
          {{ chip }}
        </v-chip>
      </div>
      <div class="metric-value mt-3">{{ value }}</div>
      <div class="metric-label">{{ label }}</div>
      <div v-if="hint" class="text-caption mt-1 text-medium-emphasis">
        {{ hint }}
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  icon: string
  value: string | number
  label: string
  hint?: string
  chip?: string
  chipColor?: string
  color?: string
  tint?: string
  delta?: string | null
  deltaDir?: 'up' | 'down' | 'flat'
}>(), {
  color: 'primary',
  tint: 'rgba(64,89,216,.12)',
  chipColor: 'primary',
  deltaDir: 'up',
})
</script>
