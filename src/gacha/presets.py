# ゲームシステムを参考にした独自実装のプリセット集。
# 特定のゲームタイトルとは一切関係のない独立した確率設定です。

from gacha.models import Banner, Item, PityConfig, Rarity, StonePrice

PRESET_IDS = ["genshin_like", "fgo_like", "uma_musume_like", "generic_high"]


def genshin_like() -> Banner:
    """0.6% SSR / soft pity 74回 / hard pity 90回 / 50-50保証ありのプリセット。"""
    return Banner(
        id="genshin_like",
        name="原神風バナー (0.6% / 天井90)",
        guaranteed_featured=True,
        pity=PityConfig(soft_pity_start=74, hard_pity=90, rate_boost_per_pull=0.06),
        stone_price=StonePrice(stones_per_pull=160, jpy_per_stone=0.50),
        items=[
            Item(id="ssr_pickup", name="ピックアップSSR", rarity=Rarity.SSR, rate=0.003, is_pickup=True),
            Item(id="ssr_standard", name="スタンダードSSR", rarity=Rarity.SSR, rate=0.003),
            Item(id="sr_1", name="SR キャラA", rarity=Rarity.SR, rate=0.051),
            Item(id="sr_2", name="SR キャラB", rarity=Rarity.SR, rate=0.051),
            Item(id="sr_3", name="SR キャラC", rarity=Rarity.SR, rate=0.051),
            Item(id="r_1", name="R アイテム", rarity=Rarity.R, rate=0.841),
        ],
    )


def fgo_like() -> Banner:
    """1.0% SSR / soft/hard pityなし(純粋確率)のプリセット。"""
    return Banner(
        id="fgo_like",
        name="FGO風バナー (1.0% / 天井なし)",
        guaranteed_featured=False,
        pity=PityConfig(soft_pity_start=998, hard_pity=999, rate_boost_per_pull=0.0),
        stone_price=StonePrice(stones_per_pull=3, jpy_per_stone=18.00),
        items=[
            Item(id="ssr_pickup", name="ピックアップSSR", rarity=Rarity.SSR, rate=0.01, is_pickup=True),
            Item(id="sr_1", name="SR キャラA", rarity=Rarity.SR, rate=0.03),
            Item(id="sr_2", name="SR キャラB", rarity=Rarity.SR, rate=0.03),
            Item(id="sr_3", name="SR キャラC", rarity=Rarity.SR, rate=0.03),
            Item(id="r_1", name="R アイテム", rarity=Rarity.R, rate=0.89),
        ],
    )


def uma_musume_like() -> Banner:
    """3.0% SSR / soft pity 36回 / hard pity 50回 / 保証ありのプリセット。"""
    return Banner(
        id="uma_musume_like",
        name="ウマ娘風バナー (3.0% / 天井50)",
        guaranteed_featured=True,
        pity=PityConfig(soft_pity_start=36, hard_pity=50, rate_boost_per_pull=0.08),
        stone_price=StonePrice(stones_per_pull=50, jpy_per_stone=0.35),
        items=[
            Item(id="ssr_pickup", name="ピックアップSSR", rarity=Rarity.SSR, rate=0.015, is_pickup=True),
            Item(id="ssr_standard", name="スタンダードSSR", rarity=Rarity.SSR, rate=0.015),
            Item(id="sr_1", name="SR キャラA", rarity=Rarity.SR, rate=0.155),
            Item(id="sr_2", name="SR キャラB", rarity=Rarity.SR, rate=0.155),
            Item(id="r_1", name="R アイテム", rarity=Rarity.R, rate=0.66),
        ],
    )


def generic_high() -> Banner:
    """5.0% SSR / soft pity 45回 / hard pity 60回 / 高レート汎用プリセット。"""
    return Banner(
        id="generic_high",
        name="高レート汎用バナー (5.0% / 天井60)",
        guaranteed_featured=True,
        pity=PityConfig(soft_pity_start=45, hard_pity=60, rate_boost_per_pull=0.10),
        stone_price=StonePrice(stones_per_pull=100, jpy_per_stone=1.00),
        items=[
            Item(id="ssr_pickup", name="ピックアップSSR", rarity=Rarity.SSR, rate=0.025, is_pickup=True),
            Item(id="ssr_standard", name="スタンダードSSR", rarity=Rarity.SSR, rate=0.025),
            Item(id="sr_1", name="SR キャラA", rarity=Rarity.SR, rate=0.18),
            Item(id="sr_2", name="SR キャラB", rarity=Rarity.SR, rate=0.18),
            Item(id="r_1", name="R アイテム", rarity=Rarity.R, rate=0.59),
        ],
    )


ALL_PRESETS: dict[str, Banner] = {
    b.id: b for b in [genshin_like(), fgo_like(), uma_musume_like(), generic_high()]
}
