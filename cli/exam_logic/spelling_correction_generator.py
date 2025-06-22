# english-language-helper/cli/exam_logic/spelling_correction_generator.py
"""
Handles the logic for generating spelling correction questions,
including prompting for LLM parameters and processing LLM responses.
"""

import json
from typing import Optional, List, Any

import click
from pydantic import ValidationError

# Project-specific imports
from schemas import ( # Schemas is now at the project root
    SpellingCorrectionQuestion,
    DifficultyDetail,
    LocalizedString,
    ChoiceDetail,
)
from .exam_generation_utils import (
    _prompt_difficulty_detail,
    _call_openai_api,
    _call_gemini_api,
)
from ..firestore_utils import add_document_to_collection


def _prompt_llm_spelling_details() -> Optional[dict]:
    """
    Prompts the user for details to request an LLM-generated SpellingCorrectionQuestion.

    This function handles interactive collection of data for an LLM-generated
    spelling correction question, including difficulty, learning objectives,
    and the target answer type.

    Returns:
        Optional[dict]:
            - dict: If LLM generation parameters are successfully collected.
            - None: If user cancels or input is invalid.
    """
    click.echo("\n--- Configure LLM for Spelling Correction Question ---")

    difficulty_details = _prompt_difficulty_detail()
    if not difficulty_details:
        return None  # Error messages handled in _prompt_difficulty_detail

    learning_objectives_default_str = "Spelling"
    learning_objectives_str = click.prompt(
        "Learning Objectives (comma-separated)",
        default=learning_objectives_default_str,
        show_default=True
    ).strip()

    if not learning_objectives_str:  # User might have cleared the default
        learning_objectives = [learning_objectives_default_str] if learning_objectives_default_str else []
    else:
        learning_objectives = [obj.strip() for obj in learning_objectives_str.split(',') if obj.strip()]
        if not learning_objectives:  # Handles case where input was just commas or spaces
            learning_objectives = [learning_objectives_default_str] if learning_objectives_default_str else []

    answer_input_type_choice = click.prompt(
        "Answer Input Type",
        type=click.Choice(["MC", "TI"], case_sensitive=False),
        default="MC",
        show_default=True
    ).upper()  # Ensure consistency

    final_answer_input_type = "MULTIPLE_CHOICE" if answer_input_type_choice == "MC" else "TEXT_INPUT"

    click.echo("\n--- LLM Generation Parameters Collected ---")
    return {
        "generation_mode": "LLM", # Retained for consistency
        "difficulty": difficulty_details.model_dump(), # Send as dict
        "learning_objectives": learning_objectives,
        "target_answer_type": final_answer_input_type
    }


def handle_spelling_correction_generation(db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]):
    """
    Main handler for generating spelling correction questions using LLM.
    Prompts user for parameters, calls LLM, processes response, and saves to Firestore.

    Args:
        db: Initialized Firestore client, or None.
        llm_api_key: The API key for the LLM service.
        llm_service_name: The name of the LLM service ("OPENAI" or "GOOGLE").
    """
    click.echo("\n--- Spelling Correction (拼字訂正) ---")

    llm_request_params = _prompt_llm_spelling_details()

    if llm_request_params:
        click.echo("\n--- LLM Generation Requested for Spelling Correction Question ---")

        # Extract parameters for LLM
        difficulty_data = llm_request_params["difficulty"]
        learning_objectives = llm_request_params["learning_objectives"]
        target_answer_type = llm_request_params["target_answer_type"]

        # Define example responses for fallback
        example_mc_response_json = """
            {
                "questionText": "Which of the following words is spelled correctly?",
                "choices": [
                    {"text": "acommodate", "isCorrect": false},
                    {"text": "accommodate", "isCorrect": true},
                    {"text": "accomodate", "isCorrect": false},
                    {"text": "acommodate", "isCorrect": false}
                ],
                "explanation": {
                    "en": "The word 'accommodate' has two 'c's and two 'm's.",
                    "zh_tw": "單字 'accommodate' 有兩個 'c' 和兩個 'm'。"
                }
            }
        """.strip()

        example_ti_response_json = """
            {
                "questionText": "Please correct the spelling of the following word:",
                "incorrectSpelling": "beleive",
                "acceptableAnswers": ["believe"],
                "explanation": {
                    "en": "The word 'believe' follows the 'i before e except after c' rule when the sound is 'ee'.",
                    "zh_tw": "單字 'believe' 在發音為 'ee' 時，遵循 'i before e except after c' 的規則。"
                }
            }
        """.strip()

        prompt_parts = [
            "You are an expert English language exam question generator.",
            "Your task is to create a spelling correction question with the following characteristics:",
            f"- Difficulty: {json.dumps(difficulty_data)}",
            f"- Learning Objectives: {', '.join(learning_objectives)}",
            f"- Question Type: Spelling Correction",
            f"- Answer Input Type: {target_answer_type}",
            "Please provide your response in a single, minified JSON object with NO markdown formatting.",
            "The JSON object should contain the following fields based on the answer input type:"
        ]

        if target_answer_type == "MULTIPLE_CHOICE":
            prompt_parts.extend([
                "  - 'questionText': A string for the question prompt (e.g., 'Which word is spelled correctly?').",
                "  - 'choices': A list of 4 objects, where each object has 'text' (string) and 'isCorrect' (boolean). Exactly one choice must have 'isCorrect: true'.",
                "  - 'explanation': An object with 'en' (string, English explanation) and 'zh_tw' (string, Chinese explanation for the correct answer)."
            ])
        else:  # TEXT_INPUT
            prompt_parts.extend([
                "  - 'questionText': A string for the question prompt (e.g., 'Correct the spelling of the given word.').",
                "  - 'incorrectSpelling': The incorrectly spelled word to present to the student.",
                "  - 'acceptableAnswers': A list containing one or more strings with the correct spelling(s).",
                "  - 'explanation': An object with 'en' (string, English explanation) and 'zh_tw' (string, Chinese explanation for the correct answer)."
            ])

        full_prompt = "\n".join(prompt_parts)
        click.echo("\n--- Formulated LLM Prompt ---")
        click.echo(full_prompt)

        llm_output_str = None
        if llm_api_key and llm_service_name:
            click.echo(f"\nLLM API Key for {llm_service_name} is available.")
            if llm_service_name == "OPENAI":
                llm_output_str = _call_openai_api(llm_api_key, full_prompt)
            elif llm_service_name == "GOOGLE":
                llm_output_str = _call_gemini_api(llm_api_key, full_prompt)

            if llm_output_str:
                click.echo(f"\n--- LLM JSON Response from {llm_service_name} API ---")
            else:
                click.echo(f"\nLLM ({llm_service_name}) API call did not return content or is currently simulated.")
                if target_answer_type == "MULTIPLE_CHOICE":
                    llm_output_str = example_mc_response_json
                else:  # TEXT_INPUT
                    llm_output_str = example_ti_response_json
                click.echo(f"Falling back to example JSON for {target_answer_type}.")
                click.echo("\n--- Using Example LLM JSON Response ---")
        else:
            click.echo("\nLLM API Key or Service Name not available/identified.")
            if target_answer_type == "MULTIPLE_CHOICE":
                llm_output_str = example_mc_response_json
            else:  # TEXT_INPUT
                llm_output_str = example_ti_response_json
            click.echo(f"Falling back to example JSON for {target_answer_type} for testing purposes.")
            click.echo("\n--- Using Example LLM JSON Response ---")

        if llm_output_str:
            click.echo(llm_output_str)  # Print the JSON that will be parsed

            try:
                llm_generated_data = json.loads(llm_output_str)

                # Merge LLM generated data with initially provided data
                final_question_details = {
                    "difficulty": DifficultyDetail(**difficulty_data), # Re-validate with Pydantic model
                    "learningObjectives": learning_objectives,
                    "questionType": "SPELLING_CORRECTION",
                    "answerInputType": target_answer_type,
                    "questionText": llm_generated_data.get("questionText"),
                    "explanation": LocalizedString(**llm_generated_data.get("explanation")) if llm_generated_data.get("explanation") else None,
                    "choices": [ChoiceDetail(**c) for c in llm_generated_data.get("choices", [])] if llm_generated_data.get("choices") else None,
                    "incorrectSpelling": llm_generated_data.get("incorrectSpelling"),
                    "acceptableAnswers": llm_generated_data.get("acceptableAnswers")
                }

                generated_question = SpellingCorrectionQuestion(**final_question_details)
                click.echo("\n--- Successfully Parsed and Validated LLM-Generated Question ---")
                click.echo(generated_question.model_dump_json(indent=2))

                if db:
                    click.echo("\nAttempting to save LLM-generated question to Firestore...")
                    new_question_id = add_document_to_collection(db, "questions", generated_question)
                    if new_question_id:
                        click.echo(f"LLM-generated question saved with ID: {new_question_id}")
                    else:
                        click.echo("Failed to save LLM-generated question to Firestore.", err=True)
                else:
                    click.echo("\nFirestore client not available. Cannot save LLM-generated question.", err=True)

            except json.JSONDecodeError as e:
                click.echo(f"\nError: Could not decode JSON response from LLM: {e}", err=True)
                click.echo(f"LLM Response that failed parsing was:\n{llm_output_str}", err=True)
            except ValidationError as e:
                click.echo(f"\nError: LLM-generated data did not match Pydantic schema for SpellingCorrectionQuestion: {e}", err=True)
                problematic_data_for_log = llm_generated_data if 'llm_generated_data' in locals() else {"error": "llm_generated_data not available"}
                click.echo(f"Problematic LLM generated data (parsed from JSON):\n{json.dumps(problematic_data_for_log, indent=2, default=str)}", err=True)
                initial_params_for_log = {
                    "difficulty": difficulty_data,
                    "learningObjectives": learning_objectives,
                    "target_answer_type": target_answer_type
                }
                click.echo(f"Initial parameters sent for merging:\n{json.dumps(initial_params_for_log, indent=2, default=str)}", err=True)
            except Exception as e:
                click.echo(f"\nAn unexpected error occurred while processing LLM response: {e}", err=True)
        else:
            click.echo("\nCritical Error: No LLM JSON response (neither from API nor fallback example) was available to process.", err=True)
    else:
        click.echo("Spelling correction question configuration cancelled or no data entered.")

    click.pause(info="\nPress any key to return to the main menu...")