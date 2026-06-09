import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from gacha.web.app import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_list_banners(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/banners")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 4


async def test_start_session(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    assert resp.status_code == 200
    assert resp.json()["banner_id"] == "genshin_like"
    assert "gacha_session" in resp.cookies


async def test_pull_requires_session(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/pull/10")
    assert resp.status_code == 400


async def test_pull_10(client: AsyncClient) -> None:
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    resp = await client.post("/api/v1/pull/10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 10


async def test_pull_count_capped_at_200(client: AsyncClient) -> None:
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    resp = await client.post("/api/v1/pull/201")
    assert resp.status_code == 422


async def test_stats_after_pull(client: AsyncClient) -> None:
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    await client.post("/api/v1/pull/10")
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pulls"] == 10


async def test_reset_session(client: AsyncClient) -> None:
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    resp = await client.delete("/api/v1/session")
    assert resp.status_code == 204
    resp2 = await client.get("/api/v1/stats")
    assert resp2.status_code == 400


async def test_concurrent_pulls(client: AsyncClient) -> None:
    """同時アクセスでセッション状態が壊れないことを確認する。"""
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    tasks = [client.post("/api/v1/pull/1") for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    for resp in responses:
        assert resp.status_code == 200


async def test_stats_includes_cost_jpy(client: AsyncClient) -> None:
    """genshin_like: 160石×¥0.50=¥80/回 → 10回=¥800。"""
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    await client.post("/api/v1/pull/10")
    resp = await client.get("/api/v1/stats")
    data = resp.json()
    assert data["cost_jpy"] == pytest.approx(800.0)


async def test_stats_cost_per_ssr_none_at_zero_pulls(client: AsyncClient) -> None:
    """引く前はSSR未獲得なのでcost_per_ssr_jpyはNone。"""
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    resp = await client.get("/api/v1/stats")
    data = resp.json()
    assert data["cost_jpy"] == pytest.approx(0.0)
    assert data["cost_per_ssr_jpy"] is None


async def test_stats_cost_none_without_stone_price(client: AsyncClient) -> None:
    """stone_priceなしのカスタムバナーはcost_jpyがNone。"""
    banner_payload = {
        "id": "test_no_price",
        "name": "石単価なしテストバナー",
        "guaranteed_featured": False,
        "pity": {
            "soft_pity_start": 10,
            "hard_pity": 20,
            "rate_boost_per_pull": 0.1,
            "boost_formula": "linear",
        },
        "items": [
            {"id": "ssr1", "name": "テストSSR", "rarity": "SSR", "rate": 0.05, "is_pickup": True},
            {"id": "r1", "name": "テストR", "rarity": "R", "rate": 0.95},
        ],
    }
    await client.post("/api/v1/banners", json=banner_payload)
    await client.post("/api/v1/session", params={"banner_id": "test_no_price"})
    await client.post("/api/v1/pull/10")
    resp = await client.get("/api/v1/stats")
    data = resp.json()
    assert data["cost_jpy"] is None
    assert data["cost_per_ssr_jpy"] is None


async def test_stats_html_shows_yen_symbol(client: AsyncClient) -> None:
    """統計フラグメントに課金表示（¥）が含まれること。"""
    await client.post("/api/v1/session", params={"banner_id": "genshin_like"})
    await client.post("/api/v1/pull/10")
    resp = await client.get("/stats")
    assert resp.status_code == 200
    assert "¥" in resp.text


async def test_custom_banner_create_and_use(client: AsyncClient) -> None:
    banner_payload = {
        "id": "test_custom",
        "name": "テストバナー",
        "guaranteed_featured": False,
        "pity": {
            "soft_pity_start": 10,
            "hard_pity": 20,
            "rate_boost_per_pull": 0.1,
            "boost_formula": "linear",
        },
        "items": [
            {"id": "ssr1", "name": "テストSSR", "rarity": "SSR", "rate": 0.05, "is_pickup": True},
            {"id": "sr1", "name": "テストSR", "rarity": "SR", "rate": 0.15},
            {"id": "r1", "name": "テストR", "rarity": "R", "rate": 0.80},
        ],
    }
    resp = await client.post("/api/v1/banners", json=banner_payload)
    assert resp.status_code == 201

    await client.post("/api/v1/session", params={"banner_id": "test_custom"})
    resp2 = await client.post("/api/v1/pull/20")
    assert resp2.status_code == 200
    results = resp2.json()["results"]
    assert any(r["item"]["rarity"] == "SSR" for r in results)
