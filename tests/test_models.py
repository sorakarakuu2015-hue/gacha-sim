from decimal import Decimal

import pytest
from pydantic import ValidationError

from gacha.models import Banner, Item, PityConfig, Rarity, StonePrice
from gacha.presets import ALL_PRESETS


def test_all_presets_validate() -> None:
    for preset_id, banner in ALL_PRESETS.items():
        assert banner.id == preset_id
        assert len(banner.items) > 0
        total = sum(i.rate for i in banner.items)
        assert total <= 1.0 + 1e-9, f"{preset_id}: rate sum {total} > 1.0"


def test_banner_rejects_empty_items() -> None:
    with pytest.raises(ValidationError, match="items must not be empty"):
        Banner(
            id="bad",
            name="bad",
            items=[],
            pity=PityConfig(soft_pity_start=74, hard_pity=90, rate_boost_per_pull=0.06),
        )


def test_banner_rejects_rate_overflow() -> None:
    with pytest.raises(ValidationError, match="exceeds 1.0"):
        Banner(
            id="bad",
            name="bad",
            items=[
                Item(id="a", name="A", rarity=Rarity.SSR, rate=0.7),
                Item(id="b", name="B", rarity=Rarity.SSR, rate=0.7),
            ],
            pity=PityConfig(soft_pity_start=74, hard_pity=90, rate_boost_per_pull=0.06),
        )


def test_pity_config_rejects_invalid_order() -> None:
    with pytest.raises(ValidationError, match="soft_pity_start must be less than hard_pity"):
        PityConfig(soft_pity_start=90, hard_pity=74, rate_boost_per_pull=0.06)


def test_stone_price_jpy_per_pull_decimal_accuracy() -> None:
    sp = StonePrice(stones_per_pull=50, jpy_per_stone=0.35)
    assert sp.jpy_per_pull() == Decimal("17.50")


def test_stone_price_jpy_per_pull_genshin() -> None:
    sp = StonePrice(stones_per_pull=160, jpy_per_stone=0.50)
    assert sp.jpy_per_pull() == Decimal("80.00")


def test_stone_price_validation_rejects_zero_stones() -> None:
    with pytest.raises(ValidationError):
        StonePrice(stones_per_pull=0, jpy_per_stone=1.0)


def test_stone_price_validation_rejects_zero_price() -> None:
    with pytest.raises(ValidationError):
        StonePrice(stones_per_pull=1, jpy_per_stone=0.0)


def test_all_presets_have_stone_price() -> None:
    for preset_id, banner in ALL_PRESETS.items():
        assert banner.stone_price is not None, f"{preset_id}: stone_price is None"
        assert banner.stone_price.stones_per_pull >= 1
        assert banner.stone_price.jpy_per_stone > 0
