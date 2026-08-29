from pydantic import BaseModel, Field
from typing import Union
from enum import Enum, IntEnum
import numpy as np
import secrets

from enum import StrEnum

from ..pvf.bindings.pvf_services import PvfAuthRelatedOutboundEmailType

# PowerChoice share vocabularies. These mirror share.object_actions / share.access_operations
# in pvf_app_startup.yaml; the pvf share link support works with the plain string values
# internally. StrEnum so f-strings/str() yield the value (e.g. "vote"), not "ShareType.vote".
class ShareType(StrEnum):
    not_set = 'not_set'
    vote = 'vote'
    vote_view = 'vote_view'
    report = 'report'

class ShareAccessOperation(StrEnum):
    not_set = 'not_set'
    vote = 'vote'
    view = 'view'
    report = 'report'

class AppSpecificOutboundEmailType(Enum):  # Warning, Auth related should not be changed for compatibility with pvf implementatins
    share_project_vote = 'share_project_vote'
    share_project_vote_view = 'share_project_vote_view'
    share_project_report = 'share_project_report'
    resending_invitation = 'resending_invitation'

combined_members = {
    item.name: item.value 
    for enum_class in (AppSpecificOutboundEmailType, PvfAuthRelatedOutboundEmailType)
    for item in enum_class
    }

# Create the third named enum
OutboundEmailType = Enum('OutboundEmailType', combined_members)
   
