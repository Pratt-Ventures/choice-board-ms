<script setup lang="ts">
definePageMeta({ layout: 'share' })

const route = useRoute()
const token = String(route.params.token || '')
const key = String(route.params.key || '')
await navigateTo({
  path: `/share/vote/${encodeURIComponent(token)}`,
  query: key ? { key } : undefined,
  replace: true,
})
</script>

<template>
  <div />
</template>
