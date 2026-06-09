import random
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from gacha.cost import CostData, compute_cost, compute_stats
from gacha.engine import pull_multi
from gacha.models import Banner, PullResult, SessionState
from gacha.presets import ALL_PRESETS
from gacha.session import SessionStore
from gacha.settings import settings

router = APIRouter(prefix="/api/v1", tags=["api"])
log: structlog.stdlib.BoundLogger = structlog.get_logger()

_store = SessionStore()
_custom_banners: dict[str, Banner] = {}


def _get_rng() -> random.Random:
    return random.Random(settings.seed) if settings.seed is not None else random.Random()


def _all_banners() -> dict[str, Banner]:
    return {**ALL_PRESETS, **_custom_banners}


class SessionResponse(BaseModel):
    session_id: str
    banner_id: str


class PullResponse(BaseModel):
    results: list[PullResult]
    state: SessionState


class StatsResponse(BaseModel):
    total_pulls: int
    ssr_count: int
    ssr_rate: float
    avg_pity: float
    cost_jpy: float | None = None
    cost_per_ssr_jpy: float | None = None


@router.get("/banners")
async def list_banners() -> list[Banner]:
    """利用可能なバナー一覧を返す。"""
    return list(_all_banners().values())


@router.post("/banners", status_code=201)
async def create_banner(banner: Banner) -> Banner:
    """カスタムバナーを登録する。"""
    if banner.id in ALL_PRESETS:
        raise HTTPException(status_code=409, detail="Cannot override preset banner")
    _custom_banners[banner.id] = banner
    log.info("custom_banner_created", banner_id=banner.id)
    return banner


@router.post("/session")
async def start_session(
    banner_id: str,
    response: Response,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> SessionResponse:
    """セッションを開始する。バナー切替時はIDを再発行する。"""
    if banner_id not in _all_banners():
        raise HTTPException(status_code=404, detail=f"Banner '{banner_id}' not found")
    if gacha_session:
        session_id = _store.regenerate(gacha_session, banner_id)
    else:
        session_id = _store.create(banner_id)
    response.set_cookie("gacha_session", session_id, httponly=True, samesite="strict")
    log.info("session_started", session_id=session_id[:8], banner_id=banner_id)
    return SessionResponse(session_id=session_id, banner_id=banner_id)


@router.post("/pull/{count}")
async def pull(
    count: Annotated[int, Field(ge=1, le=200)],
    response: Response,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> PullResponse:
    """ガチャをcount回引く。"""
    if not gacha_session:
        raise HTTPException(status_code=400, detail="No active session. POST /api/v1/session first.")
    state = _store.get(gacha_session)
    if state is None:
        raise HTTPException(status_code=404, detail="Session expired or not found.")
    banners = _all_banners()
    if state.banner_id not in banners:
        raise HTTPException(status_code=404, detail=f"Banner '{state.banner_id}' not found.")
    banner = banners[state.banner_id]
    results, new_state = pull_multi(banner, state, _get_rng(), count)
    _store.update(gacha_session, new_state)
    log.info("pull_completed", count=count, ssr_count=sum(1 for r in results if r.item.rarity.value == "SSR"))
    return PullResponse(results=results, state=new_state)


@router.get("/stats")
async def get_stats(
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> StatsResponse:
    """現在のセッション統計を返す。"""
    if not gacha_session:
        raise HTTPException(status_code=400, detail="No active session.")
    state = _store.get(gacha_session)
    if state is None:
        raise HTTPException(status_code=404, detail="Session expired or not found.")
    stats = compute_stats(state)
    banner = _all_banners().get(state.banner_id)
    cost: CostData | None = None
    if banner is not None and banner.stone_price is not None:
        cost = compute_cost(banner.stone_price, state.total_pulls, state.ssr_count)
    return StatsResponse(
        total_pulls=stats.total_pulls,
        ssr_count=stats.ssr_count,
        ssr_rate=stats.ssr_rate,
        avg_pity=stats.avg_pity,
        cost_jpy=cost.cost_jpy if cost is not None else None,
        cost_per_ssr_jpy=cost.cost_per_ssr_jpy if cost is not None else None,
    )


@router.delete("/session", status_code=204)
async def reset_session(
    response: Response,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> None:
    """セッションをリセットする。"""
    if gacha_session:
        _store.delete(gacha_session)
    response.delete_cookie("gacha_session")
