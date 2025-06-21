import requests
import json

def test_api():
    # Test the home endpoint
    print("Testing home endpoint...")
    response = requests.get('http://localhost:8000/')
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    # Test the extract endpoint with a sample URL
    print("Testing extract endpoint...")
    test_url = "https://megacloud.blog/embed-2/v2/e-1/nGvw8vuMWbml?z=1&autoPlay=1&oa=0&asi=1"
    
    payload = {
        "url": test_url
    }
    
    response = requests.post('http://localhost:8000/extract', json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("Success! Extracted data:")
        print(json.dumps(result, indent=2))
    else:
        print(f"Error: {response.text}")
    
    print()
    
    # Test the new extractor endpoint with query parameter
    print("Testing extractor endpoint with query parameter...")
    response = requests.get(f'http://localhost:8000/extractor?url={test_url}')
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("Success! Extracted data:")
        print(json.dumps(result, indent=2))
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_api() 