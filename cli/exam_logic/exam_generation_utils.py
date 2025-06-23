# english-language-helper/cli/exam_logic/exam_generation_utils.py
"""
Reusable utility functions for CLI interactions, LLM API calls,
and other common tasks related to exam question generation.
"""

from typing import Optional, List
import click
import requests  # For making HTTP requests to LLM APIs (actual calls are illustrative)
import json  # For handling JSON data
import random
import string
from pydantic import ValidationError

# Import schemas from the project root
from schemas import LocalizedString, DifficultyDetail


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
    # Add more as needed, e.g., for specific tests like TOEIC, TOEFL if stages are defined
}


# This function might become less used or adapted if most localized strings are auto-generated/translated.
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
        # Display formatted stage name for better readability
        formatted_s_option = s_option.replace("_", " ").title()
        click.echo(f"{i + 1}. {formatted_s_option}")

    default_stage_number = 1  # Fallback default
    if DEFAULT_STAGE in VALID_STAGES:
        try:
            default_stage_number = VALID_STAGES.index(DEFAULT_STAGE) + 1
        except ValueError:
            pass  # Should not happen if DEFAULT_STAGE is in VALID_STAGES

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
        type=click.IntRange(1, 10),  # Enforces range 1-10
        default=5,
        show_default=True,
    )

    # Auto-generate English name
    # Sanitize stage for better display (e.g., "JUNIOR_HIGH" -> "Junior High")
    formatted_stage = stage.replace("_", " ").title()
    en_name = f"{formatted_stage} - Grade {grade}"

    # Look up Traditional Chinese name from the fixed dictionary
    zh_tw_name = DIFFICULTY_ZH_TW_NAME_MAP.get((stage, grade))

    if zh_tw_name is None:
        click.echo(
            f"Warning: No Traditional Chinese name found in map for Stage '{stage}' Grade {grade}. "
            f"Using English name as placeholder.",
            err=True,
        )
        zh_tw_name = en_name  # Fallback to English name

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
        "response_format": {"type": "json_object"},  # Enable JSON mode
        "temperature": 0.7,  # Adjust as needed
    }
    click.echo(f"\n--- Attempting to call OpenAI API ({model}) ---")
    # The following is illustrative. In a real scenario, you'd make the HTTP request.
    # try:
    #     response = requests.post(openai_api_url, headers=headers, json=data, timeout=60)
    #     response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
    #     response_json = response.json()
    #     content = response_json.get("choices", [{}])[0].get("message", {}).get("content")
    #     if content:
    #         click.echo("OpenAI API call successful.")
    #         return content.strip()
    #     else:
    #         click.echo("Error: No content found in OpenAI API response.", err=True)
    #         click.echo(f"Response: {response_json}", err=True)
    #         return None
    # except requests.exceptions.RequestException as e:
    #     click.echo(f"Error calling OpenAI API: {e}", err=True)
    #     return None
    # except Exception as e:
    #     click.echo(f"An unexpected error occurred with OpenAI API call: {e}", err=True)
    #     return None
    click.echo("Simulating OpenAI API call. (Actual call is commented out in code).")
    return None  # Placeholder: No actual call made in this environment


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
    # Note: The exact URL might vary based on specific Gemini model (e.g., gemini-1.5-pro-latest)
    # and whether you're using Vertex AI or Google AI Studio endpoints.
    # This is a generic example for Google AI Studio's gemini-pro.
    gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "response_mime_type": "application/json",  # Request JSON output
            "temperature": 0.7,  # Adjust as needed
            # "candidateCount": 1, # Usually default
        },
    }
    click.echo(f"\n--- Attempting to call Google Gemini API ({model}) ---")
    try:
        response = requests.post(gemini_api_url, headers=headers, json=data, timeout=90)
        response.raise_for_status()
        response_json = response.json()
        # Gemini's response structure for JSON can be nested.
        # Ensure you extract the actual JSON string correctly.
        # This might need adjustment based on the actual Gemini API response structure.
        candidates = response_json.get("candidates")
        if candidates and candidates[0].get("content", {}).get("parts", [{}])[0].get(
            "text"
        ):
            json_text_response = candidates[0]["content"]["parts"][0]["text"]
            click.echo("Gemini API call successful.")
            return json_text_response.strip()
        else:
            click.echo(
                "Error: No valid JSON content found in Gemini API response.", err=True
            )
            click.echo(
                f"Response: {response_json}", err=True
            )  # Log the full response for debugging
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
        click.echo(
            "LLM API key or service name not provided for word choice generation.",
            err=True,
        )
        return None

    if num_choices <= 0:
        click.echo("Number of word choices must be positive.", err=True)
        return None

    difficulty_name = (
        difficulty_detail.name.en
        or f"{difficulty_detail.stage} Grade {difficulty_detail.grade}"
    )

    prompt = (
        f"Generate {num_choices} distinct English words appropriate for a student at the '{difficulty_name}' level, "
        f"suitable for a spelling test. Each word must have a minimum length of 7 characters. "
        f"Your response must be a single, minified JSON object with one key: 'words', "
        f"which holds a list of {num_choices} strings. "
        f'For example: {{"words": ["example", "another", "minimum", "lengthy"]}}.'
        f"Ensure the words are distinct and meet the minimum length requirement. Do not include any other text or markdown."
    )

    llm_response_str: Optional[str] = None
    click.echo(
        f"Attempting to generate {num_choices} word choices for difficulty '{difficulty_name}' using {service_name}..."
    )
    if service_name == "OPENAI":
        llm_response_str = _call_openai_api(api_key, prompt, model="gpt-3.5-turbo-1106")
    elif service_name == "GOOGLE":
        llm_response_str = _call_gemini_api(
            api_key, prompt, model="gemini-1.5-flash-latest"
        )
    else:
        click.echo(
            f"Unsupported LLM service for word choice generation: {service_name}",
            err=True,
        )
        return None

    if not llm_response_str:
        click.echo(
            "LLM call for word choice generation failed or returned no content.",
            err=True,
        )
        return None

    try:
        response_data = json.loads(llm_response_str)
        words = response_data.get("words")
        if (
            isinstance(words, list)
            and all(isinstance(word, str) for word in words)
            and len(words) == num_choices
        ):
            # Further check for distinctness, though LLM was instructed
            if len(set(words)) == num_choices:
                click.echo(f"Successfully generated word choices: {words}")
                return words
            else:
                click.echo(
                    f"LLM did not return {num_choices} distinct words. Got: {words}",
                    err=True,
                )
                # Optionally, could retry or return the list as is if partial distinctness is acceptable
                return None  # Or handle as a partial success
        else:
            click.echo(
                f"LLM word choice response did not contain a valid 'words' list of {num_choices} strings. Response: {llm_response_str}",
                err=True,
            )
            return None
    except json.JSONDecodeError as e:
        click.echo(
            f"Error decoding JSON response from LLM during word choice generation: {e}. Response: {llm_response_str}",
            err=True,
        )
        return None
    except Exception as e:
        click.echo(
            f"An unexpected error occurred processing word choice response: {e}. Response: {llm_response_str}",
            err=True,
        )
        return None
