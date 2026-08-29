<template>
  <div class="chart-wrap d-flex align-center justify-center">
    <canvas ref="canvasEl" />
  </div>
</template>

<script setup lang="ts">
import {
  Chart,
  ArcElement,
  DoughnutController,
  Legend,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js'

Chart.register(DoughnutController, ArcElement, Legend, Tooltip)

const COLORS = ['#635BFF', '#00A3C4', '#F59E0B', '#94A3B8', '#22C55E', '#EF4444', '#8B85FF', '#38BDF8']

const props = withDefaults(defineProps<{
  labels: string[]
  values: number[]
  emptyLabel?: string
}>(), {
  emptyLabel: 'No data',
})

const canvasEl = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function build() {
  if (!canvasEl.value) return
  chart?.destroy()
  const hasData = props.values.some(v => v > 0)
  const labels = hasData ? props.labels : [props.emptyLabel]
  const data = hasData ? props.values : [1]
  const colors = hasData ? props.labels.map((_, i) => COLORS[i % COLORS.length]) : ['#E2E8F0']

  const config: ChartConfiguration<'doughnut'> = {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderWidth: 0,
        hoverOffset: hasData ? 6 : 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#64748B',
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 8,
            font: { size: 11 },
          },
        },
        tooltip: { enabled: hasData },
      },
    },
  }
  chart = new Chart(canvasEl.value, config)
}

watch(() => [props.labels, props.values], () => nextTick(build), { deep: true })
onMounted(() => nextTick(build))
onBeforeUnmount(() => {
  chart?.destroy()
  chart = null
})
</script>

<style scoped>
.chart-wrap {
  height: 280px;
  position: relative;
}
</style>
