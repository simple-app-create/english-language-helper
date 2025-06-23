"""Reading tab module for the English Language Helper application."""

from typing import Any, List, Optional

import streamlit as st
from pydantic import ValidationError

# Assuming schemas.py and logger_config.py are in the project root,
# and main.py has added the project root to sys.path.
from schemas import PassageAsset, ReadingComprehensionQuestion, ChoiceDetail
from logger_config import sections_logger


# Firestore Collection Names
PASSAGE_ASSETS_COLLECTION = "passage_assets"
QUESTIONS_COLLECTION = "questions"


@st.cache_data(show_spinner="Loading passages...")
def get_passage_assets(_db: Any) -> List[PassageAsset]:
    """
    Fetches and parses passage assets from Firestore.

    Args:
        _db: Firestore client instance.

    Returns:
        A list of PassageAsset objects. Returns an empty list on failure.
    """
    if not _db:
        return []

    passages_list: List[PassageAsset] = []
    try:
        passages_ref = (
            _db.collection(PASSAGE_ASSETS_COLLECTION)
            .where("status", "==", "DRAFT")
            .stream()
        )
        for doc in passages_ref:
            try:
                passage_data = doc.to_dict()
                if passage_data:
                    # Pydantic model expects assetId, which is the doc.id in Firestore
                    passage_data["assetId"] = doc.id
                    passages_list.append(PassageAsset(**passage_data))
            except ValidationError as e:
                sections_logger.warning(f"Data validation error for passage {doc.id}: {e}", exc_info=False) # Keep False if e already has good info
                st.warning(f"Skipping a passage due to data format issue (ID: {doc.id}). See section.log for details.")
            except Exception as e:
                sections_logger.error(f"Error parsing passage document {doc.id}: {e}", exc_info=True)
                # Optionally, inform user that some data might be missing
    except Exception as e:
        sections_logger.error(f"Error fetching passages from Firestore: {e}", exc_info=True)
        st.error("Could not load reading passages. Please check section.log for details.")
        return []
    return passages_list


@st.cache_data(show_spinner="Loading questions...")
def get_questions_for_passage(
    _db: Any, passage_id: str
) -> List[ReadingComprehensionQuestion]:
    """
    Fetches and parses reading comprehension questions for a specific passage.

    Args:
        _db: Firestore client instance.
        passage_id: The ID of the passage to fetch questions for.

    Returns:
        A list of ReadingComprehensionQuestion objects. Returns an empty list on failure.
    """
    if not _db:
        return []

    questions_list: List[ReadingComprehensionQuestion] = []
    try:
        questions_ref = (
            _db.collection(QUESTIONS_COLLECTION)
            .where("contentAssetId", "==", passage_id)
            .where("questionType", "==", "READING_COMPREHENSION")
            .stream()
        )
        for doc in questions_ref:
            try:
                question_data = doc.to_dict()
                if question_data:
                    questions_list.append(ReadingComprehensionQuestion(**question_data))
            except ValidationError as e:
                sections_logger.warning(
                    f"Data validation error for question {doc.id} (passage {passage_id}): {e}", exc_info=False
                )
                st.warning(f"Skipping a question for passage {passage_id} due to data format issue (ID: {doc.id}). See section.log.")
            except Exception as e:
                sections_logger.error(
                    f"Error parsing question document {doc.id} for passage {passage_id}: {e}", exc_info=True
                )
    except Exception as e:
        sections_logger.error(
            f"Error fetching questions for passage {passage_id} from Firestore: {e}", exc_info=True
        )
        st.error(f"Could not load questions for passage {passage_id}. Please check section.log.")
        return []
    return questions_list


def show_reading_tab(tab: Any, db: Optional[Any]) -> None:
    """Display the content for the Reading Articles tab.

    Allows users to select a reading passage and view its content
    along with associated comprehension questions.

    Args:
        tab: Streamlit tab container for reading functionality.
        db: Initialized Firestore client, or None if initialization failed.

    Returns:
        None
    """
    with tab:
        st.header("📚 閱讀文章")  # Reading Articles Header

        if db is None:
            st.warning(
                "⚠️ Firestore database is not connected. Reading materials cannot be loaded."
            )
            st.info("Please ensure Firebase is correctly initialized in `main.py`.")
            return

        passage_assets = get_passage_assets(db)

        if not passage_assets:
            st.info(
                "No reading passages found or unable to load them. Check Firestore connection and data."
            )
            return

        passage_options = {passage.title.en: passage for passage in passage_assets}

        # Use session state to remember the selected passage title
        if "selected_passage_title_reading" not in st.session_state:
            st.session_state.selected_passage_title_reading = None

        # If there's only one passage, select it by default. Otherwise, prompt user.
        if len(passage_options) == 1:
            default_selection = list(passage_options.keys())[0]
        else:
            default_selection = None  # Or the first item if you prefer: list(passage_options.keys())[0] if passage_options else None

        selected_title = st.selectbox(
            "📖 Choose a passage to read:",
            options=[None]
            + list(passage_options.keys()),  # Add None for an initial empty state
            index=0,  # Default to None
            format_func=lambda x: "Select a passage..." if x is None else x,
            key="reading_passage_selector",  # Unique key for this selectbox
        )

        # Update session state when a new title is selected
        if selected_title != st.session_state.selected_passage_title_reading:
            st.session_state.selected_passage_title_reading = selected_title
            # Clear previous question answers if passage changes (if we add answer state later)
            # if 'reading_answers' in st.session_state:
            #     del st.session_state.reading_answers

        if st.session_state.selected_passage_title_reading:
            selected_passage = passage_options[
                st.session_state.selected_passage_title_reading
            ]

            st.divider()
            st.subheader(f"{selected_passage.title.en}")
            if (
                selected_passage.title.zh_tw
                and selected_passage.title.zh_tw != selected_passage.title.en
            ):
                st.caption(f"({selected_passage.title.zh_tw})")

            # Display difficulty
            difficulty = selected_passage.difficulty
            st.markdown(
                f"**Difficulty:** {difficulty.name.en} ({difficulty.name.zh_tw}) - Stage: {difficulty.stage}, Grade: {difficulty.grade}, Level: {difficulty.level}"
            )

            if selected_passage.learningObjectives:
                st.markdown(
                    f"**Learning Objectives:** {', '.join(selected_passage.learningObjectives)}"
                )

            st.markdown("---")  # Visual separator

            # Display passage content, allowing the container to auto-resize
            with st.container(border=False):  # Removed height parameter
                st.markdown(selected_passage.content)

            st.markdown("---")
            st.subheader("📝 Comprehension Questions")

            questions = get_questions_for_passage(db, selected_passage.assetId)

            if not questions:
                st.info("No comprehension questions found for this passage yet.")
            else:
                for i, q in enumerate(questions):
                    with st.container(border=True):
                        st.markdown(f"**Question {i + 1}:** {q.questionText}")

                        # Session state key for answer visibility for this specific question
                        answer_visible_key = (
                            f"reading_q_visible_{selected_passage.assetId}_{i}"
                        )
                        if answer_visible_key not in st.session_state:
                            st.session_state[answer_visible_key] = False

                        if q.choices:  # Multiple Choice Question
                            for choice_idx, choice_detail in enumerate(q.choices):
                                prefix = "◻️"  # Default prefix
                                if (
                                    st.session_state[answer_visible_key]
                                    and choice_detail.isCorrect
                                ):
                                    prefix = "✅"
                                st.markdown(
                                    f"{prefix} {chr(65 + choice_idx)}. {choice_detail.text}"
                                )

                        elif q.acceptableAnswers:  # Text Input Question
                            st.caption("This is a text input question.")
                            if st.session_state[answer_visible_key]:
                                # Show acceptable answers if "Show Answer" is active
                                st.markdown("**Acceptable Answers:**")
                                for ans in q.acceptableAnswers:
                                    st.markdown(f"- {ans}")

                        # Show/Hide Answer button
                        button_text = (
                            "Hide Answer"
                            if st.session_state[answer_visible_key]
                            else "Show Answer"
                        )
                        if st.button(
                            button_text,
                            key=f"btn_toggle_answer_{selected_passage.assetId}_{i}",
                        ):
                            st.session_state[answer_visible_key] = not st.session_state[
                                answer_visible_key
                            ]
                            st.rerun()  # Rerun to update the display immediately

                        if st.session_state[answer_visible_key] and q.explanation:
                            with st.expander(
                                "💡 Explanation", expanded=True
                            ):  # Show expanded if answer is visible
                                st.markdown(f"**English:** {q.explanation.en}")
                                if (
                                    q.explanation.zh_tw
                                    and q.explanation.zh_tw != q.explanation.en
                                ):
                                    st.markdown(f"**中文:** {q.explanation.zh_tw}")
                    st.markdown("---")  # Separator between questions
        else:
            st.info("Please select a passage from the dropdown above to start reading.")
