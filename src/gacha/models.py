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
