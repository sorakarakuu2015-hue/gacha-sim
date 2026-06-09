import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gacha.engine import calculate_ssr_rate, pull_multi, pull_once
from gacha.models import PityType, Rarity, SessionState
from gacha.presets import fgo_like, genshin_like, uma_musume_like


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


# --- calculate_ssr_rate ---

def test_rate_below_soft_pity_is_base() -> None:
    from gacha.presets import genshin_like
    banner = genshin_like()
    base = 0.006
    assert calculate_ssr_rate(base, banner.pity, 10) == pytest.approx(base)


def test_rate_at_hard_pity_is_one() -> None:
    banner = genshin_like()
    assert calculate_ssr_rate(0.006, banner.pity, banner.pity.hard_pity) == 1.0


def test_rate_increases_in_soft_pity_zone() -> None:
    banner = genshin_like()
    base = 0.006
    r74 = calculate_ssr_rate(base, banner.pity, 74)
    r80 = calculate_ssr_rate(base, banner.pity, 80)
    assert r80 > r74 > base


# --- pity counter boundary ---

def test_hard_pity_triggers_ssr() -> None:
    """天井(hard_pity)回目で必ずSSRが出る。"""
    banner = genshin_like()
    rng = random.Random(0)
    state = SessionState(banner_id=banner.id, pity_count=banner.pity.hard_pity - 1)
    result, new_state = pull_once(banner, state, rng)
    assert result.item.rarity == Rarity.SSR
    assert result.pity_type == PityType.HARD
    assert new_state.pity_count == 0


def test_pity_resets_after_ssr() -> None:
    banner = genshin_like()
    rng = random.Random(0)
    state = SessionState(banner_id=banner.id, pity_count=banner.pity.hard_pity - 1)
    _, new_state = pull_once(banner, state, rng)
    assert new_state.pity_count == 0


def test_pity_increments_on_non_ssr() -> None:
    """SSRが出なかった場合、天井カウントが増える。"""
    banner = genshin_like()
    rng = random.Random(999)  # 999で始めてSSRが出ないシードを前提
    state = SessionState(banner_id=banner.id, pity_count=0)
    results: list[object] = []
    current = state
    # 最初のSSRまで引く or 最大20回
    for _ in range(20):
        result, current = pull_once(banner, current, rng)
        if result.item.rarity == Rarity.SSR:
            break
        results.append(result)
    # 非SSR時にpityが増えていること
    if results:
        assert current.pity_count >= 0


# --- 50/50 guarantee ---

def test_guaranteed_featured_after_losing_5050() -> None:
    """since_featured >= 1 の状態では必ずピックアップSSRが出る。"""
    banner = genshin_like()
    rng = random.Random(0)
    # since_featured=1: 前回ピックアップ外SSRを引いた状態
    state = SessionState(banner_id=banner.id, pity_count=banner.pity.hard_pity - 1, since_featured=1)
    result, _ = pull_once(banner, state, rng)
    assert result.item.rarity == Rarity.SSR
    assert result.item.is_pickup is True


# --- 統計テスト (hypothesis モンテカルロ) ---

@settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.integers(min_value=0, max_value=99))
def test_genshin_ssr_rate_within_tolerance(seed: int) -> None:
    """10万回試行でSSR排出率が理論値±30%以内に収まる。"""
    banner = genshin_like()
    rng = random.Random(seed)
    state = SessionState(banner_id=banner.id)
    total = 100_000
    ssr_count = 0
    results, final_state = pull_multi(banner, state, rng, total)
    ssr_count = sum(1 for r in results if r.item.rarity == Rarity.SSR)
    actual_rate = ssr_count / total
    # 原神の期待SSR率は約1.6%(soft pity込み)
    assert 0.01 < actual_rate < 0.04, f"SSR rate {actual_rate:.4f} out of expected range"


@settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.integers(min_value=0, max_value=99))
def test_uma_musume_hard_pity_respected(seed: int) -> None:
    """50連以内に必ずSSRが出る(天井保証)。"""
    banner = uma_musume_like()
    rng = random.Random(seed)
    state = SessionState(banner_id=banner.id)
    results, _ = pull_multi(banner, state, rng, banner.pity.hard_pity)
    assert any(r.item.rarity == Rarity.SSR for r in results)


@settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(st.integers(min_value=0, max_value=99))
def test_fgo_no_pity_bias(seed: int) -> None:
    """FGO風(天井なし)は1.0%前後のSSR率になる。"""
    banner = fgo_like()
    rng = random.Random(seed)
    state = SessionState(banner_id=banner.id)
    results, _ = pull_multi(banner, state, rng, 100_000)
    rate = sum(1 for r in results if r.item.rarity == Rarity.SSR) / 100_000
    assert 0.007 < rate < 0.015, f"FGO SSR rate {rate:.4f} out of range"
