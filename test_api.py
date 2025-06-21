#!/usr/bin/env python3
"""
Test script for the Megacloud API
"""

import requests
import json
import sys

def test_local_api():
    """Test the local Flask API"""
    base_url = "http://localhost:8080"
    
    # Test URL
    test_url = "https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"
    
    print("Testing Megacloud API...")
    print(f"Base URL: {base_url}")
    print(f"Test URL: {test_url}")
    print("-" * 50)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 2: GET request
    print("2. Testing GET /api/extract...")
    try:
        response = requests.get(f"{base_url}/api/extract", params={"url": test_url})
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            if data.get('data'):
                print(f"   Sources count: {len(data['data'].get('sources', []))}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 3: POST request
    print("3. Testing POST /api/extract...")
    try:
        payload = {"url": test_url}
        response = requests.post(f"{base_url}/api/extract", json=payload)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success')}")
            if data.get('data'):
                print(f"   Sources count: {len(data['data'].get('sources', []))}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()
    
    # Test 4: Invalid URL
    print("4. Testing invalid URL...")
    try:
        response = requests.get(f"{base_url}/api/extract", params={"url": "https://invalid-url.com"})
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python test_api.py")
        print("Make sure the Flask API is running on localhost:8080")
        sys.exit(0)
    
    test_local_api() 