<template>
  <div>
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
    <template v-else-if="project">
      <div class="page-head">
        <div>
          <div class="eyebrow">Results</div>
          <div class="page-title">{{ project.project_title || project.project_tag }}</div>
          <div class="page-subtitle">A clear outcome with supporting detail and visible limitations.</div>
          <v-alert
            v-if="project.private_participation"
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            Private participation is on. Individual names are hidden; people appear as unique participant 1, 2, … in this view.
          </v-alert>
        </div>
        <div class="head-actions">
          <v-btn color="primary" variant="tonal" :to="`/projects/${project.id}/probe`">
            <i class="fa-solid fa-check-to-slot mr-2" /> Continue comparing
          </v-btn>
          <v-btn variant="outlined" :to="`/projects/${project.id}/shares`">
            <i class="fa-solid fa-share-nodes mr-2" /> Share
          </v-btn>
          <v-btn
            v-if="canRunAiAgents"
            variant="tonal"
            color="primary"
            :loading="runningAi"
            @click="runAiBaseline"
          >
            <i class="fa-solid fa-robot mr-2" /> Run AI agents
          </v-btn>
        </div>
      </div>

      <v-card v-if="hasAgentAnalysis" class="glass-card mb-5">
        <v-card-text class="pa-5 d-flex flex-wrap align-center justify-space-between ga-3">
          <div>
            <div class="text-caption text-medium-emphasis">Analyze</div>
            <div class="text-body-2">Choose whose comparisons to include in this Results view.</div>
          </div>
          <v-btn-toggle v-model="analysisMode" mandatory color="primary" divided>
            <v-btn value="human">Human only</v-btn>
            <v-btn value="agents">Agents only</v-btn>
            <v-btn value="combined">Combined</v-btn>
          </v-btn-toggle>
        </v-card-text>
      </v-card>

      <v-card v-if="displayRankings.length" class="glass-card result-hero mb-5">
        <v-card-text class="pa-6 pa-md-8">
                  <v-row align="center">
            <v-col cols="12">
              <span
                :class="['status', metrics.completion >= 95 ? 'status-results' : 'status-collecting']"
              >
                {{ metrics.completion >= 95 ? 'Final result' : 'Preliminary result' }}
              </span>
              <div class="eyebrow mt-4">{{ heroHeadline }}</div>
              <div class="text-h3 font-weight-bold mt-2" style="font-family:Manrope,Inter,sans-serif;letter-spacing:-.03em">
                {{ displayRankings[0].title }}
              </div>
              <div v-if="leaderBasisLabel" class="leader-basis mt-2">{{ leaderBasisLabel }}</div>
              <div class="text-body-1 text-medium-emphasis mt-2">{{ summaryText }}</div>
              <div
                v-if="polarizingCaption(displayRankings[0])"
                class="text-caption text-medium-emphasis mt-2"
              >
                {{ polarizingCaption(displayRankings[0]) }}
              </div>
              <div class="d-flex flex-wrap ga-2 mt-4">
                <span class="factor-tag">{{ resultViewLabel }}</span>
                <span class="factor-tag">{{ influenceModeLabel }}</span>
                <span class="factor-tag">Score {{ formatPercent(displayRankings[0].score) }}</span>
                <span v-if="displayRankings.length > 1" class="factor-tag">Lead {{ leaderGap }} pts</span>
                <span class="factor-tag">{{ uniqueParticipants }} participants</span>
                <span class="factor-tag">{{ comparisonCount }} comparisons</span>
              </div>
              <div v-if="displayRankings.length" class="overall-violin-row text-caption text-medium-emphasis">
                <span class="violin-label">Rank</span>
                <RankRangeBar
                  :expected-rank="displayRankings[0].expected_rank"
                  :rank-sd="displayRankings[0].rank_sd"
                  :rank-ci95="displayRankings[0].rank_ci95"
                  :item-count="displayRankings.length"
                  density="comfortable"
                >
                  <template #fallback>
                    <template v-if="formatRankCi(displayRankings[0].rank_ci95)">{{ formatRankCi(displayRankings[0].rank_ci95) }}</template>
                    <template v-else-if="formatExpectedRank(displayRankings[0].expected_rank)">
                      expected rank {{ formatExpectedRank(displayRankings[0].expected_rank) }}
                    </template>
                    <template v-else>
                      Mean rank {{ displayRankings[0].mean_rank != null ? Number(displayRankings[0].mean_rank).toFixed(2) : '—' }}
                    </template>
                  </template>
                </RankRangeBar>
                <template v-if="optionChanceCaption(displayRankings[0], rankingMode, reportTopN)">
                  {{ optionChanceCaption(displayRankings[0], rankingMode, reportTopN) }}
                </template>
              </div>
              <template v-if="sortedFactorRankings.length">
                <div class="overall-violin-row text-caption text-medium-emphasis" style="margin-top: 10px">
                  <span class="violin-label">Top factor — Rank</span>
                  <RankRangeBar
                    :expected-rank="sortedFactorRankings[0].expected_rank"
                    :rank-sd="sortedFactorRankings[0].rank_sd"
                    :rank-ci95="sortedFactorRankings[0].rank_ci95"
                    :item-count="sortedFactorRankings.length"
                    density="comfortable"
                  >
                    <template #fallback>
                      <span v-if="formatRankCi(sortedFactorRankings[0].rank_ci95)">{{ formatRankCi(sortedFactorRankings[0].rank_ci95) }}</span>
                      <span v-else-if="formatExpectedRank(sortedFactorRankings[0].expected_rank)">expected rank {{ formatExpectedRank(sortedFactorRankings[0].expected_rank) }}</span>
                      <span v-else>Rank 1 · {{ sortedFactorRankings[0].title }}</span>
                    </template>
                  </RankRangeBar>
                </div>
                <div class="overall-violin-row text-caption text-medium-emphasis" style="margin-top: 10px">
                  <span class="violin-label">Importance</span>
                  <WeightRangeBar
                    :weight="sortedFactorRankings[0].normalizedWeight ?? sortedFactorRankings[0].weight ?? sortedFactorRankings[0].score"
                    :weight-ci95="sortedFactorRankings[0].weight_ci95"
                    density="comfortable"
                  >
                    <template #fallback>
                      <span>
                        Importance {{ formatNullablePercent(sortedFactorRankings[0].normalizedWeight ?? sortedFactorRankings[0].weight ?? sortedFactorRankings[0].score) }}
                        <template v-if="formatWeightCi(sortedFactorRankings[0].weight_ci95)">
                          ({{ formatWeightCi(sortedFactorRankings[0].weight_ci95) }})
                        </template>
                      </span>
                    </template>
                  </WeightRangeBar>
                </div>
              </template>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-row dense class="mb-5">
        <v-col v-for="chip in insightChips" :key="`card-${chip.key}`" cols="12" :sm="insightChips.length === 2 ? 6 : 4">
          <v-card class="glass-card h-100"><v-card-text class="pa-5">
            <div class="text-caption text-medium-emphasis">{{ chip.label }}</div>
            <div class="text-h3 font-weight-bold">{{ chip.display }}</div>
            <div class="text-caption text-medium-emphasis mt-1">{{ chip.caption }}</div>
          </v-card-text></v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" lg="7">
          <v-card class="glass-card">
            <v-card-text class="pa-5 pa-md-6">
              <div class="d-flex flex-wrap justify-space-between ga-3 align-center mb-5">
                <div>
                  <div class="text-h6 font-weight-bold" style="font-family:Manrope,Inter,sans-serif">Overall ranking</div>
                  <div class="text-caption text-medium-emphasis">{{ resultViewExplanation }}</div>
                </div>
                <v-select
                  v-model="resultWeighting"
                  :items="resultViewOptions"
                  item-title="title"
                  item-value="value"
                  label="View results by"
                  density="compact"
                  hide-details
                  style="max-width:280px"
                />
              </div>
              <div v-if="displayRankings.length" class="d-flex flex-column ga-3">
                <div v-for="(item, index) in displayRankings" :key="item.id" class="rank-row">
                  <div class="d-flex align-center ga-3">
                    <div class="rank-number">{{ index + 1 }}</div>
                    <div class="flex-grow-1">
                      <div class="d-flex justify-space-between ga-3">
                        <strong>{{ item.title }}</strong>
                        <span class="font-weight-bold">{{ formatPercent(item.score) }}</span>
                      </div>
                      <v-progress-linear :model-value="scoreBarPercent(item.score)" height="8" rounded color="primary" class="mt-2" />
                      <div class="text-caption text-medium-emphasis mt-2 personal-rank-caption">
                        <RankRangeBar
                          :expected-rank="item.expected_rank"
                          :rank-sd="item.rank_sd"
                          :rank-ci95="item.rank_ci95"
                          :item-count="displayRankings.length"
                          density="comfortable"
                        >
                          <template #fallback>
                            <template v-if="formatRankCi(item.rank_ci95)">{{ formatRankCi(item.rank_ci95) }}</template>
                            <template v-else-if="formatExpectedRank(item.expected_rank)">
                              expected rank {{ formatExpectedRank(item.expected_rank) }}
                            </template>
                            <template v-else>
                              Mean rank {{ item.mean_rank != null ? Number(item.mean_rank).toFixed(2) : '—' }}
                            </template>
                            <template v-if="rankingMode === 'rank_all' && formatExpectedRank(item.expected_rank) && formatRankCi(item.rank_ci95)">
                              · expected {{ formatExpectedRank(item.expected_rank) }}
                            </template>
                          </template>
                        </RankRangeBar>
                        <template v-if="optionChanceCaption(item, rankingMode, reportTopN)">
                          {{ optionChanceCaption(item, rankingMode, reportTopN) }}
                        </template>
                        <span>· {{ item.data_points ?? item.evidence ?? 0 }} groups</span>
                      </div>
                      <div
                        v-if="polarizingCaption(item)"
                        class="text-caption mt-1"
                      >
                        {{ polarizingCaption(item) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="empty-state py-10">
                <div class="font-weight-bold">Start comparisons to establish a ranking</div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="factorRankings.length > 1" class="glass-card mt-5">
            <v-card-text class="pa-5 pa-md-6">
              <div class="d-flex flex-wrap justify-space-between ga-3 align-center mb-3">
                <div>
                  <div class="text-h6 font-weight-bold">What matters most</div>
                  <div class="text-caption text-medium-emphasis">
                    Importance is how much the factor matters. Differentiation is how much it separates options. Decision leverage is which factors actually move the outcome.
                  </div>
                </div>
                <v-btn-toggle v-model="factorSortKey" mandatory density="compact" color="primary" variant="outlined" divided>
                  <v-btn value="rank" size="small">Rank</v-btn>
                  <v-btn value="importance" size="small">Importance</v-btn>
                  <v-btn value="discrimination" size="small">Differentiation</v-btn>
                  <v-btn value="leverage" size="small">Leverage</v-btn>
                </v-btn-toggle>
              </div>
              <div v-for="(criterion, index) in sortedFactorRankings" :key="criterion.id" class="rank-row mb-3">
                <div class="d-flex align-center ga-3">
                  <div class="rank-number">{{ index + 1 }}</div>
                  <div class="flex-grow-1">
                    <div class="d-flex justify-space-between ga-3">
                      <strong>{{ criterion.title }}</strong>
                      <span class="font-weight-bold">{{ formatNullablePercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score) }}</span>
                    </div>
                    <v-progress-linear
                      :model-value="scoreBarPercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score ?? 0)"
                      height="8"
                      rounded
                      color="deep-purple"
                      class="mt-2"
                    />
                    <div class="text-caption text-medium-emphasis mt-2 factor-violin-row">
                      <span class="violin-label">Rank</span>
                      <RankRangeBar
                        :expected-rank="criterion.expected_rank"
                        :rank-sd="criterion.rank_sd"
                        :rank-ci95="criterion.rank_ci95"
                        :item-count="sortedFactorRankings.length"
                        density="comfortable"
                      >
                        <template #fallback>
                          <span v-if="formatRankCi(criterion.rank_ci95)">{{ formatRankCi(criterion.rank_ci95) }}</span>
                          <span v-else-if="formatExpectedRank(criterion.expected_rank)">expected rank {{ formatExpectedRank(criterion.expected_rank) }}</span>
                          <span v-else>Rank {{ criterion.rank ?? index + 1 }}</span>
                        </template>
                      </RankRangeBar>
                    </div>
                    <div class="text-caption text-medium-emphasis mt-1 factor-violin-row">
                      <span class="violin-label">Importance</span>
                      <WeightRangeBar
                        :weight="criterion.normalizedWeight ?? criterion.weight ?? criterion.score"
                        :weight-ci95="criterion.weight_ci95"
                        density="comfortable"
                      >
                        <template #fallback>
                          <span>
                            Importance {{ formatNullablePercent(criterion.normalizedWeight ?? criterion.weight ?? criterion.score) }}
                            <template v-if="formatWeightCi(criterion.weight_ci95)">
                              ({{ formatWeightCi(criterion.weight_ci95) }})
                            </template>
                          </span>
                        </template>
                      </WeightRangeBar>
                    </div>
                    <div class="d-flex flex-wrap ga-4 text-caption text-medium-emphasis mt-2">
                      <span>Differentiation {{ formatNullablePercent(criterion.discrimination) }}</span>
                      <span>Decision leverage {{ formatNullablePercent(criterion.leverage) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="analysisMode === 'combined' && optionAgentComparison.length" class="glass-card mt-5">
            <v-card-text class="pa-5 pa-md-6">
              <div class="text-h6 font-weight-bold mb-1">Agents vs humans — option ranking</div>
              <div class="text-caption text-medium-emphasis mb-4">
                Rank delta is human rank minus agent rank. Positive means agents ranked the option higher.
              </div>
              <div v-for="row in optionAgentComparison" :key="`cmp-opt-${row.id}`" class="rank-row mb-2">
                <div class="d-flex justify-space-between ga-3">
                  <strong>{{ row.title }}</strong>
                  <span class="text-caption">
                    Human {{ row.human_rank ?? '—' }} · Agent {{ row.agent_rank ?? '—' }}
                    <template v-if="row.rank_delta != null"> · Δ {{ row.rank_delta > 0 ? '+' : '' }}{{ row.rank_delta }}</template>
                  </span>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="analysisMode === 'combined' && factorAgentComparison.length" class="glass-card mt-5">
            <v-card-text class="pa-5 pa-md-6">
              <div class="text-h6 font-weight-bold mb-1">Agents vs humans — factor ranking</div>
              <div class="text-caption text-medium-emphasis mb-4">
                How AI agents ordered factors compared with human participants.
              </div>
              <div v-for="row in factorAgentComparison" :key="`cmp-fac-${row.id}`" class="rank-row mb-2">
                <div class="d-flex justify-space-between ga-3">
                  <strong>{{ row.title }}</strong>
                  <span class="text-caption">
                    Human {{ row.human_rank ?? '—' }} · Agent {{ row.agent_rank ?? '—' }}
                    <template v-if="row.rank_delta != null"> · Δ {{ row.rank_delta > 0 ? '+' : '' }}{{ row.rank_delta }}</template>
                  </span>
                </div>
              </div>
            </v-card-text>
          </v-card>

          <v-card v-if="perCriterionLeaders.length" class="glass-card mt-5">
            <v-card-text class="pa-5">
              <div class="text-h6 font-weight-bold mb-1">Best option by factor</div>
              <div class="text-caption text-medium-emphasis mb-4">
                Mean rank across passes under each factor (0 = best). Multi-pass averages can crown a compromise leader.
              </div>
              <div v-for="row in perCriterionLeaders" :key="row.criterion.id" class="factor-leader-row">
                <div><div class="text-caption text-medium-emphasis">Factor</div><strong>{{ row.criterion.title }}</strong></div>
                <div><div class="text-caption text-medium-emphasis">Top option</div><strong>{{ row.leaderTitle }}</strong></div>
                <div>
                  <div class="font-weight-bold">{{ formatPercent(row.score) }}</div>
                  <div class="text-caption">mean rank {{ row.mean_rank != null ? Number(row.mean_rank).toFixed(2) : '—' }}</div>
                </div>
                <div class="text-caption">
                  {{ row.evidence }} groups
                  <template v-if="row.pass_consistency != null">
                    <br>pass {{ asMetricPercent(row.pass_consistency) }}%
                  </template>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" lg="5">
          <v-card class="glass-card">
            <v-card-text class="pa-5">
              <div class="text-h6 font-weight-bold mb-1">Participants</div>
              <div class="text-caption text-medium-emphasis mb-4">
                {{ uniqueParticipants }} participants · click a row to expand individual ranking
              </div>
              <div v-if="participantRows.length" class="d-flex flex-column ga-1">
                <div
                  v-for="p in participantRows"
                  :key="p.id"
                  class="participant-row pa-2"
                  :class="{ 'is-selected': selectedParticipant?.id === p.id }"
                  @click="selectParticipant(p.id)"
                >
                  <div class="d-flex align-center justify-space-between ga-3">
                    <div class="min-w-0">
                      <div class="font-weight-medium text-truncate">
                        {{ p.display_name || p.email || `Participant ${p.id}` }}
                        <v-chip v-if="p.is_ai || p.source === 'ai'" size="x-small" class="ml-2" color="primary" variant="tonal">AI</v-chip>
                      </div>
                      <div class="text-caption text-medium-emphasis">{{ participantSubtitle(p) }}</div>
                    </div>
                    <div class="d-flex flex-column align-end ga-1 flex-shrink-0">
                      <v-chip size="x-small" variant="tonal">{{ p.leaderTitle || '—' }}</v-chip>
                      <span v-if="p.coherence != null" class="text-caption text-medium-emphasis">
                        align {{ formatCoherence(p.coherence) }}
                      </span>
                    </div>
                  </div>
                  <v-expand-transition>
                    <div v-if="selectedParticipant?.id === p.id" class="participant-detail-panel" @click.stop>
                      <div class="d-flex justify-space-between align-center mb-3">
                        <div class="text-subtitle-2 font-weight-bold">Individual ranking</div>
                        <v-btn icon variant="text" size="x-small" @click.stop="selectedParticipant = null">
                          <i class="fa-solid fa-xmark" />
                        </v-btn>
                      </div>
                      <div v-if="selectedRanking.length">
                        <div v-for="(item, index) in selectedRanking" :key="item.id" class="rank-row mb-2">
                          <div class="d-flex align-center ga-3">
                            <div class="rank-number">{{ index + 1 }}</div>
                            <div class="flex-grow-1 d-flex justify-space-between">
                              <strong>{{ item.title }}</strong>
                              <span>{{ formatPercent(item.score) }}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-caption text-medium-emphasis">No ranking available for this participant.</div>
                    </div>
                  </v-expand-transition>
                </div>
              </div>
              <div v-else class="text-medium-emphasis">No comparisons recorded yet.</div>
            </v-card-text>
          </v-card>

          <v-card class="glass-card mt-5">
            <v-card-text class="pa-5">
              <div class="d-flex flex-wrap justify-space-between ga-3 align-center mb-2">
                <div>
                  <div class="text-h6 font-weight-bold">Leader concentration</div>
                  <div class="text-caption text-medium-emphasis">
                    How often each option is a participant's #1 (ties share #1) · {{ leaderConcentrationExplanation }}
                  </div>
                </div>
                <v-select
                  v-model="leaderWeighting"
                  :items="resultViewOptions"
                  item-title="title"
                  item-value="value"
                  label="View #1s by"
                  density="compact"
                  hide-details
                  style="max-width:280px"
                />
              </div>
              <div v-for="row in leaderConcentrationRows" :key="row.id" class="mb-3">
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span>{{ row.title }}</span>
                  <strong>
                    {{ row.count }}
                    <span v-if="leaderConcentrationParticipants" class="text-medium-emphasis font-weight-regular">
                      / {{ leaderConcentrationParticipants }}
                    </span>
                  </strong>
                </div>
                <v-progress-linear
                  :model-value="leaderConcentrationParticipants ? (row.count / leaderConcentrationParticipants) * 100 : 0"
                  height="8"
                  rounded
                  color="secondary"
                />
              </div>
              <div v-if="!leaderConcentrationRows.length" class="text-medium-emphasis text-caption">
                No participant leaders yet.
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-card v-if="showPivot" class="glass-card mt-5">
        <v-card-text class="pa-5 pa-md-6">
          <div class="d-flex flex-wrap justify-space-between ga-3 align-start mb-4">
            <div>
              <div class="text-h6 font-weight-bold">Explore by axis</div>
              <div class="text-caption text-medium-emphasis">
                Choose a primary axis, optionally filter the others, sort, then select a row for supporting detail.
                Alignment uses {{ coherenceMethodLabel }}. Filters reshape this table and the detail panel.
              </div>
              <div v-if="pivotFiltersActive" class="d-flex flex-wrap ga-2 mt-2">
                <v-chip
                  v-for="label in activePivotFilterLabels"
                  :key="label"
                  size="x-small"
                  variant="tonal"
                  color="primary"
                >
                  {{ label }}
                </v-chip>
              </div>
            </div>
          </div>

          <div class="d-flex flex-wrap ga-3 mb-4">
            <v-btn-toggle v-model="pivotAxis" mandatory color="primary" density="comfortable" divided>
              <v-btn value="alternatives">Options</v-btn>
              <v-btn value="factors" :disabled="factorRankings.length <= 1">Factors</v-btn>
              <v-btn value="participants">Participants</v-btn>
            </v-btn-toggle>
            <v-select
              v-if="pivotAxis !== 'alternatives'"
              v-model="filterAlternativeId"
              :items="altFilterItems"
              item-title="title"
              item-value="value"
              label="Filter option"
              density="compact"
              hide-details
              clearable
              style="min-width:180px;max-width:220px"
            />
            <v-select
              v-if="pivotAxis !== 'factors' && factorRankings.length > 1"
              v-model="filterFactorId"
              :items="factorFilterItems"
              item-title="title"
              item-value="value"
              label="Filter factor"
              density="compact"
              hide-details
              clearable
              style="min-width:180px;max-width:220px"
            />
            <v-select
              v-if="pivotAxis !== 'participants'"
              v-model="filterParticipantId"
              :items="participantFilterItems"
              item-title="title"
              item-value="value"
              label="Filter participant"
              density="compact"
              hide-details
              clearable
              style="min-width:180px;max-width:240px"
            />
            <v-select
              v-model="pivotSortKey"
              :items="pivotSortOptions"
              item-title="title"
              item-value="value"
              label="Sort by"
              density="compact"
              hide-details
              style="min-width:150px;max-width:180px"
            />
          </div>

          <div class="pivot-table-wrap">
            <table class="pivot-table">
              <thead>
                <tr>
                  <th v-for="col in pivotColumns" :key="col.key" @click="setPivotSort(col.key)">
                    {{ col.title }}
                    <span v-if="pivotSortKey === col.key" class="sort-mark">▾</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in sortedPivotRows"
                  :key="row.id"
                  :class="{ selected: selectedPivotRowId === row.id }"
                  @click="selectPivotRow(row)"
                >
                  <td v-for="col in pivotColumns" :key="col.key">
                    {{ formatPivotCell(row, col.key) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!sortedPivotRows.length" class="text-medium-emphasis pa-4">No rows for this view yet.</div>
          </div>

          <div v-if="pivotDetailLoading" class="d-flex align-center ga-3 mt-5">
            <div class="question-group-timer" aria-hidden="true" />
            <span class="text-body-2 text-medium-emphasis">Loading supporting detail…</span>
          </div>

          <div v-else-if="pivotDetail" class="pivot-detail mt-5">
            <div class="d-flex justify-space-between align-center mb-3">
              <div>
                <div class="text-subtitle-1 font-weight-bold">{{ pivotDetail.selected_title || 'Selection' }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ pivotDetail.data_points || 0 }} data points in slice
                  · confidence {{ pivotDetail.metrics?.confidence ?? '—' }}%
                  · stability {{ pivotDetail.metrics?.stability ?? '—' }}%
                </div>
                <div v-if="pivotDetailFilterLabels.length" class="d-flex flex-wrap ga-2 mt-2">
                  <v-chip
                    v-for="label in pivotDetailFilterLabels"
                    :key="label"
                    size="x-small"
                    variant="tonal"
                    color="primary"
                  >
                    {{ label }}
                  </v-chip>
                </div>
              </div>
              <v-btn icon variant="text" size="small" @click="clearPivotDetail"><i class="fa-solid fa-xmark" /></v-btn>
            </div>

            <v-row dense>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis mb-2">Option ranking in slice</div>
                <div
                  v-for="(item, index) in (pivotDetail.option_ranking || []).slice(0, 8)"
                  :key="`opt-${item.id}`"
                  class="rank-row mb-2"
                >
                  <div class="d-flex align-center ga-3">
                    <div class="rank-number">{{ index + 1 }}</div>
                    <div class="flex-grow-1 d-flex justify-space-between">
                      <strong>{{ item.title }}</strong>
                      <span>{{ formatPercent(item.score || 0) }}</span>
                    </div>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-caption text-medium-emphasis mb-2">
                  Participants ({{ (pivotDetail.participants || []).length }})
                </div>
                <div
                  v-for="p in (pivotDetail.participants || []).slice(0, 12)"
                  :key="`pd-${p.id}`"
                  class="rank-row mb-2"
                >
                  <div class="d-flex justify-space-between ga-2">
                    <strong>{{ p.display_name || p.email || `Participant ${p.id}` }}</strong>
                    <span class="text-caption">
                      conf {{ p.confidence ?? '—' }}%
                      <template v-if="p.coherence != null"> · {{ formatCoherence(p.coherence) }}</template>
                    </span>
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    prefers {{ p.leader?.title || '—' }}
                    <template v-if="p.selected_alternative_rank != null">
                      · selected option rank #{{ p.selected_alternative_rank }}
                    </template>
                    · {{ p.data_points || 0 }} pts
                  </div>
                </div>
              </v-col>
            </v-row>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { VoteParticipant } from '~/types/api'
import {
  formatPercent,
  formatNullablePercent,
  formatRankCi,
  formatWeightCi,
  formatExpectedRank,
  scoreBarPercent,
  scoreLeadPoints,
  asMetricPercent,
  effectiveCriteria,
  mapServerRanking,
  normalizeParticipantInfluenceMode,
  normalizeRankingMode,
  headlineOptionLabel,
  optionChanceCaption,
  polarizingCaption,
  insightMetricChips,
  lookupRankMap,
  rankingFromMeanRankMap,
  participantLeaderUnderFactor,
  participantLeadersUnderFactor,
  tiedLeadersFromRanking,
} from '~/utils/ranking'

const route = useRoute()
const snackbar = useSnackbar()
const votes = useVotesApi()
const { isAdmin, aiFeaturesEnabled, requireAdmin } = useAuth()
const runningAi = ref(false)
const ws = useProjectWorkspace()

async function runAiBaseline() {
  if (!requireAdmin() || !project.value) return
  runningAi.value = true
  try {
    const res = await votes.runAiBaseline(project.value.id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    if (res.already_complete) snackbar.success('AI agents have already finished')
    else snackbar.success('AI agents started. Refresh results when they finish.')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not start AI baseline')
  }
  finally {
    runningAi.value = false
  }
}
const {
  project, altItems, factorItems, participants, report,
  loading, settings, loadProject,
} = ws

const analysisMode = ref<'human' | 'agents' | 'combined'>('human')
const canRunAiAgents = computed(() =>
  !!aiFeaturesEnabled.value
  && isAdmin.value
  && !!project.value?.include_ai_agents
  && (project.value?.ai_voter_models || []).length > 0,
)
const hasAgentAnalysis = computed(() => {
  const analysis = report.value?.analysis as Record<string, any> | undefined
  return !!(analysis?.agents || report.value?.ai_baseline?.available)
})
const viewReport = computed(() => {
  const base = report.value || {}
  const analysis = (base as any).analysis as Record<string, any> | undefined
  if (!analysis) return base
  if (analysisMode.value === 'agents' && analysis.agents) return { ...base, ...analysis.agents }
  if (analysisMode.value === 'combined' && analysis.combined) return { ...base, ...analysis.combined }
  if (analysis.human) return { ...base, ...analysis.human }
  return base
})
const optionAgentComparison = computed(() => {
  const analysis = report.value?.analysis as Record<string, any> | undefined
  return (analysis?.comparison?.option_ranking as any[]) || []
})
const factorAgentComparison = computed(() => {
  const analysis = report.value?.analysis as Record<string, any> | undefined
  return (analysis?.comparison?.factor_ranking as any[]) || []
})
const resultWeighting = ref('adjusted')
const leaderWeighting = ref('adjusted')
const selectedParticipant = ref<VoteParticipant | null>(null)
const factorSortKey = ref<'rank' | 'importance' | 'discrimination' | 'leverage'>('rank')

const pivotAxis = ref<'alternatives' | 'factors' | 'participants'>('participants')
const pivotSortKey = ref('rank')
const filterAlternativeId = ref<number | null>(null)
const filterFactorId = ref<number | null>(null)
const filterParticipantId = ref<number | null>(null)
const selectedPivotRowId = ref<number | null>(null)
const pivotDetail = ref<Record<string, any> | null>(null)
const pivotDetailLoading = ref(false)

const influenceModeLabel = computed(() => {
  const mode = normalizeParticipantInfluenceMode(project.value?.participant_influence_mode)
  if (mode === 'balanced') return 'Balanced influence'
  if (mode === 'participants_normalized') return 'Participants normalized'
  return 'Comparisons equal'
})

const metrics = computed(() => {
  const src = viewReport.value as Record<string, any>
  const m = (src?.metrics as Record<string, any>) || src || {}
  return {
    stability: asMetricPercent(m.stability ?? src?.stability),
    confidence: asMetricPercent(m.confidence ?? src?.confidence),
    completion: asMetricPercent(m.completion ?? src?.completion),
    coverage: asMetricPercent(m.coverage ?? 0),
    agreement: asMetricPercent(m.agreement ?? src?.agreement),
    multi_pass: asMetricPercent(m.multi_pass ?? m.inter_group ?? src?.multi_pass ?? 0),
    factor_divergence: asMetricPercent(m.factor_divergence ?? src?.factor_divergence ?? 0),
    inter_group: asMetricPercent(m.inter_group ?? m.multi_pass ?? 0),
    depth: asMetricPercent(m.depth ?? 0),
    stability_basis: String(m.stability_basis ?? src?.stability_basis ?? ''),
  }
})

const comparisonCount = computed(() =>
  Number(viewReport.value?.comparison_count ?? viewReport.value?.total_observations ?? viewReport.value?.observation_count ?? 0),
)

const rankingMode = computed(() =>
  normalizeRankingMode(report.value?.ranking_mode, project.value?.project_exclusive_mode),
)

const reportTopN = computed(() => Number(report.value?.top_n) || 1)

const heroHeadline = computed(() => headlineOptionLabel(rankingMode.value))

const insightChips = computed(() => insightMetricChips(report.value))

const resultViewOptions = computed(() => {
  const criteria = effectiveCriteria(factorItems.value)
  if (criteria.length === 1) return [{ title: criteria[0].title, value: `criterion:${criteria[0].id}` }]
  return [
    { title: 'All factors equally', value: 'equal' },
    { title: 'Weighted by what matters most', value: 'adjusted' },
    ...criteria.map(c => ({ title: c.title, value: `criterion:${c.id}` })),
  ]
})

const displayRankings = computed(() => {
  if (resultWeighting.value.startsWith('criterion:')) {
    const id = Number(resultWeighting.value.slice('criterion:'.length))
    const byFactor = (viewReport.value?.by_factor as Record<string, any>) || {}
    return mapServerRanking(byFactor[id] || byFactor[String(id)]) || []
  }
  if (resultWeighting.value === 'equal') {
    return mapServerRanking(
      (viewReport.value?.option_ranking_equal as any[])
      || (viewReport.value?.results as any)?.equal_weight,
    ) || mapServerRanking(viewReport.value?.option_ranking as any[]) || []
  }
  return mapServerRanking(
    (viewReport.value?.option_ranking as any[])
    || (viewReport.value?.alternative_ranking as any[])
    || (viewReport.value?.results as any)?.importance_adjusted,
  ) || []
})

const resultViewLabel = computed(() =>
  resultViewOptions.value.find(o => o.value === resultWeighting.value)?.title || 'Option ranking',
)

const leaderBasisLabel = computed(() => {
  if (effectiveCriteria(factorItems.value).length <= 1) return ''
  if (resultWeighting.value === 'equal') return 'All Factors Equal'
  if (resultWeighting.value === 'adjusted') return ''
  if (resultWeighting.value.startsWith('criterion:')) {
    const id = Number(resultWeighting.value.slice('criterion:'.length))
    const title = effectiveCriteria(factorItems.value).find(c => c.id === id)?.title
    return title ? `Based on ${title}` : ''
  }
  return ''
})

const resultViewExplanation = computed(() => {
  const rankPct = 'Rank percentage is first vs last likelihood.'
  if (resultWeighting.value === 'equal') return `Every decision factor contributes equally to this ranking. ${rankPct}`
  if (resultWeighting.value === 'adjusted') return `Decision factors contribute according to their ranked importance. ${rankPct}`
  return `This view considers only the selected factor. ${rankPct}`
})

const leaderGap = computed(() =>
  displayRankings.value.length > 1
    ? scoreLeadPoints(displayRankings.value[0].score, displayRankings.value[1].score)
    : 0,
)

const summaryText = computed(() => {
  if (!displayRankings.value.length) return ''
  const chance = optionChanceCaption(displayRankings.value[0], rankingMode.value, reportTopN.value)
  if (displayRankings.value.length < 2) {
    return chance
      ? `It is the only active option. ${chance[0].toUpperCase()}${chance.slice(1)}.`
      : 'It is the only active option.'
  }
  const lead = `It leads the next option by ${leaderGap.value} points across ${uniqueParticipants.value} participants.`
  return chance ? `${lead} ${chance[0].toUpperCase()}${chance.slice(1)}.` : lead
})

const factorRankings = computed(() => {
  const mapped = mapServerRanking(
    (viewReport.value?.factor_ranking as any[])
    || (viewReport.value?.results as any)?.criterion_weights,
  )
  if (!mapped?.length) return []
  const weights = (viewReport.value?.factor_weights as Record<string, number>) || {}
  return mapped.map((r: any) => ({
    ...r,
    normalizedWeight: r.normalizedWeight ?? weights[r.id] ?? weights[String(r.id)] ?? r.score,
    confidence: r.confidence,
    stability: r.stability,
    data_points: r.data_points ?? r.evidence ?? 0,
  }))
})

const sortedFactorRankings = computed(() => {
  const rows = [...factorRankings.value]
  const key = factorSortKey.value
  if (key === 'rank') {
    return rows.sort((a: any, b: any) => (a.rank ?? 0) - (b.rank ?? 0) || (b.normalizedWeight || 0) - (a.normalizedWeight || 0))
  }
  const valueOf = (row: any) => {
    if (key === 'importance') return Number(row.normalizedWeight ?? row.weight ?? row.score) || 0
    return Number(row[key]) || 0
  }
  return rows.sort((a: any, b: any) => valueOf(b) - valueOf(a))
})

const perCriterionLeaders = computed(() => {
  const criteria = effectiveCriteria(factorItems.value)
  if (!criteria.length) return []
  const byFactor = (viewReport.value?.by_factor as Record<string, any>) || {}
  const factorRows = (viewReport.value?.factor_ranking as any[]) || []
  return criteria.map((criterion) => {
    const raw = byFactor[criterion.id] || byFactor[String(criterion.id)] || []
    const ranking = mapServerRanking(raw) || []
    const leader = ranking[0]
    const meta = factorRows.find((f: any) => Number(f.id) === Number(criterion.id))
    const passRaw = leader?.pass_consistency ?? meta?.pass_consistency ?? raw?.[0]?.pass_consistency
    return {
      criterion,
      leaderTitle: leader?.title || meta?.leader?.title || '—',
      score: leader?.score ?? meta?.leader?.score ?? 0,
      mean_rank: leader?.mean_rank ?? meta?.leader?.mean_rank,
      evidence: leader?.data_points ?? leader?.evidence ?? meta?.data_points ?? 0,
      pass_consistency: passRaw,
    }
  }).filter(r => r.leaderTitle !== '—')
})

const dispersion = computed(() => (report.value?.dispersion as Record<string, any>) || {})
const uniqueParticipants = computed(() => Number(viewReport.value?.unique_participants || 0) || participants.value.length)
const pivot = computed(() => (report.value?.pivot as Record<string, any>) || {})
const coherenceMethodLabel = computed(() => {
  const m = String(report.value?.coherence_method || settings.value.coherenceMethod || 'spearman')
  return m === 'kendall' ? 'Kendall τ' : 'Spearman ρ'
})

const leaderConcentrationExplanation = computed(() => {
  if (leaderWeighting.value === 'equal') return 'All factors equal'
  if (leaderWeighting.value === 'adjusted') return 'Weighted by what matters most'
  if (leaderWeighting.value.startsWith('criterion:')) {
    const id = Number(leaderWeighting.value.slice('criterion:'.length))
    const title = effectiveCriteria(factorItems.value).find(c => c.id === id)?.title
    return title ? `Based on ${title}` : 'Selected factor'
  }
  return ''
})

function rankingForLeaderView(fromReport: any): any[] {
  if (!fromReport) return []
  if (leaderWeighting.value === 'equal') {
    return mapServerRanking(fromReport.option_ranking_equal || fromReport.ranking || fromReport.option_ranking) || []
  }
  if (leaderWeighting.value.startsWith('criterion:')) {
    const id = Number(leaderWeighting.value.slice('criterion:'.length))
    const ranks = lookupRankMap(fromReport.option_ranks_by_factor, id)
    return rankingFromMeanRankMap(ranks as Record<string | number, number> | undefined, altItems.value)
  }
  return mapServerRanking(fromReport.option_ranking || fromReport.ranking) || []
}

const leaderConcentrationMeta = computed(() => {
  const alts = altItems.value
  const counts = new Map<number, number>(alts.map(a => [a.id, 0]))
  const reportParts = (report.value?.participants as any[]) || []
  let participantsWithLeaders = 0

  for (const p of reportParts) {
    const leaders = tiedLeadersFromRanking(rankingForLeaderView(p))
    if (!leaders.length) continue
    participantsWithLeaders += 1
    for (const leader of leaders) {
      if (counts.has(leader.id)) counts.set(leader.id, (counts.get(leader.id) || 0) + 1)
    }
  }

  // No participant rows: fall back to group-level ranking once (still honor ties)
  if (!reportParts.length) {
    let ranking: any[] = []
    if (leaderWeighting.value.startsWith('criterion:')) {
      const id = Number(leaderWeighting.value.slice('criterion:'.length))
      const byFactor = (report.value?.by_factor as Record<string, any>) || {}
      ranking = mapServerRanking(lookupRankMap(byFactor, id) as any[]) || []
    }
    else {
      ranking = mapServerRanking(
        leaderWeighting.value === 'equal'
          ? (report.value?.option_ranking_equal as any[])
          : (report.value?.option_ranking as any[]),
      ) || []
    }
    const leaders = tiedLeadersFromRanking(ranking)
    if (leaders.length) {
      participantsWithLeaders = 1
      for (const leader of leaders) {
        if (counts.has(leader.id)) counts.set(leader.id, (counts.get(leader.id) || 0) + 1)
      }
    }
  }

  const rows = alts
    .map(a => ({ id: a.id, title: a.title, count: counts.get(a.id) || 0 }))
    .sort((a, b) => b.count - a.count || a.title.localeCompare(b.title))

  return { rows, participantsWithLeaders }
})

const leaderConcentrationRows = computed(() => leaderConcentrationMeta.value.rows)

const leaderConcentrationParticipants = computed(() =>
  leaderConcentrationMeta.value.participantsWithLeaders,
)

const leaderConcentrationTotal = computed(() =>
  leaderConcentrationRows.value.reduce((n, r) => n + r.count, 0),
)

const showPivot = computed(() =>
  uniqueParticipants.value > 0 && (altItems.value.length > 1 || factorRankings.value.length > 1),
)

function pctField(v: unknown) {
  if (v == null) return null
  return asMetricPercent(v)
}

const participantRows = computed(() => {
  const reportParts = (viewReport.value?.participants as any[]) || (report.value?.participants as any[]) || []
  const base = participants.value.length ? participants.value : reportParts.map((p: any) => ({
    id: p.id,
    display_name: p.display_name,
    email: p.email,
    source: p.source,
    is_ai: p.is_ai,
    is_complete: p.is_complete,
    observation_count: p.observation_count ?? p.comparison_count,
    comparison_count: p.comparison_count,
  }))
  const mapped = base.map((p: any) => {
    const fromReport = reportParts.find((r: any) => r.id === p.id) || p
    const ranking = mapServerRanking(fromReport?.option_ranking || fromReport?.ranking) || []
    const leader = fromReport?.leader || ranking[0] || null
    return {
      ...p,
      leaderTitle: leader?.title || null,
      ranking,
      coherence: fromReport?.coherence,
      confidence: pctField(fromReport?.confidence ?? fromReport?.metrics?.confidence),
      stability: pctField(fromReport?.stability ?? fromReport?.metrics?.stability),
      comparison_count: fromReport?.comparison_count ?? p.comparison_count ?? p.observation_count ?? 0,
      observation_count: fromReport?.comparison_count ?? p.observation_count ?? 0,
      data_points: fromReport?.data_points ?? fromReport?.comparison_count ?? 0,
    }
  })
  return mapped.filter((p: any) => {
    const ai = !!(p.is_ai || p.source === 'ai')
    if (analysisMode.value === 'human') return !ai
    if (analysisMode.value === 'agents') return ai
    return true
  })
})

const selectedRanking = computed(() => {
  if (!selectedParticipant.value) return []
  const row = participantRows.value.find(p => p.id === selectedParticipant.value?.id)
  return row?.ranking || []
})

const altFilterItems = computed(() => [
  ...altItems.value.map(a => ({ title: a.title, value: a.id })),
])
const factorFilterItems = computed(() =>
  factorRankings.value.map((f: any) => ({ title: f.title, value: f.id })),
)
const participantFilterItems = computed(() =>
  participantRows.value.map(p => ({
    title: p.display_name || p.email || `Participant ${p.id}`,
    value: p.id,
  })),
)

const pivotColumns = computed(() => {
  if (pivotAxis.value === 'alternatives') {
    return [
      { key: 'rank', title: 'Rank' },
      { key: 'title', title: 'Option' },
      { key: 'mean_rank', title: 'Mean rank' },
      { key: 'score', title: 'Score' },
      { key: 'data_points', title: 'Groups' },
      { key: 'leader_count', title: '#1s' },
    ]
  }
  if (pivotAxis.value === 'factors') {
    return [
      { key: 'rank', title: 'Rank' },
      { key: 'title', title: 'Factor' },
      { key: 'normalizedWeight', title: 'Weight' },
      { key: 'leader', title: 'Top option' },
      { key: 'leader_mean_rank', title: 'Leader mean rank' },
      { key: 'pass_consistency', title: 'Pass cons.' },
      { key: 'stability', title: 'Stab' },
      { key: 'data_points', title: 'Groups' },
    ]
  }
  return [
    { key: 'title', title: 'Participant' },
    { key: 'leader', title: 'Leader' },
    { key: 'multi_pass', title: 'Multi-pass' },
    { key: 'stability', title: 'Stab' },
    { key: 'data_points', title: 'Groups' },
    { key: 'coherence', title: 'Align' },
  ]
})

const pivotSortOptions = computed(() =>
  pivotColumns.value.map(c => ({ title: c.title, value: c.key })),
)

const pivotFiltersActive = computed(() =>
  (pivotAxis.value !== 'alternatives' && filterAlternativeId.value != null)
  || (pivotAxis.value !== 'factors' && filterFactorId.value != null)
  || (pivotAxis.value !== 'participants' && filterParticipantId.value != null),
)

function leaderCountsUnderFactor(factorId: number | null): Map<number, number> {
  const counts = new Map<number, number>()
  const alts = altItems.value
  const reportParts = (report.value?.participants as any[]) || []
  for (const p of reportParts) {
    for (const leader of participantLeadersUnderFactor(p, factorId, alts)) {
      counts.set(leader.id, (counts.get(leader.id) || 0) + 1)
    }
  }
  return counts
}

/** Server pivot rollups, reshaped by active filters; row click loads pivot-detail. */
const pivotRows = computed(() => {
  const fid = filterFactorId.value
  const aid = filterAlternativeId.value
  const pid = filterParticipantId.value
  const alts = altItems.value
  const byFactor = (report.value?.by_factor as Record<string, any>) || {}
  const reportParts = (report.value?.participants as any[]) || []

  if (pivotAxis.value === 'alternatives') {
    let source: any[] = []
    let leaderCounts: Map<number, number> | null = null

    if (pid != null) {
      const part = reportParts.find((p: any) => Number(p.id) === Number(pid))
      if (part) {
        if (fid != null) {
          const ranks = lookupRankMap(part.option_ranks_by_factor, fid)
          source = rankingFromMeanRankMap(ranks as Record<string | number, number> | undefined, alts)
        }
        else {
          source = mapServerRanking(part.option_ranking || part.ranking) || []
        }
        leaderCounts = new Map()
        if (source[0]) leaderCounts.set(Number(source[0].id), 1)
      }
    }
    else if (fid != null) {
      source = mapServerRanking(lookupRankMap(byFactor, fid) as any[]) || []
      leaderCounts = leaderCountsUnderFactor(fid)
    }
    else {
      source = (pivot.value.by_alternative?.length
        ? pivot.value.by_alternative
        : displayRankings.value) || []
    }

    return source.map((r: any, idx: number) => {
      const rankRaw = r.rank != null ? Number(r.rank) : idx
      const id = Number(r.id)
      return {
        id,
        title: r.title,
        rank: rankRaw >= 1 ? rankRaw : rankRaw + 1,
        mean_rank: r.mean_rank != null ? Number(r.mean_rank).toFixed(2) : '—',
        score: r.score,
        data_points: r.data_points ?? r.evidence ?? 0,
        leader_count: leaderCounts
          ? (leaderCounts.get(id) || 0)
          : (r.leader_count ?? 0),
        informed: true,
      }
    })
  }

  if (pivotAxis.value === 'factors') {
    const fromPivot = pivot.value.by_factor?.length
      ? pivot.value.by_factor
      : factorRankings.value.map((r: any, idx: number) => ({
          id: r.id,
          title: r.title,
          rank: idx + 1,
          normalizedWeight: r.normalizedWeight ?? r.score,
          leader: r.leader?.title || r.leader || '—',
          leader_mean_rank: r.leader?.mean_rank,
          pass_consistency: r.pass_consistency != null ? asMetricPercent(r.pass_consistency) : r.pass_consistency,
          stability: r.stability,
          data_points: r.data_points ?? 0,
        }))

    return fromPivot
      .map((r: any, idx: number) => {
        const factorId = Number(r.id)
        let leaderTitle = r.leader || r.ranking?.[0]?.title || '—'
        let leaderMean = r.leader_mean_rank
        let leaderId: number | null = null

        if (pid != null) {
          const part = reportParts.find((p: any) => Number(p.id) === Number(pid))
          const leader = participantLeaderUnderFactor(part, factorId, alts)
          leaderTitle = leader?.title || '—'
          leaderId = leader?.id ?? null
          const ranks = lookupRankMap(part?.option_ranks_by_factor, factorId) as Record<string | number, number> | undefined
          if (leader && ranks) {
            const mr = lookupRankMap(ranks, leader.id)
            leaderMean = mr != null ? Number(mr) : leaderMean
          }
          else {
            leaderMean = null
          }
        }
        else {
          const ranking = mapServerRanking(lookupRankMap(byFactor, factorId) as any[]) || []
          if (ranking[0]) {
            leaderId = Number(ranking[0].id)
            if (!r.leader && ranking[0].title) leaderTitle = ranking[0].title
            if (leaderMean == null && ranking[0].mean_rank != null) leaderMean = ranking[0].mean_rank
          }
        }

        if (aid != null && leaderId != null && Number(leaderId) !== Number(aid)) return null
        if (pid != null && leaderTitle === '—') return null

        return {
          id: factorId,
          title: r.title,
          rank: r.rank != null ? Number(r.rank) : idx + 1,
          normalizedWeight: r.normalizedWeight
            ?? factorRankings.value.find((f: any) => Number(f.id) === factorId)?.normalizedWeight,
          leader: typeof leaderTitle === 'object' ? (leaderTitle as any)?.title || '—' : leaderTitle,
          leader_mean_rank: leaderMean != null && leaderMean !== ''
            ? Number(leaderMean).toFixed(2)
            : (r.ranking?.[0]?.mean_rank != null ? Number(r.ranking[0].mean_rank).toFixed(2) : '—'),
          pass_consistency: r.pass_consistency,
          stability: r.stability,
          data_points: r.data_points ?? 0,
          informed: true,
        }
      })
      .filter(Boolean)
  }

  const source = pivot.value.by_participant?.length ? pivot.value.by_participant : participantRows.value
  return source
    .map((r: any) => {
      const partId = Number(r.id)
      const part = reportParts.find((p: any) => Number(p.id) === partId) || r
      if (pid != null && partId !== Number(pid)) return null

      const leader = participantLeaderUnderFactor(part, fid, alts)
      if (fid != null && !leader) return null
      if (aid != null) {
        if (!leader || Number(leader.id) !== Number(aid)) return null
      }

      const baseLeader = typeof r.leader === 'object' ? (r.leader?.title || '—') : (r.leader || r.leaderTitle || '—')
      return {
        id: partId,
        title: r.display_name || r.email || r.title || `Participant ${partId}`,
        leader: leader?.title || baseLeader || '—',
        data_points: r.data_points ?? r.observation_count ?? r.comparison_count ?? 0,
        multi_pass: pctField(r.multi_pass ?? r.stability),
        stability: pctField(r.stability),
        coherence: r.coherence,
        informed: true,
      }
    })
    .filter(Boolean)
})

const sortedPivotRows = computed(() => {
  const rows = [...pivotRows.value]
  const key = pivotSortKey.value
  const numericKeys = new Set([
    'rank', 'score', 'confidence', 'stability', 'multi_pass', 'pass_consistency',
    'data_points', 'coherence', 'leader_count', 'normalizedWeight', 'mean_rank', 'leader_mean_rank',
  ])
  rows.sort((a: any, b: any) => {
    const av = key === 'title' || key === 'leader' ? String(a[key] ?? '') : Number(a[key])
    const bv = key === 'title' || key === 'leader' ? String(b[key] ?? '') : Number(b[key])
    if (key === 'title' || key === 'leader') return String(av).localeCompare(String(bv))
    if (key === 'rank') {
      const an = Number.isFinite(av as number) ? (av as number) : 9999
      const bn = Number.isFinite(bv as number) ? (bv as number) : 9999
      return an - bn
    }
    if (numericKeys.has(key)) {
      const an = Number.isFinite(av as number) ? (av as number) : -Infinity
      const bn = Number.isFinite(bv as number) ? (bv as number) : -Infinity
      return bn - an
    }
    return 0
  })
  return rows
})

const activePivotFilterLabels = computed(() => {
  const labels: string[] = []
  if (pivotAxis.value !== 'alternatives' && filterAlternativeId.value != null) {
    const title = altItems.value.find(a => a.id === filterAlternativeId.value)?.title
    if (title) labels.push(`Including only option ${title}`)
  }
  if (pivotAxis.value !== 'factors' && filterFactorId.value != null) {
    const title = effectiveCriteria(factorItems.value).find(c => c.id === filterFactorId.value)?.title
      || factorRankings.value.find((f: any) => f.id === filterFactorId.value)?.title
    if (title) labels.push(`Including only factor ${title}`)
  }
  if (pivotAxis.value !== 'participants' && filterParticipantId.value != null) {
    const p = participantRows.value.find(r => r.id === filterParticipantId.value)
    const title = p?.display_name || p?.email || `Participant ${filterParticipantId.value}`
    labels.push(`Including only ${title}`)
  }
  return labels
})

const pivotDetailFilterLabels = computed(() => {
  const labels: string[] = []
  const filters = (pivotDetail.value?.filters || {}) as {
    alternative_id?: number | null
    factor_id?: number | null
    participant_id?: number | null
  }
  const axis = pivotDetail.value?.primary_axis || pivotAxis.value
  if (axis !== 'alternatives' && filters.alternative_id != null) {
    const title = altItems.value.find(a => a.id === filters.alternative_id)?.title
    if (title) labels.push(`Including only option ${title}`)
  }
  if (axis !== 'factors' && filters.factor_id != null) {
    const title = effectiveCriteria(factorItems.value).find(c => c.id === filters.factor_id)?.title
      || factorRankings.value.find((f: any) => f.id === filters.factor_id)?.title
    if (title) labels.push(`Including only factor ${title}`)
  }
  if (axis !== 'participants' && filters.participant_id != null) {
    const p = participantRows.value.find(r => r.id === filters.participant_id)
    const title = p?.display_name || p?.email || `Participant ${filters.participant_id}`
    labels.push(`Including only ${title}`)
  }
  return labels.length ? labels : activePivotFilterLabels.value
})

function formatCoherence(value: number) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return n <= 1 ? `${Math.round(n * 100)}%` : `${Math.round(n)}%`
}

function formatPivotCell(row: Record<string, any>, key: string) {
  const v = row[key]
  if (row.informed === false && key !== 'title' && key !== 'data_points' && key !== 'leader_count') {
    return '—'
  }
  if (key === 'score' || key === 'normalizedWeight') {
    if (v == null || v === '') return '—'
    return formatPercent(Number(v) || 0)
  }
  if (key === 'coherence') return v == null ? '—' : formatCoherence(Number(v))
  if (key === 'confidence' || key === 'stability' || key === 'multi_pass' || key === 'pass_consistency') {
    if (v == null || v === '') return '—'
    return `${asMetricPercent(v)}%`
  }
  if (key === 'rank' || key === 'mean_rank' || key === 'leader_mean_rank') {
    if (v == null || v === '') return '—'
    return String(v)
  }
  if (key === 'leader' && (v == null || v === '' || v === '—')) return '—'
  if (v == null || v === '') return '—'
  return String(v)
}

function setPivotSort(key: string) {
  pivotSortKey.value = key
}

function participantSubtitle(p: any) {
  const bits = [
    `${p.comparison_count || p.observation_count || 0} comparisons`,
    p.source || 'session',
  ]
  if (p.is_complete) bits.push('complete')
  if (p.confidence != null) bits.push(`conf ${p.confidence}%`)
  return bits.join(' · ')
}

function selectParticipant(id: number) {
  if (selectedParticipant.value?.id === id) {
    selectedParticipant.value = null
    return
  }
  selectedParticipant.value = participants.value.find(p => p.id === id)
    || participantRows.value.find(p => p.id === id) as any
    || null
}

async function selectPivotRow(row: Record<string, any>) {
  selectedPivotRowId.value = row.id
  pivotDetailLoading.value = true
  pivotDetail.value = null
  try {
    const res = await votes.pivotDetail({
      project_id: Number(route.params.id),
      primary_axis: pivotAxis.value,
      row_id: row.id,
      alternative_id: pivotAxis.value === 'alternatives' ? row.id : filterAlternativeId.value,
      factor_id: pivotAxis.value === 'factors' ? row.id : filterFactorId.value,
      participant_id: pivotAxis.value === 'participants' ? row.id : filterParticipantId.value,
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    pivotDetail.value = (res.detail as Record<string, any>) || null
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Failed to load detail')
  }
  finally {
    pivotDetailLoading.value = false
  }
}

function clearPivotDetail() {
  selectedPivotRowId.value = null
  pivotDetail.value = null
}

watch(pivotAxis, () => {
  pivotSortKey.value = pivotAxis.value === 'participants' ? 'coherence' : 'rank'
  clearPivotDetail()
})

watch([filterAlternativeId, filterFactorId, filterParticipantId], () => {
  if (selectedPivotRowId.value != null) {
    const row = sortedPivotRows.value.find((r: any) => r.id === selectedPivotRowId.value)
    if (row) selectPivotRow(row)
    else clearPivotDetail()
  }
})

onMounted(async () => {
  try {
    await loadProject(Number(route.params.id), { bundle: true, myVote: false })
    const criteria = effectiveCriteria(factorItems.value)
    const defaultWeight = criteria.length > 1 ? 'adjusted' : `criterion:${criteria[0]?.id ?? 0}`
    resultWeighting.value = defaultWeight
    leaderWeighting.value = defaultWeight
    if (uniqueParticipants.value > 1) pivotAxis.value = 'participants'
    else if (criteria.length > 1) pivotAxis.value = 'factors'
    else pivotAxis.value = 'alternatives'
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Failed to load results')
  }
})
</script>

<style scoped>
.personal-rank-caption {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  row-gap: 8px;
  line-height: 1.3;
  padding-right: 4px;
}
.factor-violin-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  row-gap: 12px;
  margin-bottom: 4px;
  padding-right: 4px;
}
.factor-violin-row .violin-label {
  min-width: 80px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pc-muted);
  line-height: 1.2;
}
.factor-violin-row + .factor-violin-row {
  margin-top: 10px !important;
}
.overall-violin-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  row-gap: 12px;
  margin-top: 16px;
  padding-right: 4px;
}
.overall-violin-row .violin-label {
  min-width: 80px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pc-muted);
  line-height: 1.2;
}
@media (max-width: 480px) {
  .factor-violin-row,
  .overall-violin-row,
  .personal-rank-caption {
    gap: 8px 12px;
  }
  .factor-violin-row .violin-label,
  .overall-violin-row .violin-label {
    min-width: 72px;
  }
}
</style>
