import streamlit as st
import random
import json
from pydantic import ValidationError
from logger_config import sections_logger  # Import sections_logger
from schemas import (
    GeneratedReadingMaterial,
    AnyQuestionType,
)  # Import the Pydantic model
from .reading_comp_generator import (
    generate_combined_passage_and_questions_prompt,
    TOPIC_LIST,
    DIFFICULTY_LIST,
    call_gemini_llm,  # Assuming this might be needed or used by the generate function
)


def show_genai_tab(tab):  # Add tab argument
    # st.title("Reading Comprehension Passage & Question Generator") # Removed, title handled by main app/tab name
    sections_logger.info("GenAI Reading Tab loaded.")

    # Initialize session state for the main data if it doesn't exist
    if "validated_reading_material" not in st.session_state:
        st.session_state.validated_reading_material = None

    with tab.expander("Configure Content Generation", expanded=True):
        # 1. Topic Input
        use_random_topic = st.checkbox("Choose a random topic for me", value=False)

        custom_topic = ""
        selected_topic = None

        if use_random_topic:
            if TOPIC_LIST:
                selected_topic = random.choice(TOPIC_LIST)
                st.write(f"Randomly selected topic: **{selected_topic}**")
            else:
                st.warning(
                    "TOPIC_LIST is empty. Please provide a topic manually or update the list."
                )
                selected_topic = "General Knowledge"  # Fallback
        else:
            custom_topic = st.text_input(
                "Enter a Topic (e.g., 'Space Exploration', 'Ancient Civilizations'):"
            )
            if custom_topic:
                selected_topic = custom_topic

        # 2. Difficulty Level Selection
        if not DIFFICULTY_LIST:
            st.error(
                "DIFFICULTY_LIST is not defined or empty. Please check `reading_comp_generator.py`."
            )
            difficulty_options = ["Default Difficulty"]  # Fallback
        else:
            difficulty_options = DIFFICULTY_LIST

        selected_difficulty = st.selectbox(
            "Choose a difficulty level:",
            options=difficulty_options,
            index=0,  # Default to the first item
        )

        # 3. Generate Button
        if st.button("Generate Passage and Questions"):
            # Clear previous state before generating new content
            st.session_state.validated_reading_material = None
            keys_to_delete_from_session = []
            # Iterate over a copy of keys for safe deletion if modifying session_state directly
            # or collect keys and delete after loop.
            for key_in_session in list(st.session_state.keys()): 
                if key_in_session.startswith("q"):
                    if key_in_session.endswith("_answer_visible") or \
                       key_in_session.endswith("_user_selected_idx") or \
                       key_in_session.endswith("_radio_widget_internal_key"): # Key used by st.radio
                        keys_to_delete_from_session.append(key_in_session)
            
            for key_to_del in keys_to_delete_from_session:
                if key_to_del in st.session_state: # Ensure key exists before deleting
                    del st.session_state[key_to_del]

            if not selected_topic:
                tab.error(
                    "Please enter a topic or select the 'Choose a random topic for me' option."
                )
                sections_logger.warning(
                    "Generation attempted without a selected topic."
                )
            elif not selected_difficulty:
                tab.error("Please select a difficulty level.")
                sections_logger.warning(
                    "Generation attempted without a selected difficulty."
                )
            else:
                with st.spinner(
                    f"Generating reading material on '{selected_topic}' at '{selected_difficulty}' level..."
                ):  # st.spinner is fine, it's global
                    try:
                        # Assuming generate_combined_passage_and_questions_prompt returns the prompt string
                        # And then we need to call the LLM with this prompt
                        prompt_text = generate_combined_passage_and_questions_prompt(
                            topic=selected_topic,
                            difficulty_description=selected_difficulty,
                        )

                        if not prompt_text:
                            tab.error("Failed to generate the prompt content.")
                            sections_logger.error("Prompt generation failed.")
                        else:
                            # Call the LLM
                            response_content = call_gemini_llm(
                                prompt_text
                            )  # or whatever model call function is appropriate

                            if response_content:
                                try:
                                    # Validate and parse the JSON response using the Pydantic model
                                    validated_data = (
                                        GeneratedReadingMaterial.model_validate_json(
                                            response_content
                                        )
                                    )
                                    st.session_state.validated_reading_material = (
                                        validated_data
                                    )
                                    sections_logger.info(
                                        f"Successfully generated and validated content for topic: '{selected_topic}'."
                                    )

                                except ValidationError as e:
                                    st.session_state.validated_reading_material = (
                                        None  # Ensure it's None on error
                                    )
                                    sections_logger.error(
                                        f"Data validation error for topic '{selected_topic}': {e}",
                                        exc_info=True,
                                    )
                                    tab.error(
                                        "There was an issue with the format of the generated content. Please try again."
                                    )
                                    tab.expander("See validation error details").json(
                                        e.errors()
                                    )

                                except json.JSONDecodeError as e:
                                    st.session_state.validated_reading_material = (
                                        None  # Ensure it's None on error
                                    )
                                    sections_logger.error(
                                        f"Invalid JSON response for topic '{selected_topic}': {e}",
                                        exc_info=True,
                                    )
                                    tab.error(
                                        "The generated content was not valid JSON. Please try again."
                                    )
                                    # tab.text_area("Raw invalid response", response_content, height=150) # Optional: show raw response
                            else:  # if not response_content
                                st.session_state.validated_reading_material = None
                                tab.error(
                                    "Failed to get a response from the language model."
                                )
                                sections_logger.error(
                                    "LLM call failed to return content for topic: '{selected_topic}'."
                                )
                    except Exception as e:
                        st.session_state.validated_reading_material = (
                            None  # Ensure it's None on major error
                        )
                        tab.error(f"An error occurred during generation: {e}")
                        sections_logger.error(
                            f"Exception during generation: {e}", exc_info=True
                        )
                        tab.error(
                            "Please ensure that the `generate_combined_passage_and_questions_prompt` and `call_gemini_llm` functions are working correctly and that any necessary API keys (e.g., for Gemini) are configured."
                        )

    # --- Display Passage and Questions if data exists in session state ---
    current_material = st.session_state.get("validated_reading_material")
    if current_material:
        # Access data using Pydantic model attributes
        passage_title_display = (
            current_material.passageAsset.title.zh_tw
            if current_material.passageAsset.title.zh_tw
            else current_material.passageAsset.title.en
        )

        tab.subheader(passage_title_display)
        tab.markdown(current_material.passageAsset.content)

        sections_logger.info(
            f"Displaying passage for topic: '{current_material.passageAsset.source if current_material.passageAsset.source else 'Unknown'}'. (Note: topic from sidebar might differ if regenerated)"
        )

        # --- Display Questions Interactively ---
        if current_material.questions_list:
            tab.markdown("---")  # Separator before questions
            tab.subheader("Comprehension Questions")

            for q_idx, question in enumerate(current_material.questions_list):
                question_key_prefix = f"q{q_idx}"

                # Display question text
                tab.markdown(f"**Question {q_idx + 1}:** {question.questionText}")

                if question.choices:
                    answer_visible_key = f"{question_key_prefix}_answer_visible"
                    # Key to store the index of the user's selected choice
                    user_selected_idx_key = f"{question_key_prefix}_user_selected_idx" 

                    # Initialize session states if not present
                    if answer_visible_key not in st.session_state:
                        st.session_state[answer_visible_key] = False
                    if user_selected_idx_key not in st.session_state:
                        st.session_state[user_selected_idx_key] = None # Will store the index (0, 1, 2...) of the choice

                    if st.session_state[answer_visible_key]:
                        # Display choices with feedback (✅, ❌, ◻️)
                        tab.markdown("**Choices:**")
                        user_choice_idx_val = st.session_state.get(user_selected_idx_key) # This is the index of user's choice e.g. 0, 1, ..
                        
                        for choice_idx, choice_item in enumerate(question.choices):
                            prefix = "◻️"  # Default marker
                            choice_label = chr(65 + choice_idx) # A, B, C...

                            if choice_item.isCorrect:
                                prefix = "✅"
                            elif user_choice_idx_val == choice_idx: # User selected this choice, and it's not correct (covered by above)
                                prefix = "❌"
                            
                            tab.markdown(f"{prefix} {choice_label}. {choice_item.text}")
                    else:
                        # Display radio buttons for answer selection
                        tab.markdown("**Choices:**")
                        
                        choice_indices_options = list(range(len(question.choices))) # Options for radio [0, 1, 2...]

                        def format_func_for_radio(idx_param):
                            return f"{chr(65 + idx_param)}. {question.choices[idx_param].text}"

                        current_selected_value = st.session_state.get(user_selected_idx_key)
                        
                        radio_preselection_index = None
                        if current_selected_value is not None and current_selected_value in choice_indices_options:
                            radio_preselection_index = current_selected_value # Since options are [0,1,2..], value is its own index in options

                        # st.radio returns the selected option's value (which is an index in our case)
                        # This value is stored in our session state key.
                        st.session_state[user_selected_idx_key] = tab.radio(
                            label="Select your answer:", # Label for the radio group, can be hidden with label_visibility
                            options=choice_indices_options, 
                            format_func=format_func_for_radio,
                            index=radio_preselection_index, 
                            key=f"{question_key_prefix}_radio_widget_internal_key" # Unique key for Streamlit's internal widget state
                        )

                    tab.write("")  # Adds a little space

                    # Button to toggle answer visibility
                    button_text = (
                        "Hide Answer & Explanation"
                        if st.session_state[answer_visible_key]
                        else "View Answer & Explanation"
                    )

                    if tab.button(
                        button_text,
                        key=f"{question_key_prefix}_view_answer_btn",
                    ):
                        st.session_state[answer_visible_key] = not st.session_state[
                            answer_visible_key
                        ]
                        # Re-run will occur, displaying either radio or feedback text.

                    # Display correct answer text and explanation if visible
                    if st.session_state[answer_visible_key]:
                        correct_answer_text_display = ""
                        correct_answer_label_display = ""
                        for idx, choice_item_for_answer in enumerate(question.choices):
                            if choice_item_for_answer.isCorrect:
                                correct_answer_label_display = chr(65 + idx)
                                correct_answer_text_display = choice_item_for_answer.text
                                break
                        
                        if correct_answer_text_display:
                            tab.success(f"**Correct Answer:** {correct_answer_label_display}. {correct_answer_text_display}")
                        else:
                            tab.warning("Correct answer not found in choices.") 

                        if question.explanation:
                            explanation_display = (
                                question.explanation.zh_tw
                                if question.explanation.zh_tw
                                else question.explanation.en
                            )
                            if explanation_display:
                                tab.info(f"**Explanation:** {explanation_display}")
                else:
                    # Handling for questions without choices
                    answer_visible_key = f"{question_key_prefix}_answer_visible"
                    if answer_visible_key not in st.session_state:
                        st.session_state[answer_visible_key] = False

                    button_text = (
                        "Hide Explanation"
                        if st.session_state[answer_visible_key]
                        else "View Explanation"
                    )
                    if tab.button(
                        button_text,
                        key=f"{question_key_prefix}_view_explanation_btn",
                    ):
                        st.session_state[answer_visible_key] = not st.session_state[
                            answer_visible_key
                        ]

                    if st.session_state[answer_visible_key] and question.explanation:
                        explanation_display = (
                            question.explanation.zh_tw
                            if question.explanation.zh_tw
                            else question.explanation.en
                        )
                        if explanation_display:
                            tab.info(f"**Explanation:** {explanation_display}")
                    elif st.session_state[answer_visible_key]:
                        tab.markdown("_No explanation provided for this question._")
                tab.markdown("---")  # Separator between questions
        else:
            sections_logger.info(
                "No questions found in current material from session state."
            )
    elif st.session_state.get(
        "generation_attempted", False
    ):  # Only show if a generation was tried
        # This part might be optional; if generation fails, errors are already shown.
        # Could add a placeholder like: tab.info("Generate content using the sidebar options.")
        pass


if __name__ == "__main__":
    # This check is useful if you want to run this script directly
    # For a multi-page app, Streamlit handles the routing.
    # We will assume this is part of a larger Streamlit app structure where `create_ui` is called.
    # If this file is meant to be run standalone for testing:
    # create_ui()
    pass
