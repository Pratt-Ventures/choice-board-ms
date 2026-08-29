<template>
  <div>
    <div class="mb-6">
      <div class="eyebrow">Account</div>
      <div class="page-title">Submit a report</div>
      <div class="page-subtitle">
        Choose whether this is a bug or a suggestion, then fill in the details.
      </div>
    </div>

    <v-row class="mb-6">
      <v-col cols="12" md="6">
        <button
          type="button"
          class="type-card"
          :class="{ 'type-card--active': selected === 'bug' }"
          @click="selectType('bug')"
        >
          <div class="type-card__icon">
            <i class="fa-solid fa-bug" />
          </div>
          <div class="type-card__copy">
            <div class="text-subtitle-1 font-weight-bold font-display">Bug report</div>
            <div class="text-body-2 text-medium-emphasis">
              Something is broken or not working as expected.
            </div>
          </div>
        </button>
      </v-col>
      <v-col cols="12" md="6">
        <button
          type="button"
          class="type-card"
          :class="{ 'type-card--active': selected === 'suggestion' }"
          @click="selectType('suggestion')"
        >
          <div class="type-card__icon">
            <i class="fa-solid fa-lightbulb" />
          </div>
          <div class="type-card__copy">
            <div class="text-subtitle-1 font-weight-bold font-display">Suggestion</div>
            <div class="text-body-2 text-medium-emphasis">
              An idea that would make the product more useful.
            </div>
          </div>
        </button>
      </v-col>
    </v-row>

    <SubmissionForm
      v-if="selected"
      :key="selected"
      :kind="selected"
      @submitted="onSubmitted"
      @cancel="clearType"
    />
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { userCommEnabled } = useAuth()

const selected = computed(() => {
  const raw = String(route.query.type || '')
  if (raw === 'bug' || raw === 'suggestion') return raw
  return null
})

onMounted(() => {
  if (!userCommEnabled.value) navigateTo('/projects')
})

function selectType(kind: 'bug' | 'suggestion') {
  navigateTo({ path: '/submissions/new', query: { type: kind } }, { replace: true })
}

function clearType() {
  navigateTo({ path: '/submissions/new' }, { replace: true })
}

function onSubmitted() {
  navigateTo('/submissions')
}
</script>

<style scoped>
.type-card {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  text-align: left;
  padding: 20px;
  border-radius: 14px;
  border: 1px solid var(--pc-border);
  background: rgb(var(--v-theme-surface));
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.type-card:hover {
  border-color: rgb(var(--v-theme-primary));
}
.type-card--active {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 3px rgba(var(--v-theme-primary), 0.16);
}
.type-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: rgb(var(--v-theme-primary));
  color: white;
}
.type-card__copy {
  min-width: 0;
}
</style>
