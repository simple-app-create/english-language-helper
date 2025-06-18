# English Language Helper

This repository contains the code for an English language learning helper application.

## Firestore Admin CLI Tool

This project includes a Python command-line interface (CLI) tool located in the `cli` directory (`english-language-helper/cli/firestore_admin.py`). This tool is designed to manage data in your Firebase Firestore database with administrative privileges, allowing you to add, modify, or delete content like articles and quizzes outside of the main user application.

This is useful for populating the database with content or performing administrative tasks.

### Setup

1.  **Set up Firebase Project:**
    *   Go to the Firebase console (https://console.firebase.google.com/).
    *   Create a new Firebase project or select an existing one.
    *   Upgrade your project to the **Blaze pay-as-you-go plan**. While Firestore offers a free tier, the Admin SDK typically requires billing to be enabled for production-level usage, though initial testing within the free tier limits might work.
2.  **Create a Service Account:**
    *   In your Firebase project settings, go to "Users and Permissions" -> "Service accounts".
    *   Click "Generate new private key". This will download a JSON file containing your service account credentials. **Keep this file secure** and do not share it publicly or commit it to version control. This file grants administrative access to your project.
    *   Rename the downloaded file to something descriptive, e.g., `serviceAccountKey.json`.
3.  **Install Dependencies:**
    *   Make sure you have Python installed.
    *   Install the required Python packages (`firebase-admin` and `click`) using pip:
        ```bash
        pip install firebase-admin click
        ```

### Usage

The CLI tool requires the path to your Firebase service account key JSON file for authentication. You can provide this path using one of two methods:

1.  **Using the `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` Environment Variable (Recommended):**
    Set the environment variable before running the command. This is the most secure method as the path doesn't appear in command history.

    *   On Linux/macOS (Bash/Zsh):
        ```bash
        export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
        python english-language-helper/cli/firestore_admin.py <command> [options] [arguments]
        ```
    *   On Windows (Command Prompt):
        ```cmd
        set FIREBASE_SERVICE_ACCOUNT_KEY_PATH="C:\path\to\your\serviceAccountKey.json"
        python english-language-helper/cli/firestore_admin.py <command> [options] [arguments]
        ```
    *   On Windows (PowerShell):
        ```powershell
        $env:FIREBASE_SERVICE_ACCOUNT_KEY_PATH="C:\path\to\your\serviceAccountKey.json"
        python english-language-helper/cli/firestore_admin.py <command> [options] [arguments]
        ```

2.  **Using the `--key-path` Command-Line Option:**
    Provide the path directly as an option when you run the command.

    ```bash
    python english-language-helper/cli/firestore_admin.py --key-path "/path/to/your/serviceAccountKey.json" <command> [options] [arguments]
    ```
    ```cmd
    python english-language-helper\cli\firestore_admin.py --key-path "C:\path\to\your\serviceAccountKey.json" <command> [options] [arguments]
    ```

If neither the environment variable nor the `--key-path` option is provided, the CLI will print an error message and exit.

### Available Commands

You can view the list of available commands and their options by running the script with `--help`:

```bash
python english-language-helper/cli/firestore_admin.py --help
```

Or get help for a specific command:

```bash
python english-language-helper/cli/firestore_admin.py <command> --help
```

Currently implemented example commands:

*   `check-db-connection`: Tests if the CLI can successfully initialize the Firebase Admin SDK and perform a basic read operation on Firestore.
    ```bash
    # Using env var
    export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
    python english-language-helper/cli/firestore_admin.py check-db-connection

    # Using --key-path
    python english-language-helper/cli/firestore_admin.py --key-path "/path/to/your/serviceAccountKey.json" check-db-connection
    ```

*   `add-article <article_id> <title>`: Adds a new reading article to the `articles` collection in Firestore.
    *   `<article_id>`: A unique ID for the article (e.g., `introduction-to-ai`, `the-history-of-spices`). This will be the Firestore document ID.
    *   `<title>`: The title of the article (e.g., `"An Introduction to Artificial Intelligence"`).
    *   `--content-file <path>`: (Optional) Path to a text file containing the main content of the article. If not provided, the content field will be empty.
    *   `--level <level>`: (Required) The reading level, an integer from 1 to 18 (1 = elementary grade 1, 18 = high school senior).
    *   `--tags <tags>`: (Optional) Comma-separated tags (e.g., `history,science`).

    ```bash
    # Example: Add an article with content from a file
    python english-language-helper/cli/firestore_admin.py --key-path \"/path/to/your/serviceAccountKey.json\" add-article my-first-article \"My First Article\" --content-file path/to/article_content.txt --level 10 --tags tutorial,example
    ```

You can extend `english-language-helper/cli/firestore_admin.py` with more commands as needed for managing other data like quizzes, questions, or user information (with caution when modifying user data).