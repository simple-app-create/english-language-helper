"""Listening tab module for the English Language Helper application."""
from typing import Any

import streamlit as st


def show_listening_tab(tab: Any) -> None:
    """Display the content for the Listening Practice tab.
    
    Args:
        tab: Streamlit tab container for listening functionality
        
    Returns:
        None
    """
    with tab:
        st.header("聽力練習")  # Listening Practice Header
        st.write("這個區塊將用於聽力練習活動。")  # This section will be used for listening practice activities.
        st.info("此功能正在開發中，敬請期待！")  # This feature is currently under development, please look forward to it!
        
        # TODO: Add listening practice UI and logic