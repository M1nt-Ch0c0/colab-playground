from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, SecretStr

from ..generation.catalog import DEFAULTS
from ..generation.masked_edit import source_image
from .core import State, readable

router = APIRouter(prefix="/api", tags=["改写模型"])
Kind = Literal["openai", "anthropic", "gemini"]


class Selection(BaseModel):
    provider_id: str
    model: str


class ProviderInfo(BaseModel):
    id: str
    kind: Kind
    name: str
    base_url: str
    key_set: bool
    key_masked: str
    models: list[str]
    models_fetched_at: int | None
    enhanced_rewrite: bool
    legacy_template: bool


class LlmState(BaseModel):
    providers: list[ProviderInfo]
    active: Selection | None


class ProviderInput(BaseModel):
    id: str | None = None
    kind: Kind
    name: str
    base_url: str
    api_key: SecretStr | None = None
    models: list[str] | None = None
    enhanced_rewrite: bool | None = None


class Probe(BaseModel):
    model: str | None = None


class ProbeResult(BaseModel):
    ok: bool
    ms: int
    model: str
    error: str


class Rewrite(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    mode: Literal["image", "video"] = "image"
    editing: bool = False
    ref_count: int = 0
    workflow: Literal["t2va", "fl2va", "ref2va"] = "t2va"
    num_frames: int = DEFAULTS["video"]["num_frames"]
    chain: bool = False
    has_image: bool = True
    has_last_image: bool = False
    video_task: Literal["edit", "continue", "motion"] | None = None
    edit_source_id: str | None = Field(default=None, pattern=r"^\d{3,7}$")
    provider_id: str | None = None
    model: str | None = None


class RewriteResult(BaseModel):
    prompt: str
    model: str
    format: str
    images_used: int


@readable(router, "/llm", response_model=LlmState)
def list_providers(s: State):
    return s.studio.llm.state()


@router.post("/llm/providers", response_model=LlmState)
def save_provider(body: ProviderInput, s: State):
    return s.studio.llm.save(kind=body.kind, name=body.name, base_url_value=body.base_url,
                             api_key=body.api_key.get_secret_value() if body.api_key else "",
                             models=body.models, provider_id=body.id, enhanced_rewrite=body.enhanced_rewrite)


@router.delete("/llm/providers/{provider_id}", response_model=LlmState)
def delete_provider(provider_id: str, s: State):
    return s.studio.llm.delete(provider_id)


@router.post("/llm/providers/{provider_id}/models", response_model=LlmState)
def fetch_models(provider_id: str, s: State):
    return s.studio.llm.refresh(provider_id)


@router.post("/llm/providers/{provider_id}/test", response_model=ProbeResult)
def test_provider(provider_id: str, s: State, body: Probe = Body(default_factory=Probe)):
    return s.studio.llm.test(provider_id, body.model)


@router.post("/llm/active", response_model=LlmState)
def select_provider(body: Selection, s: State):
    return s.studio.llm.active(body.provider_id, body.model)


@router.post("/prompt", response_model=RewriteResult)
def rewrite(body: Rewrite, s: State):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "请描述想生成的内容（不超过 3000 字）")
    try:
        options = body.model_dump(exclude={"text", "edit_source_id"})
        if body.edit_source_id and body.mode == "image":
            options.update(editing=True, override_images=[("局部改图原图", source_image(s.store, body.edit_source_id))])
        return s.studio.write_prompt_rich(text, **options)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
