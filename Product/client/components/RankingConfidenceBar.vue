<template>
  <div
    class="ranking-confidence"
    role="meter"
    :aria-valuemin="0"
    :aria-valuemax="100"
    :aria-valuenow="confidence.pct"
    :aria-valuetext="confidence.label"
    :aria-label="`Current ranking confidence, ${confidence.label}`"
  >
    <div class="ranking-confidence__head">
      <span class="ranking-confidence__caption">Current ranking confidence</span>
      <strong class="ranking-confidence__level" :style="{ color: confidence.color }">{{ confidence.label }}</strong>
    </div>
    <div class="ranking-confidence__track">
      <div
        class="ranking-confidence__fill"
        :style="{ width: `${confidence.pct}%`, background: confidence.color }"
      />
    </div>
    <div class="ranking-confidence__ticks" aria-hidden="true">
      <span>None</span>
      <span>Strong</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { RankingConfidence } from '~/utils/rankingConfidence'
import { emptyRankingConfidence } from '~/utils/rankingConfidence'

withDefaults(defineProps<{
  confidence?: RankingConfidence
}>(), {
  confidence: () => emptyRankingConfidence(),
})
</script>

<style scoped>
.ranking-confidence {
  padding: 10px 2px 2px;
}
.ranking-confidence__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.ranking-confidence__caption {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pc-muted);
}
.ranking-confidence__level {
  font-family: Manrope, Inter, sans-serif;
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.ranking-confidence__track {
  height: 11px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pc-border) 82%, var(--pc-ink) 18%);
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.12);
}
.ranking-confidence__fill {
  height: 100%;
  border-radius: inherit;
  min-width: 0;
  transition: width var(--pc-motion) ease, background-color var(--pc-motion) ease;
}
.ranking-confidence__ticks {
  display: flex;
  justify-content: space-between;
  margin-top: 5px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pc-muted);
}
@media (prefers-reduced-motion: reduce) {
  .ranking-confidence__fill {
    transition: none;
  }
}
</style>
