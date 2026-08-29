<template>
  <div class="d-flex align-center ga-2">
    <span class="text-body-2">{{ date ? formatDate(date, true) : empty }}</span>
    <v-tooltip v-if="note" :text="note" location="top" open-on-hover open-delay="80">
      <template #activator="{ props: tip }">
        <button type="button" class="note-info" v-bind="tip" :aria-label="ariaLabel">
          <i class="fa-solid fa-circle-info" />
        </button>
      </template>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  date?: string | null
  note?: string | null
  empty?: string
  ariaLabel?: string
}>(), {
  empty: '—',
  ariaLabel: 'Note',
})

const { formatDate } = useFormat()
</script>

<style scoped>
.note-info {
  border: 0;
  background: transparent;
  color: var(--pc-primary);
  cursor: default;
  padding: 0;
  line-height: 1;
}
</style>
