# english-language-helper/logger_config.py
"""
Centralized logging configuration for the English Language Helper application.

This module sets up two loggers:
1.  `main_app_logger`: For general application logs, typically used by `main.py`.
    Outputs to `app.log`.
2.  `sections_logger`: For logs specific to modules within the 'sections' directory.
    Outputs to `sections.log`.
"""
import logging
import os

# Define the log file path relative to the project root
# Assuming this file (logger_config.py) is in the project root.
# If it's moved elsewhere, adjust the path accordingly.
LOG_DIR = os.path.dirname(os.path.abspath(__file__)) # Gets the directory of logger_config.py

# --- Formatter (can be shared or defined per logger) ---
DEFAULT_LOG_FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
)

# --- Main Application Logger (for app.log) ---
APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")
main_app_logger = logging.getLogger("english_language_helper.main")
main_app_logger.setLevel(logging.INFO)
main_app_logger.propagate = False

# Add file handler for app.log if not already present
if not any(isinstance(h, logging.FileHandler) and h.baseFilename == APP_LOG_FILE for h in main_app_logger.handlers):
    app_file_handler = logging.FileHandler(APP_LOG_FILE, mode='a')
    app_file_handler.setFormatter(DEFAULT_LOG_FORMATTER)
    main_app_logger.addHandler(app_file_handler)

# --- Sections Logger (for sections.log) ---
SECTIONS_LOG_FILE = os.path.join(LOG_DIR, "sections.log") # Corrected filename from SECTION_LOG_FILE
sections_logger = logging.getLogger("english_language_helper.sections")
sections_logger.setLevel(logging.INFO)
sections_logger.propagate = False

# Add file handler for sections.log if not already present
if not any(isinstance(h, logging.FileHandler) and h.baseFilename == SECTIONS_LOG_FILE for h in sections_logger.handlers):
    sections_file_handler = logging.FileHandler(SECTIONS_LOG_FILE, mode='a') # Corrected from section_file_handler
    sections_file_handler.setFormatter(DEFAULT_LOG_FORMATTER) # Using the same formatter for consistency
    sections_logger.addHandler(sections_file_handler) # Corrected from section_file_handler

# --- Example Usage ---
# In main.py:
# from logger_config import main_app_logger
# main_app_logger.info("Application started.")

# In sections/some_tab.py:
# from ..logger_config import sections_logger # If logger_config.py is at root
# sections_logger.info("Something happened in a section.")
