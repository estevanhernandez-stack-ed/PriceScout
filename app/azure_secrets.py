import os
from typing import Optional

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
except Exception:
    DefaultAzureCredential = None  # type: ignore
    SecretClient = None  # type: ignore


def get_secret(name: str) -> Optional[str]:
    """
    Retrieve a secret value by name using the following precedence:
    1) Environment variable with exact name (e.g., DATABASE-URL)
    2) Azure Key Vault secret (requires AZURE_KEY_VAULT_URL and managed identity or credentials)

    Returns the secret value as a string, or None if not found/available.
    """
    # 1) Direct environment variable mapping (support both NAME and NAME with underscores)
    if name in os.environ:
        return os.environ.get(name)

    alt_env = name.replace('-', '_')
    if alt_env in os.environ:
        return os.environ.get(alt_env)

    # 2) Azure Key Vault
    kv_url = os.getenv("AZURE_KEY_VAULT_URL")
    if not kv_url or not DefaultAzureCredential or not SecretClient:
        return None

    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=kv_url, credential=credential)
        secret = client.get_secret(name)
        return secret.value
    except Exception:
        return None
