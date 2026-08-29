import type {
  CustomerProject,
  CustomerProjectResultOne,
  CustomerProjectResultMany,
  CustomerProjectDeleteResult,
  CustomerProjectAlternative,
  CustomerProjectAlternativeResultOne,
  CustomerProjectAlternativeResultMany,
  CustomerProjectFactor,
  CustomerProjectFactorResultOne,
  CustomerProjectFactorResultMany,
  FactorTemplate,
  FactorTemplateResultOne,
  FactorTemplateResultMany,
  ProjectListSummaryResult,
  ProjectPageSummaryResult,
  WsResultPackage,
} from '~/types/api'

export function useProjectsApi() {
  const { apiFetch } = useApi()

  async function listProjects() {
    return apiFetch<CustomerProjectResultMany>('/ws/custprojects/customer-projects-get-all')
  }

  async function listProjectsSummary() {
    return apiFetch<ProjectListSummaryResult>('/ws/custprojects/customer-projects-list-summary')
  }

  async function getProject(id: number) {
    return apiFetch<CustomerProjectResultOne>('/ws/custprojects/customer-project-get-by-id', {
      query: { retrieve_by_id: id },
    })
  }

  async function getProjectPageSummary(projectId: number) {
    return apiFetch<ProjectPageSummaryResult>('/ws/custprojects/customer-project-page-summary', {
      query: { project_id: projectId },
    })
  }

  async function createProject(body: {
    project_tag: string
    project_title?: string | null
    project_description?: string | null
    project_exclusive_mode?: boolean
    ranking_mode?: string
    private_participation?: boolean
    participant_influence_mode?: string
    participant_influence_min_comparisons?: number
    factor_weight_floor_alpha?: number
    min_expected_passes?: number
    max_recommended_passes?: number
    option_questions_per_group?: number
    factor_questions_per_group?: number
    option_questions_per_group_explicit?: boolean
    factor_questions_per_group_explicit?: boolean
    project_criteria_template?: number
    disabled?: boolean
    end_time?: string | null
    include_ai_agents?: boolean
    ai_voter_models?: string[]
  }) {
    return apiFetch<CustomerProjectResultOne>('/ws/custprojects/customer-project-create', {
      method: 'POST',
      body,
    })
  }

  async function updateProject(body: {
    project_tag: string
    project_title?: string | null
    project_description?: string | null
    project_exclusive_mode?: boolean
    ranking_mode?: string
    private_participation?: boolean
    participant_influence_mode?: string
    participant_influence_min_comparisons?: number
    factor_weight_floor_alpha?: number
    min_expected_passes?: number
    max_recommended_passes?: number
    option_questions_per_group?: number
    factor_questions_per_group?: number
    option_questions_per_group_explicit?: boolean
    factor_questions_per_group_explicit?: boolean
    project_criteria_template?: number
    disabled?: boolean
    end_time?: string | null
    include_ai_agents?: boolean
    ai_voter_models?: string[]
  }) {
    return apiFetch<WsResultPackage & { customer_project_id?: number }>('/ws/custprojects/customer-project-update', {
      method: 'POST',
      body,
    })
  }

  async function deleteProject(project_id: number, project_tag = '') {
    return apiFetch<CustomerProjectDeleteResult>('/ws/custprojects/customer-project-delete', {
      method: 'DELETE',
      body: { project_id, project_tag },
    })
  }

  async function listAlternatives(projectId: number) {
    return apiFetch<CustomerProjectAlternativeResultMany>('/ws/custproject-content/alternatives-get-by-project-id', {
      query: { project_id: projectId },
    })
  }

  async function createAlternative(body: {
    project_id: number
    alternative_title?: string | null
    alternative_description?: string | null
    disabled?: boolean
  }) {
    return apiFetch<CustomerProjectAlternativeResultOne>('/ws/custproject-content/alternative-create', {
      method: 'POST',
      body,
    })
  }

  async function updateAlternative(body: {
    alternative_id: number
    project_id: number
    alternative_title?: string | null
    alternative_description?: string | null
    compare_prompt?: string | null
    disabled?: boolean
  }) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/alternative-update', {
      method: 'POST',
      body,
    })
  }

  async function generateAlternativePrompt(alternative_id: number) {
    return apiFetch<WsResultPackage & { compare_prompt?: string | null }>('/ws/custproject-content/alternative-compare-prompt-generate', {
      method: 'POST',
      body: { alternative_id },
    })
  }

  async function deleteAlternative(alternative_id: number) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/alternative-delete', {
      method: 'DELETE',
      body: { alternative_id },
    })
  }

  async function listFactors(projectId: number) {
    return apiFetch<CustomerProjectFactorResultMany>('/ws/custproject-content/factors-get-by-project-id', {
      query: { project_id: projectId },
    })
  }

  async function createFactor(body: {
    project_id: number
    factor_title?: string | null
    factor_description?: string | null
    comparison_question?: string | null
    factor_polarity_positive?: boolean
    factor_polarity_note?: string | null
    disabled?: boolean
  }) {
    return apiFetch<CustomerProjectFactorResultOne>('/ws/custproject-content/factor-create', {
      method: 'POST',
      body,
    })
  }

  async function updateFactor(body: {
    factor_id: number
    project_id: number
    factor_title?: string | null
    factor_description?: string | null
    comparison_question?: string | null
    compare_prompt?: string | null
    factor_polarity_positive?: boolean
    factor_polarity_note?: string | null
    disabled?: boolean
  }) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/factor-update', {
      method: 'POST',
      body,
    })
  }

  async function generateFactorPrompt(factor_id: number) {
    return apiFetch<WsResultPackage & { compare_prompt?: string | null }>('/ws/custproject-content/factor-compare-prompt-generate', {
      method: 'POST',
      body: { factor_id },
    })
  }

  async function deleteFactor(factor_id: number) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/factor-delete', {
      method: 'DELETE',
      body: { factor_id },
    })
  }

  async function suggestFactors(body: {
    project_id: number
    project_title?: string | null
    project_description?: string | null
  }) {
    return apiFetch<WsResultPackage & { suggestions?: Array<{ title: string, description?: string }> }>(
      '/ws/custproject-content/factor-suggest',
      { method: 'POST', body },
    )
  }

  async function generateComparePrompts(project_id: number) {
    return apiFetch<WsResultPackage & { queued?: number, skipped_existing?: number, failed?: number }>('/ws/custprojects/customer-project-compare-prompts-generate', {
      method: 'POST',
      body: { project_id },
    })
  }

  async function clearComparePrompts(project_id: number) {
    return apiFetch<WsResultPackage & { cleared?: number }>('/ws/custprojects/customer-project-compare-prompts-clear', {
      method: 'POST',
      body: { project_id },
    })
  }

  async function comparePromptsStatus(project_id: number) {
    return apiFetch<WsResultPackage & { queued?: number, skipped_existing?: number, cleared?: number }>('/ws/custprojects/customer-project-compare-prompts-status', {
      query: { project_id },
    })
  }

  async function listTemplates(available = true, forUse?: 'projects' | 'options' | 'factors') {
    if (!available) {
      return apiFetch<FactorTemplateResultMany>('/ws/custproject-content/factor-templates-get-all')
    }
    const qs = forUse ? `?for_use=${encodeURIComponent(forUse)}` : ''
    return apiFetch<FactorTemplateResultMany>(`/ws/custproject-content/factor-templates-get-available${qs}`)
  }

  async function createTemplate(body: {
    factor_template_title?: string | null
    factor_template_description?: string | null
    factor_template_entries?: Array<{
      factor_title: string
      factor_description?: string | null
      comparison_question?: string | null
      factor_polarity_positive?: boolean
      factor_polarity_note?: string | null
    }>
    option_template_entries?: Array<{
      alternative_title?: string | null
      alternative_description?: string | null
    }>
    use_with_projects?: boolean
    use_with_options?: boolean
    use_with_factors?: boolean
    project_exclusive_mode?: boolean
    private_participation?: boolean
    enable_global_share?: boolean
    disabled?: boolean
  }) {
    return apiFetch<FactorTemplateResultOne>('/ws/custproject-content/factor-template-create', {
      method: 'POST',
      body,
    })
  }

  async function updateTemplate(body: {
    factor_template_id: number
    factor_template_title?: string | null
    factor_template_description?: string | null
    factor_template_entries?: Array<{
      factor_title: string
      factor_description?: string | null
      comparison_question?: string | null
      factor_polarity_positive?: boolean
      factor_polarity_note?: string | null
    }>
    option_template_entries?: Array<{
      alternative_title?: string | null
      alternative_description?: string | null
    }>
    use_with_projects?: boolean
    use_with_options?: boolean
    use_with_factors?: boolean
    project_exclusive_mode?: boolean
    private_participation?: boolean
    enable_global_share?: boolean
    disabled?: boolean
  }) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/factor-template-update', {
      method: 'POST',
      body,
    })
  }

  async function deleteTemplate(factor_template_id: number) {
    return apiFetch<WsResultPackage>('/ws/custproject-content/factor-template-delete', {
      method: 'DELETE',
      body: { factor_template_id },
    })
  }

  return {
    listProjects,
    listProjectsSummary,
    getProject,
    getProjectPageSummary,
    createProject,
    updateProject,
    deleteProject,
    listAlternatives,
    createAlternative,
    updateAlternative,
    deleteAlternative,
    listFactors,
    createFactor,
    updateFactor,
    deleteFactor,
    suggestFactors,
    generateAlternativePrompt,
    generateFactorPrompt,
    generateComparePrompts,
    clearComparePrompts,
    comparePromptsStatus,
    listTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
  }
}

export type {
  CustomerProject,
  CustomerProjectAlternative,
  CustomerProjectFactor,
  FactorTemplate,
}
