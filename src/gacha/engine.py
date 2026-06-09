import random

from gacha.models import (
    Banner,
    Item,
    PityConfig,
    PityType,
    PullResult,
    Rarity,
    SessionState,
)


def calculate_ssr_rate(base_rate: float, pity: PityConfig, pity_count: int) -> float:
    """soft/hard pity補正込みのSSR排出確率を返す。"""
    if pity_count >= pity.hard_pity:
        return 1.0
    if pity_count < pity.soft_pity_start:
        return base_rate
    steps = pity_count - pity.soft_pity_start + 1
    if pity.boost_formula == "linear":
        boost = steps * pity.rate_boost_per_pull
    else:
        boost = 1.0 - (1.0 - base_rate) * ((1.0 - pity.rate_boost_per_pull) ** steps)
    return min(base_rate + boost, 1.0)


def _determine_pity_type(pity: PityConfig, pity_count: int, base_rate: float, rolled_rate: float) -> PityType:
    """排出時のpityタイプを判定する。"""
    if pity_count >= pity.hard_pity:
        return PityType.HARD
    if pity_count >= pity.soft_pity_start and rolled_rate > base_rate:
        return PityType.SOFT
    return PityType.NORMAL


def _select_item(banner: Banner, rarity: Rarity, guarantee_pickup: bool, rng: random.Random) -> Item:
    """指定レアリティのアイテムをレートに従って抽選する。"""
    candidates = [i for i in banner.items if i.rarity == rarity]
    if not candidates:
        return rng.choice([i for i in banner.items])
    if guarantee_pickup:
        pickups = [i for i in candidates if i.is_pickup]
        if pickups:
            return rng.choice(pickups)
    weights = [i.rate for i in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


_MAX_HISTORY = 200


def pull_once(
    banner: Banner,
    state: SessionState,
    rng: random.Random,
) -> tuple[PullResult, SessionState]:
    """1回ガチャを引く。stateを更新して返す。"""
    ssr_items = [i for i in banner.items if i.rarity == Rarity.SSR]
    base_ssr_rate = sum(i.rate for i in ssr_items)

    new_pity = state.pity_count + 1
    effective_rate = calculate_ssr_rate(base_ssr_rate, banner.pity, new_pity)
    roll = rng.random()
    got_ssr = roll < effective_rate

    if got_ssr:
        pity_type = _determine_pity_type(banner.pity, new_pity, base_ssr_rate, effective_rate)
        guarantee_pickup = banner.guaranteed_featured and state.since_featured >= 1
        item = _select_item(banner, Rarity.SSR, guarantee_pickup, rng)
        new_since = 0 if item.is_pickup else state.since_featured + 1
        result = PullResult(item=item, pity_count=new_pity, pity_type=pity_type)
        new_history = ([*state.history, result])[-_MAX_HISTORY:]
        new_state = state.model_copy(
            update={
                "pity_count": 0,
                "since_featured": new_since,
                "total_pulls": state.total_pulls + 1,
                "ssr_count": state.ssr_count + 1,
                "ssr_pity_sum": state.ssr_pity_sum + new_pity,
                "history": new_history,
            }
        )
    else:
        sr_items = [i for i in banner.items if i.rarity == Rarity.SR]
        sr_rate = sum(i.rate for i in sr_items)
        if rng.random() < sr_rate / (1.0 - base_ssr_rate + 1e-12):
            item = _select_item(banner, Rarity.SR, False, rng)
        else:
            item = _select_item(banner, Rarity.R, False, rng)
        result = PullResult(item=item, pity_count=new_pity, pity_type=PityType.NORMAL)
        new_history = ([*state.history, result])[-_MAX_HISTORY:]
        new_state = state.model_copy(
            update={
                "pity_count": new_pity,
                "total_pulls": state.total_pulls + 1,
                "history": new_history,
            }
        )

    return result, new_state


def pull_multi(
    banner: Banner,
    state: SessionState,
    rng: random.Random,
    count: int = 10,
) -> tuple[list[PullResult], SessionState]:
    """n連ガチャを引く。"""
    results: list[PullResult] = []
    current_state = state
    for _ in range(count):
        result, current_state = pull_once(banner, current_state, rng)
        results.append(result)
    return results, current_state
