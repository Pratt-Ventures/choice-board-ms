<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>

<script setup lang="ts">
// Hydrate light/dark preference once Vuetify theme is available in setup.
useThemeMode()
</script>
