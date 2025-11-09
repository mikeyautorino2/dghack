"""Test script to verify Polymarket live markets API"""
import asyncio
import aiohttp
from backend.services import polymarket_api

async def test_live_markets():
    print("=" * 60)
    print("Testing Polymarket Live Markets API")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Test NFL markets
        print("\n🏈 Fetching NFL markets...")
        nfl_markets = await polymarket_api.get_active_sports_markets(session, "nfl", limit=10)
        print(f"   Found {len(nfl_markets)} NFL markets")

        if nfl_markets:
            print("\n   Sample NFL markets:")
            for m in nfl_markets[:3]:
                print(f"   • {m['away_team']} @ {m['home_team']}")
                print(f"     Away: {m['away_price']:.2%} | Home: {m['home_price']:.2%}")
                print(f"     Date: {m['game_date']}")
                print(f"     Volume: ${m['volume']:,.0f}")
                print()

        # Test NBA markets
        print("🏀 Fetching NBA markets...")
        nba_markets = await polymarket_api.get_active_sports_markets(session, "nba", limit=10)
        print(f"   Found {len(nba_markets)} NBA markets")

        if nba_markets:
            print("\n   Sample NBA markets:")
            for m in nba_markets[:3]:
                print(f"   • {m['away_team']} @ {m['home_team']}")
                print(f"     Away: {m['away_price']:.2%} | Home: {m['home_price']:.2%}")
                print(f"     Date: {m['game_date']}")
                print(f"     Volume: ${m['volume']:,.0f}")
                print()

        # Test caching
        print("🔄 Testing cache (should be instant)...")
        import time
        start = time.time()
        cached_nfl = await polymarket_api.get_active_sports_markets_cached(session, "nfl")
        elapsed = time.time() - start
        print(f"   Cached response time: {elapsed*1000:.1f}ms")
        print(f"   Same data? {len(cached_nfl) == len(nfl_markets)}")

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_live_markets())
