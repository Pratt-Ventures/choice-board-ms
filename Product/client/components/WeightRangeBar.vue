<template>
  <span class="weight-range-bar" :class="`weight-range-bar--${density}`" :title="TOOLTIP_TEXT">
    <template v-if="model">
      <span class="d-sr-only">{{ srText }}</span>
      <span class="weight-range-bar__viz" aria-hidden="true">
        <span class="weight-range-bar__axis" />
        <span
          v-for="(tick, i) in model.ticks"
          :key="`tick-${i}`"
          class="weight-range-bar__tick"
          :style="{ left: `${tick.offset}%` }"
        />
        <span class="weight-range-bar__band" :style="bandStyle" />
        <span class="weight-range-bar__peak" :style="{ left: `${model.peakOffset}%` }" />
        <template v-if="showTickLabels">
          <span
            v-for="(tick, i) in model.ticks"
            :key="`label-${i}`"
            class="weight-range-bar__tick-label"
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
  buildWeightRangeBar,
  weightRangeGradient,
  type WeightRangeBarModel,
} from '~/utils/weightRangeBar'
import { formatNullablePercent, formatWeightCi } from '~/utils/ranking'

export interface WeightRangeBarProps {
  weight?: number | null
  weightCi95?: Array<number> | null
  weightSd?: number | null
  /** compact hides numeric labels for dense list rows; comfortable shows them. */
  density?: 'compact' | 'comfortable'
}

const props = withDefaults(defineProps<WeightRangeBarProps>(), {
  weight: null,
  weightCi95: null,
  weightSd: null,
  density: 'compact',
})

const TOOLTIP_TEXT = 'visually shows the likely importance range of this factor'

const model = computed<WeightRangeBarModel | null>(() =>
  buildWeightRangeBar({
    weight: props.weight,
    weightSd: props.weightSd,
    weightCi95: props.weightCi95,
  }),
)

const bandStyle = computed(() => {
  if (!model.value) return {}
  return {
    left: `${model.value.bandStart}%`,
    width: `${Math.max(0, model.value.bandEnd - model.value.bandStart)}%`,
    background: weightRangeGradient(model.value.stops),
  }
})

const showTickLabels = computed(() =>
  props.density === 'comfortable' && (model.value?.ticks.some(t => t.label != null) ?? false),
)

const srText = computed(() => {
  const parts: string[] = []
  const ci = formatWeightCi(props.weightCi95)
  if (ci) parts.push(ci)
  const w = formatNullablePercent(props.weight)
  if (w !== '—') parts.push(`expected ${w}`)
  return parts.length ? `Likely importance range: ${parts.join(', ')}` : 'Likely importance range unavailable'
})
</script>

<style scoped>
.weight-range-bar {
  display: inline-flex;
  align-items: center;
}
.weight-range-bar__viz {
  position: relative;
  display: inline-block;
  width: 130px;
  max-width: 42vw;
}
.weight-range-bar--compact .weight-range-bar__viz {
  height: 10px;
}
.weight-range-bar--comfortable .weight-range-bar__viz {
  height: 16px;
}
.weight-range-bar__axis {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  transform: translateY(-50%);
  background: rgba(var(--v-theme-on-surface), 0.18);
}
.weight-range-bar__tick {
  position: absolute;
  top: 50%;
  width: 1px;
  height: 6px;
  transform: translate(-50%, -50%);
  background: rgba(var(--v-theme-on-surface), 0.3);
}
.weight-range-bar__band {
  position: absolute;
  top: 0;
  bottom: auto;
  height: 100%;
  border-radius: 5px;
}
.weight-range-bar--comfortable .weight-range-bar__band {
  border-radius: 7px;
}
.weight-range-bar__peak {
  position: absolute;
  top: 50%;
  width: 2px;
  height: calc(100% + 2px);
  transform: translate(-50%, -50%);
  background: rgb(94, 53, 177);
  border-radius: 1px;
}
.weight-range-bar__tick-label {
  position: absolute;
  top: 100%;
  transform: translateX(-50%);
  margin-top: 2px;
  font-size: 9px;
  line-height: 1.2;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
@media (max-width: 480px) {
  .weight-range-bar__viz {
    width: 110px;
  }
}
</style>
