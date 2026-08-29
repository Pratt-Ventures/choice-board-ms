<template>
  <div>
    <v-progress-linear v-if="loadingDraft" indeterminate color="primary" class="mb-4" />
    <div class="d-flex flex-wrap justify-space-between ga-3 mb-5">
      <div>
        <div class="eyebrow">{{ isNew ? 'Create' : 'Edit' }}</div>
        <div class="page-title">{{ isNew ? (isDuplicateDraft ? 'New project (copy)' : 'New project') : 'Edit Project Settings' }}</div>
        <div class="page-subtitle">
          {{ isDuplicateDraft
            ? 'Review the copied settings, then save to create the project. Cancel discards the copy.'
            : 'Define the decision, options, and optional factors before running comparisons.' }}
        </div>
      </div>
      <v-btn variant="text" @click="navigateTo(isNew ? '/projects' : `/projects/${projectId}`)">Cancel</v-btn>
    </div>

    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab
        v-if="!isNew"
        value="back-overview"
        :to="`/projects/${projectId}`"
      >
        <i class="fa-solid fa-arrow-left mr-2" /> Overview
      </v-tab>
      <v-tab value="overview">Project</v-tab>
      <v-tab value="options">Options</v-tab>
      <v-tab value="factors">Factors</v-tab>
      <v-tab value="review">Review</v-tab>
    </v-tabs>

    <v-window v-model="tab">
      <v-window-item value="overview">
        <v-card class="glass-card">
          <v-card-text class="pa-6">
            <div class="d-flex flex-wrap justify-space-between ga-2 mb-4">
              <div class="text-body-2 text-medium-emphasis">Project settings and optional starter content from a template.</div>
              <div class="d-flex flex-wrap ga-2">
                <v-btn
                  v-if="isNew"
                  size="small"
                  variant="tonal"
                  :disabled="!canCopyFromProject"
                  :title="copyFromDisabledHint"
                  @click="openCopyFromDialog"
                >
                  <i class="fa-solid fa-copy mr-2" /> Copy from project
                </v-btn>
                <v-btn size="small" variant="tonal" @click="openImportDialog('projects')">
                  <i class="fa-solid fa-clone mr-2" /> Start with Template
                </v-btn>
                <v-btn
                  size="small"
                  variant="text"
                  :disabled="isNew"
                  :title="isNew ? 'Save the project before creating a template' : undefined"
                  @click="openSaveAsTemplate"
                >
                  <i class="fa-solid fa-floppy-disk mr-2" /> Save as Template
                </v-btn>
              </div>
            </div>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.project_title" label="Project name" />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.project_tag" label="Short tag (unique)" :disabled="!isNew" class="mono" hint="Used as a stable identifier" persistent-hint />
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="form.project_description" label="Description" rows="3" />
              </v-col>
              <v-col v-if="!isNew" cols="12">
                <div class="text-subtitle-2 mb-2">Project branding image</div>
                <div class="text-body-2 text-medium-emphasis mb-3">
                  Optional image shown next to the project name on shared pages (upload up to 8 MB; stored near 1 MB).
                </div>
                <div class="d-flex align-center ga-4 flex-wrap">
                  <div class="project-branding-preview">
                    <img v-if="projectBrandingPreview" :src="projectBrandingPreview" alt="" class="project-branding-preview__img" />
                    <div v-else class="project-branding-preview__empty"><i class="fa-regular fa-image" /></div>
                  </div>
                  <div class="d-flex flex-wrap ga-2">
                    <input
                      ref="projectBrandFileInput"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
                      class="d-none"
                      @change="onProjectBrandFile"
                    />
                    <v-btn size="small" color="primary" variant="tonal" :loading="projectBrandUploading" :disabled="!isAdmin" @click="projectBrandFileInput?.click()">
                      {{ projectBrandHasImage ? 'Replace image' : 'Upload image' }}
                    </v-btn>
                    <v-btn v-if="projectBrandHasImage" size="small" variant="text" color="error" :loading="projectBrandDeleting" :disabled="!isAdmin" @click="onDeleteProjectBrand">
                      Delete
                    </v-btn>
                  </div>
                </div>
                <div v-if="projectBrandError" class="text-caption text-error mt-2">{{ projectBrandError }}</div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-subtitle-2 mb-2">Decision mode</div>
                <v-btn-toggle v-model="rankingMode" mandatory color="primary" divided class="flex-wrap">
                  <v-btn value="find_best">Find Best</v-btn>
                  <v-btn value="find_top_3" :disabled="activeOptionCount < 6">Find Top 3</v-btn>
                  <v-btn value="find_top_half">Find Top Half</v-btn>
                  <v-btn value="rank_all">Rank All</v-btn>
                </v-btn-toggle>
                <div class="text-caption text-medium-emphasis mt-2">
                  {{ rankingModeHint }}
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <v-switch v-model="form.disabled" label="Close input (block new comparisons)" color="warning" />
              </v-col>
              <v-col cols="12" md="6">
                <div class="text-subtitle-2 mb-1">Comparison close date</div>
                <div class="d-flex align-center ga-2 flex-wrap">
                  <v-menu v-model="endTimeMenu" :close-on-content-click="false">
                    <template #activator="{ props: menuProps }">
                      <span
                        class="text-body-1"
                        style="cursor:pointer;text-decoration:underline;text-underline-offset:3px"
                        v-bind="menuProps"
                      >{{ endTimeDisplay }}</span>
                    </template>
                    <v-card>
                      <v-date-picker
                        v-model="endTimePicker"
                        :min="endTimeMin"
                        hide-header
                        @update:model-value="onEndDatePicked"
                      />
                      <v-card-actions>
                        <v-btn variant="text" @click="clearEndTime">Clear</v-btn>
                        <v-spacer />
                        <v-btn variant="text" @click="endTimeMenu = false">Done</v-btn>
                      </v-card-actions>
                    </v-card>
                  </v-menu>
                  <v-btn size="small" variant="text" @click="endTimeMenu = true">Change</v-btn>
                  <v-btn v-if="form.end_time" size="small" variant="text" @click="clearEndTime">Clear</v-btn>
                </div>
                <div class="text-caption text-medium-emphasis mt-1">
                  Optional. Collection closes at 11:59 PM on the selected date. None means no deadline.
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <v-switch
                  v-model="form.private_participation"
                  label="Private participation (hide individual names in results)"
                  color="primary"
                  :disabled="privateParticipationSwitchDisabled"
                  :hint="privateParticipationHint"
                  persistent-hint
                />
              </v-col>
              <v-col cols="12">
                <div class="text-subtitle-2 mb-2">Balance influence</div>
                <div class="text-body-2 text-medium-emphasis mb-3">
                  How group Results weigh comparisons when participants contribute different amounts.
                </div>
                <v-btn-toggle
                  v-model="form.participant_influence_mode"
                  mandatory
                  color="primary"
                  divided
                  class="flex-wrap"
                >
                  <v-btn value="comparisons">Comparisons equal</v-btn>
                  <v-btn value="balanced">Balanced</v-btn>
                  <v-btn value="participants_normalized">Participants normalized</v-btn>
                </v-btn-toggle>
                <div class="text-caption text-medium-emphasis mt-2">
                  {{ influenceModeHint }}
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.min_expected_passes"
                  type="number"
                  min="1"
                  max="5"
                  step="1"
                  label="Minimum expected passes"
                  hint="Target passes per participant (1–5). Used for progress and encouragement."
                  persistent-hint
                  density="compact"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.max_recommended_passes"
                  type="number"
                  :min="maxPassesFloor"
                  max="10"
                  step="1"
                  label="Maximum recommended passes"
                  hint="Recommended ceiling (≥ minimum expected, ≤ 10). Hard stop is this value + 1."
                  persistent-hint
                  density="compact"
                />
              </v-col>
              <v-col v-if="aiFeaturesEnabled" cols="12">
                <div class="text-subtitle-2 mb-1">AI agents</div>
                <div class="text-caption text-medium-emphasis mb-3">
                  Each selected model votes as its own AI participant through the minimum expected number of groups.
                  Names appear as AI AGENT: model. The same model cannot vote twice.
                  When Include AI Agents is off, the list is kept but not queued.
                </div>
                <div class="d-flex align-start ga-4 flex-wrap">
                  <v-switch
                    v-model="form.include_ai_agents"
                    label="Include AI Agents"
                    color="primary"
                    hide-details
                    density="compact"
                    class="flex-grow-0 mt-1"
                    style="flex:0 0 auto"
                  />
                  <v-select
                    v-model="form.ai_voter_models"
                    :items="aiVoterItems"
                    item-title="title"
                    item-value="value"
                    label="AI participants"
                    multiple
                    chips
                    closable-chips
                    density="compact"
                    class="flex-grow-1"
                    style="min-width:220px"
                    :loading="loadingAiModels"
                    :hint="aiVoterHint"
                    persistent-hint
                  />
                </div>
              </v-col>
              <v-col v-if="!isNew" cols="12">
                <div class="text-subtitle-2 mb-1">Concise wording</div>
                <div class="text-caption text-medium-emphasis mb-3">
                  Generate crisp compare prompts for options (2-5 word labels) and factors (concise “Which …?” question). Only fills blanks. Edit after generation. Uses the workspace AI provider.
                </div>
                <div class="d-flex flex-wrap ga-2">
                  <span :title="hasProvider ? undefined : providerDisabledMsg">
                    <v-btn
                      color="primary"
                      variant="tonal"
                      size="small"
                      :loading="generatingPrompts"
                      :disabled="!hasProvider || generatingPrompts"
                      @click="generateConcisePrompts"
                    >
                      <i class="fa-solid fa-wand-magic-sparkles mr-2" /> Generate concise options and factors
                    </v-btn>
                  </span>
                  <v-btn variant="text" size="small" :disabled="generatingPrompts" @click="clearConcisePrompts">
                    <i class="fa-solid fa-eraser mr-2" /> Clear
                  </v-btn>
                  <span v-if="!hasProvider" class="text-caption text-medium-emphasis align-self-center">{{ providerDisabledMsg }}</span>
                </div>
                <div v-if="promptGenMessage" class="text-caption mt-2" :class="promptGenOk ? 'text-success' : 'text-error'">{{ promptGenMessage }}</div>
              </v-col>
              <v-col cols="12">
                <v-btn
                  variant="text"
                  size="small"
                  class="px-0"
                  @click="advancedOpen = !advancedOpen"
                >
                  <i :class="advancedOpen ? 'fa-solid fa-chevron-down mr-2' : 'fa-solid fa-chevron-right mr-2'" />
                  Advanced settings
                </v-btn>
                <v-expand-transition>
                  <div v-show="advancedOpen" class="mt-3 pa-4 rounded-lg" style="background: rgba(var(--v-theme-on-surface), 0.03)">
                    <div class="text-subtitle-2 mb-1">Factor importance spread</div>
                    <div class="text-body-2 text-medium-emphasis mb-3">
                      How strongly ranked factors differ in weight when blending overall results. Not saved to templates.
                    </div>
                    <div class="d-flex align-center ga-3 mb-1">
                      <span class="text-caption text-medium-emphasis" style="min-width: 7.5rem">Factors are more equal</span>
                      <v-slider
                        v-model="form.factor_weight_floor_alpha"
                        :min="0.1"
                        :max="0.9"
                        :step="0.05"
                        reverse
                        color="primary"
                        thumb-label
                        hide-details
                        class="flex-grow-1"
                      />
                      <span class="text-caption text-medium-emphasis" style="min-width: 8.5rem; text-align: right">Factors are more spread out</span>
                    </div>
                    <div class="text-caption text-medium-emphasis mb-5">
                      Default is the middle position. Lower values emphasize top-ranked factors more.
                    </div>
                    <v-text-field
                      v-model.number="form.participant_influence_min_comparisons"
                      type="number"
                      min="3"
                      step="1"
                      label="Minimum comparisons before amplifying influence"
                      hint="Soft floor (3+). Participants below this are not over-amplified."
                      persistent-hint
                      density="compact"
                      style="max-width: 22rem"
                    />
                    <div class="text-subtitle-2 mb-1 mt-6">Questions per group</div>
                    <div class="text-body-2 text-medium-emphasis mb-3">
                      How many pairwise comparisons each group asks. The Ford–Johnson estimate for the current item count is the guide; you can raise or lower it within the allowed range.
                    </div>
                    <v-text-field
                      v-model.number="form.option_questions_per_group"
                      type="number"
                      :min="optionQuestionBounds.min || 1"
                      :max="optionQuestionBounds.max || 500"
                      step="1"
                      label="Option comparisons per group"
                      :hint="optionQuestionHint"
                      persistent-hint
                      density="compact"
                      :disabled="optionQuestionBounds.max <= 0"
                      class="mb-4"
                      style="max-width: 22rem"
                      @update:model-value="onOptionGroupSizeInput"
                    >
                      <template #append-inner>
                        <v-chip v-if="!optionGroupSizeExplicit" size="x-small" variant="tonal">Default</v-chip>
                        <v-btn
                          v-else
                          size="x-small"
                          variant="text"
                          class="px-1"
                          @click.stop="resetOptionGroupSize"
                        >Reset</v-btn>
                      </template>
                    </v-text-field>
                    <v-text-field
                      v-model.number="form.factor_questions_per_group"
                      type="number"
                      :min="factorQuestionBounds.min || 1"
                      :max="factorQuestionBounds.max || 500"
                      step="1"
                      label="Factor comparisons per group"
                      :hint="factorQuestionHint"
                      persistent-hint
                      density="compact"
                      :disabled="factorQuestionBounds.max <= 0"
                      style="max-width: 22rem"
                      @update:model-value="onFactorGroupSizeInput"
                    >
                      <template #append-inner>
                        <v-chip v-if="!factorGroupSizeExplicit" size="x-small" variant="tonal">Default</v-chip>
                        <v-btn
                          v-else
                          size="x-small"
                          variant="text"
                          class="px-1"
                          @click.stop="resetFactorGroupSize"
                        >Reset</v-btn>
                      </template>
                    </v-text-field>
                  </div>
                </v-expand-transition>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="options">
        <v-card class="glass-card">
          <v-card-text class="pa-6">
            <div class="d-flex flex-wrap justify-space-between ga-2 mb-4">
              <div class="text-body-2 text-medium-emphasis">At least two named options are required. Disabled options are excluded from comparisons.</div>
              <div class="d-flex flex-wrap ga-2 align-center">
                <v-btn size="small" variant="tonal" @click="addOption">
                  <i class="fa-solid fa-plus mr-2" /> Add option
                </v-btn>
                <v-btn size="small" variant="text" @click="openImportDialog('options')">
                  <i class="fa-solid fa-clone mr-2" /> Import from Template
                </v-btn>
                <v-btn
                  size="small"
                  variant="text"
                  :disabled="isNew"
                  :title="isNew ? 'Save the project before creating a template' : undefined"
                  @click="openSaveAsTemplate"
                >
                  <i class="fa-solid fa-floppy-disk mr-2" /> Save as Template
                </v-btn>
                <span
                  v-if="aiFeaturesEnabled"
                  :title="hasProvider ? undefined : providerDisabledMsg"
                >
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="primary"
                    :loading="generatingMissingOptions"
                    :disabled="!hasProvider || generatingMissingOptions || suggestingFactors || isBulkGenerating || !missingOptionCount || isNew"
                    @click="generateMissingOptionPrompts"
                  >
                    <i class="fa-solid fa-wand-magic-sparkles mr-2" />
                    {{ generatingMissingOptions ? `Generating... (${bulkOptionProgress.done}/${bulkOptionProgress.total})` : `Generate Missing Compare Prompts (${missingOptionCount})` }}
                  </v-btn>
                </span>
              </div>
              <v-progress-linear
                v-if="generatingMissingOptions"
                :model-value="bulkOptionProgress.total ? (bulkOptionProgress.done / bulkOptionProgress.total) * 100 : 0"
                color="primary"
                height="4"
                rounded
                class="mb-3 mt-2"
              />
              <div v-if="generatingMissingOptions" class="text-caption text-medium-emphasis mb-3">
                Generating {{ bulkOptionProgress.done }}/{{ bulkOptionProgress.total }} — {{ bulkOptionProgress.failed ? `${bulkOptionProgress.failed} failed` : 'progressing sequentially...' }}
              </div>
            </div>
            <div v-for="(opt, idx) in options" :key="idx" class="rank-row mb-3">
              <div class="d-flex ga-3 align-start">
                <div class="rank-number">{{ idx + 1 }}</div>
                <div class="flex-grow-1">
                  <v-text-field v-model="opt.title" label="Option title" density="compact" hide-details class="mb-2" />
                  <v-textarea v-model="opt.description" label="Description" rows="2" density="compact" hide-details class="mb-2" />
                  <v-text-field v-model="opt.compare_prompt" label="Compare prompt (concise, 2-5 words)" placeholder="Crisp label for comparison" density="compact" hide-details class="mb-2" counter="280" maxlength="280" />
                  <div class="d-flex flex-wrap ga-1 mb-2 align-center">
                    <span :title="hasProvider ? undefined : providerDisabledMsg">
                      <v-btn size="x-small" variant="tonal" color="primary" :disabled="!hasProvider || !opt.id || isAnyBulkGenerating" :loading="(opt as any)._generating" @click="generateOptionPrompt(idx)">
                        <i class="fa-solid fa-wand-magic-sparkles mr-1" /> Generate
                      </v-btn>
                    </span>
                    <v-btn size="x-small" variant="text" :disabled="!opt.compare_prompt || (opt as any)._generating" @click="opt.compare_prompt = ''">Clear</v-btn>
                    <span v-if="!opt.compare_prompt && !(opt as any)._bulkError" class="text-caption text-medium-emphasis ml-2">Original title/description used when blank</span>
                    <span v-if="!(opt as any)._generating && (opt as any)._bulkError" class="d-inline-flex align-center ga-1 ml-2">
                      <span class="text-caption text-error">{{ (opt as any)._bulkError }}</span>
                      <v-btn size="x-small" variant="text" color="error" :disabled="!opt.id || isAnyBulkGenerating" @click="generateOptionPrompt(idx)">Retry</v-btn>
                    </span>
                  </div>
                  <v-checkbox v-model="opt.disabled" label="Disabled (exclude from comparisons)" density="compact" hide-details color="warning" />
                </div>
                <v-btn icon variant="text" :disabled="options.length <= 2" @click="options.splice(idx, 1)">
                  <i class="fa-solid fa-trash" />
                </v-btn>
              </div>
            </div>
            <div class="d-flex justify-end mt-2">
              <v-btn size="small" variant="tonal" @click="addOption">
                <i class="fa-solid fa-plus mr-2" /> Add option
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="factors">
        <v-card class="glass-card">
          <v-card-text class="pa-6">
            <v-alert type="info" variant="tonal" class="mb-4">
              Factors show what matters when people compare options — the “why” behind the ranking.
            </v-alert>
            <div class="d-flex flex-wrap justify-space-between ga-2 mb-2">
              <v-radio-group v-model="factorMode" inline class="ma-0">
                <v-radio label="Overall only" value="overall" />
                <v-radio label="Multiple factors" value="multi" />
              </v-radio-group>
              <v-btn
                size="small"
                variant="text"
                :disabled="isNew"
                :title="isNew ? 'Save the project before creating a template' : undefined"
                @click="openSaveAsTemplate"
              >
                <i class="fa-solid fa-floppy-disk mr-2" /> Save as Template
              </v-btn>
            </div>

            <div v-if="aiFeaturesEnabled && factorMode === 'overall'" class="mb-4">
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                :disabled="!canSuggestFactors || suggestingFactors"
                :loading="suggestingFactors"
                :title="canSuggestFactors ? undefined : 'Add a project title and description first'"
                @click="suggestFactorsFromProblem"
              >
                <i class="fa-solid fa-wand-magic-sparkles mr-2" /> Suggest factors
              </v-btn>
            </div>
            <template v-if="factorMode === 'multi'">
              <div class="d-flex flex-wrap ga-2 mb-4 align-center">
                <v-btn size="small" variant="tonal" @click="addFactor">
                  <i class="fa-solid fa-plus mr-2" /> Add factor
                </v-btn>
                <v-btn size="small" variant="text" @click="openImportDialog('factors')">
                  <i class="fa-solid fa-clone mr-2" /> Import from Template
                </v-btn>
                <v-btn
                  v-if="aiFeaturesEnabled"
                  size="small"
                  variant="tonal"
                  color="primary"
                  :disabled="!canSuggestFactors || suggestingFactors || isAnyBulkGenerating"
                  :loading="suggestingFactors"
                  :title="canSuggestFactors ? undefined : 'Add a project title and description first'"
                  @click="suggestFactorsFromProblem"
                >
                  <i class="fa-solid fa-wand-magic-sparkles mr-2" /> Suggest factors
                </v-btn>
                <span
                  v-if="aiFeaturesEnabled && (hasMissing || generatingMissing)"
                  :title="hasProvider ? undefined : providerDisabledMsg"
                >
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="primary"
                    :loading="generatingMissing"
                    :disabled="!hasProvider || generatingMissing || generatingMissingOptions || suggestingFactors"
                    @click="generateMissingFactorQuestions"
                  >
                    <i class="fa-solid fa-wand-magic-sparkles mr-2" />
                    {{ generatingMissing ? `Generating... (${bulkProgress.done}/${bulkProgress.total})` : `Generate Missing Factor Questions (${missingCount})` }}
                  </v-btn>
                </span>
              </div>
              <v-progress-linear
                v-if="generatingMissing"
                :model-value="bulkProgress.total ? (bulkProgress.done / bulkProgress.total) * 100 : 0"
                color="primary"
                height="4"
                rounded
                class="mb-3"
              />
              <div v-if="generatingMissing" class="text-caption text-medium-emphasis mb-3">
                Generating {{ bulkProgress.done }}/{{ bulkProgress.total }} — {{ bulkProgress.failed ? `${bulkProgress.failed} failed` : 'progressing sequentially...' }}
              </div>
              <div v-for="(c, idx) in criteria" :key="idx" class="rank-row mb-3">
                <div class="d-flex ga-3 align-start">
                  <div class="flex-grow-1">
                    <v-text-field v-model="c.title" label="Factor title" density="compact" hide-details class="mb-2" />
                    <v-textarea v-model="c.description" label="Description" rows="2" density="compact" hide-details class="mb-2" />
                    <v-text-field
                      v-model="c.compare_prompt"
                      label="Compare prompt (concise 'Which ...?' question)"
                      placeholder='Enter a clear single question, like, "Which requires less engineering resources"'
                      hint="Title/description used when blank"
                      persistent-hint
                      counter="280"
                      maxlength="280"
                      density="compact"
                      class="mb-2"
                    />
                    <div class="d-flex flex-wrap ga-1 mb-2 align-center">
                      <span :title="hasProvider ? undefined : providerDisabledMsg">
                        <v-btn size="x-small" variant="tonal" color="primary" :disabled="!hasProvider || !c.id || isAnyBulkGenerating" :loading="(c as any)._generating" @click="generateFactorPrompt(idx)">
                          <i class="fa-solid fa-wand-magic-sparkles mr-1" /> Generate
                        </v-btn>
                      </span>
                      <v-btn size="x-small" variant="text" :disabled="!c.compare_prompt || (c as any)._generating" @click="c.compare_prompt = ''">Clear</v-btn>
                      <span v-if="!c.compare_prompt && !(c as any)._bulkError" class="text-caption text-medium-emphasis ml-2">Title/description used when blank</span>
                      <span v-if="!(c as any)._generating && (c as any)._bulkError" class="d-inline-flex align-center ga-1 ml-2">
                        <span class="text-caption text-error">{{ (c as any)._bulkError }}</span>
                        <v-btn size="x-small" variant="text" color="error" :disabled="!c.id || isAnyBulkGenerating" @click="generateFactorPrompt(idx)">Retry</v-btn>
                      </span>
                    </div>
                    <v-checkbox v-model="c.disabled" label="Disabled (exclude from comparisons)" density="compact" hide-details color="warning" />
                  </div>
                  <v-btn icon variant="text" @click="criteria.splice(idx, 1)"><i class="fa-solid fa-trash" /></v-btn>
                </div>
              </div>
              <div class="d-flex justify-end mt-2">
                <v-btn size="small" variant="tonal" @click="addFactor">
                  <i class="fa-solid fa-plus mr-2" /> Add factor
                </v-btn>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-window-item>

      <v-window-item value="review">
        <v-card class="glass-card">
          <v-card-text class="pa-6">
            <div class="text-h6 font-weight-bold mb-2">{{ form.project_title || 'Untitled project' }}</div>
            <div class="text-body-2 text-medium-emphasis mb-4">{{ form.project_description }}</div>
            <div class="d-flex flex-wrap ga-2 mb-4">
              <v-chip>{{ mode === 'exclusive' ? 'Pick one' : 'Rank all' }}</v-chip>
              <v-chip>{{ namedOptions.length }} options</v-chip>
              <v-chip>{{ factorMode === 'multi' ? namedCriteria.length + ' factors' : 'Overall only' }}</v-chip>
            </div>
            <v-alert v-if="validationError" type="error" variant="tonal" class="mb-4">{{ validationError }}</v-alert>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>

    <div class="d-flex justify-space-between mt-5">
      <v-btn variant="text" :disabled="tab === 'overview'" @click="prevTab">Back</v-btn>
      <div class="d-flex ga-2">
        <template v-if="tab !== 'review'">
          <v-btn
            v-if="!isNew"
            color="primary"
            variant="flat"
            :loading="saving"
            @click="save({ stay: true })"
          >
            Update
          </v-btn>
          <v-btn color="primary" variant="tonal" @click="nextTab">Continue</v-btn>
        </template>
        <template v-else>
          <v-btn
            color="primary"
            variant="tonal"
            :loading="saving"
            @click="save()"
          >
            {{ isNew ? 'Save' : 'Update' }}
          </v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="save({ startProbe: true })">
            {{ isNew ? 'Save' : 'Update' }} & start comparisons
          </v-btn>
        </template>
      </div>
    </div>

    <!-- Import picker -->
    <v-dialog v-model="importDialog" max-width="560">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">{{ importDialogTitle }}</span>
          <v-btn icon variant="text" size="small" @click="importDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <v-radio-group v-model="selectedTemplateId" :disabled="!importCandidates.length">
            <v-radio
              v-for="t in importCandidates"
              :key="t.id"
              :value="t.id"
              :label="t.factor_template_title || `Template ${t.id}`"
            >
              <template #label>
                <div>
                  <div>{{ t.factor_template_title || `Template ${t.id}` }}</div>
                  <div class="text-caption text-medium-emphasis">{{ t.factor_template_description || '' }}</div>
                </div>
              </template>
            </v-radio>
          </v-radio-group>
          <div v-if="!importCandidates.length" class="text-medium-emphasis">No templates available for this page.</div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="importDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!selectedTemplateId"
            @click="confirmImport"
          >
            {{ importConfirmLabel }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Copy from project -->
    <v-dialog v-model="copyFromDialog" max-width="560">
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Copy from project</span>
          <v-btn icon variant="text" size="small" @click="copyFromDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <div class="text-body-2 text-medium-emphasis mb-3">
            Copies the settings, options, and factors of an existing project into this new draft. Votes, shares, and schedules are not copied.
          </div>
          <v-text-field
            v-model="copyFromSearch"
            placeholder="Search projects"
            prepend-inner-icon="mdi-magnify"
            density="compact"
            hide-details
            clearable
            class="mb-3"
          />
          <div class="copy-from-list">
            <v-radio-group v-model="copyFromSelectedId" :disabled="!copyFromFiltered.length" hide-details class="ma-0">
              <v-radio v-for="item in copyFromFiltered" :key="item.project.id" :value="item.project.id">
                <template #label>
                  <div>
                    <div>{{ item.project.project_title || item.project.project_tag || `Project ${item.project.id}` }}</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ [item.project.project_tag, `${item.alternative_count || 0} option(s)`, `${item.factor_count || 0} factor(s)`].filter(Boolean).join(' · ') }}
                    </div>
                  </div>
                </template>
              </v-radio>
            </v-radio-group>
            <div v-if="!copyFromFiltered.length" class="text-medium-emphasis py-4">
              {{ copyFromCandidates.length ? 'No projects match your search.' : 'No projects available to copy from yet.' }}
            </div>
          </div>
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="copyFromDialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!copyFromSelectedId" @click="confirmCopyFromProject">Copy</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Save as template -->
    <v-dialog v-model="saveTemplateDialog" max-width="720" scrollable>
      <v-card class="pc-dialog-card">
        <v-card-title class="d-flex justify-space-between align-center pa-6 pb-2">
          <span class="text-h6 font-weight-bold font-display">Save as Template</span>
          <v-btn icon variant="text" size="small" @click="saveTemplateDialog = false"><i class="fa-solid fa-xmark" /></v-btn>
        </v-card-title>
        <v-card-text class="px-6 pt-2">
          <div class="template-note mb-4">
            <i class="fa-solid fa-copy mt-1" />
            <div>Creates a copy of the current project settings, options, and factors. Later edits stay independent.</div>
          </div>
          <v-text-field v-model="saveEditor.title" label="Template name" variant="outlined" class="mb-2" />
          <v-textarea v-model="saveEditor.description" label="Description" variant="outlined" rows="2" class="mb-3" />
          <div class="text-subtitle-2 mb-2">Offer for import on</div>
          <div class="d-flex flex-wrap ga-4 mb-4">
            <v-checkbox v-model="saveEditor.use_with_projects" label="Project" density="compact" hide-details color="primary" />
            <v-checkbox v-model="saveEditor.use_with_options" label="Options" density="compact" hide-details color="primary" />
            <v-checkbox v-model="saveEditor.use_with_factors" label="Factors" density="compact" hide-details color="primary" />
          </div>
          <div class="text-body-2 text-medium-emphasis mb-2">
            Includes {{ namedOptions.length }} option(s),
            {{ factorMode === 'multi' ? namedCriteria.length : 0 }} factor(s),
            mode {{ mode === 'exclusive' ? 'Choose one' : 'Rank all' }},
            private participation {{ form.private_participation ? 'on' : 'off' }}.
          </div>
          <v-switch
            v-if="isSystemAdmin"
            v-model="saveEditor.enable_global_share"
            label="Globally shared"
            color="primary"
            hint="Visible to all workspaces. System admin only."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions class="px-6 pb-5 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="saveTemplateDialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="savingTemplate" @click="confirmSaveAsTemplate">Save template</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import type { FactorTemplate, ProjectListSummaryItem } from '~/types/api'
import { formatEndDateMdY, localEndTimeIso } from '~/utils/projectEndTime'
import {
  DEFAULT_QUESTIONS_PER_GROUP,
  clampMaxRecommendedPasses,
  clampMinExpectedPasses,
  clampQuestionsPerGroup,
  defaultQuestionsPerGroupForN,
  questionBudgetBounds,
} from '~/utils/sortCompare'

const route = useRoute()
const api = useProjectsApi()
const brandingApi = useBrandingApi()
const snackbar = useSnackbar()
const { requireAdmin, isSystemAdmin, isAdmin, aiFeaturesEnabled } = useAuth()
const { apiFetch } = useApi()
const suggestingFactors = ref(false)
const loadingAiModels = ref(false)
const aiCatalog = ref<Array<{ id: string, name: string }>>([])
const aiCatalogDefault = ref<string | null>(null)
const aiCatalogDefaultIsSystem = ref(false)
const aiCatalogError = ref('')
const DEFAULT_AI_MODEL_KEY = '__default__'
const aiVoterItems = computed(() => {
  const rows = [
    { title: 'AI AGENT: Default Model', value: DEFAULT_AI_MODEL_KEY },
    ...aiCatalog.value.map(m => ({ title: `AI AGENT: ${m.name || m.id}`, value: m.id })),
  ]
  const seen = new Set<string>()
  return rows.filter((row) => {
    if (seen.has(row.value)) return false
    seen.add(row.value)
    return true
  })
})
const aiVoterHint = computed(() => {
  if (aiCatalogError.value) return aiCatalogError.value
  if (!aiCatalog.value.length) return 'Configure an AI provider in Settings, or use the system default model.'
  return 'Select unique models. Default Model uses the workspace or system setting.'
})

async function loadAiVoterCatalog() {
  if (!aiFeaturesEnabled.value) return
  loadingAiModels.value = true
  aiCatalogError.value = ''
  try {
    const res = await apiFetch<{
      failure_reason?: string
      models?: Array<{ id: string, name: string }>
      default_model?: string | null
      default_is_system?: boolean
    }>('/ws/core/llm-available-models')
    if (res.failure_reason) {
      aiCatalogError.value = res.failure_reason
      return
    }
    aiCatalog.value = res.models || []
    aiCatalogDefault.value = res.default_model || null
    aiCatalogDefaultIsSystem.value = !!res.default_is_system
    if (form.include_ai_agents && !form.ai_voter_models.length) {
      form.ai_voter_models = [aiCatalogDefaultIsSystem.value ? DEFAULT_AI_MODEL_KEY : (aiCatalogDefault.value || DEFAULT_AI_MODEL_KEY)]
    }
  }
  catch (e: unknown) {
    aiCatalogError.value = e instanceof Error ? e.message : 'Could not load models'
  }
  finally {
    loadingAiModels.value = false
  }
}
const canSuggestFactors = computed(() =>
  !!aiFeaturesEnabled.value
  && !!(form.project_title || '').trim()
  && !!(form.project_description || '').trim(),
)

const hasProvider = ref(false)
const providerDisabledMsg = 'There is no provider set up for this customer, check settings to enable'
const generatingPrompts = ref(false)
const promptGenMessage = ref('')
const promptGenOk = ref(false)

// Bulk generate missing factor questions (project-factor-settings-lkb6vk)
const generatingMissing = ref(false)
const bulkAbort = ref(false)
const bulkProgress = reactive({ done: 0, total: 0, failed: 0 })

function isEmptyFactorQuestion(c: ContentRow): boolean {
  return !((c.compare_prompt || '').trim())
}

const emptyFactorIndices = computed(() => {
  if (factorMode.value !== 'multi') return [] as number[]
  const out: number[] = []
  criteria.value.forEach((c, i) => {
    if (!c.id) return
    if (c.disabled) return
    if (!isEmptyFactorQuestion(c)) return
    out.push(i)
  })
  return out
})
const missingCount = computed(() => emptyFactorIndices.value.length)
const hasMissing = computed(() => aiFeaturesEnabled.value && factorMode.value === 'multi' && !isNew.value && missingCount.value > 0)
const isBulkGenerating = computed(() => generatingMissing.value)

// Bulk generate missing option prompts — mirrors Factors bulk flow
const generatingMissingOptions = ref(false)
const bulkOptionAbort = ref(false)
const bulkOptionProgress = reactive({ done: 0, total: 0, failed: 0 })

function isEmptyOptionPrompt(opt: ContentRow): boolean {
  return !((opt.compare_prompt || '').trim())
}

const emptyOptionIndices = computed(() => {
  const out: number[] = []
  options.value.forEach((o, i) => {
    if (!o.id) return
    if (o.disabled) return
    if (!isEmptyOptionPrompt(o)) return
    out.push(i)
  })
  return out
})
const missingOptionCount = computed(() => emptyOptionIndices.value.length)
const hasMissingOptions = computed(() => aiFeaturesEnabled.value && !isNew.value && missingOptionCount.value > 0)
const isAnyBulkGenerating = computed(() => generatingMissing.value || generatingMissingOptions.value)

async function loadProviderStatus() {
  try {
    const res = await apiFetch<{ failure_reason?: string, ai_provider?: string | null, key_configured?: boolean }>('/ws/core/customer-ai-settings')
    if (res.failure_reason) { hasProvider.value = false; return }
    hasProvider.value = !!(res.ai_provider && res.key_configured)
  } catch { hasProvider.value = false }
}

async function generateConcisePrompts() {
  if (!hasProvider.value) { snackbar.error(providerDisabledMsg); return }
  generatingPrompts.value = true
  promptGenMessage.value = ''
  // eslint-disable-next-line no-console
  console.info('bulk_generate_concise_prompts:start', { project_id: projectId.value })
  postUiLog('bulk_generate_concise_prompts:start', 'info', { project_id: projectId.value })
  try {
    const res = await api.generateComparePrompts(projectId.value)
    if (res.failure_reason) throw new Error(res.failure_reason)
    promptGenOk.value = true
    promptGenMessage.value = 'Auto generate or refine questions has been done.'
    snackbar.success(promptGenMessage.value)
    // eslint-disable-next-line no-console
    console.info('bulk_generate_concise_prompts:done', { project_id: projectId.value, queued: res.queued, failed: res.failed, skipped: res.skipped_existing })
    postUiLog('bulk_generate_concise_prompts:done', res.failed ? 'warning' : 'info', { queued: res.queued, failed: res.failed, skipped: res.skipped_existing })
    await loadContentRows(projectId.value, true)
  } catch (e: unknown) {
    promptGenOk.value = false
    promptGenMessage.value = e instanceof Error ? e.message : 'Could not generate prompts'
    snackbar.error(promptGenMessage.value)
    // eslint-disable-next-line no-console
    console.info('bulk_generate_concise_prompts:failed', { project_id: projectId.value, error: promptGenMessage.value })
    postUiLog(`bulk_generate_concise_prompts failed: ${promptGenMessage.value.slice(0,200)}`, 'warning', { error: promptGenMessage.value.slice(0,300) })
  } finally { generatingPrompts.value = false }
}

async function clearConcisePrompts() {
  if (isNew.value) { options.value.forEach(o => o.compare_prompt = ''); criteria.value.forEach(c => c.compare_prompt = ''); return }
  try {
    const res = await api.clearComparePrompts(projectId.value)
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Compare prompts cleared')
    await loadContentRows(projectId.value, true)
  } catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not clear prompts')
  }
}

async function postUiLog(message: string, severity: 'info' | 'warning' | 'error' = 'info', kw: Record<string, unknown> = {}) {
  const sevMap: Record<string, number> = { debug: 0, info: 1, warning: 2, error: 3, critical: 4 }
  const sev = sevMap[severity] ?? 1
  try {
    await apiFetch('/ws/log/post-log-event', {
      method: 'POST',
      body: {
        severity: sev,
        log_message: message,
        kw_details: { project_id: projectId.value, ...kw },
        computer_name: 'client:factor-generate',
      },
    })
  } catch { /* best-effort observability */ }
}

async function generateOptionPrompt(idx: number) {
  const row = options.value[idx]
  if (!row?.id || !hasProvider.value) return
  ;(row as any)._generating = true
  ;(row as any)._bulkError = ''
  try {
    const res = await api.generateAlternativePrompt(row.id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    const prompt = (res.compare_prompt || '').trim()
    if (!prompt) throw new Error('No prompt generated')
    row.compare_prompt = prompt
    snackbar.success('Option prompt generated')
    // eslint-disable-next-line no-console
    console.info('single_generate_option_question', { option_id: row.id, project_id: projectId.value })
    postUiLog('single_generate_option_question:done', 'info', { option_id: row.id, prompt_len: (res.compare_prompt || '').length })
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Could not generate'
    ;(row as any)._bulkError = msg
    snackbar.error(msg)
    // eslint-disable-next-line no-console
    console.info('single_generate_option_question:failed', { option_id: row.id, project_id: projectId.value, error: msg })
    postUiLog(`single_generate_option_question failed: ${msg.slice(0,200)}`, 'warning', { option_id: row.id, error: msg.slice(0,300) })
  } finally { (row as any)._generating = false }
}

async function generateMissingOptionPrompts() {
  if (!hasProvider.value) { snackbar.error(providerDisabledMsg); return }
  if (generatingMissingOptions.value || generatingMissing.value || suggestingFactors.value) return
  if (!missingOptionCount.value) return
  const targets = [...emptyOptionIndices.value]
  if (!targets.length) return
  generatingMissingOptions.value = true
  bulkOptionAbort.value = false
  bulkOptionProgress.done = 0
  bulkOptionProgress.total = targets.length
  bulkOptionProgress.failed = 0
  // eslint-disable-next-line no-console
  console.info('bulk_generate_option_questions:start', { total: targets.length, project_id: projectId.value })
  postUiLog('bulk_generate_option_questions:start', 'info', { total: targets.length, option_ids: targets.map(i => (options.value[i] as any)?.id).filter(Boolean) })
  for (let ti = 0; ti < targets.length; ti++) {
    if (bulkOptionAbort.value) break
    const idx = targets[ti]
    const row = options.value[idx] as ContentRow & { _generating?: boolean, _bulkError?: string }
    if (!row || !row.id || row.disabled) { bulkOptionProgress.done++; continue }
    if (!isEmptyOptionPrompt(row)) { bulkOptionProgress.done++; continue }
    ;(row as any)._generating = true
    ;(row as any)._bulkError = ''
    try {
      const res = await api.generateAlternativePrompt(row.id)
      if (res.failure_reason) throw new Error(res.failure_reason)
      const prompt = (res.compare_prompt || '').trim()
      if (!prompt) throw new Error('No prompt generated')
      row.compare_prompt = prompt
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not generate'
      ;(row as any)._bulkError = msg
      bulkOptionProgress.failed++
      // eslint-disable-next-line no-console
      console.info('bulk_generate_option_questions:item_failed', { option_id: row.id, project_id: projectId.value, error: msg })
      postUiLog(`bulk_generate_option_questions:item_failed option ${row.id}: ${msg.slice(0,200)}`, 'warning', { option_id: row.id, error: msg.slice(0,300), index: ti, total: targets.length })
    } finally {
      ;(row as any)._generating = false
      bulkOptionProgress.done++
      await nextTick()
    }
    if (bulkOptionAbort.value) break
    if (ti < targets.length - 1) {
      await new Promise<void>(resolve => setTimeout(resolve, 400))
      if (bulkOptionAbort.value) break
    }
  }
  const succeeded = bulkOptionProgress.done - bulkOptionProgress.failed
  // eslint-disable-next-line no-console
  console.info('bulk_generate_option_questions:done', { total: bulkOptionProgress.total, succeeded, failed: bulkOptionProgress.failed, project_id: projectId.value })
  if (bulkOptionAbort.value) {
    postUiLog('bulk_generate_option_questions:aborted', 'warning', { total: bulkOptionProgress.total, succeeded, failed: bulkOptionProgress.failed })
  } else if (bulkOptionProgress.failed > 0) {
    snackbar.error(`Generated ${succeeded}/${bulkOptionProgress.total}, ${bulkOptionProgress.failed} failed – see inline errors`)
    postUiLog(`bulk_generate_option_questions:done with failures succeeded=${succeeded} failed=${bulkOptionProgress.failed}`, 'warning', { total: bulkOptionProgress.total, succeeded, failed: bulkOptionProgress.failed })
  } else if (bulkOptionProgress.done > 0) {
    snackbar.success(`Generated ${succeeded}/${bulkOptionProgress.total} option prompt${succeeded === 1 ? '' : 's'}`)
    postUiLog('bulk_generate_option_questions:done success', 'info', { total: bulkOptionProgress.total, succeeded, failed: bulkOptionProgress.failed })
  } else {
    postUiLog('bulk_generate_option_questions:done no work', 'info', { total: bulkOptionProgress.total })
  }
  generatingMissingOptions.value = false
}

async function generateFactorPrompt(idx: number) {
  const row = criteria.value[idx]
  if (!row?.id || !hasProvider.value) return
  ;(row as any)._generating = true
  ;(row as any)._bulkError = ''
  try {
    const res = await api.generateFactorPrompt(row.id)
    if (res.failure_reason) throw new Error(res.failure_reason)
    row.compare_prompt = res.compare_prompt || ''
    snackbar.success('Factor prompt generated')
    // eslint-disable-next-line no-console
    console.info('single_generate_factor_question', { factor_id: row.id, project_id: projectId.value })
    postUiLog('single_generate_factor_question:done', 'info', { factor_id: row.id, prompt_len: (res.compare_prompt || '').length })
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Could not generate'
    ;(row as any)._bulkError = msg
    snackbar.error(msg)
    // eslint-disable-next-line no-console
    console.info('single_generate_factor_question:failed', { factor_id: row.id, project_id: projectId.value, error: msg })
    postUiLog(`single_generate_factor_question failed: ${msg.slice(0,200)}`, 'warning', { factor_id: row.id, error: msg.slice(0,300) })
  } finally { (row as any)._generating = false }
}

async function generateMissingFactorQuestions() {
  if (!hasProvider.value) { snackbar.error(providerDisabledMsg); return }
  if (generatingMissing.value || suggestingFactors.value) return
  if (!missingCount.value) return
  const targets = [...emptyFactorIndices.value]
  if (!targets.length) return
  generatingMissing.value = true
  bulkAbort.value = false
  bulkProgress.done = 0
  bulkProgress.total = targets.length
  bulkProgress.failed = 0
  // eslint-disable-next-line no-console
  console.info('bulk_generate_factor_questions:start', { total: targets.length, project_id: projectId.value })
  postUiLog('bulk_generate_factor_questions:start', 'info', { total: targets.length, factor_ids: targets.map(i => (criteria.value[i] as any)?.id).filter(Boolean) })
  for (let ti = 0; ti < targets.length; ti++) {
    if (bulkAbort.value) break
    const idx = targets[ti]
    const row = criteria.value[idx] as ContentRow & { _generating?: boolean, _bulkError?: string }
    if (!row || !row.id || row.disabled) { bulkProgress.done++; continue }
    if (!isEmptyFactorQuestion(row)) { bulkProgress.done++; continue }
    ;(row as any)._generating = true
    ;(row as any)._bulkError = ''
    try {
      const res = await api.generateFactorPrompt(row.id)
      if (res.failure_reason) throw new Error(res.failure_reason)
      const prompt = (res.compare_prompt || '').trim()
      if (!prompt) throw new Error('No question generated')
      row.compare_prompt = prompt
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not generate'
      ;(row as any)._bulkError = msg
      bulkProgress.failed++
      // eslint-disable-next-line no-console
      console.info('bulk_generate_factor_questions:item_failed', { factor_id: row.id, project_id: projectId.value, error: msg })
      postUiLog(`bulk_generate_factor_questions:item_failed factor ${row.id}: ${msg.slice(0,200)}`, 'warning', { factor_id: row.id, error: msg.slice(0,300), index: ti, total: targets.length })
    } finally {
      ;(row as any)._generating = false
      bulkProgress.done++
      await nextTick()
    }
    if (bulkAbort.value) break
    if (ti < targets.length - 1) {
      await new Promise<void>(resolve => setTimeout(resolve, 400))
      if (bulkAbort.value) break
    }
  }
  const succeeded = bulkProgress.done - bulkProgress.failed
  // eslint-disable-next-line no-console
  console.info('bulk_generate_factor_questions:done', { total: bulkProgress.total, succeeded, failed: bulkProgress.failed, project_id: projectId.value })
  if (bulkAbort.value) {
    postUiLog('bulk_generate_factor_questions:aborted', 'warning', { total: bulkProgress.total, succeeded, failed: bulkProgress.failed })
  } else if (bulkProgress.failed > 0) {
    snackbar.error(`Generated ${succeeded}/${bulkProgress.total}, ${bulkProgress.failed} failed – see inline errors`)
    postUiLog(`bulk_generate_factor_questions:done with failures succeeded=${succeeded} failed=${bulkProgress.failed}`, 'warning', { total: bulkProgress.total, succeeded, failed: bulkProgress.failed })
  } else if (bulkProgress.done > 0) {
    snackbar.success(`Generated ${succeeded}/${bulkProgress.total} factor question${succeeded === 1 ? '' : 's'}`)
    postUiLog('bulk_generate_factor_questions:done success', 'info', { total: bulkProgress.total, succeeded, failed: bulkProgress.failed })
  } else {
    postUiLog('bulk_generate_factor_questions:done no work', 'info', { total: bulkProgress.total })
  }
  generatingMissing.value = false
}

function abortBulkGenerate() {
  if (generatingMissing.value) bulkAbort.value = true
  if (generatingMissingOptions.value) bulkOptionAbort.value = true
}

function abortBulkOptionGenerate() {
  if (generatingMissingOptions.value) bulkOptionAbort.value = true
}

onBeforeUnmount(() => {
  abortBulkGenerate()
})

async function suggestFactorsFromProblem() {
  if (!requireAdmin() || !canSuggestFactors.value) return
  const named = namedCriteria.value.filter(c => c.title.trim())
  if (named.length && !window.confirm('Replace the current unsaved factors with AI suggestions?')) return
  suggestingFactors.value = true
  try {
    const res = await api.suggestFactors({
      project_id: isNew.value ? 0 : projectId.value,
      project_title: form.project_title,
      project_description: form.project_description,
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    const rows = res.suggestions || []
    if (!rows.length) throw new Error('No factors were suggested')
    factorMode.value = 'multi'
    criteria.value = rows.map(r => ({
      title: r.title || '',
      description: r.description || '',
      compare_prompt: '',
      disabled: false,
    }))
    snackbar.success('Suggested factors added. Review, then save.')
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not suggest factors')
  }
  finally {
    suggestingFactors.value = false
  }
}

const projectId = computed(() => Number(route.params.id))
const isNew = computed(() => !projectId.value || projectId.value <= 0)

const projectBrandFileInput = ref<HTMLInputElement | null>(null)
const projectBrandHasImage = ref(false)
const projectBrandingPreview = ref('')
const projectBrandUploading = ref(false)
const projectBrandDeleting = ref(false)
const projectBrandError = ref('')

async function loadProjectBranding() {
  if (isNew.value) return
  projectBrandError.value = ''
  try {
    const res = await brandingApi.projectMeta(projectId.value)
    projectBrandHasImage.value = !!res.has_image
    projectBrandingPreview.value = res.has_image
      ? brandingApi.projectImageUrl(projectId.value, res.modify_date || Date.now())
      : ''
  }
  catch {
    projectBrandHasImage.value = false
    projectBrandingPreview.value = ''
  }
}

async function onProjectBrandFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || isNew.value) return
  if (file.size > 8 * 1_048_576) {
    projectBrandError.value = 'Image must be 8 MB or smaller'
    return
  }
  projectBrandUploading.value = true
  projectBrandError.value = ''
  try {
    const res = await brandingApi.uploadProjectImage(projectId.value, file)
    if (res.failure_reason) {
      projectBrandError.value = res.failure_reason
      return
    }
    projectBrandHasImage.value = true
    projectBrandingPreview.value = brandingApi.projectImageUrl(projectId.value, res.modify_date || Date.now())
    snackbar.success('Project branding image saved')
  }
  catch (e: unknown) {
    projectBrandError.value = e instanceof Error ? e.message : 'Upload failed'
  }
  finally {
    projectBrandUploading.value = false
  }
}

async function onDeleteProjectBrand() {
  if (isNew.value) return
  projectBrandDeleting.value = true
  projectBrandError.value = ''
  try {
    const res = await brandingApi.deleteProjectImage(projectId.value)
    if (res.failure_reason) {
      projectBrandError.value = res.failure_reason
      return
    }
    projectBrandHasImage.value = false
    projectBrandingPreview.value = ''
    snackbar.success('Project branding image removed')
  }
  catch (e: unknown) {
    projectBrandError.value = e instanceof Error ? e.message : 'Delete failed'
  }
  finally {
    projectBrandDeleting.value = false
  }
}
const duplicateFromId = computed(() => {
  const raw = route.query.from
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isFinite(n) && n > 0 ? n : 0
})
const isDuplicateDraft = ref(false)

const tab = ref('overview')
const tabs = ['overview', 'options', 'factors', 'review']

watch(tab, (val) => {
  if (generatingMissing.value || generatingMissingOptions.value) abortBulkGenerate()
  if (val !== 'back-overview') return
  tab.value = 'overview'
  goToProjectOverview()
})
const saving = ref(false)
const loadingDraft = ref(false)

const form = reactive({
  project_title: '',
  project_tag: '',
  project_description: '',
  disabled: false,
  end_time: null as string | null,
  private_participation: false,
  participant_influence_mode: 'comparisons' as 'comparisons' | 'balanced' | 'participants_normalized',
  participant_influence_min_comparisons: 10,
  factor_weight_floor_alpha: 0.5,
  min_expected_passes: 2,
  max_recommended_passes: 2,
  include_ai_agents: false,
  ai_voter_models: [] as string[],
  option_questions_per_group: DEFAULT_QUESTIONS_PER_GROUP,
  factor_questions_per_group: DEFAULT_QUESTIONS_PER_GROUP,
  project_criteria_template: 0,
})
const optionGroupSizeExplicit = ref(false)
const factorGroupSizeExplicit = ref(false)
const syncingGroupSize = ref(false)
const privateParticipationLocked = ref(false)
const advancedOpen = ref(false)
const endTimeMenu = ref(false)
const endTimeMin = computed(() => {
  const n = new Date()
  return new Date(n.getFullYear(), n.getMonth(), n.getDate())
})
const endTimeDisplay = computed(() => form.end_time ? formatEndDateMdY(form.end_time) : 'None')
const endTimePicker = computed({
  get() {
    if (!form.end_time) return null
    const d = new Date(form.end_time)
    return Number.isNaN(d.getTime()) ? null : d
  },
  set(value: Date | string | null) {
    applyEndDate(value)
  },
})

function applyEndDate(value: Date | string | null | undefined) {
  if (!value) {
    form.end_time = null
    return
  }
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return
  form.end_time = localEndTimeIso(d)
}

function onEndDatePicked(value: Date | string | null) {
  applyEndDate(value)
  if (value) endTimeMenu.value = false
}

function clearEndTime() {
  form.end_time = null
  endTimeMenu.value = false
}
const mode = ref<'exclusive' | 'rank'>('exclusive')
const rankingMode = ref<'find_best' | 'find_top_3' | 'find_top_half' | 'rank_all'>('rank_all')
const rankingModeHint = computed(() => {
  if (rankingMode.value === 'find_best') return 'Concentrate comparisons on identifying the single best option.'
  if (rankingMode.value === 'find_top_3') return 'Concentrate comparisons around the top-three boundary. Available with six or more options.'
  if (rankingMode.value === 'find_top_half') return 'Concentrate comparisons on separating the top half of options.'
  return 'Spend the question budget on a full ranking from best to worst.'
})
watch(rankingMode, (v) => {
  mode.value = v === 'find_best' ? 'exclusive' : 'rank'
})
const factorMode = ref<'overall' | 'multi'>('overall')

function clampFactorWeightFloorAlpha(value: unknown): number {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0.5
  return Math.min(0.9, Math.max(0.1, Math.round(n * 20) / 20))
}

const maxPassesFloor = computed(() => clampMinExpectedPasses(form.min_expected_passes))

watch(() => form.min_expected_passes, (v) => {
  const mn = clampMinExpectedPasses(v)
  if (form.max_recommended_passes < mn) form.max_recommended_passes = mn
})

const privateParticipationSwitchDisabled = computed(
  () => privateParticipationLocked.value && !isSystemAdmin.value,
)
const privateParticipationHint = computed(() => {
  const base = 'When on, reports show unique participant 1, 2, … instead of names. Locked once comparisons are collected.'
  if (!privateParticipationLocked.value) return base
  if (isSystemAdmin.value) {
    return `${base} System Admin - This can be reversed`
  }
  return `${base} Locked.`
})
const influenceModeHint = computed(() => {
  if (form.participant_influence_mode === 'balanced') {
    return 'Moderately reduces the pull of participants who made many more comparisons.'
  }
  if (form.participant_influence_mode === 'participants_normalized') {
    return 'Strongly normalizes influence across participants (not fully equal). Best when contribution volume varies widely.'
  }
  return 'Every comparison counts the same (default). Heavy contributors have more total influence.'
})

type ContentRow = {
  id?: number
  title: string
  description: string
  compare_prompt?: string
  disabled: boolean
}

const options = ref<ContentRow[]>([
  { title: '', description: '', compare_prompt: '', disabled: false },
  { title: '', description: '', compare_prompt: '', disabled: false },
])
const criteria = ref<ContentRow[]>([{ title: '', description: '', compare_prompt: '', disabled: false }])
const existingTag = ref('')

// Import dialog
type ImportScope = 'projects' | 'options' | 'factors'
const importDialog = ref(false)
const importScope = ref<ImportScope>('factors')
const importCandidates = ref<FactorTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)
const allTemplates = ref<FactorTemplate[]>([])

const importDialogTitle = computed(() => {
  if (importScope.value === 'projects') return 'Start with Template'
  if (importScope.value === 'options') return 'Import Options from Template'
  return 'Import Factors from Template'
})
const importConfirmLabel = computed(() => {
  if (importScope.value === 'projects') return 'Import'
  if (importScope.value === 'options') return 'Import Options'
  return 'Import Factors'
})

// Save as template
const saveTemplateDialog = ref(false)
const savingTemplate = ref(false)
const saveEditor = reactive({
  title: '',
  description: '',
  use_with_projects: true,
  use_with_options: true,
  use_with_factors: true,
  enable_global_share: false,
})

function addOption() {
  options.value.push({ title: '', description: '', compare_prompt: '', disabled: false })
}
function addFactor() {
  criteria.value.push({ title: '', description: '', compare_prompt: '', disabled: false })
}

const namedOptions = computed(() => options.value.filter(o => o.title.trim()))
const namedCriteria = computed(() => criteria.value.filter(c => c.title.trim()))
const activeOptionCount = computed(() => namedOptions.value.filter(o => !o.disabled).length)
const activeFactorCount = computed(() => (
  factorMode.value === 'multi' ? namedCriteria.value.filter(c => !c.disabled).length : 0
))
const optionQuestionBounds = computed(() => questionBudgetBounds(activeOptionCount.value))
const factorQuestionBounds = computed(() => questionBudgetBounds(activeFactorCount.value))
const optionQuestionHint = computed(() => {
  const b = optionQuestionBounds.value
  const n = activeOptionCount.value
  const mode = optionGroupSizeExplicit.value ? 'Custom value.' : 'Default is about two-thirds of the estimate.'
  if (b.max <= 0) return `Add at least two options to set a range. ${mode}`
  return `Ford–Johnson estimate for ${n} option${n === 1 ? '' : 's'} is ${b.estimate}. Allowed range ${b.min}–${b.max}. ${mode}`
})
const factorQuestionHint = computed(() => {
  const b = factorQuestionBounds.value
  const n = activeFactorCount.value
  const mode = factorGroupSizeExplicit.value ? 'Custom value.' : 'Default is about two-thirds of the estimate.'
  if (b.max <= 0) return `Available when two or more factors are named. ${mode}`
  return `Ford–Johnson estimate for ${n} factor${n === 1 ? '' : 's'} is ${b.estimate}. Allowed range ${b.min}–${b.max}. ${mode}`
})
function withGroupSizeSync(fn: () => void) {
  syncingGroupSize.value = true
  try { fn() }
  finally {
    nextTick(() => { syncingGroupSize.value = false })
  }
}
function onOptionGroupSizeInput() {
  if (!syncingGroupSize.value) optionGroupSizeExplicit.value = true
}
function onFactorGroupSizeInput() {
  if (!syncingGroupSize.value) factorGroupSizeExplicit.value = true
}
function resetOptionGroupSize() {
  withGroupSizeSync(() => {
    optionGroupSizeExplicit.value = false
    form.option_questions_per_group = defaultQuestionsPerGroupForN(activeOptionCount.value)
  })
}
function resetFactorGroupSize() {
  withGroupSizeSync(() => {
    factorGroupSizeExplicit.value = false
    form.factor_questions_per_group = defaultQuestionsPerGroupForN(activeFactorCount.value)
  })
}
watch(activeOptionCount, (n) => {
  withGroupSizeSync(() => {
    form.option_questions_per_group = optionGroupSizeExplicit.value
      ? clampQuestionsPerGroup(form.option_questions_per_group, n)
      : defaultQuestionsPerGroupForN(n)
  })
  if (n < 6 && rankingMode.value === 'find_top_3') rankingMode.value = 'find_best'
})
watch(activeFactorCount, (n) => {
  withGroupSizeSync(() => {
    form.factor_questions_per_group = factorGroupSizeExplicit.value
      ? clampQuestionsPerGroup(form.factor_questions_per_group, n)
      : defaultQuestionsPerGroupForN(n)
  })
})
const validationError = computed(() => {
  if (!form.project_title.trim()) return 'Name the project.'
  if (!form.project_tag.trim()) return 'Provide a short unique tag.'
  if (namedOptions.value.length < 2) return 'Add at least two named options.'
  if (factorMode.value === 'multi' && !namedCriteria.value.length) return 'Name at least one factor, or choose overall only.'
  return ''
})

function goToProjectOverview() {
  if (isNew.value) return
  navigateTo(`/projects/${projectId.value}`)
}

function nextTab() {
  const i = tabs.indexOf(tab.value)
  if (tab.value === 'overview' && !form.project_title.trim()) {
    snackbar.error('Name the project before continuing.')
    return
  }
  if (tab.value === 'options' && namedOptions.value.length < 2) {
    snackbar.error('Add at least two named options.')
    return
  }
  if (i < tabs.length - 1) tab.value = tabs[i + 1]
}

function prevTab() {
  const i = tabs.indexOf(tab.value)
  if (i > 0) tab.value = tabs[i - 1]
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || `project-${Date.now().toString(36)}`
}

watch(() => form.project_title, (v) => {
  if (isNew.value && !existingTag.value) form.project_tag = slugify(v || '')
})

async function openImportDialog(scope: ImportScope) {
  importScope.value = scope
  selectedTemplateId.value = null
  try {
    const res = await api.listTemplates(true, scope)
    importCandidates.value = res.factor_template_info_list || []
  }
  catch {
    importCandidates.value = allTemplates.value.filter((t) => {
      if (scope === 'projects') return !!t.use_with_projects
      if (scope === 'options') return !!t.use_with_options
      return t.use_with_factors !== false
    })
  }
  importDialog.value = true
}

function applyFactorsFromTemplate(t: FactorTemplate) {
  criteria.value = (t.factor_template_entries || []).map(e => ({
    title: e.factor_title || '',
    description: e.factor_description || '',
    compare_prompt: (e as any).compare_prompt || '',
    disabled: false,
  }))
  if (!criteria.value.length) criteria.value = [{ title: '', description: '', compare_prompt: '', disabled: false }]
  factorMode.value = criteria.value.some(c => c.title.trim()) ? 'multi' : factorMode.value
}

function applyOptionsFromTemplate(t: FactorTemplate) {
  const opts = (t.option_template_entries || []).map(e => ({
    title: e.alternative_title || '',
    description: e.alternative_description || '',
    disabled: false,
  })).filter(o => o.title.trim())
  if (opts.length) {
    options.value = opts.length >= 2 ? opts : [...opts, { title: '', description: '', disabled: false }]
  }
}

function confirmImport() {
  const t = importCandidates.value.find(x => x.id === selectedTemplateId.value)
  if (!t) return
  if (importScope.value === 'projects') {
    if (t.factor_template_description) {
      form.project_description = t.factor_template_description
    }
    mode.value = t.project_exclusive_mode ? 'exclusive' : 'rank'
    form.private_participation = !!t.private_participation
    applyOptionsFromTemplate(t)
    applyFactorsFromTemplate(t)
    form.project_criteria_template = t.id
    snackbar.success('Template imported into project')
  }
  else if (importScope.value === 'options') {
    applyOptionsFromTemplate(t)
    if (!(t.option_template_entries || []).length) {
      snackbar.error('This template has no options to import')
      return
    }
    snackbar.success('Options imported from template')
  }
  else {
    applyFactorsFromTemplate(t)
    form.project_criteria_template = t.id
    snackbar.success('Factors imported from template')
  }
  importDialog.value = false
}

function openSaveAsTemplate() {
  if (isNew.value) {
    snackbar.error('Save the project before creating a template')
    return
  }
  if (!requireAdmin()) return
  saveEditor.title = form.project_title.trim() ? `${form.project_title.trim()} template` : ''
  saveEditor.description = form.project_description.trim()
  saveEditor.use_with_projects = true
  saveEditor.use_with_options = namedOptions.value.length > 0
  saveEditor.use_with_factors = factorMode.value === 'multi' && namedCriteria.value.length > 0
  saveEditor.enable_global_share = false
  saveTemplateDialog.value = true
}

async function confirmSaveAsTemplate() {
  if (!requireAdmin()) return
  if (!saveEditor.title.trim()) {
    snackbar.error('Template name is required')
    return
  }
  savingTemplate.value = true
  try {
    const res = await api.createTemplate({
      factor_template_title: saveEditor.title.trim(),
      factor_template_description: saveEditor.description.trim(),
      factor_template_entries: factorMode.value === 'multi'
        ? namedCriteria.value.map(c => ({
            factor_title: c.title.trim(),
            factor_description: c.description.trim(),
          }))
        : [],
      option_template_entries: namedOptions.value.map(o => ({
        alternative_title: o.title.trim(),
        alternative_description: o.description.trim(),
      })),
      use_with_projects: saveEditor.use_with_projects,
      use_with_options: saveEditor.use_with_options,
      use_with_factors: saveEditor.use_with_factors,
      project_exclusive_mode: mode.value === 'exclusive',
      private_participation: form.private_participation,
      ...(isSystemAdmin.value ? { enable_global_share: saveEditor.enable_global_share } : {}),
    })
    if (res.failure_reason) throw new Error(res.failure_reason)
    snackbar.success('Template saved')
    saveTemplateDialog.value = false
    const tmpls = await api.listTemplates(true)
    allTemplates.value = tmpls.factor_template_info_list || []
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Save template failed')
  }
  finally {
    savingTemplate.value = false
  }
}

function applyProjectSettings(project: {
  project_title?: string | null
  project_tag: string
  project_description?: string | null
  disabled?: boolean | null
  end_time?: string | null
  private_participation?: boolean | null
  participant_influence_mode?: string | null
  participant_influence_min_comparisons?: number | null
  factor_weight_floor_alpha?: number | null
  min_expected_passes?: number | null
  max_recommended_passes?: number | null
  option_questions_per_group?: number | null
  factor_questions_per_group?: number | null
  option_questions_per_group_explicit?: boolean | null
  factor_questions_per_group_explicit?: boolean | null
  ranking_mode?: string | null
  project_criteria_template?: number | null
  project_exclusive_mode?: boolean | null
  include_ai_agents?: boolean | null
  ai_voter_models?: string[] | null
}, opts: { asDuplicate?: boolean; privateLocked?: boolean } = {}) {
  const baseTitle = (project.project_title || project.project_tag || '').trim()
  form.project_title = opts.asDuplicate
    ? (baseTitle ? `${baseTitle} - Copy` : 'Copy')
    : (project.project_title || '')
  form.project_tag = opts.asDuplicate ? slugify(form.project_title) : project.project_tag
  form.project_description = project.project_description || ''
  form.disabled = opts.asDuplicate ? false : !!project.disabled
  form.end_time = opts.asDuplicate ? null : (project.end_time || null)
  form.private_participation = !!project.private_participation
  const infMode = project.participant_influence_mode || 'comparisons'
  form.participant_influence_mode = (
    ['comparisons', 'balanced', 'participants_normalized'].includes(infMode)
      ? infMode
      : 'comparisons'
  ) as typeof form.participant_influence_mode
  form.min_expected_passes = clampMinExpectedPasses(project.min_expected_passes ?? 2)
  form.max_recommended_passes = clampMaxRecommendedPasses(
    project.max_recommended_passes ?? form.min_expected_passes,
    form.min_expected_passes,
  )
  optionGroupSizeExplicit.value = !!project.option_questions_per_group_explicit
  factorGroupSizeExplicit.value = !!project.factor_questions_per_group_explicit
  withGroupSizeSync(() => {
    const optionN = namedOptions.value.filter(o => !o.disabled).length
    const factorN = factorMode.value === 'multi' ? namedCriteria.value.filter(c => !c.disabled).length : 0
    form.option_questions_per_group = optionGroupSizeExplicit.value
      ? clampQuestionsPerGroup(project.option_questions_per_group ?? DEFAULT_QUESTIONS_PER_GROUP, optionN)
      : defaultQuestionsPerGroupForN(optionN)
    form.factor_questions_per_group = factorGroupSizeExplicit.value
      ? clampQuestionsPerGroup(project.factor_questions_per_group ?? DEFAULT_QUESTIONS_PER_GROUP, factorN)
      : defaultQuestionsPerGroupForN(factorN)
  })
  form.participant_influence_min_comparisons = Math.max(
    3,
    Number(project.participant_influence_min_comparisons ?? 10) || 10,
  )
  form.factor_weight_floor_alpha = clampFactorWeightFloorAlpha(project.factor_weight_floor_alpha ?? 0.5)
  form.project_criteria_template = project.project_criteria_template || 0
  form.include_ai_agents = !!project.include_ai_agents
  form.ai_voter_models = Array.from(new Set((project.ai_voter_models || []).map(v => String(v || '').trim()).filter(Boolean)))
  privateParticipationLocked.value = opts.asDuplicate ? false : !!opts.privateLocked
  existingTag.value = opts.asDuplicate ? '' : project.project_tag
  const rm = String(project.ranking_mode || '')
  if (rm === 'find_best' || rm === 'find_top_3' || rm === 'find_top_half' || rm === 'rank_all') {
    rankingMode.value = rm
  } else {
    rankingMode.value = project.project_exclusive_mode ? 'find_best' : 'rank_all'
  }
  mode.value = rankingMode.value === 'find_best' ? 'exclusive' : 'rank'
}

async function loadContentRows(sourceProjectId: number, withIds: boolean) {
  const [alts, facts] = await Promise.all([
    api.listAlternatives(sourceProjectId),
    api.listFactors(sourceProjectId),
  ])
  const altList = alts.alternative_info_list || []
  options.value = altList.length
    ? altList.map(a => ({
        ...(withIds ? { id: a.id } : {}),
        title: a.alternative_title || '',
        description: a.alternative_description || '',
        compare_prompt: (a as any).compare_prompt || '',
        disabled: !!a.disabled,
      }))
    : [
        { title: '', description: '', compare_prompt: '', disabled: false },
        { title: '', description: '', compare_prompt: '', disabled: false },
      ]
  const factList = facts.factor_info_list || []
  if (factList.length) {
    factorMode.value = 'multi'
    criteria.value = factList.map(f => ({
      ...(withIds ? { id: f.id } : {}),
      title: f.factor_title || '',
      description: f.factor_description || '',
      compare_prompt: (f as any).compare_prompt || '',
      disabled: !!f.disabled,
    }))
  }
  else {
    factorMode.value = 'overall'
    criteria.value = [{ title: '', description: '', compare_prompt: '', disabled: false }]
  }
}

async function loadExisting() {
  if (isNew.value) return
  const p = await api.getProject(projectId.value)
  if (p.failure_reason || !p.customer_project_info) throw new Error(p.failure_reason || 'Not found')
  applyProjectSettings(p.customer_project_info, {
    privateLocked: !!p.private_participation_locked,
  })
  await loadContentRows(p.customer_project_info.id, true)
}

async function applyDuplicateSource(sourceProjectId: number) {
  loadingDraft.value = true
  try {
    const p = await api.getProject(sourceProjectId)
    if (p.failure_reason || !p.customer_project_info) throw new Error(p.failure_reason || 'Source project not found')
    applyProjectSettings(p.customer_project_info, { asDuplicate: true })
    await loadContentRows(p.customer_project_info.id, false)
    isDuplicateDraft.value = true
    return p.customer_project_info
  }
  finally {
    loadingDraft.value = false
  }
}

async function loadDuplicateDraft() {
  if (!isNew.value || !duplicateFromId.value) return
  await applyDuplicateSource(duplicateFromId.value)
}

// Copy from project
const copyFromDialog = ref(false)
const copyFromCandidates = ref<ProjectListSummaryItem[]>([])
const copyFromSelectedId = ref<number | null>(null)
const copyFromSearch = ref('')
const canCopyFromProject = computed(() => !namedOptions.value.length && !namedCriteria.value.length)
const copyFromDisabledHint = computed(() => (canCopyFromProject.value ? undefined : 'Clear entered options before copying'))
const copyFromFiltered = computed(() => {
  const q = copyFromSearch.value.trim().toLowerCase()
  if (!q) return copyFromCandidates.value
  return copyFromCandidates.value.filter(item =>
    (item.project.project_title || '').toLowerCase().includes(q)
    || (item.project.project_tag || '').toLowerCase().includes(q),
  )
})

async function openCopyFromDialog() {
  if (!isNew.value || !canCopyFromProject.value) return
  loadingDraft.value = true
  try {
    const res = await api.listProjectsSummary()
    if (res.failure_reason) throw new Error(res.failure_reason)
    copyFromCandidates.value = res.projects || []
    copyFromSelectedId.value = null
    copyFromSearch.value = ''
    copyFromDialog.value = true
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Could not load projects')
  }
  finally {
    loadingDraft.value = false
  }
}

async function confirmCopyFromProject() {
  const item = copyFromCandidates.value.find(x => x.project?.id === copyFromSelectedId.value)
  if (!item?.project?.id) return
  const sourceName = item.project.project_title || item.project.project_tag || `project ${item.project.id}`
  copyFromDialog.value = false
  try {
    await applyDuplicateSource(item.project.id)
    snackbar.success(`Settings copied from ${sourceName}`)
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Copy failed')
  }
}

async function retireAlternative(projectId: number, alternativeId: number) {
  await api.updateAlternative({
    alternative_id: alternativeId,
    project_id: projectId,
    disabled: true,
  }).catch(() => null)
  await api.deleteAlternative(alternativeId).catch(() => null)
}

async function retireFactor(projectId: number, factorId: number) {
  await api.updateFactor({
    factor_id: factorId,
    project_id: projectId,
    disabled: true,
  }).catch(() => null)
  await api.deleteFactor(factorId).catch(() => null)
}

async function syncOptions(projectId: number) {
  const currentAlts = isNew.value ? [] : (await api.listAlternatives(projectId)).alternative_info_list || []
  const byId = new Map(currentAlts.map(a => [a.id, a]))
  const keepIds = new Set<number>()

  for (const opt of namedOptions.value) {
    const title = opt.title.trim()
    const description = opt.description.trim()
    const comparePrompt = (opt.compare_prompt || '').trim() || null
    const disabled = !!opt.disabled
    if (opt.id && byId.has(opt.id)) {
      keepIds.add(opt.id)
      const existing = byId.get(opt.id)!
      const same
        = (existing.alternative_title || '') === title
          && (existing.alternative_description || '') === description
          && ((existing as any).compare_prompt || null) === comparePrompt
          && !!existing.disabled === disabled
      if (!same) {
        const res = await api.updateAlternative({
          alternative_id: opt.id,
          project_id: projectId,
          alternative_title: title,
          alternative_description: description,
          compare_prompt: comparePrompt,
          disabled,
        })
        if (res.failure_reason) throw new Error(res.failure_reason)
      }
    }
    else {
      const res = await api.createAlternative({
        project_id: projectId,
        alternative_title: title,
        alternative_description: description,
        disabled,
      } as any)
      if (res.failure_reason || !res.alternative_info) throw new Error(res.failure_reason || 'Create option failed')
      opt.id = res.alternative_info.id
      keepIds.add(res.alternative_info.id)
      if (comparePrompt) {
        await api.updateAlternative({ alternative_id: opt.id, project_id: projectId, compare_prompt: comparePrompt } as any).catch(() => null)
      }
    }
  }

  for (const a of currentAlts) {
    if (!keepIds.has(a.id)) await retireAlternative(projectId, a.id)
  }
}

async function syncFactors(projectId: number) {
  const currentFacts = isNew.value ? [] : (await api.listFactors(projectId)).factor_info_list || []
  const byId = new Map(currentFacts.map(f => [f.id, f]))
  const keepIds = new Set<number>()

  if (factorMode.value === 'multi') {
    for (const c of namedCriteria.value) {
      const title = c.title.trim()
      const description = c.description.trim()
      const comparePrompt = (c.compare_prompt || '').trim() || null
      const disabled = !!c.disabled
      if (c.id && byId.has(c.id)) {
        keepIds.add(c.id)
        const existing = byId.get(c.id)!
        const same
          = (existing.factor_title || '') === title
            && (existing.factor_description || '') === description
            && ((existing as any).compare_prompt || null) === comparePrompt
            && !!existing.disabled === disabled
        if (!same) {
          const res = await api.updateFactor({
            factor_id: c.id,
            project_id: projectId,
            factor_title: title,
            factor_description: description,
            compare_prompt: comparePrompt,
            disabled,
          } as any)
          if (res.failure_reason) throw new Error(res.failure_reason)
        }
      }
      else {
        const res = await api.createFactor({
          project_id: projectId,
          factor_title: title,
          factor_description: description,
          disabled,
        } as any)
        if (res.failure_reason || !res.factor_info) throw new Error(res.failure_reason || 'Create factor failed')
        c.id = res.factor_info.id
        keepIds.add(res.factor_info.id)
        if (comparePrompt) {
          await api.updateFactor({ factor_id: c.id, project_id: projectId, compare_prompt: comparePrompt } as any).catch(() => null)
        }
      }
    }
  }

  for (const f of currentFacts) {
    if (!keepIds.has(f.id)) await retireFactor(projectId, f.id)
  }
}

async function save(opts: { startProbe?: boolean; stay?: boolean } = {}) {
  if (!requireAdmin()) return
  if (validationError.value) {
    snackbar.error(validationError.value)
    tab.value = 'review'
    return
  }
  saving.value = true
  try {
    let id = projectId.value
    if (isNew.value) {
      const created = await api.createProject({
        project_tag: form.project_tag.trim(),
        project_title: form.project_title.trim(),
        project_description: form.project_description.trim(),
        project_exclusive_mode: rankingMode.value === 'find_best',
        ranking_mode: rankingMode.value,
        private_participation: form.private_participation,
        participant_influence_mode: form.participant_influence_mode,
        participant_influence_min_comparisons: Math.max(3, Number(form.participant_influence_min_comparisons) || 10),
        factor_weight_floor_alpha: clampFactorWeightFloorAlpha(form.factor_weight_floor_alpha),
        min_expected_passes: clampMinExpectedPasses(form.min_expected_passes),
        max_recommended_passes: clampMaxRecommendedPasses(
          form.max_recommended_passes,
          form.min_expected_passes,
        ),
        option_questions_per_group: optionGroupSizeExplicit.value
          ? clampQuestionsPerGroup(form.option_questions_per_group, activeOptionCount.value)
          : defaultQuestionsPerGroupForN(activeOptionCount.value),
        factor_questions_per_group: factorGroupSizeExplicit.value
          ? clampQuestionsPerGroup(form.factor_questions_per_group, activeFactorCount.value)
          : defaultQuestionsPerGroupForN(activeFactorCount.value),
        option_questions_per_group_explicit: optionGroupSizeExplicit.value,
        factor_questions_per_group_explicit: factorGroupSizeExplicit.value,
        project_criteria_template: form.project_criteria_template,
        disabled: form.disabled,
        end_time: form.end_time,
        include_ai_agents: !!form.include_ai_agents,
        ai_voter_models: Array.from(new Set(form.ai_voter_models)),
      })
      if (created.failure_reason || !created.customer_project_info) throw new Error(created.failure_reason || 'Create failed')
      id = created.customer_project_info.id
    }
    else {
      const updated = await api.updateProject({
        project_tag: form.project_tag,
        project_title: form.project_title.trim(),
        project_description: form.project_description.trim(),
        project_exclusive_mode: rankingMode.value === 'find_best',
        ranking_mode: rankingMode.value,
        private_participation: form.private_participation,
        participant_influence_mode: form.participant_influence_mode,
        participant_influence_min_comparisons: Math.max(3, Number(form.participant_influence_min_comparisons) || 10),
        factor_weight_floor_alpha: clampFactorWeightFloorAlpha(form.factor_weight_floor_alpha),
        min_expected_passes: clampMinExpectedPasses(form.min_expected_passes),
        max_recommended_passes: clampMaxRecommendedPasses(
          form.max_recommended_passes,
          form.min_expected_passes,
        ),
        option_questions_per_group: optionGroupSizeExplicit.value
          ? clampQuestionsPerGroup(form.option_questions_per_group, activeOptionCount.value)
          : defaultQuestionsPerGroupForN(activeOptionCount.value),
        factor_questions_per_group: factorGroupSizeExplicit.value
          ? clampQuestionsPerGroup(form.factor_questions_per_group, activeFactorCount.value)
          : defaultQuestionsPerGroupForN(activeFactorCount.value),
        option_questions_per_group_explicit: optionGroupSizeExplicit.value,
        factor_questions_per_group_explicit: factorGroupSizeExplicit.value,
        project_criteria_template: form.project_criteria_template,
        disabled: form.disabled,
        end_time: form.end_time,
        include_ai_agents: !!form.include_ai_agents,
        ai_voter_models: Array.from(new Set(form.ai_voter_models)),
      })
      if (updated.failure_reason) throw new Error(updated.failure_reason)
    }

    await syncOptions(id)
    await syncFactors(id)

    if (!isNew.value || opts.stay) {
      const refreshed = await api.getProject(id)
      privateParticipationLocked.value = !!refreshed.private_participation_locked
      if (refreshed.customer_project_info) {
        form.private_participation = !!refreshed.customer_project_info.private_participation
      }
    }

    snackbar.success(isNew.value ? 'Project saved' : 'Project updated')
    if (opts.stay) return
    if (opts.startProbe) await navigateTo(`/projects/${id}/probe`)
    else await navigateTo(`/projects/${id}`)
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : (isNew.value ? 'Save failed' : 'Update failed'))
  }
  finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const tmpls = await api.listTemplates(true)
    allTemplates.value = tmpls.factor_template_info_list || []
    if (isNew.value && duplicateFromId.value) await loadDuplicateDraft()
    else await loadExisting()
    await loadProjectBranding()
    await loadAiVoterCatalog()
    await loadProviderStatus()
  }
  catch (e: unknown) {
    snackbar.error(e instanceof Error ? e.message : 'Failed to load')
  }
})
</script>

<style scoped>
.copy-from-list {
  max-height: 320px;
  overflow-y: auto;
}
.project-branding-preview {
  width: 72px;
  height: 72px;
  border-radius: 14px;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgba(var(--v-theme-surface-variant), 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}
.project-branding-preview__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.project-branding-preview__empty {
  color: rgba(var(--v-theme-on-surface), 0.35);
  font-size: 1.25rem;
}
</style>
