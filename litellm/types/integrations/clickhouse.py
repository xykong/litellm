from typing import Optional
from typing_extensions import TypedDict


class ClickHouseBatchElement(TypedDict):
    request_id: str
    call_type: str
    api_key: str
    spend: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    startTime: str
    endTime: str
    completionStartTime: Optional[str]
    model: str
    model_id: str
    model_group: str
    api_base: str
    user: str
    metadata: str
    cache_hit: str
    cache_key: str
    request_tags: str
    team_id: str
    end_user: str
    requester_ip_address: str
    messages: str
    response: str
    session_id: str
