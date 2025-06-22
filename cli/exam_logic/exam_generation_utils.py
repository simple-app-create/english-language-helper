# english-language-helper/cli/exam_logic/exam_generation_utils.py
"""
Reusable utility functions for CLI interactions, LLM API calls,
and other common tasks related to exam question generation.
"""

from typing import Optional, List
import click
import requests # For making HTTP requests to LLM APIs (actual calls are illustrative)
import json # For handling JSON data
from pydantic import ValidationError

# Import schemas from the project root
from schemas import LocalizedString, DifficultyDetail


def _prompt_localized_string(prompt_message: str) -> LocalizedString:
    """
    Prompts the user for English and Chinese (Taiwan) versions of a string.

    Args:
        prompt_message: The base message to display to the user for this input.

    Returns:
        LocalizedString: A Pydantic model containing the 'en' and 'zh_tw' strings.
    """
    en_text = click.prompt(f"{prompt_message} (English)", default="", show_default=False).strip()
    zh_tw_text = click.prompt(f"{prompt_message} (Chinese - Taiwan)", default="", show_default=False).strip()
    return LocalizedString(en=en_text, zh_tw=zh_tw_text)


def _prompt_difficulty_detail() -> Optional[DifficultyDetail]:
    """
    Prompts the user for the details of a question's difficulty.

    Returns:
        Optional[DifficultyDetail]: A Pydantic model containing the difficulty details,
                                     or None if input is invalid or user cancels.
    """
    click.echo("\n--- Enter Difficulty Details ---")
    stage = click.prompt(
        "Stage (e.g., ELEMENTARY, JUNIOR_HIGH, SENIOR_HIGH)",
        default="JUNIOR_HIGH",
        show_default=True
    ).strip().upper()

    grade = click.prompt(
        "Grade (e.g., 1, 2, 3)",
        type=int,
        default=1,
        show_default=True
    )
    
    level = click.prompt(
        "Overall Level",
        type=click.IntRange(1, 10), # Enforces range 1-10
        default=5,
        show_default=True
    )

    # Prompt for difficulty name, allowing empty strings if user presses Enter
    # _prompt_localized_string already handles default="" for its prompts
    name_loc_str = _prompt_localized_string("Difficulty Name (e.g., 'Junior High - Grade 1') (Optional)")

    try:
        difficulty = DifficultyDetail(
            stage=stage,
            grade=grade,
            level=level,
            # If name is truly optional, the schema for DifficultyDetail.name might need Optional[LocalizedString]
            # For now, we pass it as is. LocalizedString schema allows empty en/zh_tw.
            name=name_loc_str 
        )
        return difficulty
    except ValidationError as e:
        click.echo(f"Error validating difficulty details: {e}", err=True)
        return None


def _call_openai_api(api_key: str, prompt_text: str, model: str = "gpt-3.5-turbo-1106") -> Optional[str]:
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
        "response_format": {"type": "json_object"}, # Enable JSON mode
        "temperature": 0.7, # Adjust as needed
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
    return None # Placeholder: No actual call made in this environment


def _call_gemini_api(api_key: str, prompt_text: str, model: str = "gemini-pro") -> Optional[str]:
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
            "response_mime_type": "application/json", # Request JSON output
            "temperature": 0.7, # Adjust as needed
            # "candidateCount": 1, # Usually default
        }
    }
    click.echo(f"\n--- Attempting to call Google Gemini API ({model}) ---")
    # The following is illustrative. In a real scenario, you'd make the HTTP request.
    # try:
    #     response = requests.post(gemini_api_url, headers=headers, json=data, timeout=90)
    #     response.raise_for_status()
    #     response_json = response.json()
    #     # Gemini's response structure for JSON can be nested.
    #     # Ensure you extract the actual JSON string correctly.
    #     # This might need adjustment based on the actual Gemini API response structure.
    #     candidates = response_json.get("candidates")
    #     if candidates and candidates[0].get("content", {}).get("parts", [{}])[0].get("text"):
    #         json_text_response = candidates[0]["content"]["parts"][0]["text"]
    #         click.echo("Gemini API call successful.")
    #         return json_text_response.strip()
    #     else:
    #         click.echo("Error: No valid JSON content found in Gemini API response.", err=True)
    #         click.echo(f"Response: {response_json}", err=True) # Log the full response for debugging
    #         return None
    # except requests.exceptions.RequestException as e:
    #     click.echo(f"Error calling Gemini API: {e}", err=True)
    #     return None
    # except Exception as e:
    #     click.echo(f"An unexpected error occurred with Gemini API call: {e}", err=True)
    #     return None
    click.echo("Simulating Gemini API call. (Actual call is commented out in code).")
    return None # Placeholder: No actual call made in this environment