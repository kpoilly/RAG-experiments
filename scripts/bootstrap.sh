#!/bin/bash

ENV_FILE=".env"

generate_jwt_key() {
    openssl rand -hex 32
}
generate_fernet_key() {
    openssl rand -base64 32
}

if [ ! -f "$ENV_FILE" ]; then
    echo "Creating a new .env file..."
    touch "$ENV_FILE"
    echo "# Environment variables for RAG Experiments" >> "$ENV_FILE"
fi

check_and_add_key() {
    KEY_NAME=$1
    GENERATOR_FUNC=$2
    if ! grep -q "^${KEY_NAME}=" "$ENV_FILE"; then
        echo "'${KEY_NAME}' is missing. Generating a new one..."
        NEW_VALUE=$($GENERATOR_FUNC)
        echo "" >> "$ENV_FILE"
        echo "${KEY_NAME}=${NEW_VALUE}" >> "$ENV_FILE"
        echo "'${KEY_NAME}' has been generated and saved to .env"
    else
        echo "'${KEY_NAME}' already exists. Skipping."
    fi
}

echo "--- Ensuring secrets are present in .env file ---"
check_and_add_key "JWT_SECRET_KEY" generate_jwt_key
check_and_add_key "ENCRYPTION_KEY" generate_fernet_key
echo "Secret check complete."