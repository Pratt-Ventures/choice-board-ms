from os import environ

from ..pvf.bindings.pvf_invocation import PvfGlobalSettings

class GlobalSettings(PvfGlobalSettings):
    """PowerChoice application settings.

    Framework-generic values (share links, external API, watcher, email, stripe,
    tokens) live in PvfGlobalSettings. Deployment-fixed feature switches and share
    vocabularies are owned by pvf_app_startup.yaml (see PvfGlobalSettings
    startup-owned ClassVars). Only PowerChoice-specific values belong here.
    """
    VERSION: str = "0.7.96"
    # Dev environment helpers
    APPLICATION_NAME: str = environ.get("APPLICATION_NAME", "Power Choice Pro")

    ANALYTIC_TRACKING_TOKEN: str = environ.get("ANALYTIC_TRACKING_TOKEN", "")   # If empty, the analytic code is not injected (restart required)
    ANALYTIC_TRACKING_STATIC_SCRIPT: str = environ.get("ANALYTIC_TRACKING_STATIC_SCRIPT", "<script src=\"https://app.rybbit.io/api/script.js\" data-site-id=\"{ANALYTIC_TRACKING_TOKEN}\" defer></script>")  # restart required
    ANALYTIC_TRACKING_WHITELIST: list[str] = [s.strip() for s in environ.get("ANALYTIC_TRACKING_WHITELIST", "rybbit.io").split(",") if s.strip()]  # if empty, no script delivery allowed; include port number suffix if needed; use a single '*' entry to enable all (not recommended); restart required
    COMPARE_DEFAULT_QUESTIONS_PER_GROUP: int = 20
    COMPARE_PARTIAL_FLUSH_COUNT: int = 5
    COMPARE_PARTIAL_IDLE_SECONDS: int = 90

    AI_MAX_CONCURRENT_PROJECTS: int = int(environ.get("AI_MAX_CONCURRENT_PROJECTS", 2))
    AI_MAX_PAIRS_PER_PROJECT: int = int(environ.get("AI_MAX_PAIRS_PER_PROJECT", 500))
    AI_PAIRS_PER_TICK: int = int(environ.get("AI_PAIRS_PER_TICK", 20))
    AI_SKIP_RATE_ABORT: float = float(environ.get("AI_SKIP_RATE_ABORT", 0.25))

    # AI participant prompting — system-level, not end-user editable.
    # Python format-string templates; placeholders are explicit ambient params.
    AI_TIE_SKIP_QUOTA_RATIO: float = float(environ.get("AI_TIE_SKIP_QUOTA_RATIO", 0.2))
    AI_TIE_SKIP_QUOTA_MIN: int = int(environ.get("AI_TIE_SKIP_QUOTA_MIN", 1))
    # The next three values are for AI comparison prompts when only a pair of options is presented, without any factor consideration.
    AI_PROMPT_CHOICE_TIE_SKIP: str = environ.get(
        "AI_PROMPT_CHOICE_TIE_SKIP", """
Respond with exactly one of: 1, 2, TIE, UNSURE, or SKIP.

Choose 1 or 2 whenever the available information supports a meaningful overall preference, even if the advantage is modest.

Use TIE only when the options are genuinely about equally strong overall.
Use UNSURE only when the comparison is meaningful but there is not enough information to form a reasonable overall preference.
Use SKIP only when the options cannot reasonably be compared in the stated project context.

Do not provide an explanation or any other text.""")
    AI_PROMPT_CHOICE_STRICT: str = environ.get(
        "AI_PROMPT_CHOICE_STRICT", """
You must select the option that has the stronger overall case, even if the difference is small or the evidence is uncertain.

Respond with exactly 1 or 2. Do not provide an explanation or any other text.""")
    # Placeholders:
    #  single: {project_title} {project_description} {option1_title} {option1_description} {option2_title} {option2_description} {choice_1} {choice_2}
    AI_PROMPT_SINGLE_OPTION_TEMPLATE: str = environ.get(
        "AI_PROMPT_SINGLE_OPTION_TEMPLATE", """
You are evaluating two options in a pairwise comparison. Your task is to decide which option is the better overall choice in the context of the project described below.

No single factor or criterion is being evaluated. Make a balanced overall judgment using the considerations that reasonably matter for this decision.

Consider meaningful advantages, disadvantages, tradeoffs, risks, benefits, practicality, and likely outcomes as appropriate to the project context. Give greater weight to differences that are likely to matter more to the decision, rather than treating every possible consideration as equally important.

Do not choose based on a single characteristic unless that characteristic is clearly decisive in the project context.

Option numbering is arbitrary. Option 1 and Option 2 may appear in either order, so do not favor an option because of its number or presentation order.

Use the project context and option information together. Apply relevant general knowledge when useful, but do not invent project-specific facts, requirements, priorities, or constraints that are not provided.

Choose the option that has the stronger overall case. The preferred option does not need to be better in every respect; weigh important tradeoffs and select the option whose overall advantages are more compelling for the stated project.

Project Context: {project_title}
{project_description}

Option 1: {option1_title}
{option1_description}

Option 2: {option2_title}
{option2_description}

1. {choice_1}
2. {choice_2}
""")
    # The next three values are for AI comparison prompts when a pair of options is considered WITH a specific factor to predominantly consider.
    AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR: str = environ.get(
        "AI_PROMPT_CHOICE_TIE_SKIP_WITH_FACTOR", """
Respond with exactly one of: 1, 2, TIE, UNSURE, or SKIP.

Choose 1 or 2 whenever the available information supports a meaningful preference, even if the advantage is modest.

Use TIE only when the options are genuinely about equally strong on the stated factor.
Use UNSURE only when the comparison is relevant but there is not enough information to form a reasonable preference.
Use SKIP only when the comparison cannot reasonably be evaluated for the stated factor, such as when the information is inapplicable or fundamentally insufficient.
Do not provide an explanation or any other text.
""")
    AI_PROMPT_CHOICE_STRICT_WITH_FACTOR: str = environ.get(
        "AI_PROMPT_CHOICE_STRICT_WITH_FACTOR", """
You must select the option that has the stronger case on the stated factor, even if the difference is small or the evidence is uncertain.

Respond with exactly 1 or 2. Do not provide an explanation or any other text.""")
    # Placeholders:
    #  factor-option: {project_title} {project_description} {factor_title} {factor_description} {factor_question} {option1_title} {option1_description} {option2_title} {option2_description} {choice_1} {choice_2}
    AI_PROMPT_FACTOR_OPTION_TEMPLATE: str = environ.get(
        "AI_PROMPT_FACTOR_OPTION_TEMPLATE", """
You are evaluating two options in a pairwise comparison. Your task is to decide which option better satisfies the specific factor and question given below.

Evaluate only the factor being asked about. Do not choose based on which option you prefer overall, or on unrelated advantages or disadvantages.

Option numbering is arbitrary. Option 1 and Option 2 may appear in either order, so do not favor an option because of its number or presentation order.

Use the project context, factor description, factor question, and option information together. Apply relevant general knowledge when useful, but do not invent project-specific facts that are not provided. Interpret the direction of preference from the factor question—for example, lower cost, less risk, or faster delivery may be better, while greater value, capability, or potential may be better.

Choose the option that has the stronger case on the stated factor. When the evidence is mixed, weigh the differences that matter most to that factor rather than requiring one option to be better in every respect.

Project Context: {project_title}
{project_description}

Current Factor: {factor_title}
{factor_description}

Question:
{factor_question}

Option 1: {option1_title}
{option1_description}

Option 2: {option2_title}
{option2_description}

{choice_1}
{choice_2}
""")
    # The next three values are for AI comparison prompts when only factors are being considered, used for factor ranking determination
    AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY: str = environ.get(
        "AI_PROMPT_CHOICE_TIE_SKIP_FACTORS_ONLY", """
Respond with exactly one of: 1, 2, TIE, UNSURE, or SKIP.

Choose 1 or 2 whenever the available information supports a meaningful difference in importance, even if the difference is modest.

Use TIE only when the two factors should reasonably have about equal influence on the decision.
Use UNSURE only when the comparison is meaningful but there is not enough information to determine which factor should receive greater weight.
Use SKIP only when the factors cannot reasonably be compared for importance in the stated project context.

Do not provide an explanation or any other text.
""")
    AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY: str = environ.get(
        "AI_PROMPT_CHOICE_STRICT_FACTORS_ONLY", """
You must select the factor that has the stronger case for receiving greater weight in the decision, even if the difference is small or the evidence is uncertain.

Respond with exactly 1 or 2. Do not provide an explanation or any other text.
""")
    # Placeholders:
    #  factor-ranking: {project_title} {project_description} {factor1_title} {factor1_question} {factor1_description} {factor2_title} {factor2_question} {factor2_description} {choice_1} {choice_2}
    AI_PROMPT_FACTOR_RANKING_TEMPLATE: str = environ.get(
        "AI_PROMPT_FACTOR_RANKING_TEMPLATE", """
You are evaluating the relative importance of two factors used in a weighted decision process. Your task is to decide which factor should have greater influence on the final decision in the context of the project described below.

Compare the importance of the factors themselves. Do not evaluate specific options, and do not decide which factor any particular option would perform better on.

Interpret each factor using its title, description, and question format. Consider how strongly each factor should influence a sound overall decision given the project's goals, context, likely consequences, risks, benefits, and tradeoffs.

A factor should receive greater importance when differences on that factor would reasonably matter more to the quality or outcome of the decision. Do not favor a factor merely because it is easier to measure, more familiar, more concrete, has larger possible numerical values, or has more detailed wording.

Use the project information provided and relevant general knowledge when useful, but do not invent project-specific priorities, requirements, constraints, or facts that are not supplied.

Factor numbering is arbitrary. Factor 1 and Factor 2 may appear in either order, so do not favor a factor because of its number or presentation order.

Choose the factor that has the stronger case for receiving greater weight in this decision. The difference does not need to be large.

Project Context: {project_title}
{project_description}

Factor 1: {factor1_title}
Factor 1 Question Format: {factor1_question}
Factor 1 Description: {factor1_description}

Factor 2: {factor2_title}
Factor 2 Question Format: {factor2_question}
Factor 2 Description: {factor2_description}

{choice_1}
{choice_2}"""
    )

    # Concise rewrite prompts for compare_prompt generation
    AI_REWRITE_OPTION_PROMPT: str = environ.get(
        "AI_REWRITE_OPTION_PROMPT",
        "Rewrite the option title and description as a crisp 2-6 word consistent label for pairwise comparison. Preserve meaning, no punctuation at end, return JSON {\"compare_prompt\": string}.",
    )
    AI_REWRITE_FACTOR_PROMPT: str = environ.get(
        "AI_REWRITE_FACTOR_PROMPT",
        """
You convert a decision factor into one short, natural question for comparing two options.

Input:

* A factor title
* An optional brief description of 0–2 sentences

Task:
Write exactly one concise question that asks which of the two already-presented options is better on that factor.

Rules:

1. Do not mention or repeat the option names, numbers, positions, or labels.
2. Infer the preferred direction of the factor:

   * For factors where lower is normally better, use language such as “less,” “lower,” “faster,” “shorter,” or “easier.”
   * For factors where higher is normally better, use language such as “more,” “greater,” “stronger,” or “higher.”
3. Use normal practical judgment to infer polarity from the title and description.

   * Examples usually minimized: cost, time, effort, complexity, risk, delay.
   * Examples usually maximized: revenue, market potential, confidence, quality, strategic value, competitive position.
4. Prefer a direct comparative question such as:

   * “Which requires less engineering effort?”
   * “Which has more revenue potential?”
   * “Which can reach the market faster?”
   * “Which has lower implementation risk?”
5. Prefer natural comparative wording over mechanically inserting “more” or “less.”
6. If the preferred direction is genuinely ambiguous or subjective, ask which is the better choice for that factor without inventing a direction.
7. Start with “Which” whenever natural.
8. Keep the question short, clear, conversational, and grammatically complete.
9. Produce exactly one sentence ending with a question mark.
10. Do not add explanations, qualifications, commentary, or alternative questions.

Return only valid JSON in exactly this form:

{"compare_prompt":"Which ...?"}
"""
        "Rewrite this decision factor as a concise question in simple language. It must be in the form of a question, including punctuation. The response is a choice of two options being compared. The options below and format is already clear and are not stated in the generated prompt. The choices are simple 1 (left or first presented) or 2 (right or second presented) choice incorporates polarity (is 'more' or 'less' better? factors like time and cost are usually minimized with 'faster' or 'lower cost', while revenue and positioning are maximized, like 'more revenue' or 'strongest position'), make a reasonable estimate if unclear, fall back to 'better choice' verbage if needed. Clarity and smoothness are important, like \"Which one requires less less engineering effort?\" or \"Which has more revenue potential?\" Use 'Which' or similar smooth language to start the question. Return JSON {\"compare_prompt\": string}.",
    )
    AI_REWRITE_OPTION_MAX_TOKENS: int = int(environ.get("AI_REWRITE_OPTION_MAX_TOKENS", 1200))
    AI_REWRITE_FACTOR_MAX_TOKENS: int = int(environ.get("AI_REWRITE_FACTOR_MAX_TOKENS", 1200))


settings = GlobalSettings()
