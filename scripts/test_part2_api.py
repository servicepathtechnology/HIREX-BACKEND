"""Test script for Part 2 API endpoints.

This script tests all 12 endpoints for Daily/Weekly/Monthly Challenges.
Requires a running backend server and valid JWT token.

Usage:
    python scripts/test_part2_api.py <JWT_TOKEN>
"""

import sys
import requests
import json
from datetime import date

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


def print_test(name: str):
    """Print test header."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)


def print_result(success: bool, response=None, error=None):
    """Print test result."""
    if success:
        print("✅ PASS")
        if response:
            print(f"Response: {json.dumps(response, indent=2)}")
    else:
        print("❌ FAIL")
        if error:
            print(f"Error: {error}")


def test_challenge_hub(token: str):
    """Test GET /api/v1/challenges/hub"""
    print_test("Challenge Hub")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/hub",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "daily" in data
            assert "weekly" in data
            assert "monthly" in data
            assert "streak" in data
            assert "recent_completions" in data
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def test_daily_challenge(token: str):
    """Test GET /api/v1/challenges/daily"""
    print_test("Get Daily Challenge")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/daily",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "question" in data
            assert data["difficulty"] == "easy"
            assert data["xp_reward"] == 30
            print_result(True, data)
            return data["id"]
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_start_daily(token: str):
    """Test POST /api/v1/challenges/daily/start"""
    print_test("Start Daily Challenge")
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/challenges/daily/start",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "challenge_id" in data
            assert "room_url" in data
            assert "room_token" in data
            print_result(True, data)
            return data
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_weekly_challenge(token: str):
    """Test GET /api/v1/challenges/weekly"""
    print_test("Get Weekly Challenge")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/weekly",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "question" in data
            assert data["difficulty"] == "medium"
            assert data["xp_reward"] == 75
            print_result(True, data)
            return data["id"]
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_start_weekly(token: str):
    """Test POST /api/v1/challenges/weekly/start"""
    print_test("Start Weekly Challenge")
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/challenges/weekly/start",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "challenge_id" in data
            assert "room_url" in data
            assert "room_token" in data
            print_result(True, data)
            return data
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_monthly_challenge(token: str):
    """Test GET /api/v1/challenges/monthly"""
    print_test("Get Monthly Challenge")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/monthly",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "question" in data
            assert data["difficulty"] == "hard"
            assert data["xp_reward"] == 150
            print_result(True, data)
            return data["id"]
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_start_monthly(token: str):
    """Test POST /api/v1/challenges/monthly/start"""
    print_test("Start Monthly Challenge")
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/challenges/monthly/start",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "challenge_id" in data
            assert "room_url" in data
            assert "room_token" in data
            print_result(True, data)
            return data
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
            return None
    
    except Exception as e:
        print_result(False, error=str(e))
        return None


def test_get_streak(token: str):
    """Test GET /api/v1/challenges/streaks/me"""
    print_test("Get My Streak")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/streaks/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "current_streak" in data
            assert "longest_streak" in data
            assert "grace_day_available" in data
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def test_get_preferences(token: str):
    """Test GET /api/v1/challenges/preferences"""
    print_test("Get Preferences")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/preferences",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "weekly_day" in data
            assert "monthly_date" in data
            assert "notification_time" in data
            assert "timezone" in data
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def test_update_preferences(token: str):
    """Test PATCH /api/v1/challenges/preferences"""
    print_test("Update Preferences")
    
    try:
        payload = {
            "weekly_day": "monday",
            "monthly_date": 15,
            "notification_time": "09:00",
            "timezone": "Asia/Kolkata"
        }
        
        response = requests.patch(
            f"{BASE_URL}{API_PREFIX}/challenges/preferences",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "updated"
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def test_solo_room_data(challenge_id: str, token: str):
    """Test GET /api/v1/challenges/solo/{type}/{id}"""
    print_test("Get Solo Room Data (JWT Auth)")
    
    try:
        response = requests.get(
            f"{BASE_URL}{API_PREFIX}/challenges/solo/daily/{challenge_id}",
            params={"token": token}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "challenge_type" in data
            assert "question" in data
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def test_submit_solution(challenge_id: str, token: str):
    """Test POST /api/v1/challenges/solo/{type}/{id}/submit"""
    print_test("Submit Solution (JWT Auth)")
    
    try:
        payload = {
            "code": "def solution():\n    return 42",
            "language": "python"
        }
        
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/challenges/solo/daily/{challenge_id}/submit",
            params={"token": token},
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "score" in data
            assert "xp_earned" in data
            print_result(True, data)
        else:
            print_result(False, error=f"Status {response.status_code}: {response.text}")
    
    except Exception as e:
        print_result(False, error=str(e))


def run_all_tests(token: str):
    """Run all API tests."""
    print("\n" + "="*60)
    print("HireX Part 2 — API Test Suite")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Token: {token[:20]}...")
    
    # Test 1: Challenge Hub
    test_challenge_hub(token)
    
    # Test 2-3: Daily Challenge
    daily_id = test_daily_challenge(token)
    daily_data = test_start_daily(token)
    
    # Test 4-5: Weekly Challenge
    weekly_id = test_weekly_challenge(token)
    weekly_data = test_start_weekly(token)
    
    # Test 6-7: Monthly Challenge
    monthly_id = test_monthly_challenge(token)
    monthly_data = test_start_monthly(token)
    
    # Test 8: Streak
    test_get_streak(token)
    
    # Test 9-10: Preferences
    test_get_preferences(token)
    test_update_preferences(token)
    
    # Test 11-12: Solo Room (if we have a challenge)
    if daily_data and "room_token" in daily_data:
        test_solo_room_data(daily_data["challenge_id"], daily_data["room_token"])
        test_submit_solution(daily_data["challenge_id"], daily_data["room_token"])
    
    print("\n" + "="*60)
    print("Test Suite Complete")
    print("="*60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_part2_api.py <JWT_TOKEN>")
        print("\nTo get a JWT token:")
        print("1. Login to the HireX app")
        print("2. Copy the Firebase ID token from localStorage")
        print("3. Pass it as the first argument to this script")
        sys.exit(1)
    
    jwt_token = sys.argv[1]
    run_all_tests(jwt_token)
