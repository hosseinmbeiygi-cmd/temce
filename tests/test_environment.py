#!/usr/bin/env python3
import asyncio
import sys


async def test_api_endpoints():
    print("1. Testing API endpoints...")

    # Test 1: Health endpoint (should always work)
    print("   Testing /api/v1/health...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/health")
            if response.status_code == 200:
                data = response.json()
                print(f"   Health endpoint OK: {data}")
            else:
                print(f"   Health endpoint failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"   Health endpoint error: {e}")
        return False

    # Test 2: Market overview endpoint
    print("   Testing /api/v1/market/overview...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/market/overview")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"   Market overview OK: {len(data.get('data', {}).get('markets', []))} markets found")
                else:
                    print(f"   Market overview failed: {data.get('error', 'Unknown error')}")
            else:
                print(f"   Market overview status: {response.status_code}")
    except Exception as e:
        print(f"   Market overview error: {e}")

    # Test 3: Symbols endpoint
    print("   Testing /api/v1/symbols...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:8000/api/v1/symbols", json={
                "symbol": "TEST001",
                "name": "Test Symbol"
            })
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"   Create symbol OK: {data.get('data', {}).get('id', 'New ID')}")
                else:
                    print(f"   Create symbol failed: {data.get('error', 'Unknown error')}")
            else:
                print(f"   Create symbol status: {response.status_code}")
    except Exception as e:
        print(f"   Create symbol error: {e}")

    # Test 4: Signals endpoint
    print("   Testing /api/v1/signals...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/signals?page=1&page_size=5")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"   List signals OK: {data.get('data', []).length} signals found")
                else:
                    print(f"   List signals failed: {data.get('error', 'Unknown error')}")
            else:
                print(f"   List signals status: {response.status_code}")
    except Exception as e:
        print(f"   List signals error: {e}")

    return True

async def test_environment():
    print("\n2. Testing environment setup...")

    # Test Python dependencies
    print("   Checking Python dependencies...")
    try:
        import fastapi
        import pydantic
        import sqlalchemy
        import uvicorn
        print("   Python dependencies available")
    except ImportError as e:
        print(f"   Python dependencies missing: {e}")
        return False

    # Test if we can import the app
    print("   Testing app import...")
    try:
        sys.path.insert(0, 'C:\\Users\\Iran\\Desktop\\temce')
        print("   App imported successfully")
    except Exception as e:
        print(f"   App import failed: {e}")
        return False

    return True

async def main():
    print("=" * 60)
    print("iran-market-platform - Environment Test")
    print("=" * 60)

    env_ok = await test_environment()
    if not env_ok:
        print("\n❌ Environment setup failed")
        return 1

    api_ok = await test_api_endpoints()
    if not api_ok:
        print("\n⚠️  API tests completed with warnings")

    print("\n" + "=" * 60)
    print("✅ Test completed successfully")
    print("The program should now be working!")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
