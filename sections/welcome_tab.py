# english-language-helper/sections/welcome_tab.py
"""Welcome tab module for the English Language Helper application."""
from typing import Any

import streamlit as st


def show_welcome_tab(tab: Any) -> None:
    """Display the content for the Welcome tab.

    This tab serves as the main landing page for the application,
    providing a greeting and a brief overview.

    Args:
        tab: Streamlit tab container for welcome functionality.

    Returns:
        None
    """
    with tab:
        st.header("🎉 Welcome to the Children's English Learning Companion! 🎉")
        st.subheader("您的英語學習好夥伴！") # Your English Learning Good Partner!

        st.markdown(
            """
            Hello there, young learner! 👋

            This application is designed to help you practice and improve your English skills
            in a fun and interactive way.

            **Here's what you can do:**
            *   📚 **閱讀文章 (Reading Articles):** Dive into interesting stories and articles.
            *   ✍️ **單字練習 (Vocabulary Practice):** Learn new words and test your knowledge.
            *   🎧 **聽力練習 (Listening Practice):** Sharpen your listening comprehension.
            *   ❓ **測驗 (Quizzes/Questions):** Challenge yourself with various questions.

            Navigate through the tabs above to explore each section.
            Let's start your English learning adventure!
            """
        )

        st.info("Select a tab above to begin! 🚀")