import click
import firebase_admin
from firebase_admin import credentials, firestore
import os
from typing import Optional # Import Optional

# Define the name of the environment variable for the key path
SERVICE_ACCOUNT_KEY_ENV_VAR = 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH'

# Global variable for the Firestore database client
# This helps to reuse the initialized client within the same process/session
_db_client: Optional[firestore.Client] = None # Explicitly type _db_client to allow None

def get_firestore_client(key_path: str = None) -> Optional[firestore.Client]: # Add return type hint
    """
    Initializes Firebase Admin SDK if not already initialized and returns a Firestore client.
    It reuses an existing client if one has already been initialized by this function.

    Args:
        key_path (str, optional): Path to the Firebase service account key JSON file.
                                  If None, it tries to use the FIREBASE_SERVICE_ACCOUNT_KEY_PATH
                                  environment variable.

    Returns:
        firestore.Client or None: An initialized Firestore client, or None if initialization fails.
    """
    global _db_client
    if _db_client is not None:
        return _db_client

    effective_key_path = key_path or os.environ.get(SERVICE_ACCOUNT_KEY_ENV_VAR)

    if not effective_key_path:
        click.echo(
            f"Error: Firebase service account key path is required. "
            f"Set the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable or provide the --key-path argument.",
            err=True
        )
        return None

    if not os.path.exists(effective_key_path):
        click.echo(f"Error: Service account key file not found at path: {effective_key_path}", err=True)
        return None

    try:
        cred = credentials.Certificate(effective_key_path)
        # Initialize the app only if it hasn't been initialized elsewhere.
        # This check is robust for various scenarios (e.g., running multiple commands in one script).
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        # If an app IS initialized, we assume it's the one we want to use,
        # and firestore.client() will use it.
        
        _db_client = firestore.client()
        # click.echo("Firebase Admin SDK initialized successfully and Firestore client obtained.", err=True) # Optional debug
        return _db_client
    except ValueError as ve: # Often indicates a problem with the key file itself
        click.echo(f"Error initializing Firebase with key file {effective_key_path}. "
                   f"Is it a valid JSON key file? Details: {ve}", err=True)
        return None
    except Exception as e:
        click.echo(f"An unexpected error occurred during Firebase initialization: {e}", err=True)
        return None

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    # You would need to set the environment variable or pass a path
    # export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
    # python english-language-helper/cli/firestore_utils.py
    
    print("Attempting to get Firestore client (ensure env var is set or modify for direct test)...")
    # For direct testing, you might want to provide a path if the env var isn't set globally
    # test_key_path = "/path/to/your/serviceAccountKey.json" 
    # client = get_firestore_client(key_path=test_key_path)
    client = get_firestore_client() # Relies on env var for this simple test
    
    if client:
        print("Successfully obtained Firestore client.")
        # You could add a simple test query here if needed, e.g., list collections
        try:
            collections = [col.id for col in client.collections()]
            print(f"Available collections: {collections}")
        except Exception as e:
            print(f"Error listing collections: {e}")
    else:
        print("Failed to obtain Firestore client. Check service account key path and permissions.")
