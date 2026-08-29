# Manual expansion / completion of AI Agent Resposnes and Factor assistance

## Short Description
### user
A ticket to add agents that can vote in projects was just processed in a recent session 'AI Agent Responses' - 

It's main summary was (modified in some areas, as we are allowing per-customer keys, model selection on the project AI voter, and multiple AI voters): 
New system configuration parameters specifies an AI service, access key, and model. Opencode GO/Zen is the initial configuration to test. When this is enabled on the system, agents will enhance features on the service.

On the project settings, if the customer has a provider selected, it defaults to their pre-set model, but allows another model to be selected. Each model creates an AI participant. 

All AI interactions will be orchestrated by the server. The keys and specifics of the AI model are never communicated to the client, except during customer model setup when the keys are supplied. Since the initial request, we are updating to add client-specific AI endpoints in a BYOK configuration.

AI can be invoked to suggest factors for a problem once the title and description are provided. It will take the information and prefill factors. The user can then delete and adjust.

Separately, a single AI participant can respond to the maximum number of groups for a project. A sequence of concise prompts, with grouping and systemetic information gain biased random order (equivalent to human participants) will be fed to an agent. The resposes collected. The extra groups and special status will provide an AI baseline in the final results. 

--> HERE IS A CHANGE FROM THE ORIGINAL REQUEST <--

We will allow multiple AI participants. Always flag AI participants as such, and their name becomes AI AGENT: <model name>; or just AI AGENT: Default Model (when the system setting is used). Always flag the AI participants as such with new columns as needed. The UI should allow multiple unique AI contributions, provided each has a unique model name. No model can participate twice. All models participate only to the minimum target number of groups.


The final results will have settings at the top of the page, analyze Human Only, Agents Only, or Combined. When agents are present, added modules at the bottom of the combined view page will show show agents vs humans in the option ranking and factor ranking.

------------------------------

I don't see evidence of the changes in the user interface.

Please evaluate what changes may have been made and modify per the below. There may be minor changes to adjust or remove unnecessary changes in pvf.  We will add new support for this LLM capability in the toolkit. It appears the prior ticket added 'active_ai_agents.' We will use that.

There should be needed framework src/pvf/config/pvf_config_settings.py settings to specify a globally available LLM provider (opencode Zen/Go or OpenRouter are the only supported initially), a model identifier, and an authorization key.

Additionally, in the customer profile, there should be a customer-specific provider, model, and authorization key. The key in the customer record should be both encrypted and stored in a readable (e.g., base64) encoding. It the value provided on update is different than the encrypted value, it is assumed to be a change and will be re-encrypted and encoded before storage (otherwise left unchanged). A blank key can be stored as an empty value. The key will be decrypted when utilized.


A new service in src/pvf/bindings/pvf_services.py will be added to send a prompt to the current provider and model. The query_llm_model will take a prompt and return to values, the session contents and the 'result' area. All prompt preparatation and respose parsing are the responsibility of the caller. Another service in that library will verify the settings for a provider (opencode zen/go, openrouter), model (glm 5.2; Grok 4.6; etc), and key are valid. If the provider and key are valid, a list of available models is returned.

The application's customer profile editor will add a block of information to choose a provider, model, and provide a key, and test the provider connection. The model should be a pulldown, based on available models the provider indicates.

If customer settings are populated, the customer level settings are used. If not, the system settings are checked. If neither settings are present, the request fails gracefully with 'no providers configured.'  The customer record in PVF will be adjusted to include these new fields and the added handling to check for changes and handle encrypt/encode and decode/decrypt when needed. 

Some related settings were added to src/config files, like AI_SERVICE, AI_API_KEY, AI_MODEL, AI_HTTP_TIMEOUT_SECONDS, AI_HTTP_RETRIES, which were moved into the pvf/config/pvf_config_settings.py. 

Others added in src/config/config_settings.py include AI_BASE_URL, AI_MAX_CONCURRENT_PROJECTS, AI_MAX_PAIRS_PER_PROJECT, AI_PAIRS_PER_TICK, AI_SKIP_RATE_ABORT. These appear more application-specific. If it is determined they are tied to the framework on a case by case basis, they can be moved to the pvf_config_settings.py as appropriate.


Please review the current state and complete the implementation of this feature. I'm tired and may have missed something, so please make reasonable assumptions to build a better product and robust capability or ask any clarifying questions that will improve the outcome and precision.
[comment: updated 2026-08-21T03:55:27.225Z | id manual-expansion-completion-of-ai-agent-5ppp95]

## Expanded Description

## Plan

## Build Summary

## Code Review Guide

## UI Review Guide

## History
- 2026-08-21T02:58:28.370Z created (source: user)
