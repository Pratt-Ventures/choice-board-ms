<template>
  <div>
    <template v-if="variant === 'intro'">
      <div class="intro-pass-kicker">{{ kicker }}</div>
      <div v-if="showTitleBanner && bannerTitle" class="criterion-banner mt-2 mb-3">
        <div class="criterion-label">{{ bannerLabel }}</div>
        <div class="criterion-title">{{ bannerTitle }}</div>
        <div v-if="details.description" class="text-body-2 text-medium-emphasis mt-2" style="font-weight:500">
          {{ details.description }}
        </div>
      </div>
      <div class="batch-mode-header" :class="{ criteria: isCriteria }">
        <div class="d-flex align-start justify-space-between ga-2">
          <div class="flex-grow-1">
            <div class="mode-title">{{ question }}</div>
          </div>
          <v-btn
            v-if="showInfo"
            icon
            variant="text"
            size="small"
            aria-label="Factor details"
            @click="detailsOpen = true"
          >
            <i class="fa-solid fa-circle-info" />
          </v-btn>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="batch-mode-header" :class="{ criteria: isCriteria }">
        <div class="d-flex align-start justify-space-between ga-2">
          <div class="flex-grow-1">
            <div class="mode-kicker">{{ kicker }}</div>
            <div class="mode-title">{{ question }}</div>
          </div>
          <v-btn
            v-if="showInfo"
            icon
            variant="text"
            size="small"
            aria-label="Factor details"
            @click="detailsOpen = true"
          >
            <i class="fa-solid fa-circle-info" />
          </v-btn>
        </div>
      </div>
      <div v-if="showTitleBanner && bannerTitle" class="criterion-banner mt-2 mb-4">
        <div class="criterion-label">{{ bannerLabel }}</div>
        <div class="criterion-title">{{ bannerTitle }}</div>
      </div>
    </template>
    <v-dialog v-model="detailsOpen" max-width="480">
      <v-card class="pc-dialog-card">
        <v-card-title class="text-h6 font-weight-bold pt-5 px-6">{{ details.title }}</v-card-title>
        <v-card-text v-if="details.description" class="px-6 pb-2">{{ details.description }}</v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="detailsOpen = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type { CompareCriterion } from '~/utils/comparePrompt'
import {
  factorDetailsCopy,
  hasCustomComparisonQuestion,
  optionCompareQuestion,
  optionCompareTitle,
} from '~/utils/comparePrompt'

const props = defineProps<{
  isCriteria: boolean
  passIndex: number
  criterion?: CompareCriterion
  criterionId?: number | null
  variant: 'intro' | 'pair'
}>()

const detailsOpen = ref(false)

const kicker = computed(() => {
  const kind = props.isCriteria ? 'Factor priorities' : 'Option comparisons'
  return `${kind} · Pass ${props.passIndex}`
})

const question = computed(() => {
  if (props.isCriteria) return 'Which factor matters more?'
  return optionCompareQuestion(props.criterion)
})

const bannerTitle = computed(() => {
  if (props.isCriteria) return props.variant === 'intro' ? 'Factor priorities' : ''
  return optionCompareTitle(props.criterion, props.criterionId)
})

const showTitleBanner = computed(() => {
  if (props.isCriteria) return props.variant === 'intro'
  if (!bannerTitle.value) return false
  if (props.variant === 'intro') return true
  return !hasCustomComparisonQuestion(props.criterion)
})

const bannerLabel = computed(() => (props.isCriteria ? 'Next focus' : 'Consider'))
const showInfo = computed(() => !props.isCriteria)
const details = computed(() => factorDetailsCopy(props.criterion, props.criterionId))
</script>
