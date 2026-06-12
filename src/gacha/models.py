import uuid
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Rarity(StrEnum):
    R = "R"
    SR = "SR"
    SSR = "SSR"
    UR = "UR"


class PityType(StrEnum):
    NORMAL = "normal"
    SOFT = "soft"
    HARD = "hard"


class Item(BaseModel):
    id: str
    name: str
    rarity: Rarity
    rate: float = Field(gt=0.0, le=1.0)
    is_pickup: bool = False


class PityConfig(BaseModel):
    soft_pity_start: int = Field(ge=1)
    hard_pity: int = Field(ge=1)
    rate_boost_per_pull: float = Field(ge=0.0, le=1.0)
    boost_formula: Literal["linear", "exponential"] = "linear"

    @model_validator(mode="after")
    def validate_pity_order(self) -> "PityConfig":
        if self.soft_pity_start >= self.hard_pity:
            raise ValueError("soft_pity_start must be less than hard_pity")
        return self


class StonePrice(BaseModel):
    stones_per_pull: int = Field(ge=1, description="1回引くのに必要な石数")
    jpy_per_stone: float = Field(gt=0.0, description="1石あたりの円単価（最良パック基準・参考値）")

    def jpy_per_pull(self) -> Decimal:
        """1回引くあたりの参考コスト（円）。Decimal演算で精度を保証する。"""
        return (Decimal(str(self.jpy_per_stone)) * self.stones_per_pull).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


class Banner(BaseModel):
    id: str
    name: str
    items: list[Item]
    pity: PityConfig
    guaranteed_featured: bool = True
    stone_price: StonePrice | None = None

    @model_validator(mode="after")
    def validate_items_and_rates(self) -> "Banner":
        if not self.items:
            raise ValueError("items must not be empty")
        total = sum(i.rate for i in self.items)
        if total > 1.0 + 1e-9:
            raise ValueError(f"sum of item rates {total:.4f} exceeds 1.0")
        return self


class PullResult(BaseModel):
    item: Item
    pity_count: int
    pity_type: PityType


class SessionState(BaseModel):
    banner_id: str
    pity_count: int = 0
    since_featured: int = 0
    total_pulls: int = 0
    ssr_count: int = 0
    ssr_pity_sum: int = 0
    history: list[PullResult] = Field(default_factory=list)
    custom_banners: dict[str, Banner] = Field(default_factory=dict)


class CustomBannerInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    ssr_rate_pct: float = Field(gt=0, le=50)
    soft_pity_start: int = Field(ge=10, le=989)
    hard_pity: int = Field(ge=20, le=999)
    jpy_per_pull: float | None = Field(default=None, gt=0, le=99999)

    @model_validator(mode="after")
    def validate_pity_gap(self) -> "CustomBannerInput":
        """hard_pity と soft_pity_start の差が10以上あることを保証する。"""
        if self.hard_pity - self.soft_pity_start < 10:
            raise ValueError("hard_pity は soft_pity_start より10以上大きくしてください")
        return self

    def to_banner(self) -> Banner:
        """CustomBannerInput から Banner を生成する。"""
        banner_id = f"custom_{uuid.uuid4().hex[:12]}"
        ssr_rate = self.ssr_rate_pct / 100
        # SSR率が上がるほどSR・R率も比例縮小し合計が常に1.0になる
        sr_total = (1.0 - ssr_rate) * 0.15
        r_rate = (1.0 - ssr_rate) * 0.85
        # soft pity 区間でSSR率を段階的に引き上げる boost 量。
        # ゾーン全体で (ssr_rate * 5) 分の押し上げ効果を均等に配分する設計。
        pity_zone = self.hard_pity - self.soft_pity_start
        rate_boost = round(ssr_rate * 5.0 / pity_zone, 6)
        stone_price = (
            StonePrice(stones_per_pull=1, jpy_per_stone=self.jpy_per_pull)
            if self.jpy_per_pull is not None  # 0除外は gt=0 フィールド制約で保証済み
            else None
        )
        return Banner(
            id=banner_id,
            name=self.name,
            guaranteed_featured=True,
            pity=PityConfig(
                soft_pity_start=self.soft_pity_start,
                hard_pity=self.hard_pity,
                rate_boost_per_pull=rate_boost,
            ),
            stone_price=stone_price,
            items=[
                Item(id="ssr_pickup", name="ピックアップSSR", rarity=Rarity.SSR,
                     rate=round(ssr_rate / 2, 8), is_pickup=True),
                Item(id="ssr_std",    name="スタンダードSSR", rarity=Rarity.SSR,
                     rate=round(ssr_rate / 2, 8)),
                Item(id="sr_1",       name="SR キャラA",      rarity=Rarity.SR,
                     rate=round(sr_total / 2, 8)),
                Item(id="sr_2",       name="SR キャラB",      rarity=Rarity.SR,
                     rate=round(sr_total / 2, 8)),
                Item(id="r_1",        name="R アイテム",      rarity=Rarity.R,
                     rate=round(r_rate, 8)),
            ],
        )
