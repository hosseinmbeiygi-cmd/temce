#!/usr/bin/env python3
import asyncio
import sys
import requests

async def test_fixes():
    # Test 1: Check if app can be imported
    print("1. Testing app import...")
    try:
        from apps.api.app import app
        print("   ✓ App imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import app: {e}")
        return False

    # Test 2: Check if root route redirects
    print("2. Testing root route...")
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        response = client.get("/")
        print(f"   Response status: {response.status_code}")
        if response.status_code == 307 or response.status_code == 303:
            location = response.headers.get("location")
            print(f"   Redirect location: {location}")
            if "/api/v1/docs" in location:
                print("   ✓ Root route redirects to API docs")
                return True
            else:
                print(f"   ✗ Root route redirects to wrong location: {location}")
                return False
        else:
            print(f"   ✗ Root route didn't redirect (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Failed to test root route: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_fixes())
    sys.exit(0 if success else 1)