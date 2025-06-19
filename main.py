"""Main entry point for the English Language Helper Streamlit application."""

import streamlit as st
from sections import reading_tab, saved_words_tab, quizzes_tab, listening_tab


def main() -> None:
    """Initialize and run the English Language Helper application.
    
    Sets up the Streamlit interface with tabbed navigation for different
    learning activities including reading, vocabulary, listening, and quizzes.
    """
    st.title("兒童英語閱讀輔助程式")  # App Title in Traditional Chinese

    # Define the tab labels in Traditional Chinese
    tab_labels: list[str] = ["閱讀文章", "單字練習", "聽力練習", "測驗"]

    # Create the tabs
    tab_reading, tab_saved_words, tab_listening, tab_quizzes = st.tabs(tab_labels)

    # Call functions from separate files to display tab content
    reading_tab.show_reading_tab(tab_reading)
    saved_words_tab.show_saved_words_tab(tab_saved_words)
    listening_tab.show_listening_tab(tab_listening)
    quizzes_tab.show_quizzes_tab(tab_quizzes)


if __name__ == "__main__":
    main()