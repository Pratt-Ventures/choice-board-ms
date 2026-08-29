"""PowerChoice application model registration.

Importing this module registers every application table (plus all pvf framework
tables) on SQLModel.metadata. It is the models_module named in pvf_app_startup.yaml
and is loaded both at runtime (by the application shell) and by
pvf_get_alembic_config for alembic schema probing.
"""
from sqlmodel import SQLModel

from ...pvf.bindings.pvf_services import import_all_models, pvf_get_target_metadata

# Framework tables are always registered so the migrated schema stays complete
# regardless of which features are activated at runtime.
import_all_models()

from .customer_projects import CustomerProject  # noqa: F401
from .customer_project_alternatives_criteria import (  # noqa: F401
    CustomerFactorTemplates,
    CustomerProjectAlternatives,
    CustomerProjectFactors,
)
from .project_vote_events import ProjectVoteParticipant, ProjectVoteGroupResult  # noqa: F401
from .ai_agent_jobs import AiAgentJob  # noqa: F401
from .compare_prompt_jobs import ComparePromptJob  # noqa: F401


# Minimal bootstrap module for Alembic migrations
def get_target_metadata():
    return pvf_get_target_metadata()
