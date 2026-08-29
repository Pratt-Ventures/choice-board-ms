<template>
  <div class="chart-wrap">
    <canvas ref="canvasEl" />
  </div>
</template>

<script setup lang="ts">
import {
  Chart,
  Filler,
  LineController,
  LineElement,
  LinearScale,
  CategoryScale,
  PointElement,
  Tooltip,
  type ChartConfiguration,
} from 'chart.js'
import type { ProbeDayBucket } from '~/types/api'

Chart.register(LineController, LineElement, LinearScale, CategoryScale, PointElement, Filler, Tooltip)

const props = defineProps<{
  series: ProbeDayBucket[]
}>()

const canvasEl = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

function build() {
  if (!canvasEl.value) return
  chart?.destroy()
  const labels = props.series.map((b) => {
    const d = new Date(b.day)
    return Number.isNaN(d.getTime())
      ? String(b.day)
      : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })
  const vals = props.series.map(b => b.count)
  const ctx = canvasEl.value.getContext('2d')
  const grad = ctx?.createLinearGradient(0, 0, 0, 280)
  grad?.addColorStop(0, 'rgba(99,91,255,.28)')
  grad?.addColorStop(1, 'rgba(99,91,255,0)')

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: vals,
        borderColor: '#635BFF',
        backgroundColor: grad || 'rgba(99,91,255,.15)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4,
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { color: '#64748B', maxTicksLimit: 7, font: { size: 11 } },
        },
        y: {
          grid: { color: 'rgba(10,37,64,.08)' },
          border: { display: false },
          ticks: {
            color: '#64748B',
            font: { size: 11 },
            callback: (v) => {
              const n = Number(v)
              return n >= 1000 ? `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k` : String(n)
            },
          },
        },
      },
    },
  }
  chart = new Chart(canvasEl.value, config)
}

watch(() => props.series, () => nextTick(build), { deep: true })
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
