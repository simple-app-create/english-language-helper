import streamlit as st

def show_saved_words_tab(tab):
    """Displays the content for the Saved Words tab."""
    with tab:
        st.header("單字練習") # Saved Words Header
        st.write("這個區塊將用於練習您儲存的單字。") # Placeholder text
        st.info("此功能正在開發中，敬請期待！") # Info box
        # --- Saved Words UI and logic will go here ---
        pass # Remove this 'pass' when adding actual content