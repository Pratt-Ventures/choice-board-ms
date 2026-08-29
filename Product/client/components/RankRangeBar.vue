<template>
  <span class="rank-range-bar" :class="`rank-range-bar--${density}`" :title="TOOLTIP_TEXT">
    <template v-if="model">
      <span class="d-sr-only">{{ srText }}</span>
      <span class="rank-range-bar__viz" aria-hidden="true">
        <span class="rank-range-bar__axis" />
        <span
          v-for="(tick, i) in model.ticks"
          :key="`tick-${i}`"
          class="rank-range-bar__tick"
          :style="{ left: `${tick.offset}%` }"
        />
        <span class="rank-range-bar__band" :style="bandStyle" />
        <span class="rank-range-bar__peak" :style="{ left: `${model.peakOffset}%` }" />
        <template v-if="showTickLabels">
          <span
            v-for="(tick, i) in model.ticks"
            :key="`label-${i}`"
            class="rank-range-bar__tick-label"
            :style="{ left: `${tick.offset}%` }"
          >{{ tick.label }}</span>
        </template>
      </span>
    </template>
    <template v-else>
      <slot name="fallback" />
    </template>
  </span>
</template>

<script setup lang="ts">
import {
  buildRankRangeBar,
  rankRangeGradient,
  type RankRangeBarModel,
} from '~/utils/rankRangeBar'
import { formatExpectedRank, formatRankCi } from '~/utils/ranking'

export interface RankRangeBarProps {
  expectedRank?: number | null
  rankSd?: number | null
  rankCi95?: Array<number> | null
  itemCount?: number | null
  /** compact hides numeric labels for dense list rows; comfortable shows them. */
  density?: 'compact' | 'comfortable'
}

const props = withDefaults(defineProps<RankRangeBarProps>(), {
  expectedRank: null,
  rankSd: null,
  rankCi95: null,
  itemCount: 0,
  density: 'compact',
})

const TOOLTIP_TEXT = 'visually shows the likely rank range of this item'

const model = computed<RankRangeBarModel | null>(() =>
  buildRankRangeBar({
    expectedRank: props.expectedRank,
    rankSd: props.rankSd,
    rankCi95: props.rankCi95,
    itemCount: Number(props.itemCount || 0),
  }),
)

const bandStyle = computed(() => {
  if (!model.value) return {}
  return {
    left: `${model.value.bandStart}%`,
    width: `${Math.max(0, model.value.bandEnd - model.value.bandStart)}%`,
    background: rankRangeGradient(model.value.stops),
  }
})

const showTickLabels = computed(() =>
  props.density === 'comfortable' && (model.value?.ticks.some(t => t.label != null) ?? false),
)

const srText = computed(() => {
  const parts: string[] = []
  const ci = formatRankCi(props.rankCi95)
  if (ci) parts.push(ci)
  const expected = formatExpectedRank(props.expectedRank)
  if (expected) parts.push(`expected ${expected}`)
  return parts.length ? `Likely rank range: ${parts.join(', ')}` : 'Likely rank range unavailable'
})
</script>

<style scoped>
.rank-range-bar {
  display: inline-flex;
  align-items: center;
}
.rank-range-bar__viz {
  position: relative;
  display: inline-block;
  width: 130px;
  max-width: 42vw;
}
.rank-range-bar--compact .rank-range-bar__viz {
  height: 10px;
}
.rank-range-bar--comfortable .rank-range-bar__viz {
  height: 16px;
}
.rank-range-bar__axis {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  transform: translateY(-50%);
  background: rgba(var(--v-theme-on-surface), 0.18);
}
.rank-range-bar__tick {
  position: absolute;
  top: 50%;
  width: 1px;
  height: 6px;
  transform: translate(-50%, -50%);
  background: rgba(var(--v-theme-on-surface), 0.3);
}
.rank-range-bar__band {
  position: absolute;
  top: 0;
  bottom: auto;
  height: 100%;
  border-radius: 5px;
}
.rank-range-bar--comfortable .rank-range-bar__band {
  border-radius: 7px;
}
.rank-range-bar__peak {
  position: absolute;
  top: 50%;
  width: 2px;
  height: calc(100% + 2px);
  transform: translate(-50%, -50%);
  background: rgb(var(--pc-primary-rgb));
  border-radius: 1px;
}
.rank-range-bar__tick-label {
  position: absolute;
  top: 100%;
  transform: translateX(-50%);
  margin-top: 2px;
  font-size: 9px;
  line-height: 1.2;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
@media (max-width: 480px) {
  .rank-range-bar__viz {
    width: 110px;
  }
}
</style>
