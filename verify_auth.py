import requests
import sys

BASE_URL = "http://localhost:8000"

def test_auth():
    print("Testing Authentication...")

    # 1. Login
    login_data = {
        "username": "admin",
        "password": "admin"
    }
    try:
        response = requests.post(f"{BASE_URL}/token", data=login_data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            print(f"SUCCESS: Login successful. Token received.")
        else:
            print(f"FAILURE: Login failed. Status: {response.status_code}")
            print(response.text)
            sys.exit(1)
    except Exception as e:
        print(f"FAILURE: Could not connect to backend. {e}")
        sys.exit(1)

    # 2. Access Protected Route
    print("\nTesting Protected Route...")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        response = requests.get(f"{BASE_URL}/api/responses", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Protected route accessed.")
            print(f"Count of responses: {len(data)}")
        else:
            print(f"FAILURE: Protected route access denied. Status: {response.status_code}")
            print(response.text)
            sys.exit(1)
    except Exception as e:
        print(f"FAILURE: Could not connect to backend. {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_auth()
