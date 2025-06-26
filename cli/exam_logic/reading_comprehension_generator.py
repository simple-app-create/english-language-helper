# english-language-helper/cli/exam_logic/reading_comprehension_generator.py
"""
Handles the logic for generating 'Reading Comprehension' questions.
This module provides options to generate new reading passages with associated questions,
generate passages only, or to generate questions for existing passages.
LLM is mandatory for new passage and title generation if API keys are configured.
"""

from typing import Optional, Any, List, Dict
import click
import uuid
from datetime import datetime, timezone
import json
import random # For random selection of learning objectives

from schemas import (
    DifficultyDetail,
    LocalizedString,
    ChoiceDetail,
    PassageAsset,
    ReadingComprehensionQuestion,
)
from .exam_generation_utils import (
    _prompt_difficulty_detail,
    _call_openai_api,
    _call_gemini_api,
    READING_COMP_LEARNING_OBJECTIVES,
    get_passages_without_questions, # For listing passages that need questions
    _prompt_select_learning_objectives # Still used by _create_new_passage_asset_interactive for passage LOs
)


# Number of questions to generate in a batch by default
NUM_QUESTIONS_PER_BATCH = 3


def _save_passage_asset_to_db(db: Any, passage_asset: PassageAsset) -> bool:
    """
    Saves a PassageAsset to the Firestore database.

    Args:
        db: The Firestore client.
        passage_asset: The PassageAsset object to save.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    if not db:
        click.echo("Database client not available. Cannot save passage asset.", err=True)
        return False
    try:
        db.collection("passage_assets").document(passage_asset.assetId).set(passage_asset.model_dump())
        click.echo(f"Passage asset '{passage_asset.title.en}' (ID: {passage_asset.assetId}) saved successfully.")
        return True
    except Exception as e:
        click.echo(f"Error saving passage asset to DB: {e}", err=True)
        return False

def _save_reading_comprehension_question_to_db(db: Any, question: ReadingComprehensionQuestion) -> bool:
    """
    Saves a ReadingComprehensionQuestion to the Firestore database.

    Args:
        db: The Firestore client.
        question: The ReadingComprehensionQuestion object to save.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    if not db:
        click.echo("Database client not available. Cannot save question.", err=True)
        return False
    try:
        doc_ref = db.collection("questions").document()
        doc_ref.set(question.model_dump())
        click.echo(f"Question (for asset ID: {question.contentAssetId}) saved with new ID: {doc_ref.id}.")
        return True
    except Exception as e:
        click.echo(f"Error saving question to DB: {e}", err=True)
        return False

def _list_and_select_passage_asset(
    db: Optional[Any], details: bool = True
) -> Optional[PassageAsset]:
    """
    Lists passage assets from Firestore that DO NOT HAVE ANY ASSOCIATED QUESTIONS
    and allows the user to select one.

    Args:
        db: The Firestore client.
        details: Whether to show detailed information for each passage.

    Returns:
        Optional[PassageAsset]: The selected passage asset, or None if no selection is made or an error occurs.
    """
    if not db:
        click.echo("Database connection not available. Cannot list passages.", err=True)
        return None

    click.echo("\n--- Select a Passage Asset (Showing only passages without questions) ---")
    
    # Call the helper from exam_generation_utils.py
    # The helper function already prints status messages during its fetch.
    passages_to_display = get_passages_without_questions(db) 

    if not passages_to_display:
        # get_passages_without_questions prints "No passages found without questions..." if that's the case.
        # An additional message here can confirm the outcome for this specific selection step.
        click.echo("No passages without questions are currently available for selection.")
        return None

    click.echo("\n--- Available Passages Without Questions ---")
    for i, p_asset in enumerate(passages_to_display):
        title_display = p_asset.title.en if p_asset.title else "Untitled"
        status_display = p_asset.status
        updated_at_str = p_asset.updatedAt.strftime("%Y-%m-%d %H:%M") if p_asset.updatedAt else "N/A"
        
        click.echo(f"{i + 1}. {title_display} (ID: {p_asset.assetId}, Status: {status_display}, Updated: {updated_at_str})")
        if details:
            difficulty_display = p_asset.difficulty.name.en if p_asset.difficulty and p_asset.difficulty.name else "Unknown Difficulty"
            click.echo(f"     Difficulty: {difficulty_display}")
            if p_asset.learningObjectives: # Show passage LOs for context
                click.echo(f"     Passage LOs: {', '.join(p_asset.learningObjectives)}")

    choice_num_str = click.prompt(
        f"Enter the number of the passage to use (1-{len(passages_to_display)}), or 0 to cancel", 
        type=str, 
        default="0"
    )
    try:
        choice_num = int(choice_num_str)
        if choice_num == 0:
            click.echo("Selection cancelled.")
            return None
        if not (1 <= choice_num <= len(passages_to_display)):
            click.echo("Invalid selection number. Aborting.", err=True)
            return None
    except ValueError:
        click.echo("Invalid input. Please enter a number. Aborting.", err=True)
        return None

    selected_passage = passages_to_display[choice_num - 1]
    click.echo(f"Selected passage for adding questions: '{selected_passage.title.en if selected_passage.title else 'Untitled'}'")
    return selected_passage


def _create_new_passage_asset_interactive(
    llm_api_key: Optional[str], llm_service_name: Optional[str]
) -> Optional[PassageAsset]:
    """
    Interactively guides the user to create a new PassageAsset using LLM.
    English title, Traditional Chinese title, and content are generated by LLM based on a user-provided topic.
    LLM API keys must be configured. If LLM generation fails or is rejected, creation is aborted.
    """
    click.echo(
        click.style(
            "\n--- Create New Reading Passage Asset (LLM Required) ---",
            fg="blue",
            bold=True,
        )
    )

    difficulty = _prompt_difficulty_detail()
    if not difficulty:
        click.echo(
            "Failed to get difficulty details. Aborting passage creation.", err=True
        )
        return None

    if not llm_api_key or not llm_service_name:
        click.echo(
            "LLM API key and/or service name not configured. Cannot generate passage. Aborting.",
            err=True,
        )
        return None

    title_obj_final: Optional[LocalizedString] = None
    passage_content_final: Optional[str] = None

    click.echo(
        click.style("\n--- LLM-Powered Title & Passage Generation ---", fg="magenta")
    )
    topic = click.prompt(
        "Enter a topic for the LLM to generate a passage and titles about",
        type=str,
        default="A Surprising Discovery",
    ).strip()
    if not topic:
        click.echo("Topic cannot be empty for LLM generation. Aborting.", err=True)
        return None

    paragraph_count = click.prompt(
        "Approximate target paragraph count for the passage", type=int, default=2
    )
    word_count_target = click.prompt(
        "Approximate target word count for the passage", type=int, default=150
    )

    llm_prompt = (
        f"You are an expert writer creating educational content for English language learners.\\n"
        f"The target student difficulty level is: {difficulty.name.en} (Stage: {difficulty.stage}, Grade: {difficulty.grade}).\\n"
        f"The topic is: '{topic}'.\\n"
        f"Generate an engaging and coherent reading passage consisting of {paragraph_count} paragraphs in approximately {word_count_target} words suitable for this level.\\n"
        f"Also, create a concise and relevant English title AND a Traditional Chinese title for this passage.\\n"
        f"Your response MUST be a single, minified JSON object with exactly THREE keys:\\n"
        f"1. 'suggested_title_en': A string containing the English title (e.g., \\\"The Lost Kitten\\\").\\n"
        f"2. 'suggested_title_zh_tw': A string containing the Traditional Chinese translation of the title (e.g., \\\"走失的小貓\\\").\\n"
        f"3. 'passage_text': A string containing the full text of the reading passage.\\n"
        f"Example JSON: {{\"suggested_title_en\": \"A Day at the Beach\", \"suggested_title_zh_tw\": \"海灘上的一天\", \"passage_text\": \"The waves crashed gently on the shore...\"}}\\n"
        f"Ensure the language, vocabulary, and sentence structure are appropriate for the specified difficulty.\\n"
        f"Do not include any other text, markdown, or explanations outside this JSON structure."
    )

    click.echo("Requesting titles and passage from LLM...")
    response_str: Optional[str] = None
    if llm_service_name == "OPENAI":
        response_str = _call_openai_api(llm_api_key, llm_prompt)
    elif llm_service_name == "GOOGLE":
        response_str = _call_gemini_api(llm_api_key, llm_prompt)

    if not response_str:
        click.echo(
            "LLM call failed or returned no content. Aborting passage creation.",
            err=True,
        )
        return None

    try:
        data = json.loads(response_str)
        llm_title_en = data.get("suggested_title_en")
        llm_title_zh_tw = data.get("suggested_title_zh_tw")
        llm_passage_content = data.get("passage_text")

        if not (
            isinstance(llm_title_en, str)
            and llm_title_en.strip()
            and isinstance(llm_title_zh_tw, str)
            and llm_title_zh_tw.strip()
            and isinstance(llm_passage_content, str)
            and llm_passage_content.strip()
        ):
            click.echo(
                "LLM response did not contain valid 'suggested_title_en', 'suggested_title_zh_tw', or 'passage_text'. Aborting.",
                err=True,
            )
            click.echo(f"LLM Raw Response Snippet: {response_str[:300]}", err=True)
            return None

        llm_title_en = llm_title_en.strip()
        llm_title_zh_tw = llm_title_zh_tw.strip()
        llm_passage_content = llm_passage_content.strip()

        click.echo(
            click.style(f"\nLLM Suggested Title (EN): {llm_title_en}", fg="green")
        )
        click.echo(
            click.style(f"LLM Suggested Title (ZH_TW): {llm_title_zh_tw}", fg="green")
        )
        click.echo(click.style("LLM Generated Passage (Preview):", fg="green"))
        click.echo(
            f"{llm_passage_content[:300]}{'...' if len(llm_passage_content) > 300 else ''}"
        )

        if not click.confirm(
            "\nDo you want to use this LLM-generated title and passage content?",
            default=True,
        ):
            click.echo(
                "User rejected LLM-generated output. Aborting passage creation.",
                fg="yellow",
            )
            return None

        # Finalize English Title
        final_title_en = click.prompt(
            "Confirm or edit English Title", default=llm_title_en
        ).strip()
        if not final_title_en:
            click.echo("English title cannot be empty. Aborting.", err=True)
            return None

        # Finalize Chinese Title
        final_title_zh_tw = click.prompt(
            "Confirm or edit Traditional Chinese Title", default=llm_title_zh_tw
        ).strip()
        title_obj_final = LocalizedString(
            en=final_title_en, zh_tw=final_title_zh_tw or final_title_en
        )

        # Finalize Passage Content
        if click.confirm(
            "Do you want to edit the LLM-generated passage content?", default=False
        ):
            edited_content = click.edit(text=llm_passage_content, extension=".txt")
            if edited_content is not None:
                passage_content_final = edited_content.strip()
                if not passage_content_final:
                    click.echo(
                        "Passage content cannot be empty after editing. Aborting.",
                        err=True,
                    )
                    return None
            else:  # Edit was aborted
                click.echo("Edit cancelled. Using original LLM passage content.")
                passage_content_final = llm_passage_content
        else:
            passage_content_final = llm_passage_content

    except json.JSONDecodeError:
        click.echo(
            f"Error decoding JSON response from LLM. Raw: {response_str[:300]}... Aborting.",
            err=True,
        )
        return None
    except Exception as e:
        click.echo(
            f"An unexpected error occurred while processing LLM response: {e}. Aborting.",
            err=True,
        )
        return None

    click.echo("\n--- Additional Passage Details ---")
    click.echo(
        "Select learning objectives covered by THIS PASSAGE (can be different from question LOs):"
    )
    passage_learning_objectives = _prompt_select_learning_objectives(
        READING_COMP_LEARNING_OBJECTIVES
    )

    desc_en = click.prompt(
        "Enter a short description for the passage (English, optional)",
        default="",
        show_default=False,
    ).strip()
    desc_zh_tw = ""
    if desc_en:
        desc_zh_tw = click.prompt(
            f"Enter short description (Traditional Chinese, optional, default: '{desc_en}')",
            default=desc_en,
            show_default=False,
        ).strip()
    description_obj = (
        LocalizedString(en=desc_en, zh_tw=desc_zh_tw or desc_en)
        if desc_en or desc_zh_tw
        else None
    )

    tags_str = click.prompt(
        "Enter tags for the passage (comma-separated, optional)",
        default="",
        show_default=False,
    )
    tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]

    source = click.prompt(
        "Source of the passage (e.g., 'Original', 'Adapted from ...', 'AI Generated', optional)",
        default="AI Generated", # Default to AI Generated as LLM is now mandatory
        show_default=True,
    ).strip()

    asset_id = uuid.uuid4().hex
    try:
        new_passage_asset = PassageAsset(
            assetId=asset_id,
            title=title_obj_final,
            description=description_obj,
            difficulty=difficulty,
            learningObjectives=passage_learning_objectives,
            tags=tags,
            status="DRAFT",
            version=1,
            source=source,
            createdBy="cli_user",
            createdAt=datetime.now(timezone.utc),
            updatedAt=datetime.now(timezone.utc),
            content=passage_content_final,
            assetType="PASSAGE",
        )
        click.echo(click.style("\n--- Passage Asset Preview ---", fg="yellow"))
        click.echo(f"ID: {new_passage_asset.assetId}")
        click.echo(f"Title (EN): {new_passage_asset.title.en}")
        if new_passage_asset.title.zh_tw != new_passage_asset.title.en:
            click.echo(f"Title (ZH_TW): {new_passage_asset.title.zh_tw}")
        click.echo(f"Difficulty: {new_passage_asset.difficulty.name.en}")
        if new_passage_asset.learningObjectives:
            click.echo(
                f"Passage Learning Objectives: {', '.join(new_passage_asset.learningObjectives)}"
            )
        else:
            click.echo("Passage Learning Objectives: None specified")
        click.echo(
            f"Content snippet: {new_passage_asset.content[:150].replace(chr(10), ' ')}..."
        )

        if click.confirm(
            "\nDo you want to proceed with this passage asset (it's not saved yet)?",
            default=True,
        ):
            return new_passage_asset
        else:
            click.echo("Passage creation aborted by user.", fg="red")
            return None

    except Exception as e:
        click.echo(f"Error creating passage asset object: {e}", err=True)
        return None

def _generate_interactive_questions_for_passage(
    passage_asset: PassageAsset, 
    llm_api_key: Optional[str], 
    llm_service_name: Optional[str]
) -> List[ReadingComprehensionQuestion]:
    """
    Interactively prompts for question type, then generates a fixed batch of questions 
    with randomly selected learning objectives for the given passage using a single LLM call.
    """
    generated_questions: List[ReadingComprehensionQuestion] = []

    if not llm_api_key or not llm_service_name:
        click.echo("LLM API key and/or service name not provided. Cannot generate questions.", err=True)
        return generated_questions

    question_type_options = {"1": "Multiple Choice (MCQ)", "2": "Text Input (Short Answer)"}
    click.echo("\nSelect the type for the batch of questions:")
    for key, value in question_type_options.items():
        click.echo(f"{key}: {value}")
    q_type_choice_key = click.prompt("Choose question type", type=click.Choice(list(question_type_options.keys())), default='1', show_choices=False)
    chosen_question_type_str = "MCQ" if q_type_choice_key == '1' else "TEXT_INPUT"
    click.echo(f"Selected question type for all {NUM_QUESTIONS_PER_BATCH} questions: {question_type_options[q_type_choice_key]}")

    # Randomly select learning objectives
    question_learning_objectives: List[str] = []
    if READING_COMP_LEARNING_OBJECTIVES:
        num_to_select = min(NUM_QUESTIONS_PER_BATCH, len(READING_COMP_LEARNING_OBJECTIVES))
        if num_to_select > 0:
            question_learning_objectives = random.sample(READING_COMP_LEARNING_OBJECTIVES, num_to_select)
            click.echo(click.style(f"Randomly selected learning objectives for this batch: {', '.join(question_learning_objectives)}", fg="cyan"))
        else: # Should ideally not happen if READING_COMP_LEARNING_OBJECTIVES is populated
            click.echo(click.style("No learning objectives available in the predefined list to select from.", fg="yellow"))
    else:
        click.echo(click.style("READING_COMP_LEARNING_OBJECTIVES list is empty. Using general comprehension for questions.", fg="yellow"))

    if not question_learning_objectives: # Fallback if selection was empty or list was empty
        click.echo("Using 'general comprehension' for questions as no specific learning objectives were set/selected.", fg="yellow")
        # The LLM prompt will handle an empty list by defaulting to 'general comprehension'

    click.echo(
        f"\n--- Generating {NUM_QUESTIONS_PER_BATCH} {question_type_options[q_type_choice_key]} questions for passage '{passage_asset.title.en}' in a single batch ---"
    )
    
    llm_prompt_batch = (
        f"You are an expert assistant tasked with creating a batch of {NUM_QUESTIONS_PER_BATCH} reading comprehension questions based on the provided passage and specifications.\\n"
        f"Reading Passage Content:\\n```\\n{passage_asset.content}\\n```\\n"
        f"The passage is intended for a '{passage_asset.difficulty.name.en}' student level.\\n"
        f"Generate exactly {NUM_QUESTIONS_PER_BATCH} questions of type '{question_type_options[q_type_choice_key]}'.\\n"
        f"All generated questions should focus on these learning objectives: {', '.join(question_learning_objectives) if question_learning_objectives else 'general comprehension and understanding of the passage'}.\\n"
        f"Your response MUST be a single, minified JSON object with a top-level key named 'questions_list'.\\n"
        f"The value of 'questions_list' MUST be a JSON array containing exactly {NUM_QUESTIONS_PER_BATCH} question objects.\\n"
        f"Each question object in the 'questions_list' array must have the following keys:\\n"
        f"- 'questionText': (String) The main question text in English.\\n"
    )
    if chosen_question_type_str == "MCQ":
        llm_prompt_batch += (
            f"- 'choices': (List of 3 to 4 objects) Each choice object must have: \\n"
            f"    - 'text': (String) The answer option in English.\\n"
            f"    - 'isCorrect': (Boolean) True for exactly ONE choice, false for others.\\n"
        )
    else:  # TEXT_INPUT
        llm_prompt_batch += (
            f"- 'acceptableAnswers': (List of 1 to 3 strings) Each string is an acceptable short answer in English.\\n"
        )
    llm_prompt_batch += (
        f"- 'explanation_en': (String) A concise explanation for the answer in English.\\n"
        f"- 'explanation_zh_tw': (String) A concise explanation for the answer in Traditional Chinese.\\n"
        f"Important: Ensure each generated question is directly answerable from the provided passage content and is distinct from other questions in the batch.\\n"
        f"Example of the 'questions_list' containing ONE MCQ question (you need to generate {NUM_QUESTIONS_PER_BATCH} such objects in the list):\\n"
        f"{{ \\\"questions_list\\\": [ {{\\\"questionText\\\":\\\"What is the main color of the described house?\\\", \\\"choices\\\":[{{\\\"text\\\":\\\"Blue\\\",\\\"isCorrect\\\":false}},{{\\\"text\\\":\\\"Red\\\",\\\"isCorrect\\\":true}},{{\\\"text\\\":\\\"Green\\\",\\\"isCorrect\\\":false}}], \\\"explanation_en\\\":\\\"The passage states the house was red.\\\", \\\"explanation_zh_tw\\\":\\\"文章指出房子是紅色的.\\\"}} ] }}"
    )

    batch_llm_response_str: Optional[str] = None
    if llm_service_name == "OPENAI":
        batch_llm_response_str = _call_openai_api(llm_api_key, llm_prompt_batch)
    elif llm_service_name == "GOOGLE":
        batch_llm_response_str = _call_gemini_api(llm_api_key, llm_prompt_batch)
    
    if not batch_llm_response_str:
        click.echo("LLM call for batch question generation failed to return content. No questions generated.", err=True)
        return generated_questions

    try:
        response_data = json.loads(batch_llm_response_str)
        questions_data_list = response_data.get("questions_list")

        if not isinstance(questions_data_list, list):
            click.echo(f"LLM response for batch questions did not contain a valid 'questions_list' array. Aborting.", err=True)
            click.echo(f"LLM Raw Response Snippet: {batch_llm_response_str[:300]}...", err=True)
            return generated_questions
            
        if len(questions_data_list) != NUM_QUESTIONS_PER_BATCH:
            click.echo(
                f"Warning: LLM was asked for {NUM_QUESTIONS_PER_BATCH} questions but returned {len(questions_data_list)}. Processing available items if valid, but this indicates an LLM compliance issue.", 
                fg="yellow"
            )
            if not questions_data_list: # If list is empty
                click.echo("LLM returned an empty list of questions. No questions generated.", err=True)
                return generated_questions

        for idx, q_data_from_llm in enumerate(questions_data_list):
            if not isinstance(q_data_from_llm, dict):
                click.echo(f"Item {idx+1} in 'questions_list' is not a valid question object (not a dict). Skipping.", err=True)
                continue
            
            click.echo(f"\n--- Processing Question {idx + 1} of {len(questions_data_list)} from batch ---")
            rc_question_data_dict = {} 
            try:
                question_text = q_data_from_llm.get("questionText")
                explanation_en = q_data_from_llm.get("explanation_en")
                explanation_zh_tw = q_data_from_llm.get("explanation_zh_tw")

                if not (isinstance(question_text, str) and question_text.strip() and 
                          isinstance(explanation_en, str) and explanation_en.strip() and 
                          isinstance(explanation_zh_tw, str) and explanation_zh_tw.strip()):
                    click.echo(f"Question {idx+1} from batch missing required text fields or fields are empty. Skipping.", err=True)
                    click.echo(f"Problematic question data: {q_data_from_llm}", err=True)
                    continue
                
                rc_question_data_dict = {
                    "questionType": "READING_COMPREHENSION", "contentAssetId": passage_asset.assetId,
                    "difficulty": passage_asset.difficulty.model_copy(), 
                    "learningObjectives": question_learning_objectives, # Apply same LOs to all questions in batch
                    "questionText": str(question_text).strip(),
                    "explanation": LocalizedString(en=str(explanation_en).strip(), zh_tw=str(explanation_zh_tw).strip()),
                    "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
                }

                if chosen_question_type_str == "MCQ":
                    llm_choices = q_data_from_llm.get("choices")
                    if not isinstance(llm_choices, list) or not (3 <= len(llm_choices) <= 4): 
                        click.echo(f"Question {idx+1} (MCQ): Invalid 'choices' format or count. Expected list of 3-4 items. Skipping. Got: {llm_choices}", err=True)
                        click.echo(f"Problematic choices data: {llm_choices}", err=True)
                        continue
                    parsed_choices = []
                    correct_choices_count = 0
                    for choice_idx, choice_data in enumerate(llm_choices):
                        if not isinstance(choice_data, dict): 
                            click.echo(f"Choice {choice_idx+1} for Question {idx+1} is not a dictionary. Skipping question.", err=True); parsed_choices = []; break
                        choice_text_val = choice_data.get("text"); is_correct_val = choice_data.get("isCorrect")
                        if not (isinstance(choice_text_val, str) and choice_text_val.strip() and isinstance(is_correct_val, bool)):
                             click.echo(f"Invalid text/isCorrect type or empty text in choice {choice_idx+1} for Question {idx+1}. Skipping question. Data: {choice_data}", err=True); parsed_choices = []; break
                        parsed_choices.append(ChoiceDetail(text=choice_text_val.strip(), isCorrect=is_correct_val))
                        if is_correct_val: correct_choices_count +=1
                    
                    if not parsed_choices and (isinstance(llm_choices, list) and llm_choices): 
                        continue 
                    if not parsed_choices and not llm_choices:
                         click.echo(f"Question {idx+1} (MCQ): 'choices' list was empty or invalid. Skipping.", err=True); continue

                    if correct_choices_count != 1:
                        click.echo(f"MCQ Question {idx+1} must have exactly one correct choice. Found {correct_choices_count}. Skipping.", err=True)
                        continue
                    rc_question_data_dict["choices"] = parsed_choices
                    rc_question_data_dict["acceptableAnswers"] = None
                else:  # TEXT_INPUT
                    llm_ans = q_data_from_llm.get("acceptableAnswers")
                    if not isinstance(llm_ans, list) or not (1 <= len(llm_ans) <= 3) or not all(isinstance(a, str) and a.strip() for a in llm_ans):
                        click.echo(f"Question {idx+1} (Text Input): Invalid 'acceptableAnswers'. Expected list of 1-3 non-empty strings. Skipping. Got: {llm_ans}", err=True)
                        click.echo(f"Problematic answers data: {llm_ans}", err=True)
                        continue
                    rc_question_data_dict["acceptableAnswers"] = [ans.strip() for ans in llm_ans]
                    rc_question_data_dict["choices"] = None
                
                new_question = ReadingComprehensionQuestion(**rc_question_data_dict)
                generated_questions.append(new_question)
                click.echo(f"Successfully validated and generated Question {idx + 1} from batch: {new_question.questionText[:60]}...")
            
            except Exception as e_indiv: 
                click.echo(f"Error processing data for Question {idx+1} in batch: {e_indiv}", err=True)
                click.echo(f"  Problematic question data from LLM: {q_data_from_llm}", err=True)
                # click.echo(f"  Data being validated: {rc_question_data_dict}", err=True) # Uncomment for deeper debugging if needed
    
    except json.JSONDecodeError: 
        click.echo(f"Error decoding main JSON response for batch questions. Raw response snippet: {batch_llm_response_str[:200]}...", err=True)
    except Exception as e_batch: 
        click.echo(f"An unexpected error occurred processing the batch of questions: {e_batch}", err=True)
        click.echo(f"LLM Raw Response Snippet for batch: {batch_llm_response_str[:300]}...", err=True)
            
    return generated_questions

def _workflow_generate_new_passage_and_questions(
    db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]
):
    click.echo("\n--- Generate New Passage & Associated Questions ---")
    
    passage_asset = _create_new_passage_asset_interactive(
        llm_api_key, llm_service_name
    )
    if not passage_asset: 
        click.echo("Passage asset creation failed or was aborted. Cannot generate questions.", err=True)
        return

    generated_questions: List[ReadingComprehensionQuestion] = []
    
    if click.confirm(
        "\nDo you want to generate comprehension questions for this passage now?",
        default=True,
    ):
        generated_questions = _generate_interactive_questions_for_passage(
            passage_asset=passage_asset,
            llm_api_key=llm_api_key,
            llm_service_name=llm_service_name
        )

    click.echo(f"\n--- Question Generation Complete ---")
    if generated_questions:
        click.echo(f"{len(generated_questions)} questions were generated and validated.")
    else:
        click.echo("No questions were generated or validated successfully.")

    click.echo(click.style("\n\n--- Generated Content Review ---", fg="cyan", bold=True))
    if passage_asset:
        click.echo(click.style("\n--- Passage Details ---", fg="green", bold=True))
        click.echo(click.style(f"Title (EN): {passage_asset.title.en}", bold=True))
        if passage_asset.title.zh_tw and passage_asset.title.zh_tw != passage_asset.title.en: 
            click.echo(click.style(f"Title (ZH_TW): {passage_asset.title.zh_tw}", bold=True))
        click.echo(f"Difficulty: {passage_asset.difficulty.name.en} ({passage_asset.difficulty.name.zh_tw})")
        click.echo(f"  Stage: {passage_asset.difficulty.stage}, Grade: {passage_asset.difficulty.grade}, Level: {passage_asset.difficulty.level}")
        if passage_asset.learningObjectives:
            click.echo(f"Passage Learning Objectives: {', '.join(passage_asset.learningObjectives)}")
        if passage_asset.description and (passage_asset.description.en or passage_asset.description.zh_tw):
            click.echo(click.style("Description (EN):", underline=True)); click.echo(f"  {passage_asset.description.en or 'N/A'}")
            if passage_asset.description.zh_tw and passage_asset.description.zh_tw != passage_asset.description.en:
                 click.echo(click.style("Description (ZH_TW):", underline=True)); click.echo(f"  {passage_asset.description.zh_tw}")
        click.echo(click.style("\nPassage Content:", underline=True, bold=True)); click.echo(passage_asset.content)
    else: 
        click.echo(click.style("No passage asset was created or available for review.", fg="yellow"))

    if generated_questions:
        click.echo(click.style(f"\n--- Generated Questions ({len(generated_questions)}) ---", fg="green", bold=True))
        for idx, q in enumerate(generated_questions):
            click.echo(click.style(f"\nQuestion {idx + 1}:", bold=True, underline=True)); click.echo(q.questionText)
            # Learning objectives are part of the question object, set during its creation
            if q.learningObjectives: 
                click.echo(f"  Question LOs: {', '.join(q.learningObjectives)}")
            if q.choices:
                click.echo("  Options:")
                for c_idx, choice in enumerate(q.choices):
                    prefix = click.style(f"    [{'*' if choice.isCorrect else ' '}] {chr(65 + c_idx)}. ", fg="blue" if choice.isCorrect else None)
                    click.echo(f"{prefix}{choice.text}")
            elif q.acceptableAnswers:
                click.echo(f"  Acceptable Answers: {click.style('; '.join(q.acceptableAnswers), fg='blue')}")
            if q.explanation:
                click.echo(click.style("  Explanation (EN):", dim=True)); click.echo(click.style(f"    {q.explanation.en}", dim=True))
                if q.explanation.zh_tw and q.explanation.zh_tw != q.explanation.en:
                    click.echo(click.style("  Explanation (ZH_TW):", dim=True)); click.echo(click.style(f"    {q.explanation.zh_tw}", dim=True))
            if idx < len(generated_questions) - 1:
                click.echo("---")
    elif passage_asset: 
        click.echo(click.style("\nNo questions were generated for this passage.", fg="yellow"))

    click.echo(click.style("\n--- Save to Database ---", fg="magenta", bold=True))
    if db and passage_asset:
        if click.confirm(
            "\nDo you want to save the passage and its generated questions to the database?", default=True
        ):
            passage_saved = _save_passage_asset_to_db(db, passage_asset)
            if passage_saved:
                saved_q_count = 0
                if generated_questions:
                    for q_to_save in generated_questions:
                        # Note: q_to_save already has its difficulty and learningObjectives set 
                        # by _generate_interactive_questions_for_passage
                        if _save_reading_comprehension_question_to_db(db, q_to_save): 
                            saved_q_count += 1
                    click.echo(f"{saved_q_count} of {len(generated_questions)} questions saved.")
                else: 
                    click.echo("No questions to save (none were generated/validated).")
            else: 
                click.echo("Passage save failed. Questions not saved.", err=True)
        else: 
            click.echo("Passage and questions not saved.")
    elif passage_asset: 
        click.echo("Database connection not available. Cannot save.")

def _workflow_generate_new_passage_only(
    db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]
):
    click.echo("\n--- Generate New Passage Only ---")

    passage_asset = _create_new_passage_asset_interactive(
        llm_api_key, llm_service_name
    )
    if not passage_asset:
        click.echo("Passage asset creation failed or was aborted.", err=True)
        return

    click.echo(click.style("\n\n--- Generated Content Review ---", fg="cyan", bold=True))
    click.echo(click.style("\n--- Passage Details ---", fg="green", bold=True))
    click.echo(click.style(f"Title (EN): {passage_asset.title.en}", bold=True))
    if passage_asset.title.zh_tw and passage_asset.title.zh_tw != passage_asset.title.en: 
        click.echo(click.style(f"Title (ZH_TW): {passage_asset.title.zh_tw}", bold=True))
    click.echo(f"Difficulty: {passage_asset.difficulty.name.en} ({passage_asset.difficulty.name.zh_tw})")
    if passage_asset.learningObjectives:
        click.echo(f"Passage Learning Objectives: {', '.join(passage_asset.learningObjectives)}")
    if passage_asset.description and (passage_asset.description.en or passage_asset.description.zh_tw):
        click.echo(click.style("Description (EN):", underline=True)); click.echo(f"  {passage_asset.description.en or 'N/A'}")
        if passage_asset.description.zh_tw and passage_asset.description.zh_tw != passage_asset.description.en:
             click.echo(click.style("Description (ZH_TW):", underline=True)); click.echo(f"  {passage_asset.description.zh_tw}")
    click.echo(click.style("\nPassage Content:", underline=True, bold=True)); click.echo(passage_asset.content)

    click.echo(click.style("\n--- Save to Database ---", fg="magenta", bold=True))
    if db:
        if click.confirm(
            "\nDo you want to save this passage to the database?", default=True
        ):
            if _save_passage_asset_to_db(db, passage_asset):
                 click.echo("Passage saved successfully.")
            else:
                 click.echo("Failed to save passage.", err=True)
        else:
            click.echo("Passage not saved.")
    else:
        click.echo("Database connection not available. Cannot save passage.")

def _workflow_generate_questions_for_existing_passage(
    db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]
):
    click.echo("\n--- Generate Questions for Existing Passage ---")
    
    if not db:
        click.echo("Database client not available. Cannot list or select passages.", err=True)
        return
        
    passage_asset = _list_and_select_passage_asset(db, details=True)
    if not passage_asset:
        click.echo("No passage selected or found. Aborting question generation.")
        return

    click.echo(f"\nGenerating questions for passage: '{passage_asset.title.en}' (ID: {passage_asset.assetId})")

    generated_questions = _generate_interactive_questions_for_passage(
        passage_asset=passage_asset,
        llm_api_key=llm_api_key,
        llm_service_name=llm_service_name
    )
    
    click.echo(
        f"\n--- Question Generation Complete for passage '{passage_asset.title.en}' ---"
    )
    if generated_questions:
        click.echo(f"{len(generated_questions)} questions were generated and validated.")
    else:
        click.echo(
            "No questions were generated or validated successfully for this passage."
        )

    if generated_questions:
        click.echo(
            click.style(
                f"\n--- Generated Questions ({len(generated_questions)}) for '{passage_asset.title.en}' ---",
                fg="green",
                bold=True,
            )
        )
        for idx, q in enumerate(generated_questions):
            click.echo(
                click.style(f"\nQuestion {idx + 1}:", bold=True, underline=True)
            )
            click.echo(q.questionText)
            if q.learningObjectives:
                click.echo(f"  Question LOs: {', '.join(q.learningObjectives)}")
            if q.choices: # MCQ
                click.echo("  Options:")
                for c_idx, choice_detail in enumerate(q.choices):
                    prefix = click.style(
                        f"    [{'*' if choice_detail.isCorrect else ' '}] {chr(65 + c_idx)}. ",
                        fg="blue" if choice_detail.isCorrect else None,
                    )
                    click.echo(f"{prefix}{choice_detail.text}")
            elif q.acceptableAnswers:  # Text Input
                click.echo(
                    f"  Acceptable Answers: {click.style('; '.join(q.acceptableAnswers), fg='blue')}"
                )
            if q.explanation:
                click.echo(click.style(f"  Explanation (EN): {q.explanation.en}", dim=True))
                if q.explanation.zh_tw and q.explanation.zh_tw != q.explanation.en:
                    click.echo(
                        click.style(
                            f"  Explanation (ZH_TW): {q.explanation.zh_tw}", dim=True
                        )
                    )
    
        click.echo(click.style("\n--- Save Questions to Database ---", fg="magenta", bold=True))
        if db:
            if click.confirm(
                f"\nDo you want to save these {len(generated_questions)} questions for passage '{passage_asset.title.en}' to the database?",
                default=True,
            ):
                saved_q_count = 0
                for q_to_save in generated_questions:
                    # Note: q_to_save already has its difficulty and learningObjectives set
                    if _save_reading_comprehension_question_to_db(db, q_to_save):
                        saved_q_count += 1
                click.echo(f"{saved_q_count} of {len(generated_questions)} questions saved for passage ID {passage_asset.assetId}.")
            else: click.echo("Generated questions not saved.")
        else: click.echo("Database connection not available. Cannot save questions.")
    elif passage_asset: 
        click.echo(click.style(f"\nNo questions were generated for passage '{passage_asset.title.en}'.", fg="yellow"))

def handle_reading_comprehension_generation(
    db: Optional[Any],
    llm_api_key: Optional[str],
    llm_service_name: Optional[str]
):
    """
    Main handler for reading comprehension generation tasks.
    Allows user to choose between generating new passage + questions,
    new passage only, or questions for existing passage.
    """
    click.echo(click.style("\n--- Reading Comprehension Generation Menu ---", fg="blue", bold=True))

    workflow_options: Dict[str, str] = {
        "1": "Generate NEW Passage AND associated Questions",
        "2": "Generate NEW Passage ONLY",
        "3": "Generate Questions for an EXISTING Passage",
        "4": "Back to main menu"
    }

    while True:
        click.echo("\nChoose an action:")
        for key, value in workflow_options.items():
            click.echo(f"{key}. {value}")
        
        choice = click.prompt("Enter your choice", type=click.Choice(list(workflow_options.keys())), show_choices=False)

        if choice == "1":
            _workflow_generate_new_passage_and_questions(db, llm_api_key, llm_service_name)
        elif choice == "2":
            _workflow_generate_new_passage_only(db, llm_api_key, llm_service_name)
        elif choice == "3":
            _workflow_generate_questions_for_existing_passage(db, llm_api_key, llm_service_name)
        elif choice == "4":
            click.echo("Returning to main menu...")
            break
        
        if not click.confirm("\nPerform another reading comprehension task?", default=True):
            click.echo("Exiting reading comprehension generation.")
            break