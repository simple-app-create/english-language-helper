import streamlit as st
from sections import reading_tab, saved_words_tab, quizzes_tab, listening_tab

st.title("兒童英語閱讀輔助程式") # App Title in Traditional Chinese

# Define the tab labels in Traditional Chinese
tab_labels = ["閱讀文章", "單字練習", "聽力練習", "測驗"] # Added "Listening Activity"

# Create the tabs
tab_reading, tab_saved_words, tab_listening, tab_quizzes = st.tabs(tab_labels) # Added tab_listening

# Call functions from separate files to display tab content
reading_tab.show_reading_tab(tab_reading)
saved_words_tab.show_saved_words_tab(tab_saved_words)
listening_tab.show_listening_tab(tab_listening) # Added call for listening tab
quizzes_tab.show_quizzes_tab(tab_quizzes)

# Optional: Add some common footer or sidebar content if needed
# st.sidebar.write("設定選項放在這裡") # Settings options go here