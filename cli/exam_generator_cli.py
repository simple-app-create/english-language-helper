# exam_generator_cli.py

# Import necessary modules
import os # For API key management
from typing import List, Optional, Union # For type hinting
import json # For handling JSON data
import click # For CLI interactions


# from google.cloud import firestore # For Firestore integration
from dotenv import load_dotenv # To load .env file for local development

from pydantic import ValidationError

# Import Pydantic models from schemas.py (now at project root)
from schemas import SpellingCorrectionQuestion, DifficultyDetail, LocalizedString, ChoiceDetail


# Import functions from local modules
from .firestore_utils import get_firestore_client, add_document_to_collection
from .exam_logic.exam_generation_utils import _prompt_localized_string, _prompt_difficulty_detail, _call_openai_api, _call_gemini_api
from .exam_logic.spelling_correction_generator import handle_spelling_correction_generation
from .exam_logic.fill_in_the_blank_generator import handle_fill_in_the_blank_generation
from .exam_logic.reading_comprehension_generator import handle_reading_comprehension_generation
from .exam_logic.sentence_translation_generator import handle_sentence_translation_generation
from .exam_logic.picture_description_generator import handle_picture_description_generation
from .exam_logic.listening_comprehension_generator import handle_listening_comprehension_generation
# from firestore_utils import get_document # Example function, uncomment if needed

# Placeholder for LLM API Key
LLM_API_KEY = None
LLM_SERVICE_NAME = None # To store "OPENAI" or "GOOGLE"

# Global Firestore client
db = None

def load_llm_api_key():
    """
    Placeholder function to load LLM API key.
    Refer to llm_article_generator.py for an example of how to load API keys,
    e.g., using environment variables or a .env file.
    It will try to load GOOGLE_API_KEY first, then OPENAI_API_KEY.
    """
    global LLM_API_KEY, LLM_SERVICE_NAME
    load_dotenv()  # Load environment variables from .env file if it exists

    google_api_key = os.getenv("GOOGLE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if google_api_key:
        LLM_API_KEY = google_api_key
        LLM_SERVICE_NAME = "GOOGLE"
        print("Successfully loaded GOOGLE_API_KEY (Gemini).")
    elif openai_api_key:
        LLM_API_KEY = openai_api_key
        LLM_SERVICE_NAME = "OPENAI"
        print("Successfully loaded OPENAI_API_KEY.")
    else:
        print("Error: Neither GOOGLE_API_KEY nor OPENAI_API_KEY found in environment variables.")
        print("Please set one of these environment variables or ensure your .env file is configured correctly.")
        # Decide if the program should exit or continue without an API key
        # For now, it will continue, but generation functions will fail.
        LLM_API_KEY = None
        LLM_SERVICE_NAME = None


def initialize_firestore():
    """
    Placeholder function to initialize Firestore client.
    Uses get_firestore_client from firestore_utils.py.
    """
    global db
    print("Attempting to initialize Firestore client...")
    try:
        # get_firestore_client will handle messages for success/failure
        # and environment variable checks for FIREBASE_SERVICE_ACCOUNT_KEY_PATH
        db = get_firestore_client()
        if db:
            print("Firestore client initialized successfully.")
        else:
            print("Failed to initialize Firestore client. Check logs from firestore_utils.")
            # Program can continue, but functions requiring db will need to check if db is None
    except Exception as e:
        print(f"An unexpected error occurred during Firestore initialization in exam_generator_cli.py: {e}")
        click.echo(f"An unexpected error occurred during Firebase initialization: {e}", err=True)
        db = None # Ensure db is None if any unexpected error occurs here


# Note: _prompt_spelling_details and generate_spelling_correction were moved to 
# exam_logic/spelling_correction_generator.py

# Note: _call_openai_api and _call_gemini_api were moved to exam_generation_utils.py

# generate_fill_in_the_blank() was moved to cli/exam_logic/fill_in_the_blank_generator.py
# It is now imported as handle_fill_in_the_blank_generation.

# generate_reading_comprehension() was moved to cli/exam_logic/reading_comprehension_generator.py
# It is now imported as handle_reading_comprehension_generation.
 
 # generate_spelling_correction() and its helper _prompt_spelling_details()
 # were moved to cli/exam_logic/spelling_correction_generator.py
 # It is now imported as handle_spelling_correction_generation.
 
# generate_sentence_translation() was moved to cli/exam_logic/sentence_translation_generator.py
# It is now imported as handle_sentence_translation_generation.

# generate_picture_description() was moved to cli/exam_logic/picture_description_generator.py
# It is now imported as handle_picture_description_generation.

# generate_listening_comprehension() was moved to cli/exam_logic/listening_comprehension_generator.py
# It is now imported as handle_listening_comprehension_generation.

@click.command()
def main():
    """English Exam Question Generator CLI."""
    # Load API Key and Initialize Firestore at the start
    load_llm_api_key()
    initialize_firestore()

    menu_options = {
        '1': ("Fill in the Blank (句子填空)", lambda: handle_fill_in_the_blank_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '2': ("Spelling Correction (拼字訂正)", lambda: handle_spelling_correction_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '3': ("Reading Comprehension (閱讀測驗)", lambda: handle_reading_comprehension_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '4': ("Sentence Translation (句子翻譯)", lambda: handle_sentence_translation_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '5': ("Picture Description (看圖辨義)", lambda: handle_picture_description_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '6': ("Listening Comprehension (聽力測驗)", lambda: handle_listening_comprehension_generation(db, LLM_API_KEY, LLM_SERVICE_NAME)),
        '7': ("Exit", None) # Special case for exiting
    }

    while True:
        click.echo("\n--- English Exam Question Generator ---")
        for key, (text, _) in menu_options.items():
            click.echo(f"{key}. {text}")
        click.echo("---------------------------------------")
        
        choice = click.prompt("Enter your choice", type=click.Choice(list(menu_options.keys())), show_choices=False)

        if choice == '7':
            click.echo("Exiting program. Goodbye!")
            break
        
        text, func = menu_options[choice]
        if func:
            func()
        else:
            # Should not happen with current menu_options if choice is not '7'
            click.echo(f"No function defined for '{text}'. This is unexpected.", err=True)

if __name__ == "__main__":
    main()
