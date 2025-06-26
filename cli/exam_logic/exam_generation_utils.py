# english-language-helper/cli/exam_logic/exam_generation_utils.py
"""
Reusable utility functions for CLI interactions, LLM API calls,
and other common tasks related to exam question generation.
"""

from typing import Optional, List, Any, Dict, Set # Added Set
import click
import requests
import json
import random
import string
from pydantic import ValidationError

# Import schemas from the project root
from schemas import LocalizedString, DifficultyDetail, PassageAsset # Added PassageAsset


def get_random_english_letter() -> str:
    """
    Returns a random lowercase English letter.

    Returns:
        str: A single random lowercase English letter.
    """
    return random.choice(string.ascii_lowercase)


# Dictionary for Traditional Chinese names of difficulty levels
# Keys are (STAGE_UPPERCASE, grade_int)
DIFFICULTY_ZH_TW_NAME_MAP = {
    ("ELEMENTARY", 1): "國小一年級",
    ("ELEMENTARY", 2): "國小二年級",
    ("ELEMENTARY", 3): "國小三年級",
    ("ELEMENTARY", 4): "國小四年級",
    ("ELEMENTARY", 5): "國小五年級",
    ("ELEMENTARY", 6): "國小六年級",
    ("JUNIOR_HIGH", 1): "國中一年級",
    ("JUNIOR_HIGH", 2): "國中二年級",
    ("JUNIOR_HIGH", 3): "國中三年級",
    ("SENIOR_HIGH", 1): "高中一年級",
    ("SENIOR_HIGH", 2): "高中二年級",
    ("SENIOR_HIGH", 3): "高中三年級",
}


READING_COMP_LEARNING_OBJECTIVES = [
    "Identify main ideas.",
    "Recall key details.",
    "Determine author's purpose.",
    "Understand vocabulary in context.",
    "Make logical inferences.",
    "Distinguish fact from opinion.",
    "Summarize text accurately.",
    "Recognize text structure.",
    "Predict probable outcomes.",
    "Analyze character development.",
    "Understand figurative language.",
    "Draw evidence-based conclusions.",
    "Compare and contrast texts.",
    "Follow written directions.",
    "Paraphrase core concepts.",
]


def _prompt_select_learning_objectives(predefined_objectives: List[str]) -> List[str]:
    """
    Prompts the user to select one or more learning objectives from a predefined list.

    Args:
        predefined_objectives: A list of learning objective strings.

    Returns:
        A list of selected learning objective strings.
    """
    if not predefined_objectives:
        click.echo("No predefined learning objectives provided.", err=True)
        return []

    click.echo("\n--- Select Learning Objectives for the Questions ---")
    for i, objective in enumerate(predefined_objectives):
        click.echo(f"{i + 1}. {objective}")

    selected_objectives = []
    while True:
        choice_str = click.prompt(
            f"Enter the numbers of the objectives (e.g., 1, 3, 5), or type 'all' to include all (1-{len(predefined_objectives)})",
            type=str,
        ).strip()

        if not choice_str:
            click.echo("Input cannot be empty. Please enter objective numbers or 'all'.")
            continue

        if choice_str.lower() == "all":
            selected_objectives = list(predefined_objectives)
            click.echo(f"Selected all {len(selected_objectives)} learning objectives.")
            break

        try:
            chosen_indices = [int(num_str.strip()) - 1 for num_str in choice_str.split(',')]
            
            valid_choices = True
            temp_objectives = []
            for index in chosen_indices:
                if 0 <= index < len(predefined_objectives):
                    if predefined_objectives[index] not in temp_objectives: 
                        temp_objectives.append(predefined_objectives[index])
                else:
                    click.echo(
                        f"Invalid selection: Number {index + 1} is out of range (1-{len(predefined_objectives)}). Please try again.",
                        err=True,
                    )
                    valid_choices = False
                    break
            
            if valid_choices and temp_objectives:
                selected_objectives = temp_objectives
                click.echo(f"Selected objectives: {', '.join(selected_objectives)}")
                break
            elif valid_choices and not temp_objectives: 
                 click.echo("No objectives selected. Please enter valid numbers or 'all'.")

        except ValueError:
            click.echo(
                "Invalid input. Please enter numbers separated by commas (e.g., 1, 3, 5) or 'all'.",
                err=True,
            )

    return selected_objectives


def _prompt_difficulty_detail() -> Optional[DifficultyDetail]:
    """
    Prompts the user for stage, grade, level, and auto-generates the difficulty name.
    English name is generated programmatically.
    Traditional Chinese name is looked up from a fixed dictionary.

    Returns:
        Optional[DifficultyDetail]: A Pydantic model containing the difficulty details,
                                     or None if input is invalid.
    """
    click.echo("\n--- Enter Difficulty Details ---")

    VALID_STAGES = ["ELEMENTARY", "JUNIOR_HIGH", "SENIOR_HIGH"]
    DEFAULT_STAGE = "JUNIOR_HIGH"

    click.echo("Select the Stage:")
    for i, s_option in enumerate(VALID_STAGES):
        formatted_s_option = s_option.replace("_", " ").title()
        click.echo(f"{i + 1}. {formatted_s_option}")

    default_stage_number = VALID_STAGES.index(DEFAULT_STAGE) + 1 if DEFAULT_STAGE in VALID_STAGES else 1

    stage_choice_num = click.prompt(
        "Enter the number for the Stage",
        type=click.IntRange(min=1, max=len(VALID_STAGES)),
        default=default_stage_number,
        show_default=True,
    )
    stage = VALID_STAGES[stage_choice_num - 1]

    grade = click.prompt(
        "Grade (e.g., 1, 2, 3)", type=int, default=1, show_default=True
    )

    level = click.prompt(
        "Overall Level",
        type=click.IntRange(1, 10),
        default=5,
        show_default=True,
    )

    formatted_stage = stage.replace("_", " ").title()
    en_name = f"{formatted_stage} - Grade {grade}"
    zh_tw_name = DIFFICULTY_ZH_TW_NAME_MAP.get((stage, grade), en_name)

    if zh_tw_name == en_name and (stage, grade) not in DIFFICULTY_ZH_TW_NAME_MAP:
        click.echo(
            f"Warning: No Traditional Chinese name found in map for Stage '{stage}' Grade {grade}. "
            f"Using English name as placeholder.",
            err=True,
        )

    click.echo(f"Auto-generated Difficulty Name (English): {en_name}")
    click.echo(f"Difficulty Name (Traditional Chinese): {zh_tw_name}")

    name_loc_str = LocalizedString(en=en_name, zh_tw=zh_tw_name)

    try:
        difficulty = DifficultyDetail(
            stage=stage, grade=grade, level=level, name=name_loc_str
        )
        return difficulty
    except ValidationError as e:
        click.echo(f"Error validating difficulty details: {e}", err=True)
        return None


def _call_openai_api(
    api_key: str, prompt_text: str, model: str = "gpt-3.5-turbo-1106"
) -> Optional[str]:
    """
    Calls the OpenAI API to get a response for the given prompt, expecting JSON.

    Args:
        api_key: The OpenAI API key.
        prompt_text: The full prompt to send to the LLM.
        model: The OpenAI model to use.

    Returns:
        Optional[str]: The JSON string response from the LLM, or None if an error occurs.
    """
    openai_api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    click.echo(f"\n--- Attempting to call OpenAI API ({model}) ---")
    try:
        response = requests.post(openai_api_url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        response_json = response.json()
        content = response_json.get("choices", [{}])[0].get("message", {}).get("content")
        if content:
            click.echo("OpenAI API call successful.")
            return content.strip()
        else:
            click.echo("Error: No content found in OpenAI API response.", err=True)
            click.echo(f"Response: {response_json}", err=True)
            return None
    except requests.exceptions.RequestException as e:
        click.echo(f"Error calling OpenAI API: {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"An unexpected error occurred with OpenAI API call: {e}", err=True)
        return None


def _call_gemini_api(
    api_key: str, prompt_text: str, model: str = "gemini-1.5-flash-latest"
) -> Optional[str]:
    """
    Calls the Google Gemini API to get a response for the given prompt, expecting JSON.

    Args:
        api_key: The Google API key for Gemini.
        prompt_text: The full prompt to send to the LLM.
        model: The Gemini model to use.

    Returns:
        Optional[str]: The JSON string response from the LLM, or None if an error occurs.
    """
    gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.7,
        },
    }
    click.echo(f"\n--- Attempting to call Google Gemini API ({model}) ---")
    try:
        response = requests.post(gemini_api_url, headers=headers, json=data, timeout=90)
        response.raise_for_status()
        response_json = response.json()
        candidates = response_json.get("candidates")
        if candidates and candidates[0].get("content", {}).get("parts", [{}])[0].get("text"):
            json_text_response = candidates[0]["content"]["parts"][0]["text"]
            click.echo("Gemini API call successful.")
            return json_text_response.strip()
        else:
            click.echo("Error: No valid JSON content found in Gemini API response.", err=True)
            click.echo(f"Response: {response_json}", err=True)
            return None
    except requests.exceptions.RequestException as e:
        click.echo(f"Error calling Gemini API: {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"An unexpected error occurred with Gemini API call: {e}", err=True)
        return None


def _generate_word_choices_for_difficulty(
    difficulty_detail: DifficultyDetail,
    num_choices: int,
    api_key: Optional[str],
    service_name: Optional[str],
) -> Optional[List[str]]:
    """
    Generates a list of distinct English words suitable for a given difficulty level using an LLM.

    Args:
        difficulty_detail: The difficulty details (stage, grade, level).
        num_choices: The number of distinct words to generate.
        api_key: The API key for the LLM service.
        service_name: The name of the LLM service ("OPENAI" or "GOOGLE").

    Returns:
        A list of generated words, or None if generation fails.
    """
    if not api_key or not service_name:
        click.echo("LLM API key or service name not provided for word choice generation.", err=True)
        return None

    if num_choices <= 0:
        click.echo("Number of word choices must be positive.", err=True)
        return None

    difficulty_name = difficulty_detail.name.en or f"{difficulty_detail.stage} Grade {difficulty_detail.grade}"

    prompt = (
        f"Generate {num_choices} distinct English words appropriate for a student at the '{difficulty_name}' level, "
        f"suitable for a spelling test. Each word must have a minimum length of 7 characters. "
        f"Your response must be a single, minified JSON object with one key: 'words', "
        f"which holds a list of {num_choices} strings. "
        f'For example: {{\"words\": [\"example\", \"another\", \"minimum\", \"lengthy\"]}}.'
        f"Ensure the words are distinct and meet the minimum length requirement. Do not include any other text or markdown."
    )

    llm_response_str: Optional[str] = None
    click.echo(f"Attempting to generate {num_choices} word choices for difficulty '{difficulty_name}' using {service_name}...")
    
    if service_name == "OPENAI":
        llm_response_str = _call_openai_api(api_key, prompt, model="gpt-3.5-turbo-1106")
    elif service_name == "GOOGLE":
        llm_response_str = _call_gemini_api(api_key, prompt, model="gemini-1.5-flash-latest")
    else:
        click.echo(f"Unsupported LLM service for word choice generation: {service_name}", err=True)
        return None

    if not llm_response_str:
        click.echo("LLM call for word choice generation failed or returned no content.", err=True)
        return None

    try:
        response_data = json.loads(llm_response_str)
        words = response_data.get("words")
        if (
            isinstance(words, list)
            and all(isinstance(word, str) for word in words)
            and len(words) == num_choices
        ):
            if len(set(words)) == num_choices:
                click.echo(f"Successfully generated word choices: {words}")
                return words
            else:
                click.echo(f"LLM did not return {num_choices} distinct words. Got: {words}", err=True)
                return None
        else:
            click.echo(f"LLM word choice response did not contain a valid 'words' list of {num_choices} strings. Response: {llm_response_str}", err=True)
            return None
    except json.JSONDecodeError as e:
        click.echo(f"Error decoding JSON response from LLM during word choice generation: {e}. Response: {llm_response_str}", err=True)
        return None
    except Exception as e:
        click.echo(f"An unexpected error occurred processing word choice response: {e}. Response: {llm_response_str}", err=True)
        return None

# Collection name constants for database queries
_PASSAGE_ASSETS_COLLECTION_NAME = "passage_assets"
_QUESTIONS_COLLECTION_NAME = "questions"

def get_passages_without_questions(db: Any, passage_limit: int = 100) -> List[PassageAsset]:
    """
    Retrieves a list of PassageAsset objects that do not have any associated questions.

    Args:
        db: The Firestore client instance.
        passage_limit: The maximum number of recent passages to check. Defaults to 100.

    Returns:
        A list of PassageAsset objects that have no questions.
        Returns an empty list if an error occurs or no such passages are found.
    """
    if not db:
        click.echo("Database client not available. Cannot retrieve passages.", err=True)
        return []

    questioned_passage_ids: Set[str] = set()
    passages_without_questions: List[PassageAsset] = []

    try:
        click.echo("Fetching IDs of passages that currently have questions...", nl=False)
        questions_query = db.collection(_QUESTIONS_COLLECTION_NAME).select(["contentAssetId"]).stream()
        question_ref_count = 0
        for question_doc in questions_query:
            question_ref_count +=1
            data = question_doc.to_dict()
            if data and "contentAssetId" in data and data["contentAssetId"]:
                questioned_passage_ids.add(data["contentAssetId"])
        click.echo(f" Done. Found {len(questioned_passage_ids)} unique passages referenced by {question_ref_count} questions.")

        click.echo(f"Fetching up to {passage_limit} most recent passages to check...", nl=False)
        all_passages_query = db.collection(_PASSAGE_ASSETS_COLLECTION_NAME).order_by("updatedAt", direction="DESCENDING").limit(passage_limit).stream()
        
        processed_passage_count = 0
        for passage_doc in all_passages_query:
            processed_passage_count += 1
            passage_id = passage_doc.id
            if passage_id not in questioned_passage_ids:
                try:
                    passage_data = passage_doc.to_dict()
                    if passage_data:
                        passage_data['assetId'] = passage_id 
                        # Ensure list fields are present for Pydantic model if they might be missing
                        passage_data.setdefault('tags', [])
                        passage_data.setdefault('learningObjectives', [])
                        
                        # Perform basic validation for critical fields before Pydantic instantiation
                        if not passage_data.get('title') or not isinstance(passage_data.get('title'), dict):
                             click.echo(f"\nWarning: Skipping passage {passage_id} due to missing/invalid title structure.", err=True)
                             continue
                        if not passage_data.get('difficulty') or not isinstance(passage_data.get('difficulty'), dict):
                             click.echo(f"\nWarning: Skipping passage {passage_id} due to missing/invalid difficulty structure.", err=True)
                             continue
                        if 'content' not in passage_data: # Content is mandatory
                             click.echo(f"\nWarning: Skipping passage {passage_id} due to missing content field.", err=True)
                             continue
                        if passage_data.get('assetType') != "PASSAGE": # assetType is mandatory and must be PASSAGE
                             click.echo(f"\nWarning: Skipping passage {passage_id} - assetType is not PASSAGE or missing (was: {passage_data.get('assetType')}).", err=True)
                             continue
                        
                        passages_without_questions.append(PassageAsset(**passage_data))
                    else:
                        click.echo(f"\nWarning: Passage {passage_id} has no data. Skipping.", err=True)
                except ValidationError as ve: # Catch Pydantic validation errors specifically
                    click.echo(f"\nError validating passage data for {passage_id}: {ve}", err=True)
                except Exception as e_parse:
                    click.echo(f"\nError parsing passage {passage_id}: {e_parse}", err=True)
        click.echo(f" Done. Checked {processed_passage_count} passages.")
        
        if not passages_without_questions:
            click.echo(f"No passages found without questions among the latest {processed_passage_count} checked.")
        else:
            click.echo(f"Found {len(passages_without_questions)} passage(s) without questions.")

    except Exception as e_db: # Catch general database or other errors
        click.echo(f"An error occurred during database operations: {e_db}", err=True)
        return []

    return passages_without_questions