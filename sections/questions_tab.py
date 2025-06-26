# english-language-helper/sections/questions_tab.py
"""Questions tab module for the English Language Helper application."""
from typing import Any, List, Optional, Dict, Type

import streamlit as st
from google.cloud.firestore import FieldFilter
from pydantic import ValidationError

# Absolute imports, assuming main.py has added project root to sys.path
from schemas import (
    AnyQuestionType,
    SpellingCorrectionQuestion,
    FillInTheBlankQuestion,
    QuestionBase,  # Base for type checking
    LocalizedString, # For explanations
    DifficultyDetail # For displaying difficulty
)
from logger_config import sections_logger

# Firestore Collection Name
QUESTIONS_COLLECTION = "questions"

# Map of user-friendly names to questionType strings and their Pydantic models
# Keys are in Traditional Chinese for UI display
AVAILABLE_QUESTION_TYPES: Dict[str, Dict[str, Any]] = {
    "拼字校正": {  # Spelling Correction
        "type_str": "SPELLING_CORRECTION",
        "model": SpellingCorrectionQuestion
    },
    "克漏字": {  # Fill in the Blank
        "type_str": "FILL_IN_THE_BLANK",
        "model": FillInTheBlankQuestion
    },
    # TODO: Add more types here as they are implemented
    # "翻譯練習": {"type_str": "TRANSLATION", "model": TranslationQuestion},
    # "閱讀理解": {"type_str": "READING_COMPREHENSION", "model": ReadingComprehensionQuestion}
}

# Helper function to fetch and parse questions
# Not using st.cache_data here as we want a "Fetch New Questions" button to explicitly get new sets.
def fetch_and_parse_questions(
    db: Any, question_type_str: str, model_class: Type[QuestionBase], limit: int = 3
) -> List[AnyQuestionType]:
    """
    Fetches questions of a specific type from Firestore and parses them.
    Returns a list of parsed question objects.
    """
    if not db:
        sections_logger.error("Database client not available in fetch_and_parse_questions. Returning empty list.")
        return []
    
    questions_list: List[AnyQuestionType] = []
    try:
        query = db.collection(QUESTIONS_COLLECTION) \
                  .where(filter=FieldFilter("questionType", "==", question_type_str)) \
                  .limit(limit) 
        
        docs = query.stream()

        for doc_idx, doc in enumerate(docs): 
            try:
                data = doc.to_dict()
                if data:
                    questions_list.append(model_class(**data))
            except ValidationError as ve:
                sections_logger.warning(f"Data validation error for question (Doc ID: {doc.id}, Type: {question_type_str}): {ve}. Skipping this question.", exc_info=False)
            except Exception as e:
                sections_logger.error(f"Error parsing question document {doc.id} (Type: {question_type_str}): {e}. Skipping this question.", exc_info=True)
        
        if not questions_list and limit > 0: 
             st.info(f"No questions found matching type '{question_type_str}' or failed to parse them.")

    except Exception as e:
        sections_logger.error(f"Error fetching questions of type '{question_type_str}' from Firestore: {e}", exc_info=True)
        # The UI in show_questions_tab will indicate if no questions were loaded.
        return []
    return questions_list


def display_spelling_correction_question_ui(q_obj: SpellingCorrectionQuestion, q_idx: int, q_key_prefix: str):
    """Displays UI elements for a spelling correction question."""
    st.markdown(f"**Question {q_idx + 1}:** {q_obj.questionText or 'Identify the correctly/incorrectly spelled word or correct the sentence.'}")

    if q_obj.sentenceWithMisspelledWord:
        st.markdown(f"Sentence: *\"{q_obj.sentenceWithMisspelledWord}\"*")
    elif q_obj.wordChoices:
        st.markdown("Options:")
        for i, word in enumerate(q_obj.wordChoices):
            st.markdown(f"- {word}")


def display_fill_in_the_blank_question_ui(q_obj: FillInTheBlankQuestion, q_idx: int, q_key_prefix: str):
    """Displays UI elements for a fill-in-the-blank question."""
    st.markdown(f"**Question {q_idx + 1}:** {q_obj.questionText}")


def show_questions_tab(tab: Any, db: Optional[Any]) -> None:
    """Display the content for the Questions tab.

    Allows users to select a question type, fetch a set of questions,
    and practice by showing/hiding answers.
    
    Args:
        tab: Streamlit tab container for question functionality.
        db: Initialized Firestore client, or None if initialization failed.
        
    Returns:
        None
    """
    with tab:
        # --- Error Display Logic ---
        if 'questions_tab_error_message' not in st.session_state:
            st.session_state.questions_tab_error_message = None

        if st.session_state.questions_tab_error_message:
            st.error(st.session_state.questions_tab_error_message)
            if st.button("Clear Error Message", key="q_tab_clear_error_button"):
                st.session_state.questions_tab_error_message = None
                st.rerun()

        st.header("❓ Practice Questions")

        if db is None:
            sections_logger.warning("Firestore database client is None in show_questions_tab.")
            st.warning("⚠️ Firestore database is not connected. Questions cannot be loaded.")
            st.info("Please ensure Firebase is correctly initialized in `main.py` and check app.log/section.log for details.")
            return

        # Initialize session state for this tab if not already present
        if 'questions_tab_current_questions' not in st.session_state:
            st.session_state.questions_tab_current_questions = []
        if 'questions_tab_selected_type_key' not in st.session_state: 
            st.session_state.questions_tab_selected_type_key = None
        if 'questions_tab_last_fetched_type_key' not in st.session_state:
            st.session_state.questions_tab_last_fetched_type_key = None

        try:
            # --- UI for selecting question type and fetching ---
            col1, col2 = st.columns([3, 1.2]) 
            with col1:
                selected_type_display_name = st.selectbox(
                    "選擇練習題型：",  # Translated label
                    options=[None] + list(AVAILABLE_QUESTION_TYPES.keys()), 
                    format_func=lambda x: "選擇題型..." if x is None else x,  # Translated prompt
                    key="q_tab_type_selector" 
                )
                st.session_state.questions_tab_selected_type_key = selected_type_display_name
            
            with col2:
                st.write("") 
                st.write("") 
                fetch_disabled = st.session_state.questions_tab_selected_type_key is None
                if st.button("🔄 獲取新題目", key="q_tab_fetch_new_button", disabled=fetch_disabled, use_container_width=True): # Translated button text
                    if st.session_state.questions_tab_selected_type_key:
                        type_info = AVAILABLE_QUESTION_TYPES[st.session_state.questions_tab_selected_type_key]
                        st.session_state.questions_tab_current_questions = fetch_and_parse_questions(
                            db, type_info["type_str"], type_info["model"], limit=3 
                        )
                        st.session_state.questions_tab_last_fetched_type_key = st.session_state.questions_tab_selected_type_key
                        for key_in_state in list(st.session_state.keys()):
                            if key_in_state.startswith(f"q_tab_ans_visible_{type_info['type_str']}"): # Clear answer visibility for this type
                                del st.session_state[key_in_state]
                        st.rerun() 

            st.divider()

            if st.session_state.questions_tab_selected_type_key and \
               st.session_state.questions_tab_selected_type_key == st.session_state.questions_tab_last_fetched_type_key:

                questions_to_display = st.session_state.questions_tab_current_questions
                current_type_display_name = st.session_state.questions_tab_selected_type_key
                type_info_for_display = AVAILABLE_QUESTION_TYPES[current_type_display_name]

                if not questions_to_display:
                    st.info(f"目前尚無「{current_type_display_name}」類型的題目。請稍後再嘗試獲取新題目，或確認題目是否已添加到資料庫中。")
                else:
                    st.subheader(f"Practice: {current_type_display_name}")
                    st.caption(f"Displaying {len(questions_to_display)} question(s).")

                    for q_idx, q_obj in enumerate(questions_to_display):
                        q_key_prefix = f"{type_info_for_display['type_str']}_{q_idx}"

                        with st.container(border=True):
                            if isinstance(q_obj, SpellingCorrectionQuestion):
                                display_spelling_correction_question_ui(q_obj, q_idx, q_key_prefix)
                            elif isinstance(q_obj, FillInTheBlankQuestion):
                                display_fill_in_the_blank_question_ui(q_obj, q_idx, q_key_prefix)
                            else: 
                                sections_logger.warning(f"Display UI for question type '{q_obj.questionType}' is not explicitly implemented. Using fallback.")
                                st.markdown(f"**Question {q_idx + 1}:** {getattr(q_obj, 'questionText', 'N/A')}")
                                st.caption(f"Note: Specific UI for '{q_obj.questionType}' is under development.")

                            answer_visible_key = f"q_tab_ans_visible_{q_key_prefix}"
                            if answer_visible_key not in st.session_state:
                                st.session_state[answer_visible_key] = False

                            button_text = "Hide Answer" if st.session_state[answer_visible_key] else "Show Answer"
                            if st.button(button_text, key=f"q_tab_btn_toggle_ans_{q_key_prefix}"):
                                st.session_state[answer_visible_key] = not st.session_state[answer_visible_key]
                                st.rerun()

                            if st.session_state[answer_visible_key]:
                                st.markdown("---") 
                                st.markdown("**Correct Answer(s):**")
                                
                                answer_displayed = False
                                if isinstance(q_obj, SpellingCorrectionQuestion):
                                    if q_obj.correctWord:
                                        st.success(f"➡️ {q_obj.correctWord}")
                                        answer_displayed = True
                                elif isinstance(q_obj, FillInTheBlankQuestion):
                                    if q_obj.acceptableAnswers:
                                        for blank_idx, answers_for_blank in enumerate(q_obj.acceptableAnswers):
                                            st.write(f"Blank {blank_idx + 1}: **{', '.join(answers_for_blank)}**")
                                        answer_displayed = True
                                
                                if not answer_displayed:
                                    sections_logger.info(f"Answer display format for question type '{q_obj.questionType}' not specifically handled. Question object (first 100 chars): {str(q_obj)[:100]}")
                                    st.info("Answer format for this question type not fully specified for display.")

                                if q_obj.explanation and (q_obj.explanation.en or q_obj.explanation.zh_tw):
                                     with st.expander("💡 Explanation", expanded=True):
                                        if q_obj.explanation.en:
                                            st.markdown(f"**English:** {q_obj.explanation.en}")
                                        if q_obj.explanation.zh_tw and q_obj.explanation.zh_tw != q_obj.explanation.en:
                                             st.markdown(f"**中文:** {q_obj.explanation.zh_tw}")
                                elif hasattr(q_obj, 'explanation') and q_obj.explanation is None: 
                                     st.caption("No explanation provided for this question.")
                        
                        st.markdown("---") 
            
            elif st.session_state.questions_tab_selected_type_key:
                st.info(f"請點擊「🔄 獲取新題目」來載入「{st.session_state.questions_tab_selected_type_key}」的練習題。") 
            else:
                st.info("請從上面的下拉選單中選擇一個題型開始練習。") 
            
        except Exception as e:
            sections_logger.error("Unhandled error occurred in Questions Tab UI", exc_info=True)
            st.session_state.questions_tab_error_message = (
                f"An unexpected error occurred: {str(e)}. "
                "Please check section.log for more details or try fetching new questions."
            )
            # Temporarily commenting out st.rerun() here to make errors more sticky in the UI.
            # The error will display on the next natural user interaction or script run.
            # if "running_in_streamlit" not in st.session_state or not st.session_state.running_in_streamlit: # Simple guard
            #      st.session_state.running_in_streamlit = True # Mark that we are trying a rerun
            #      st.rerun()

        # TODO: Implement user input fields for answers.
        # TODO: Implement grading logic.
        # TODO: Consider pagination or "load more" for questions.