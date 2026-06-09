from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from gacha.models import SessionState, StonePrice


class StatsData(BaseModel):
    total_pulls: int
    ssr_count: int
    ssr_rate: float
    avg_pity: float


class CostData(BaseModel):
    cost_jpy: float
    cost_per_ssr_jpy: float | None


def compute_stats(state: SessionState) -> StatsData:
    """SessionStateの増分カウンタから統計を計算する。O(1)。"""
    total = state.total_pulls
    ssr = state.ssr_count
    return StatsData(
        total_pulls=total,
        ssr_count=ssr,
        ssr_rate=round(ssr / total, 4) if total > 0 else 0.0,
        avg_pity=round(state.ssr_pity_sum / ssr, 2) if ssr > 0 else 0.0,
    )


def compute_cost(stone_price: StonePrice, total_pulls: int, ssr_count: int) -> CostData:
    """引き数と石単価からコストを計算する。Decimal演算で精度を保証する。"""
    jpy = stone_price.jpy_per_pull()
    cost = (Decimal(total_pulls) * jpy).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    per_ssr: float | None = None
    if ssr_count > 0:
        raw = (cost / Decimal(ssr_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        per_ssr = float(raw)
    return CostData(cost_jpy=float(cost), cost_per_ssr_jpy=per_ssr)
