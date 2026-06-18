from typing import Literal

from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    agent_name: str = "Rafa"
    role: str = "consultor comercial"
    objective: str = "entender a necessidade e orientar o próximo passo"
    voice: str = "natural, direto e acolhedor"
    formality: Literal["baixa", "media", "alta"] = "media"
    concision: Literal["curta", "equilibrada", "detalhada"] = "equilibrada"
    emoji_mode: Literal["nunca", "espelhar", "leve"] = "espelhar"
    commercial_initiative: int = Field(default=50, ge=0, le=100)
    max_questions: int = Field(default=1, ge=0, le=3)
    split_messages: bool = True
    typo_probability: float = Field(default=0, ge=0, le=0.05)
    preferred_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    business_rules: str = ""
    system_prompt: str = ""
    whatsapp_provider: Literal["official", "evolution"] = "official"
    evolution_url: str = ""
    evolution_key: str = ""
    evolution_instance: str = ""
    openai_api_key: str = ""
    model: str = "gpt-4o-mini"


class LabSessionRequest(BaseModel):
    name: str = Field(default="Conversa de teste", min_length=1, max_length=100)


class LabMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    ai_configured: bool
    whatsapp_configured: bool
    whatsapp_details: dict | None = None



class FlowStep(BaseModel):
    type: Literal["text", "image", "document", "video", "audio"]
    text: str | None = None
    media_url: str | None = None


class FlowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    trigger_intent: str = Field(min_length=1, max_length=500)
    steps: list[FlowStep] = Field(default_factory=list)


class FlowResponse(BaseModel):
    id: int
    name: str
    trigger_intent: str
    steps: list[FlowStep]
    created_at: str
    updated_at: str
