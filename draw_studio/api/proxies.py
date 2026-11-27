from fastapi import APIRouter, Body
from pydantic import BaseModel, SecretStr

from .core import State, readable

router = APIRouter(prefix="/api/proxy", tags=["出口线路"])


class ProxyInfo(BaseModel):
    id: str
    label: str
    masked: str
    hint: str
    configured: bool


class ProxyTest(BaseModel):
    profile: str
    ok: bool
    loc: str
    colo: str
    ms: int
    at: int
    error: str


class ProxyState(BaseModel):
    active: str
    profiles: list[ProxyInfo]
    last_test: ProxyTest | None


class ProfileInput(BaseModel):
    id: str | None = None
    label: str
    url: SecretStr | None = None


class ProxySelection(BaseModel):
    active: str | None = None
    custom_url: SecretStr | None = None


class TestInput(BaseModel):
    profile: str | None = None


@readable(router, "", response_model=ProxyState)
def list_profiles(s: State):
    return s.studio.proxies.state()


@router.post("/profiles", response_model=ProxyState)
def save_profile(body: ProfileInput, s: State):
    return s.studio.proxies.save(body.label, body.url.get_secret_value() if body.url else "", body.id)


@router.delete("/profiles/{profile_id}", response_model=ProxyState)
def delete_profile(profile_id: str, s: State):
    return s.studio.proxies.delete(profile_id)


@router.post("")
def select_profile(body: ProxySelection, s: State):
    url = body.custom_url.get_secret_value() if body.custom_url is not None else None
    return {"ok": True, **s.studio.proxies.configure(body.active, url)}


@router.post("/test", response_model=ProxyTest)
def test_profile(s: State, body: TestInput = Body(default_factory=TestInput)):
    return s.studio.proxies.test(body.profile)
