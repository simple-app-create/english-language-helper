"""Main entry point for the English Language Helper Streamlit application."""

import sys
import os

# Get the absolute path of the directory containing main.py (project root)
_project_root = os.path.dirname(os.path.abspath(__file__))

# Add the project root to sys.path if it's not already there
# This allows for absolute imports from the project root (e.g., "from schemas import ...")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
from sections import (
    welcome_tab,
    reading_tab,
    saved_words_tab,
    questions_tab,
    listening_tab,
    genai_reading_tab,
)

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv  # Re-added for local .env file support
from logger_config import main_app_logger  # Import main_app_logger

# --- Logging Setup ---
# Logging is now configured in logger_config.py
# logger = logging.getLogger(__name__) # Removed


# --- Firebase Initialization ---
@st.cache_resource
def get_firestore_client():
    """
    Initializes Firebase Admin SDK and returns a Firestore client.
    Loads credentials primarily from st.secrets (for FIREBASE_SERVICE_ACCOUNT_JSON).
    As a fallback for local development, loads a path to the service account key
    from an environment variable (FIREBASE_SERVICE_ACCOUNT_KEY_PATH) via a .env file.
    Returns None if initialization fails.
    """
    load_dotenv()  # Load environment variables from .env file for local development

    try:
        # Check if Firebase app is already initialized
        if not firebase_admin._apps:
            cred = None  # Initialize cred to None
            cred_object_from_json_string = None

            # Option 1: Service account JSON content directly in st.secrets (preferred for Streamlit Cloud)
            if "FIREBASE_SERVICE_ACCOUNT_JSON" in st.secrets:
                service_account_json_str = st.secrets["FIREBASE_SERVICE_ACCOUNT_JSON"]
                if (
                    isinstance(service_account_json_str, str)
                    and service_account_json_str.strip()
                ):
                    try:
                        parsed_json = json.loads(service_account_json_str)
                        cred_object_from_json_string = credentials.Certificate(
                            parsed_json
                        )
                        main_app_logger.info(
                            "Attempting to initialize Firebase with FIREBASE_SERVICE_ACCOUNT_JSON from st.secrets."
                        )
                        cred = cred_object_from_json_string
                    except json.JSONDecodeError as e:
                        main_app_logger.error(
                            f"Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON from st.secrets: {e}",
                            exc_info=True,
                        )
                    except (
                        Exception
                    ) as e:  # Catch other potential errors with Certificate creation
                        main_app_logger.error(
                            f"Error creating credential from FIREBASE_SERVICE_ACCOUNT_JSON (st.secrets): {e}",
                            exc_info=True,
                        )
                else:
                    main_app_logger.warning(
                        "FIREBASE_SERVICE_ACCOUNT_JSON found in st.secrets but is empty or not a string."
                    )

            if not cred:
                main_app_logger.error(
                    "Firebase credentials not successfully loaded. "
                    "Checked for FIREBASE_SERVICE_ACCOUNT_JSON in Streamlit secrets and "
                    "FIREBASE_SERVICE_ACCOUNT_KEY_PATH in environment variables (e.g., .env file)."
                )
                st.error(
                    "Firebase configuration error: Credentials not found or invalid. Please check: \n"
                    "1. Streamlit secrets for 'FIREBASE_SERVICE_ACCOUNT_JSON' (for deployed apps or local .streamlit/secrets.toml).\n"
                    "2. Your .env file for 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH' (for local development)."
                )
                return None

        firebase_admin.initialize_app(cred)
        main_app_logger.info("Firebase Admin SDK initialized successfully!")

        db = firestore.client()
        return db
    except Exception as e:
        main_app_logger.critical(
            f"Critical error during Firebase initialization: {e}", exc_info=True
        )
        st.error("Firebase initialization failed. Please check app.log for details.")
        return None


db_client = get_firestore_client()


def main() -> None:
    """Initialize and run the English Language Helper application.

    Sets up the Streamlit interface with tabbed navigation for different
    learning activities including reading, vocabulary, listening, and quizzes.
    """
    st.title("兒童英語閱讀輔助程式")  # App Title in Traditional Chinese

    # Define the tab labels in Traditional Chinese
    tab_labels: list[str] = [
        "歡迎",
        "AI 閱讀測驗",
        "閱讀文章",
        "單字練習",
        "聽力練習",
        "測驗",
    ]  # "歡迎" is Welcome

    # Create the tabs
    (
        tab_welcome,
        tab_reading_comp_gen,
        tab_reading,
        tab_saved_words,
        tab_listening,
        tab_questions,
    ) = st.tabs(tab_labels)

    # Call functions from separate files to display tab content
    welcome_tab.show_welcome_tab(tab_welcome)
    genai_reading_tab.show_genai_tab(tab_reading_comp_gen)  # New tab: "AI 生成練習"
    reading_tab.show_reading_tab(tab_reading, db_client)  # Corresponds to "閱讀文章"
    saved_words_tab.show_saved_words_tab(tab_saved_words)  # Corresponds to "單字練習"
    listening_tab.show_listening_tab(tab_listening)  # Corresponds to "聽力練習"
    questions_tab.show_questions_tab(tab_questions, db_client)  # Corresponds to "測驗"


if __name__ == "__main__":
    main()
