import os
import time
import requests

from cryptography.fernet import Fernet
from secrets import token_hex
from dotenv import load_dotenv, set_key, find_dotenv

# --- Config ---
API_URL = "http://localhost/api/auth"
TOKEN_FILE = ".auth_token"
ENV_FILE = find_dotenv()

DEFAULT_USER = os.getenv("DEFAULT_USER_EMAIL", "admin@admin.com")
DEFAULT_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "admin")


def generate_secret_key(length=32):
    return token_hex(length)

def generate_fernet_key():
    return Fernet.generate_key().decode()

def check_and_generate_secrets():
    """
    Check if secrets are in .env, and if not, generate them.
    """
    print("--- Checking for required secrets in .env file ---")
    load_dotenv(ENV_FILE)
    
    secrets_to_check = {
        "JWT_SECRET_KEY": generate_secret_key,
        "ENCRYPTION_KEY": generate_fernet_key,
    }
    
    updated = False
    for key, generator_func in secrets_to_check.items():
        if not os.getenv(key) or os.getenv(key) in ["", "your-secret-key", "your-encryption-key"]:
            print(f"'{key}' is missing or has a default value. Generating a new one...")
            new_value = generator_func()
            set_key(ENV_FILE, key, new_value)
            print(f"✅ '{key}' has been generated and saved to .env")
            updated = True
        else:
            print(f"'{key}' already exists. Skipping.")

    if updated:
        print(".env file has been updated. Please restart the services if they are already running.")
    else:
        print("All secrets are properly configured.")


def wait_for_api_ready(timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get("http://localhost/api/health")
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(2)
    print("Error: Timed out waiting for the API to become available.")
    return False

def bootstrap_auth():
    print("--- Bootstrapping Authentication ---")
    if not wait_for_api_ready():
        return

    print(f"Ensuring default user '{DEFAULT_USER}' exists...")
    try:
        register_payload = {"email": DEFAULT_USER, "password": DEFAULT_PASSWORD}
        response = requests.post(f"{API_URL}/register", json=register_payload)
        if response.status_code == 200:
            print("Default user created successfully.")
        elif response.status_code == 400 and "already registered" in response.text:
            print("Default user already exists. Skipping registration.")
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error during registration: {e}")
        return

    print("Requesting authentication token...")
    try:
        login_payload = {"username": DEFAULT_USER, "password": DEFAULT_PASSWORD}
        response = requests.post(f"{API_URL}/token", data=login_payload)
        response.raise_for_status()
        
        token = response.json().get("access_token")
        if not token:
            print("Login failed: No access token in response.")
            return

        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"Token saved successfully to '{TOKEN_FILE}'.")
    except requests.RequestException as e:
        print(f"Error during login: {e}")
        if e.response is not None:
            print(f"Server response: {e.response.text}")
        return


if __name__ == "__main__":
    if not ENV_FILE:
        with open(".env", "w") as f:
            f.write("# Environment variables for RAG Experiments\n")
        ENV_FILE = ".env"
        print("Created a new .env file.")
    check_and_generate_secrets()
    bootstrap_auth()
