<template>
  <v-app>
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
const versionCheck = useVersionCheck()
</script>
