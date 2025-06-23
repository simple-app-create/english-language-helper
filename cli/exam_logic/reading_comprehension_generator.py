# english-language-helper/cli/exam_logic/reading_comprehension_generator.py
"""
Handles the logic for generating 'Reading Comprehension' questions.
This module provides options to generate new reading passages with associated questions,
generate passages only, or to generate questions for existing passages.
"""

from typing import Optional, Any, List
import click
import uuid
from datetime import datetime, timezone
import json

# Corrected imports:
# 'schemas' is imported absolutely from the project root (assuming sys.path is set correctly by the caller)
# '.exam_generation_utils' is a relative import from the same package (exam_logic)
from schemas import (
    DifficultyDetail,
    LocalizedString,
    ChoiceDetail,
    PassageAsset,
    ReadingComprehensionQuestion,
    AssetBase,
)
from .exam_generation_utils import _prompt_difficulty_detail, _call_openai_api, _call_gemini_api


# Firestore Collection Names
PASSAGE_ASSETS_COLLECTION = "passage_assets"
QUESTIONS_COLLECTION = "questions"

# --- Firestore Helper Functions ---
def _save_passage_asset_to_db(db: Any, passage_asset: PassageAsset) -> bool:
    """Saves a PassageAsset to Firestore."""
    if not db:
        click.echo("Database client not available. Cannot save passage asset.", err=True)
        return False
    try:
        doc_ref = db.collection(PASSAGE_ASSETS_COLLECTION).document(passage_asset.assetId)
        doc_ref.set(passage_asset.model_dump(mode='json'))
        click.echo(f"Passage Asset '{passage_asset.title.en}' (ID: {passage_asset.assetId}) saved successfully to '{PASSAGE_ASSETS_COLLECTION}'.")
        return True
    except Exception as e:
        click.echo(f"Error saving passage asset (ID: {passage_asset.assetId}) to Firestore: {e}", err=True)
        return False

def _save_reading_comprehension_question_to_db(db: Any, question: ReadingComprehensionQuestion) -> bool:
    """Saves a ReadingComprehensionQuestion to Firestore."""
    if not db:
        click.echo("Database client not available. Cannot save question.", err=True)
        return False
    try:
        question_doc_id = uuid.uuid4().hex
        doc_ref = db.collection(QUESTIONS_COLLECTION).document(question_doc_id)
        doc_ref.set(question.model_dump(mode='json'))
        click.echo(f"Question '{question.questionText[:50]}...' (Doc ID: {question_doc_id}) saved successfully to '{QUESTIONS_COLLECTION}'.")
        return True
    except Exception as e:
        click.echo(f"Error saving question (Passage ID: {question.contentAssetId}) to Firestore: {e}", err=True)
        return False

def _list_and_select_passage_asset(db: Any) -> Optional[PassageAsset]:
    """Lists passage assets from Firestore and allows user selection."""
    if not db:
        click.echo("Database client not available. Cannot list passages.", err=True)
        return None
    try:
        passages_ref = db.collection(PASSAGE_ASSETS_COLLECTION).stream()
        passages_list = []
        for doc in passages_ref:
            try:
                passage_data = doc.to_dict()
                if passage_data:
                    passage_data['assetId'] = doc.id
                    passages_list.append(PassageAsset(**passage_data))
            except Exception as e:
                click.echo(f"Warning: Could not parse passage document {doc.id}. Error: {e}", err=True)
                continue

        if not passages_list:
            click.echo("No passage assets found in the database.")
            return None

        click.echo("\n--- Available Passage Assets ---")
        for i, pa in enumerate(passages_list):
            title_en = pa.title.en if pa.title else "N/A"
            difficulty_name = pa.difficulty.name.en if pa.difficulty and pa.difficulty.name else "N/A"
            click.echo(f"{i + 1}. ID: {pa.assetId} - Title: {title_en} (Difficulty: {difficulty_name})")

        choice = click.prompt(
            "Select a passage asset by number (or 0 to cancel)",
            type=int,
            default=0,
            show_default=True,
        )
        if choice <= 0 or choice > len(passages_list):
            click.echo("Selection cancelled or invalid.")
            return None

        selected_passage_asset = passages_list[choice - 1]
        click.echo(f"Selected passage: {selected_passage_asset.title.en if selected_passage_asset.title else 'N/A'}")
        return selected_passage_asset

    except Exception as e:
        click.echo(f"Error listing passage assets from Firestore: {e}", err=True)
        return None

# --- Refactored Passage Creation Logic ---
def _create_new_passage_asset_interactive(llm_api_key: Optional[str], llm_service_name: Optional[str]) -> Optional[PassageAsset]:
    """
    Interactive workflow to create a new PassageAsset object (in memory).
    Handles difficulty, topic, content generation (manual/LLM), title, description, learning objectives, and translations.
    """
    # 1. Difficulty Detail
    difficulty_detail: Optional[DifficultyDetail] = _prompt_difficulty_detail()
    if not difficulty_detail:
        click.echo("Failed to get difficulty details. Aborting passage creation.", err=True)
        return None

    # 2. Topic Selection (User or LLM)
    passage_topic: Optional[str] = None
    topic_source_choice_prompt = click.style("Topic for the reading passage: (M)anually enter, or have the (L)LM suggest one?", fg="blue")
    topic_source_choice = click.prompt(
        topic_source_choice_prompt,
        type=click.Choice(['M', 'L'], case_sensitive=False),
        default='M'
    ).upper()

    if topic_source_choice == 'L':
        if not llm_api_key or not llm_service_name:
            click.echo("LLM API key/service not available for topic suggestion. Please enter topic manually.", err=True)
            topic_source_choice = 'M'
        else:
            while True:
                prompt_llm_topic = (
                    f"You are an assistant helping to create educational content. "
                    f"Suggest one engaging and suitable topic for a reading passage for a student at the '{difficulty_detail.name.en}' level. "
                    f"The topic should be concise (ideally 3-7 words). "
                    f"Your response MUST be a single, minified JSON object with one key: 'suggested_topic'. "
                    f"Example: {{\"suggested_topic\": \"A Journey to the Stars\"}}"
                )
                click.echo(f"\nRequesting LLM to suggest a topic for '{difficulty_detail.name.en}' level...")
                llm_topic_response_str: Optional[str] = None
                if llm_service_name == "OPENAI": llm_topic_response_str = _call_openai_api(llm_api_key, prompt_llm_topic)
                elif llm_service_name == "GOOGLE": llm_topic_response_str = _call_gemini_api(llm_api_key, prompt_llm_topic)

                suggested_topic_from_llm: Optional[str] = None
                if llm_topic_response_str:
                    try:
                        topic_data = json.loads(llm_topic_response_str)
                        suggested_topic_from_llm = topic_data.get("suggested_topic")
                        if isinstance(suggested_topic_from_llm, str) and suggested_topic_from_llm.strip():
                            suggested_topic_from_llm = suggested_topic_from_llm.strip()
                            click.echo(click.style(f"LLM suggested topic: \"{suggested_topic_from_llm}\"", fg="green"))
                        else:
                            suggested_topic_from_llm = None
                            click.echo("LLM did not provide a valid topic string in the expected format.", err=True)
                    except json.JSONDecodeError:
                        click.echo(f"Failed to decode LLM response for topic suggestion. Raw: {llm_topic_response_str[:200]}...", err=True)
                        suggested_topic_from_llm = None
                
                if suggested_topic_from_llm:
                    topic_review_choice = click.prompt(
                        "Use this topic? (Y)es, (N)o (enter manually), (R)egenerate",
                        type=click.Choice(['Y', 'N', 'R'], case_sensitive=False), default='Y'
                    ).upper()
                    if topic_review_choice == 'Y': passage_topic = suggested_topic_from_llm; break
                    elif topic_review_choice == 'N': topic_source_choice = 'M'; break
                else:
                    click.echo("LLM topic suggestion failed to produce a valid topic.", err=True)
                    if not click.confirm("Try LLM suggestion again?", default=False):
                        topic_source_choice = 'M'; break
    
    if topic_source_choice == 'M':
        passage_topic = click.prompt(
            "Enter the topic for the reading passage (e.g., 'The Importance of Recycling')",
            type=str, default="A Visit to the Zoo"
        ).strip()

    if not passage_topic or not passage_topic.strip():
        click.echo("No topic provided or topic is empty. Aborting passage creation.", err=True)
        return None
    click.echo(f"Using topic: \"{passage_topic}\"")

    # 3. Passage Length/Style
    PASSAGE_LENGTH_OPTIONS = {
        '1': "One Paragraph (approx. 50-100 words)", '2': "Short (approx. 100-150 words, 1-2 paragraphs)",
        '3': "Medium (approx. 200-300 words, 2-3 paragraphs)", '4': "Long (approx. 400-500 words, 3-5 paragraphs)"
    }
    click.echo("\nSelect the desired passage length and style:")
    for key, value in PASSAGE_LENGTH_OPTIONS.items(): click.echo(f"{key}: {value}")
    length_choice_key = click.prompt("Choose passage length/style", type=click.Choice(list(PASSAGE_LENGTH_OPTIONS.keys())), default='2', show_choices=False)
    passage_length_style_description = PASSAGE_LENGTH_OPTIONS[length_choice_key]
    click.echo(f"Selected: {passage_length_style_description}")

    # 4. Passage Content (LLM or Manual)
    click.echo("\nHow would you like to provide the passage content?")
    click.echo("L: Generate content and title using an LLM (requires API key).")
    click.echo("M: Enter content manually (you will be prompted for a title separately).")
    content_source_choice = click.prompt("Choose content source (L/M)", type=click.Choice(['L', 'M'], case_sensitive=False), default='L').upper()

    passage_content_text: Optional[str] = None
    suggested_llm_title: Optional[str] = None 

    if content_source_choice == 'L':
        if not llm_api_key or not llm_service_name:
            click.echo("LLM API key/service not available. Please enter content manually.", err=True)
            content_source_choice = 'M'
        
        if content_source_choice == 'L':
            initial_generation_done = False
            while True:
                if not initial_generation_done or (initial_generation_done and content_source_choice == 'L_REGENERATE'):
                    current_llm_call_succeeded = False
                    prompt_llm_content = (
                        f"You are an assistant helping to create educational content. Generate a reading passage and a suitable title for it.\n"
                        f"The student's level is '{difficulty_detail.name.en}'.\n"
                        f"The topic for the passage is: '{passage_topic}'.\n"
                        f"The desired style and length for the passage is: '{passage_length_style_description}'.\n"
                        f"Your response MUST be a single, minified JSON object with exactly two keys:\n"
                        f"1. 'suggested_title': A concise and relevant title for the passage, in English.\n"
                        f"2. 'passage_text': The full text of the reading passage.\n"
                        f"Example: {{\"suggested_title\": \"A Fun Day at the Park\", \"passage_text\": \"The sun was shining brightly...\"}}"
                    )
                    click.echo(f"\nRequesting LLM to generate passage and title for '{passage_topic}'...")
                    llm_content_response_str: Optional[str] = None
                    if llm_service_name == "OPENAI": llm_content_response_str = _call_openai_api(llm_api_key, prompt_llm_content)
                    elif llm_service_name == "GOOGLE": llm_content_response_str = _call_gemini_api(llm_api_key, prompt_llm_content)

                    if llm_content_response_str:
                        try:
                            content_data = json.loads(llm_content_response_str)
                            temp_title = content_data.get("suggested_title")
                            temp_text = content_data.get("passage_text")
                            if isinstance(temp_title, str) and temp_title.strip() and isinstance(temp_text, str) and temp_text.strip():
                                suggested_llm_title = temp_title.strip()
                                passage_content_text = temp_text.strip()
                                initial_generation_done = True; current_llm_call_succeeded = True
                                click.echo(click.style(f"\nLLM Suggested Title: {suggested_llm_title}", fg="green"))
                                click.echo(f"Generated Passage Text:\n---\n{passage_content_text}\n---")
                            else: click.echo("LLM response missing title/text.", err=True)
                        except json.JSONDecodeError: click.echo(f"Failed to decode LLM content response. Raw: {llm_content_response_str[:200]}...", err=True)
                    
                    if not current_llm_call_succeeded:
                        click.echo("LLM call failed to produce valid content.", err=True)
                        if not initial_generation_done:
                            if click.confirm("Enter content manually instead?", default=True): content_source_choice = 'M'; break
                            else: click.echo("Aborting passage creation.", err=True); return None
                    if content_source_choice == 'L_REGENERATE': content_source_choice = 'L'

                if not passage_content_text and not initial_generation_done: click.echo("No content to review. Aborting.", err=True); return None
                
                click.echo("\nReview the generated passage text:"); click.echo("(A)ccept"); click.echo("(E)dit")
                click.echo("(R)egenerate from LLM"); click.echo("(M)anual Fallback"); click.echo("(X)Exit to RC Menu")
                review_choice = click.prompt("Your choice", type=click.Choice(['A', 'E', 'R', 'M', 'X'], case_sensitive=False), default='A').upper()

                if review_choice == 'A': break
                elif review_choice == 'X': click.echo("Exiting passage creation..."); return None
                elif review_choice == 'M': content_source_choice = 'M'; break
                elif review_choice == 'E':
                    edited_text = click.edit(text=(passage_content_text or ""), extension=".txt")
                    if edited_text is not None: passage_content_text = edited_text.strip(); click.echo(f"Edited Passage Text:\n---\n{passage_content_text}\n---")
                    else: click.echo("Edit cancelled.")
                elif review_choice == 'R':
                    if not llm_api_key or not llm_service_name: click.echo("Cannot regenerate, LLM API not available.", err=True); continue
                    content_source_choice = 'L_REGENERATE'
            
            if content_source_choice != 'M' and not passage_content_text: click.echo("No passage content. Aborting.", err=True); return None

    if content_source_choice == 'M':
        click.echo("\n--- Manual Passage Content Input ---")
        click.echo("Your system's default text editor will open.")
        initial_text_for_editor = passage_content_text if passage_content_text else ""
        if initial_text_for_editor: click.echo("(Editor pre-filled with LLM text if available.)")
        edited_text_manual = click.edit(text=initial_text_for_editor, extension=".txt")
        if edited_text_manual is None:
            click.echo("Passage input aborted.", err=True)
            if passage_content_text and click.confirm("Use previously available text?", default=True): click.echo("Using previous text.")
            else: click.echo("Aborting passage creation.", err=True); return None
        else: passage_content_text = edited_text_manual.strip()
        if not passage_content_text: click.echo("No content provided. Aborting.", err=True); return None
        click.echo(f"Final Passage Content (Manually Entered/Edited):\n---\n{passage_content_text}\n---")

    if not passage_content_text: click.echo("Failed to obtain passage content. Aborting.", err=True); return None

    # 5. LLM-Generated English Description & Learning Objectives
    llm_suggested_description_en = ""
    if llm_api_key and llm_service_name and passage_content_text:
        desc_prompt = (
            f"Based on the following passage, generate a concise, one-sentence English description (max 20 words):\n\n"
            f"Passage:\n```\n{passage_content_text[:1000]}\n```\n\n"
            f"Your response MUST be a single, minified JSON object with one key: 'description_en'. "
            f"Example: {{\"description_en\": \"A brief summary of the passage content.\"}}"
        )
        click.echo("\nGenerating English description using LLM...")
        llm_desc_response_str = None
        if llm_service_name == "OPENAI": llm_desc_response_str = _call_openai_api(llm_api_key, desc_prompt)
        elif llm_service_name == "GOOGLE": llm_desc_response_str = _call_gemini_api(llm_api_key, desc_prompt)
        if llm_desc_response_str:
            try:
                desc_data = json.loads(llm_desc_response_str)
                temp_desc = desc_data.get("description_en")
                if isinstance(temp_desc, str) and temp_desc.strip():
                    llm_suggested_description_en = temp_desc.strip()
                    click.echo(f"LLM suggested EN description: \"{llm_suggested_description_en}\"")
            except Exception: click.echo("Could not get EN description from LLM.", err=True)
        else: click.echo("LLM call for EN description failed.", err=True)

    llm_suggested_learning_objectives_list = []
    if llm_api_key and llm_service_name and passage_content_text:
        lo_prompt = (
            f"Based on the following passage (intended for difficulty level '{difficulty_detail.name.en}'), "
            f"suggest 2-3 key learning objectives. Focus on skills (e.g., 'Identifying main idea', 'Understanding vocabulary in context') "
            f"or specific knowledge areas targeted. List them concisely.\n\n"
            f"Passage:\n```\n{passage_content_text[:1000]}\n```\n\n"
            f"Your response MUST be a single, minified JSON object with one key: 'learning_objectives', which holds a list of strings. "
            f"Example: {{\"learning_objectives\": [\"Vocabulary: Animals\", \"Reading for Detail\"]}}"
        )
        click.echo("\nGenerating learning objectives using LLM...")
        llm_lo_response_str = None
        if llm_service_name == "OPENAI": llm_lo_response_str = _call_openai_api(llm_api_key, lo_prompt)
        elif llm_service_name == "GOOGLE": llm_lo_response_str = _call_gemini_api(llm_api_key, lo_prompt)
        if llm_lo_response_str:
            try:
                lo_data = json.loads(llm_lo_response_str)
                temp_los = lo_data.get("learning_objectives")
                if isinstance(temp_los, list) and all(isinstance(lo, str) for lo in temp_los):
                    llm_suggested_learning_objectives_list = [lo.strip() for lo in temp_los if lo.strip()]
                    click.echo(f"LLM suggested learning objectives: {', '.join(llm_suggested_learning_objectives_list)}")
            except Exception: click.echo("Could not get learning objectives from LLM.", err=True)
        else: click.echo("LLM call for learning objectives failed.", err=True)

    # 6. Finalize Passage Asset Metadata (with LLM auto-translations)
    click.echo("\n--- Enter/Confirm Passage Asset Details ---")
    
    default_title_en = passage_topic[:80].replace("_", " ").title()
    if suggested_llm_title: default_title_en = suggested_llm_title
    passage_title_en = click.prompt("English title for this passage", default=default_title_en).strip()
    
    passage_title_zh_tw = passage_title_en 
    if passage_title_en and llm_api_key and llm_service_name:
        click.echo("\nAttempting automatic translation of English title to Traditional Chinese...")
        title_translate_prompt = (
            f"Translate the following English text to Traditional Chinese: \"{passage_title_en}\". "
            f"Your response MUST be a single, minified JSON object with one key: 'translation'. Example: {{\"translation\": \"一個傳統的中文標題\"}}"
        )
        llm_title_translation_str = None
        if llm_service_name == "OPENAI": llm_title_translation_str = _call_openai_api(llm_api_key, title_translate_prompt)
        elif llm_service_name == "GOOGLE": llm_title_translation_str = _call_gemini_api(llm_api_key, title_translate_prompt)
        if llm_title_translation_str:
            try:
                translation_data = json.loads(llm_title_translation_str)
                translated_title = translation_data.get("translation")
                if isinstance(translated_title, str) and translated_title.strip():
                    passage_title_zh_tw = translated_title.strip()
                    click.echo(f"LLM translated ZH-TW title: \"{passage_title_zh_tw}\"")
            except Exception: click.echo("LLM title translation failed or gave invalid format.", err=True)
        else: click.echo("LLM call for title translation failed.", err=True)
    passage_title_zh_tw = click.prompt("Confirm/Edit Traditional Chinese title", default=passage_title_zh_tw).strip()

    passage_description_en = click.prompt("Confirm/Edit English description (optional)", default=llm_suggested_description_en).strip()
    
    passage_description_zh_tw = passage_description_en
    if passage_description_en and llm_api_key and llm_service_name:
        click.echo("\nAttempting automatic translation of English description to Traditional Chinese...")
        desc_translate_prompt = (
            f"Translate the following English text to Traditional Chinese: \"{passage_description_en}\". "
            f"Your response MUST be a single, minified JSON object with one key: 'translation'. Example: {{\"translation\": \"一個傳統的中文描述\"}}"
        )
        llm_desc_translation_str = None
        if llm_service_name == "OPENAI": llm_desc_translation_str = _call_openai_api(llm_api_key, desc_translate_prompt)
        elif llm_service_name == "GOOGLE": llm_desc_translation_str = _call_gemini_api(llm_api_key, desc_translate_prompt)
        if llm_desc_translation_str:
            try:
                translation_data = json.loads(llm_desc_translation_str)
                translated_desc = translation_data.get("translation")
                if isinstance(translated_desc, str) and translated_desc.strip():
                    passage_description_zh_tw = translated_desc.strip()
                    click.echo(f"LLM translated ZH-TW description: \"{passage_description_zh_tw}\"")
            except Exception: click.echo("LLM description translation failed or gave invalid format.", err=True)
        else: click.echo("LLM call for description translation failed.", err=True)
    passage_description_zh_tw = click.prompt("Confirm/Edit Traditional Chinese description (optional)", default=passage_description_zh_tw).strip()
    
    default_lo_str = ", ".join(llm_suggested_learning_objectives_list) if llm_suggested_learning_objectives_list else passage_topic
    passage_learning_objectives_str = click.prompt("Confirm/Edit learning objectives (comma-separated)", default=default_lo_str).strip()
    passage_learning_objectives = [lo.strip() for lo in passage_learning_objectives_str.split(',') if lo.strip()]

    # 7. Create PassageAsset Object
    try:
        asset_id = uuid.uuid4().hex
        created_at_dt = datetime.now(timezone.utc)
        if difficulty_detail is None: click.echo("Critical error: Difficulty detail is None.", err=True); return None # Should be caught earlier

        passage_asset_data = {
            "assetId": asset_id, "assetType": "PASSAGE",
            "title": LocalizedString(en=passage_title_en, zh_tw=passage_title_zh_tw),
            "description": LocalizedString(en=passage_description_en, zh_tw=passage_description_zh_tw),
            "difficulty": difficulty_detail, "learningObjectives": passage_learning_objectives,
            "content": passage_content_text, "tags": [], "status": "DRAFT", "version": 1,
            "createdBy": "cli_user", "createdAt": created_at_dt, "updatedAt": created_at_dt
        }
        passage_asset_obj = PassageAsset(**passage_asset_data)
        click.echo("\nPassage Asset object created (in memory).")
        click.echo(f"Asset ID: {passage_asset_obj.assetId}")
        return passage_asset_obj
    except Exception as e:
        click.echo(f"Error creating PassageAsset object: {e}", err=True)
        return None

# --- Main Workflow Functions ---
def _workflow_generate_new_passage_and_questions(db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]):
    click.echo("\n--- Generate New Passage & Associated Questions ---")
    generated_questions: List[ReadingComprehensionQuestion] = []
    
    passage_asset = _create_new_passage_asset_interactive(llm_api_key, llm_service_name)
    if not passage_asset: return

    if click.confirm("\nDo you want to generate comprehension questions for this passage now?", default=True):
        if not llm_api_key or not llm_service_name:
            click.echo("LLM API key/service not available. Cannot generate questions.", err=True)
        else:
            num_questions_to_gen = click.prompt("How many questions to generate?", type=int, default=3)
            if num_questions_to_gen <= 0: click.echo("Number of questions must be positive.")
            else:
                question_type_options = {"1": "Multiple Choice (MCQ)", "2": "Text Input (Short Answer)"}
                click.echo("Select the type for these questions:")
                for key, value in question_type_options.items(): click.echo(f"{key}: {value}")
                q_type_choice_key = click.prompt("Choose question type", type=click.Choice(list(question_type_options.keys())), default='1', show_choices=False)
                chosen_question_type_str = "MCQ" if q_type_choice_key == '1' else "TEXT_INPUT"
                click.echo(f"Selected question type: {question_type_options[q_type_choice_key]}")

                q_learning_objectives_str = click.prompt(
                    "Enter learning objectives for these questions (comma-separated)",
                    default=", ".join(passage_asset.learningObjectives)
                ).strip()
                question_learning_objectives = [lo.strip() for lo in q_learning_objectives_str.split(',') if lo.strip()]

                for i in range(num_questions_to_gen):
                    click.echo(f"\n--- Generating Question {i + 1} of {num_questions_to_gen} ---")
                    llm_prompt_for_question = (
                        f"You are an assistant creating reading comprehension questions.\n"
                        f"Reading passage:\n```\n{passage_asset.content}\n```\n"
                        f"Passage level: '{passage_asset.difficulty.name.en}'.\n"
                        f"Generate one '{question_type_options[q_type_choice_key]}' question.\n"
                        f"Learning objectives: {', '.join(question_learning_objectives) if question_learning_objectives else 'general comprehension'}.\n"
                        f"Response MUST be JSON with keys: 'questionText' (string, English), "
                    )
                    if chosen_question_type_str == "MCQ":
                        llm_prompt_for_question += (
                            f"'choices' (list of 3-4 objects, each with 'text' (string, English) and 'isCorrect' (boolean, one true)), "
                        )
                    else: # TEXT_INPUT
                        llm_prompt_for_question += (
                            f"'acceptableAnswers' (list of 1-3 strings, English), "
                        )
                    llm_prompt_for_question += (
                        f"'explanation_en' (string, English), 'explanation_zh_tw' (string, Traditional Chinese).\n"
                        f"Example MCQ JSON: {{\"questionText\":\"What is the sky?\",\"choices\":[{{\"text\":\"Blue\",\"isCorrect\":true}},...],\"explanation_en\":\"Sky is blue.\",\"explanation_zh_tw\":\"天空是藍色的.\"}}\n"
                        f"Example Text Input JSON: {{\"questionText\":\"What is Alice's name?\",\"acceptableAnswers\":[\"Alice\"],\"explanation_en\":\"Her name is Alice.\",\"explanation_zh_tw\":\"她的名字是愛麗絲.\"}}"
                    )

                    q_llm_response_str: Optional[str] = None
                    if llm_service_name == "OPENAI": q_llm_response_str = _call_openai_api(llm_api_key, llm_prompt_for_question)
                    elif llm_service_name == "GOOGLE": q_llm_response_str = _call_gemini_api(llm_api_key, llm_prompt_for_question)
                    
                    if not q_llm_response_str: click.echo(f"LLM call for question {i+1} failed. Skipping.", err=True); continue
                    try:
                        q_data_from_llm = json.loads(q_llm_response_str)
                        question_text = q_data_from_llm.get("questionText")
                        explanation_en = q_data_from_llm.get("explanation_en")
                        explanation_zh_tw = q_data_from_llm.get("explanation_zh_tw")

                        if not (question_text and explanation_en and explanation_zh_tw):
                            click.echo(f"LLM response for Q{i+1} missing text fields. Skipping.", err=True); continue
                        
                        rc_question_data = {
                            "questionType": "READING_COMPREHENSION", "contentAssetId": passage_asset.assetId,
                            "difficulty": passage_asset.difficulty, "learningObjectives": question_learning_objectives,
                            "questionText": str(question_text),
                            "explanation": LocalizedString(en=str(explanation_en), zh_tw=str(explanation_zh_tw)),
                            "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
                            "choices": None, "acceptableAnswers": None
                        }

                        if chosen_question_type_str == "MCQ":
                            llm_choices = q_data_from_llm.get("choices")
                            if not isinstance(llm_choices, list) or not llm_choices: click.echo(f"Invalid 'choices' for MCQ Q{i+1}. Skipping.", err=True); continue
                            parsed_choices = []
                            correct_found = False
                            for choice_data in llm_choices:
                                choice_text = choice_data.get("text"); is_correct = choice_data.get("isCorrect")
                                if not isinstance(choice_text, str) or not isinstance(is_correct, bool): continue
                                parsed_choices.append(ChoiceDetail(text=choice_text, isCorrect=is_correct))
                                if is_correct: correct_found = True
                            if not correct_found and parsed_choices: click.echo(f"Warning: No correct choice for MCQ Q{i+1}.", err=True) # Or auto-fix
                            if not parsed_choices: click.echo(f"No valid choices for MCQ Q{i+1}. Skipping.", err=True); continue
                            rc_question_data["choices"] = parsed_choices
                        else: # TEXT_INPUT
                            llm_ans = q_data_from_llm.get("acceptableAnswers")
                            if not isinstance(llm_ans, list) or not all(isinstance(a, str) for a in llm_ans) or not llm_ans:
                                click.echo(f"Invalid 'acceptableAnswers' for Text Q{i+1}. Skipping.", err=True); continue
                            rc_question_data["acceptableAnswers"] = llm_ans
                        
                        new_question = ReadingComprehensionQuestion(**rc_question_data)
                        generated_questions.append(new_question)
                        click.echo(f"Successfully generated question {i + 1}: {new_question.questionText[:60]}...")
                    except json.JSONDecodeError: click.echo(f"Error decoding JSON for Q{i+1}. Raw: {q_llm_response_str[:200]}...", err=True)
                    except Exception as e: click.echo(f"Error processing Q{i+1}: {e}. Raw: {q_llm_response_str[:200]}...", err=True)

    click.echo(f"\n--- Question Generation Complete ---")
    if generated_questions: click.echo(f"{len(generated_questions)} questions were generated.")
    else: click.echo("No questions were generated.")

    click.echo(click.style("\n\n--- Generated Content Review ---", fg="cyan", bold=True))
    if passage_asset:
        click.echo(click.style("\n--- Passage Details ---", fg="green", bold=True))
        click.echo(click.style(f"Title (EN): {passage_asset.title.en}", bold=True))
        if passage_asset.title.zh_tw and passage_asset.title.zh_tw != passage_asset.title.en: click.echo(click.style(f"Title (ZH_TW): {passage_asset.title.zh_tw}", bold=True))
        click.echo(f"Difficulty: {passage_asset.difficulty.name.en} ({passage_asset.difficulty.name.zh_tw})")
        click.echo(f"  Stage: {passage_asset.difficulty.stage}, Grade: {passage_asset.difficulty.grade}, Level: {passage_asset.difficulty.level}")
        if passage_asset.learningObjectives: click.echo(f"Passage Learning Objectives: {', '.join(passage_asset.learningObjectives)}")
        if passage_asset.description and (passage_asset.description.en or passage_asset.description.zh_tw):
            click.echo(click.style("Description (EN):", underline=True)); click.echo(f"  {passage_asset.description.en or 'N/A'}")
            if passage_asset.description.zh_tw and passage_asset.description.zh_tw != passage_asset.description.en:
                 click.echo(click.style("Description (ZH_TW):", underline=True)); click.echo(f"  {passage_asset.description.zh_tw}")
        click.echo(click.style("\nPassage Content:", underline=True, bold=True)); click.echo(passage_asset.content)
    else: click.echo(click.style("No passage asset was created.", fg="yellow"))

    if generated_questions:
        click.echo(click.style(f"\n--- Generated Questions ({len(generated_questions)}) ---", fg="green", bold=True))
        for idx, q in enumerate(generated_questions):
            click.echo(click.style(f"\nQuestion {idx + 1}:", bold=True, underline=True)); click.echo(q.questionText)
            if q.learningObjectives: click.echo(f"  Question LOs: {', '.join(q.learningObjectives)}")
            if q.choices:
                click.echo("  Options:")
                for c_idx, choice in enumerate(q.choices):
                    prefix = click.style(f"    [{'*' if choice.isCorrect else ' '}] {chr(65 + c_idx)}. ", fg="blue" if choice.isCorrect else None)
                    click.echo(f"{prefix}{choice.text}")
            elif q.acceptableAnswers: click.echo(f"  Acceptable Answers: {click.style('; '.join(q.acceptableAnswers), fg='blue')}")
            if q.explanation:
                click.echo(click.style("  Explanation (EN):", dim=True)); click.echo(click.style(f"    {q.explanation.en}", dim=True))
                if q.explanation.zh_tw and q.explanation.zh_tw != q.explanation.en:
                    click.echo(click.style("  Explanation (ZH_TW):", dim=True)); click.echo(click.style(f"    {q.explanation.zh_tw}", dim=True))
            if idx < len(generated_questions) - 1: click.echo("---")
    elif passage_asset: click.echo(click.style("\nNo questions were generated for this passage.", fg="yellow"))

    click.echo(click.style("\n--- Save to Database ---", fg="magenta", bold=True))
    if db and passage_asset:
        if click.confirm("\nDo you want to save the passage and its generated questions to the database?", default=True):
            passage_saved = _save_passage_asset_to_db(db, passage_asset)
            if passage_saved:
                saved_q_count = 0
                if generated_questions:
                    for q_to_save in generated_questions:
                        if _save_reading_comprehension_question_to_db(db, q_to_save): saved_q_count += 1
                    click.echo(f"{saved_q_count} of {len(generated_questions)} questions saved.")
                else: click.echo("No questions to save.")
            else: click.echo("Passage save failed. Questions not saved.", err=True)
        else: click.echo("Passage and questions not saved.")
    elif passage_asset: click.echo("Database connection not available. Cannot save.")
    pass

def _workflow_generate_new_passage_only(db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]):
    click.echo("\n--- Generate New Passage Only ---")
    passage_asset = _create_new_passage_asset_interactive(llm_api_key, llm_service_name)
    if not passage_asset: return

    click.echo(click.style("\n\n--- Created Passage Review ---", fg="cyan", bold=True))
    click.echo(click.style("\n--- Passage Details ---", fg="green", bold=True))
    click.echo(click.style(f"Title (EN): {passage_asset.title.en}", bold=True))
    if passage_asset.title.zh_tw and passage_asset.title.zh_tw != passage_asset.title.en: click.echo(click.style(f"Title (ZH_TW): {passage_asset.title.zh_tw}", bold=True))
    click.echo(f"Difficulty: {passage_asset.difficulty.name.en} ({passage_asset.difficulty.name.zh_tw})")
    if passage_asset.learningObjectives: click.echo(f"Passage LOs: {', '.join(passage_asset.learningObjectives)}")
    if passage_asset.description and (passage_asset.description.en or passage_asset.description.zh_tw):
        click.echo(click.style("Description (EN):", underline=True)); click.echo(f"  {passage_asset.description.en or 'N/A'}")
        if passage_asset.description.zh_tw and passage_asset.description.zh_tw != passage_asset.description.en:
            click.echo(click.style("Description (ZH_TW):", underline=True)); click.echo(f"  {passage_asset.description.zh_tw}")
    click.echo(click.style("\nPassage Content:", underline=True, bold=True)); click.echo(passage_asset.content)
    
    click.echo(click.style("\n--- Save Passage to Database ---", fg="magenta", bold=True))
    if db and passage_asset:
        if click.confirm("\nDo you want to save this passage to the database?", default=True):
            _save_passage_asset_to_db(db, passage_asset)
        else: click.echo("Passage will not be saved.")
    elif passage_asset: click.echo("Database connection not available. Cannot save passage.")
    pass

def _workflow_generate_questions_for_existing_passage(db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]):
    click.echo("\n--- Generate Questions for Existing Passage ---")
    if not db: click.echo("DB not available. Cannot select existing passages.", err=True); return

    selected_passage_asset = _list_and_select_passage_asset(db)
    if not selected_passage_asset: click.echo("No passage selected."); return

    generated_questions: List[ReadingComprehensionQuestion] = []
    click.echo(click.style("\n--- Selected Passage for Question Generation ---", fg="cyan", bold=True))
    click.echo(click.style(f"Title (EN): {selected_passage_asset.title.en}", bold=True))
    click.echo(f"Content (Snippet): {selected_passage_asset.content[:200]}...")

    if not llm_api_key or not llm_service_name: click.echo("\nLLM API not available. Cannot generate questions.", err=True); return

    num_questions_to_gen = click.prompt("\nHow many questions for this passage?", type=int, default=3)
    if num_questions_to_gen <= 0: click.echo("Number of questions must be positive."); return
    
    question_type_options = {"1": "MCQ", "2": "Text Input"}
    click.echo("Select question type:"); [click.echo(f"{k}: {v}") for k, v in question_type_options.items()]
    q_type_choice_key = click.prompt("Choose type", type=click.Choice(list(question_type_options.keys())), default='1', show_choices=False)
    chosen_question_type_str = "MCQ" if q_type_choice_key == '1' else "TEXT_INPUT"
    
    q_los_str = click.prompt("Learning objectives for these questions (comma-separated)", default=", ".join(selected_passage_asset.learningObjectives)).strip()
    question_learning_objectives = [lo.strip() for lo in q_los_str.split(',') if lo.strip()]

    for i in range(num_questions_to_gen):
        click.echo(f"\n--- Generating Question {i + 1} for Passage ID: {selected_passage_asset.assetId} ---")
        llm_prompt_for_question = (
            f"You are an assistant creating reading comprehension questions.\n"
            f"Reading passage:\n```\n{selected_passage_asset.content}\n```\n"
            f"Passage level: '{selected_passage_asset.difficulty.name.en}'.\n"
            f"Generate one '{question_type_options[q_type_choice_key]}' question.\n"
            f"Learning objectives: {', '.join(question_learning_objectives) if question_learning_objectives else 'general comprehension'}.\n"
            f"Response MUST be JSON with keys: 'questionText' (string, English), "
        )
        if chosen_question_type_str == "MCQ":
            llm_prompt_for_question += f"'choices' (list of 3-4 objects, each 'text' (string, English), 'isCorrect' (boolean, one true)), "
        else: # TEXT_INPUT
            llm_prompt_for_question += f"'acceptableAnswers' (list of 1-3 strings, English), "
        llm_prompt_for_question += (
            f"'explanation_en' (string, English), 'explanation_zh_tw' (string, Traditional Chinese).\n"
            f"Example MCQ JSON: {{\"questionText\":\"Q?\",\"choices\":[{{\"text\":\"A\",\"isCorrect\":true}}],\"explanation_en\":\"Expl.\",\"explanation_zh_tw\":\"解釋.\"}}\n"
            f"Example Text Input JSON: {{\"questionText\":\"Q?\",\"acceptableAnswers\":[\"Ans\"],\"explanation_en\":\"Expl.\",\"explanation_zh_tw\":\"解釋.\"}}"
        )

        q_llm_response_str: Optional[str] = None
        if llm_service_name == "OPENAI": q_llm_response_str = _call_openai_api(llm_api_key, llm_prompt_for_question)
        elif llm_service_name == "GOOGLE": q_llm_response_str = _call_gemini_api(llm_api_key, llm_prompt_for_question)
        
        if not q_llm_response_str: click.echo(f"LLM call for Q{i+1} failed. Skipping.", err=True); continue
        try:
            q_data = json.loads(q_llm_response_str)
            q_text = q_data.get("questionText"); expl_en = q_data.get("explanation_en"); expl_zh = q_data.get("explanation_zh_tw")
            if not (q_text and expl_en and expl_zh): click.echo(f"LLM response for Q{i+1} missing fields. Skipping.", err=True); continue
            
            rc_q_data = {
                "questionType": "READING_COMPREHENSION", "contentAssetId": selected_passage_asset.assetId,
                "difficulty": selected_passage_asset.difficulty, "learningObjectives": question_learning_objectives,
                "questionText": str(q_text), "explanation": LocalizedString(en=str(expl_en), zh_tw=str(expl_zh)),
                "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
                "choices": None, "acceptableAnswers": None
            }
            if chosen_question_type_str == "MCQ":
                choices = q_data.get("choices")
                if not isinstance(choices, list) or not choices: click.echo(f"Invalid 'choices' for MCQ Q{i+1}. Skipping.", err=True); continue
                parsed_choices = [ChoiceDetail(**c) for c in choices if isinstance(c.get("text"), str) and isinstance(c.get("isCorrect"), bool)]
                if not any(c.isCorrect for c in parsed_choices) and parsed_choices: click.echo(f"Warning: No correct choice for MCQ Q{i+1}.", err=True)
                if not parsed_choices: click.echo(f"No valid choices for MCQ Q{i+1}. Skipping.", err=True); continue
                rc_q_data["choices"] = parsed_choices
            else:
                ans = q_data.get("acceptableAnswers")
                if not isinstance(ans, list) or not all(isinstance(a,str) for a in ans) or not ans: click.echo(f"Invalid 'answers' for Text Q{i+1}. Skipping.", err=True); continue
                rc_q_data["acceptableAnswers"] = ans
            
            new_q = ReadingComprehensionQuestion(**rc_q_data); generated_questions.append(new_q)
            click.echo(f"Successfully generated Q{i + 1}: {new_q.questionText[:60]}...")
        except Exception as e: click.echo(f"Error processing Q{i+1}: {e}. Raw: {q_llm_response_str[:200]}...", err=True)

    click.echo(f"\n--- Question Generation Complete for Passage ID: {selected_passage_asset.assetId} ---")
    if generated_questions:
        click.echo(f"{len(generated_questions)} questions were generated.")
        click.echo(click.style(f"\n--- Newly Generated Questions for '{selected_passage_asset.title.en}' ---", fg="green", bold=True))
        for idx, q in enumerate(generated_questions): # Display logic copied and adapted
            click.echo(click.style(f"\nQuestion {idx + 1}:", bold=True, underline=True)); click.echo(q.questionText)
            if q.choices:
                for c_idx, choice in enumerate(q.choices):
                    prefix = click.style(f"    [{'*' if choice.isCorrect else ' '}] {chr(65 + c_idx)}. ", fg="blue" if choice.isCorrect else None)
                    click.echo(f"{prefix}{choice.text}")
            elif q.acceptableAnswers: click.echo(f"  Acceptable Answers: {click.style('; '.join(q.acceptableAnswers), fg='blue')}")
            if q.explanation: click.echo(click.style(f"  Explanation (EN): {q.explanation.en}", dim=True))
            if idx < len(generated_questions) - 1: click.echo("---")
        
        click.echo(click.style("\n--- Save Newly Generated Questions ---", fg="magenta", bold=True))
        if db and click.confirm("\nSave these new questions to the database?", default=True):
            saved_count = 0
            for q_to_save in generated_questions:
                if _save_reading_comprehension_question_to_db(db, q_to_save): saved_count += 1
            click.echo(f"{saved_count} of {len(generated_questions)} new questions saved.")
        else: click.echo("New questions not saved.")
    else: click.echo("No questions were generated for the selected passage.")
    pass

def handle_reading_comprehension_generation(db: Optional[Any], llm_api_key: Optional[str], llm_service_name: Optional[str]):
    click.echo(click.style("\n--- Reading Comprehension (閱讀測驗) ---", fg="blue", bold=True))
    if not llm_api_key: click.echo(click.style("Warning: LLM API Key not available.", fg="yellow"), err=True)

    while True:
        click.echo("\nSelect an action:")
        click.echo("1: Generate New Passage & Associated Questions")
        click.echo("2: Generate Questions for an Existing Passage")
        click.echo("3: Generate New Passage Only (No Questions)")
        click.echo("0: Return to Main Exam Generator Menu")

        choice = click.prompt("Enter your choice", type=click.Choice(['1', '2', '3', '0']), show_choices=False)

        if choice == '1': _workflow_generate_new_passage_and_questions(db, llm_api_key, llm_service_name)
        elif choice == '2': _workflow_generate_questions_for_existing_passage(db, llm_api_key, llm_service_name)
        elif choice == '3': _workflow_generate_new_passage_only(db, llm_api_key, llm_service_name)
        elif choice == '0': click.echo("Returning to the main exam generator menu..."); break
        
        if choice != '0':
            click.pause(info=click.style("\nPress any key to continue with Reading Comprehension tasks or choose '0' to exit...", dim=True))