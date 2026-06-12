import pathlib
import random
from typing import Annotated

import structlog
from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from gacha.cost import CostData, compute_cost, compute_stats
from gacha.engine import pull_multi
from gacha.models import CustomBannerInput, SessionState
from gacha.settings import settings
from gacha.web.api.routes import _all_banners, _custom_banners, _custom_banners_lock, _store

router = APIRouter(tags=["views"])
log: structlog.stdlib.BoundLogger = structlog.get_logger()

_templates_dir = pathlib.Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


def _get_rng() -> random.Random:
    return random.Random(settings.seed) if settings.seed is not None else random.Random()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """メインページを返す。"""
    banners = list(_all_banners().values())
    state: SessionState | None = None
    if gacha_session:
        state = _store.get(gacha_session)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"banners": banners, "state": state},
    )


@router.post("/pull/{count}", response_class=HTMLResponse)
async def pull_fragment(
    count: int,
    request: Request,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """htmx用: pull結果のHTMLフラグメントを返す。"""
    count = max(1, min(count, 200))
    new_cookie: str | None = None
    if not gacha_session:
        gacha_session = _store.create("genshin_like")
        new_cookie = gacha_session

    state = _store.get(gacha_session)
    if state is None:
        state = SessionState(banner_id="genshin_like")
        _store.update(gacha_session, state)

    banners = _all_banners()
    banner_id = state.banner_id if state.banner_id in banners else "genshin_like"
    banner = banners[banner_id]

    results, new_state = pull_multi(banner, state, _get_rng(), count)
    _store.update(gacha_session, new_state)

    resp = templates.TemplateResponse(
        request,
        "fragments/pull_result.html",
        {
            "results": results,
            "pity_count": new_state.pity_count,
            "hard_pity": banner.pity.hard_pity,
            "soft_pity_start": banner.pity.soft_pity_start,
            "total_pulls": new_state.total_pulls,
            "ssr_count": new_state.ssr_count,
            "ssr_rate": new_state.ssr_count / new_state.total_pulls if new_state.total_pulls > 0 else 0.0,
        },
    )
    if new_cookie is not None:
        resp.set_cookie("gacha_session", new_cookie, httponly=True, samesite="strict")
    return resp


@router.get("/stats", response_class=HTMLResponse)
async def stats_fragment(
    request: Request,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """htmx用: 統計HTMLフラグメントを返す。"""
    if not gacha_session:
        return templates.TemplateResponse(request, "fragments/stats.html", {"total_pulls": 0})
    state = _store.get(gacha_session)
    if state is None:
        return templates.TemplateResponse(request, "fragments/stats.html", {"total_pulls": 0})
    stats = compute_stats(state)
    banner = _all_banners().get(state.banner_id)
    cost: CostData | None = None
    if banner is not None and banner.stone_price is not None:
        cost = compute_cost(banner.stone_price, state.total_pulls, state.ssr_count)
    return templates.TemplateResponse(
        request,
        "fragments/stats.html",
        {
            "total_pulls": stats.total_pulls,
            "ssr_count": stats.ssr_count,
            "ssr_rate": stats.ssr_rate,
            "avg_pity": stats.avg_pity,
            "cost_jpy": cost.cost_jpy if cost is not None else None,
            "cost_per_ssr_jpy": cost.cost_per_ssr_jpy if cost is not None else None,
        },
    )


def _format_error(exc: Exception) -> str:
    """ValidationError / ValueError を日本語メッセージに変換する。"""
    if isinstance(exc, ValidationError):
        msgs = [e["msg"].removeprefix("Value error, ") for e in exc.errors()]
        return " / ".join(msgs)
    return str(exc)


@router.post("/session/custom", response_class=HTMLResponse)
async def create_custom_banner(
    request: Request,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """カスタムバナーを作成してセッションを切り替える。"""
    form = await request.form()
    try:
        jpy_raw = str(form.get("jpy_per_pull", "")).strip()
        inp = CustomBannerInput(
            name=str(form.get("name", "")),
            ssr_rate_pct=float(str(form.get("ssr_rate_pct", "0"))),
            soft_pity_start=int(str(form.get("soft_pity_start", "0"))),
            hard_pity=int(str(form.get("hard_pity", "0"))),
            jpy_per_pull=float(jpy_raw) if jpy_raw else None,
        )
    except (ValueError, ValidationError) as exc:
        return templates.TemplateResponse(
            request,
            "fragments/custom_error.html",
            {"error": _format_error(exc)},
            status_code=422,
        )
    banner = inp.to_banner()
    with _custom_banners_lock:
        _custom_banners[banner.id] = banner
    log.info("custom_banner_created_via_form", banner_id=banner.id, name=banner.name)

    if gacha_session:
        new_session_id = _store.regenerate(gacha_session, banner.id)
    else:
        new_session_id = _store.create(banner.id)

    banners_list = list(_all_banners().values())
    state = _store.get(new_session_id)
    resp = templates.TemplateResponse(
        request,
        "fragments/banner_switched.html",
        {
            "banner": banner,
            "banners": banners_list,
            "state": state,
            "clear_custom_error": True,
        },
    )
    resp.set_cookie("gacha_session", new_session_id, httponly=True, samesite="strict")
    return resp


@router.post("/session/switch", response_class=HTMLResponse)
async def switch_banner(
    request: Request,
    gacha_session: Annotated[str | None, Cookie()] = None,
) -> HTMLResponse:
    """バナー切り替え: セッションIDを再発行してリダイレクト。"""
    form = await request.form()
    banner_id = str(form.get("banner_id", "genshin_like"))
    banners = _all_banners()
    if banner_id not in banners:
        banner_id = "genshin_like"

    if gacha_session:
        new_session_id = _store.regenerate(gacha_session, banner_id)
    else:
        new_session_id = _store.create(banner_id)

    banners_list = list(banners.values())
    state = _store.get(new_session_id)

    resp = templates.TemplateResponse(
        request,
        "fragments/banner_switched.html",
        {"banner": banners[banner_id], "banners": banners_list, "state": state},
    )
    resp.set_cookie("gacha_session", new_session_id, httponly=True, samesite="strict")
    return resp
