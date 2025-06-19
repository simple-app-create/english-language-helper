import click
from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR
from firebase_admin import firestore
import json
import os # For API key env vars potentially
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError # For specific exceptions
from openai.types.chat import ChatCompletionMessageParam # Import for explicit typing

# Pydantic for LLM output validation
from pydantic import BaseModel, ValidationError, Field
from typing import List, Annotated # For type hinting if needed

# Add specific imports for Gemini
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions # For more specific error handling

# --- Pydantic Model for LLM Output Validation ---
class ChoiceItem(BaseModel):
    id: Annotated[str, Field(min_length=1, pattern=r"^[A-Z0-9]+$")] # Simple IDs like "A", "B", "1"
    text: Annotated[str, Field(min_length=1)]

class ComprehensionQuestionItem(BaseModel):
    question: Annotated[str, Field(min_length=1)]
    choices: Annotated[List[ChoiceItem], Field(min_items=2, max_items=4)] # 2-4 choices per question
    correct_choice_id: Annotated[str, Field(min_length=1)] # Must match an id in its 'choices'

class LLMArticleOutput(BaseModel):
    title: Annotated[str, Field(min_length=1)]  # Title must not be empty
    content: Annotated[str, Field(min_length=1)] # Content must not be empty
    # Tags can be an empty list, but if tags exist, they must be non-empty strings.
    tags: Annotated[List[Annotated[str, Field(min_length=1)]], Field(min_length=0)]
    comprehension_questions: Annotated[List[ComprehensionQuestionItem], Field(min_items=0, max_items=5)] | None = None # Optional, 0-5 questions

# --- LLM Configuration & System Prompt ---
LLM_SYSTEM_PROMPT = """\
You are an expert content creator and linguist specializing in crafting clear, engaging, and educational articles for English language learners. Your goal is to generate an article based on a given topic and target reading level.

**Instructions:**
1.  **Target Audience:** The article is for English language learners at the specified reading level. Use vocabulary, sentence structures, and concepts appropriate for this level.
2.  **Content:** The article should be informative, well-structured, and factually accurate. It needs an introduction, body, and conclusion.
3.  **Output Format:** YOU MUST PROVIDE YOUR RESPONSE STRICTLY AS A VALID JSON OBJECT with the following keys:
    *   `\"title\"` (string): A concise and engaging title for the article.
    *   `\"content\"` (string): The full text of the article. Paragraphs MUST be separated by a double newline character (`\\n\\n`).
    *   `\"tags\"` (array of strings): A list of 3-5 relevant lowercase keywords. Include the main topic.
    *   `\"comprehension_questions\"` (array of objects, optional): A list of 2-3 multiple-choice comprehension questions based on the article content. If you cannot generate relevant questions, you may omit this field or provide an empty list. Each object in the array MUST strictly adhere to the following structure:
        *   `\"question\"` (string): The text of the multiple-choice question.
        *   `\"choices\"` (array of objects): A list of 2 to 4 answer choices. Each choice object MUST contain:
            *   `\"id\"` (string): A unique identifier for the choice (e.g., "A", "B", "C", "D").
            *   `\"text\"` (string): The text content of the answer choice.
        *   `\"correct_choice_id\"` (string): The "id" (from the "choices" list) that represents the correct answer.
        Example of a single question object within the "comprehension_questions" array:
        {
          "question": "What is the main topic discussed in the article?",
          "choices": [
            {"id": "A", "text": "The history of space exploration."},
            {"id": "B", "text": "The impact of climate change."},
            {"id": "C", "text": "The benefits of regular exercise."}
          ],
          "correct_choice_id": "B"
        }

**Input Variables (will be provided in the user prompt):**
*   `topic`: The subject of the article.
*   `level_name`: The descriptive name of the target reading level.

**Your Task:**
Generate the article based on the provided topic and level_name, returning it in the specified JSON format.
"""

RANDOM_TOPIC_SYSTEM_PROMPT = """
You are an assistant that generates creative and suitable article topics.
Your task is to provide a single, specific, and engaging topic title for an article aimed at English Language art students.
The topic should be interesting and relevant to their studies, focusing on aspects of English language, literature, art, science, technology, cultures, natures, Taiwan, geography, geology, and world history from an English learner's perspective.
Return ONLY the topic title as a plain string, without any quotation marks, labels (e.g., "Topic:"), or additional text.
Example of good output: The Symbolism of Colors in Shakespeare's Plays
Example of bad output: "Topic: The Symbolism of Colors in Shakespeare's Plays"
Example of bad output: Here is a topic for you: The Symbolism of Colors in Shakespeare's Plays
"""

# --- Unified LLM Request Function ---
def _perform_llm_request(
    provider: str,
    model_name_option: str | None,
    llm_api_key_option: str | None,
    llm_base_url_option: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    request_json_response: bool
) -> str | None:
    """
    Core function to interact with the specified LLM provider.
    Returns the raw text response from the LLM or None if an error occurs.
    """
    click.echo(click.style(f"  Preparing LLM request for {provider.upper()}...", fg="blue"))
    llm_response_text: str | None = None

    try:
        if provider == 'openai':
            current_api_key = llm_api_key_option or os.environ.get("OPENAI_API_KEY")
            if not current_api_key:
                click.echo(click.style("OpenAI API key not found. Set OPENAI_API_KEY or use --llm-api-key.", fg="red"), err=True)
                return None

            client = OpenAI(api_key=current_api_key, base_url=llm_base_url_option) # base_url will be None for official OpenAI
            effective_model = model_name_option or "gpt-3.5-turbo"
            click.echo(f"  Using OpenAI model: {effective_model} (Base URL: {llm_base_url_option or 'default'})")

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response_format_arg = {"type": "json_object"} if request_json_response else None

            response = client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=temperature,
                response_format=response_format_arg
            )
            llm_response_text = response.choices[0].message.content

        elif provider == 'gemini':
            current_api_key = llm_api_key_option or os.environ.get("GOOGLE_API_KEY")
            if not current_api_key:
                click.echo(click.style("Google API key not found. Set GOOGLE_API_KEY or use --llm-api-key.", fg="red"), err=True)
                return None

            genai.configure(api_key=current_api_key)
            effective_model = model_name_option or "gemini-1.5-flash-latest"
            click.echo(f"  Using Gemini model: {effective_model}")

            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if request_json_response else "text/plain"
            )
            model_instance = genai.GenerativeModel(
                model_name=effective_model,
                system_instruction=system_prompt,
                generation_config=generation_config
            )
            response = model_instance.generate_content(user_prompt)
            llm_response_text = response.text

        elif provider == 'lmstudio' or provider == 'ollama':
            effective_base_url = llm_base_url_option
            if not effective_base_url:
                default_port = 1234 if provider == 'lmstudio' else 11434
                effective_base_url = f"http://localhost:{default_port}/v1"
                click.echo(click.style(f"No base URL provided for {provider}, defaulting to {effective_base_url}", fg="yellow"))

            # API key for local LLMs is usually optional or "not-needed"
            client = OpenAI(base_url=effective_base_url, api_key=llm_api_key_option or "not-needed")
            effective_model = model_name_option

            if not effective_model:
                try:
                    click.echo(click.style(f"No model specified for {provider}, attempting to use first available model...", fg="yellow"))
                    models_response = client.models.list()
                    if models_response.data:
                        effective_model = models_response.data[0].id
                        click.echo(click.style(f"Using first available model for {provider}: {effective_model}", fg="yellow"))
                    else:
                        click.echo(click.style(f"No model specified and no models found for {provider} at {effective_base_url}. Ensure server is running and a model is loaded/available.", fg="red"), err=True)
                        return None
                except Exception as e:
                    click.echo(click.style(f"Error fetching models for {provider} (is server running/configured?): {e}", fg="red"), err=True)
                    return None

            click.echo(f"  Using {provider} model: {effective_model} via {effective_base_url}")
            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response_format_arg = {"type": "json_object"} if request_json_response else None

            response = client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=temperature,
                response_format=response_format_arg
            )
            llm_response_text = response.choices[0].message.content
        else:
            click.echo(click.style(f"Provider '{provider}' is not supported by _perform_llm_request.", fg="red"), err=True)
            return None

        if not llm_response_text or not llm_response_text.strip():
            click.echo(click.style(f"LLM ({provider.upper()}) returned empty or whitespace-only content.", fg="red"), err=True)
            return None

        click.echo(click.style(f"LLM ({provider.upper()}) raw response received.", fg="green"))
        return llm_response_text.strip()

    except ImportError as ie:
        if 'openai' in str(ie).lower() and provider in ['openai', 'lmstudio', 'ollama']:
            click.echo(click.style(f"OpenAI SDK not installed. Please install it: pip install openai", fg="red"), err=True)
        elif 'google.generativeai' in str(ie).lower() and provider == 'gemini':
            click.echo(click.style(f"Google Generative AI SDK not installed. Please install it: pip install google-generativeai", fg="red"), err=True)
        else:
            click.echo(click.style(f"Import error for {provider}: {ie}", fg="red"), err=True)
        return None
    except APIConnectionError as e: # OpenAI specific or compatible
        click.echo(click.style(f"  {provider.upper()} API Connection Error: {e}", fg="red"), err=True)
        return None
    except RateLimitError as e: # OpenAI specific or compatible
        click.echo(click.style(f"  {provider.upper()} API Rate Limit Exceeded: {e}", fg="red"), err=True)
        return None
    except APIStatusError as e: # OpenAI specific or compatible
        click.echo(click.style(f"  {provider.upper()} API Status Error (code {e.status_code}): {e.message}", fg="red"), err=True)
        return None
    except google_exceptions.GoogleAPIError as e: # Gemini specific
        click.echo(click.style(f"  Google Gemini API Error: {e}", fg="red"), err=True)
        return None
    except Exception as e:
        click.echo(click.style(f"  An unexpected error occurred during LLM request with {provider.upper()}: {e}", fg="red"), err=True)
        # For more detailed debugging:
        # import traceback
        # click.echo(traceback.format_exc(), err=True)
        return None

# --- Core LLM Generation Logic ---
def _generate_article_from_llm(provider, model_name_option, llm_api_key_option, llm_base_url_option, topic, level_name_for_prompt):
    """
    Generates article content (title, content, tags) using the specified LLM provider.
    Returns a dictionary like {"title": ..., "content": ..., "tags": ...} or None if generation fails.
    """
    click.echo(f"\nAttempting to generate article using {provider.upper()} for topic '{topic}' at level '{level_name_for_prompt}'.")
    user_prompt = f"Generate an article on the topic '{topic}' for the '{level_name_for_prompt}' reading level."

    raw_llm_text_response = _perform_llm_request(
        provider=provider,
        model_name_option=model_name_option,
        llm_api_key_option=llm_api_key_option,
        llm_base_url_option=llm_base_url_option,
        system_prompt=LLM_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7,  # Default temperature for article generation
        request_json_response=True
    )

    if not raw_llm_text_response:
        click.echo(click.style(f"LLM ({provider.upper()}) did not return any text content for article generation.", fg="red"), err=True)
        return None

    try:
        raw_llm_output = json.loads(raw_llm_text_response)
        validated_data = LLMArticleOutput(**raw_llm_output)
        click.echo(click.style(f"LLM ({provider.upper()}) article content generated and validated successfully.", fg="green"))
        return validated_data.model_dump()
    except json.JSONDecodeError as e:
        click.echo(click.style(f"  Error decoding JSON response from LLM ({provider.upper()}) for article: {e}.", fg="red"), err=True)
        click.echo(click.style(f"  Raw LLM response was: {raw_llm_text_response}", fg="red"), err=True)
        return None
    except ValidationError as e:
        click.echo(click.style(f"  LLM ({provider.upper()}) article response failed Pydantic validation: {e}", fg="red"), err=True)
        click.echo(click.style(f"  Raw LLM response causing validation error: {raw_llm_text_response}", fg="red"), err=True)
        return None
    except Exception as e: # Catch-all for unexpected issues during parsing/validation
        click.echo(click.style(f"  Unexpected error processing LLM article response from {provider.upper()}: {e}", fg="red"), err=True)
        return None

# --- Firestore Helper ---
def _get_level_details(firestore_db, level_order_num):
    """Fetches levelId and nameEnglish from Firestore based on level_order."""
    if not firestore_db: return None, None # Should not happen if pre-checked
    try:
        levels_query = firestore_db.collection('levels').where('order', '==', level_order_num).limit(1)
        level_docs = list(levels_query.stream()) # Execute the query
        if not level_docs:
            click.echo(f"Error: No level found in 'levels' collection with order = {level_order_num}. Please ensure a level with this order exists.", err=True)
            return None, None

        level_doc = level_docs[0] # Get the first document
        level_id = level_doc.id
        level_name_english = level_doc.get('nameEnglish') or f"Level Order {level_order_num}" # Default if nameEnglish is missing or empty
        click.echo(f"Using levelId: '{level_id}' (Name: '{level_name_english}') for order {level_order_num}.")
        return level_id, level_name_english
    except Exception as e:
        click.echo(f"Error querying 'levels' collection: {e}", err=True)
        return None, None

def _generate_random_topic_with_llm(provider, model_name_option, llm_api_key_option, llm_base_url_option):
    """
    Generates a random topic string using the specified LLM provider.
    Returns the topic string or None if generation fails.
    """
    click.echo(click.style(f"\nAttempting to generate a random topic using {provider.upper()}...", fg="cyan"))
    user_prompt = "Generate a random topic suitable for English Language art students, focusing on language, literature, or art."

    raw_topic_text = _perform_llm_request(
        provider=provider,
        model_name_option=model_name_option,
        llm_api_key_option=llm_api_key_option,
        llm_base_url_option=llm_base_url_option,
        system_prompt=RANDOM_TOPIC_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8,
        request_json_response=False # Expecting plain text for topic
    )

    if not raw_topic_text:
        click.echo(click.style(f"LLM ({provider.upper()}) did not return any text content for topic generation.", fg="red"), err=True)
        return None

    try:
        # Clean up potential quotation marks or "Topic:" prefixes from the LLM response
        cleaned_topic_text = raw_topic_text.strip('\"\'').replace("Topic:", "").replace("topic:", "").strip()

        if not cleaned_topic_text: # If stripping made it empty
            click.echo(click.style(f"LLM ({provider.upper()}) returned an empty topic after cleaning. Original: '{raw_topic_text}'", fg="red"), err=True)
            return None

        click.echo(click.style(f"LLM ({provider.upper()}) suggested topic: \"{cleaned_topic_text}\"", fg="green"))
        return cleaned_topic_text
    except Exception as e: # Should be unlikely here unless raw_topic_text is not a string, or an issue with strip/replace
        click.echo(click.style(f"Error cleaning topic from {provider.upper()}: {e}. Original text: '{raw_topic_text}'", fg="red"), err=True)
        return None

# --- Click Command ---
@click.command()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to Firebase service account key JSON file. Can also be set via {SERVICE_ACCOUNT_KEY_ENV_VAR} env var.'
)
@click.option(
    '--topic',
    type=str,
    required=False, # Changed from True
    default=None,   # Explicitly set default to None
    help='The topic for the article to be generated. If not provided, a random topic will be generated.'
)
@click.option(
    '--level-order',
    type=click.IntRange(min=1),
    required=True,
    help='The target reading level order (e.g., 1, 2, 3) to map to a levelId from the "levels" collection.'
)
@click.option(
    '--provider',
    type=click.Choice(['openai', 'gemini', 'lmstudio', 'ollama'], case_sensitive=False),
    required=False,
    default='gemini',
    help='The LLM provider to use for article generation. Defaults to gemini.'
)
@click.option(
    '--model',
    'model_name_option', # Use a different internal name to avoid conflict with 'model' in LLM calls
    type=str,
    help='(Optional) Specific model name for the chosen LLM provider (e.g., "gpt-4", "gemini-1.5-pro-latest").'
)
@click.option(
    '--llm-api-key',
    'llm_api_key_option',
    type=str,
    # Attempt to read from common env vars if not provided. Click doesn't directly support multiple envvars for one option.
    # We will handle os.environ.get() inside _generate_article_from_llm
    help='API key for the LLM provider (OpenAI, Gemini). If not set, checks OPENAI_API_KEY or GOOGLE_API_KEY env vars.'
)
@click.option(
    '--llm-base-url',
    'llm_base_url_option',
    type=str,
    help='(Optional) Base URL for local LLM providers like LMStudio (e.g. http://localhost:1234/v1) or Ollama with OpenAI compatibility.'
)
def generate_article(key_path, topic, level_order, provider, model_name_option, llm_api_key_option, llm_base_url_option):
    """
    Generates a new article using a specified LLM based on topic and level order,
    then adds it to the 'articles' collection in Firestore.
    """
    # 1. Initialize Firestore Client
    firestore_db = get_firestore_client(key_path)
    if firestore_db is None:
        click.echo("Failed to initialize Firestore client. Aborting.", err=True)
        exit(1)

    # 2. Get Level Details from Firestore
    level_id, level_name_english = _get_level_details(firestore_db, level_order)
    if not level_id:
        # Error message already printed by _get_level_details
        exit(1)

    # 3. Handle Topic (Provided or Generated)
    if topic is None:
        click.echo(click.style("\nNo topic provided. Attempting to generate a random topic...", fg="cyan"))
        generated_topic = _generate_random_topic_with_llm(
            provider=provider, # Use the same provider specified for article generation
            model_name_option=model_name_option,
            llm_api_key_option=llm_api_key_option,
            llm_base_url_option=llm_base_url_option
        )
        if not generated_topic:
            click.echo(click.style("Failed to generate a random topic. Exiting.", fg="red"), err=True)
            exit(1)
        topic = generated_topic # Assign the generated topic
        click.echo(click.style(f"Successfully generated topic: \"{topic}\"", fg="green"))
    else:
        click.echo(click.style(f"\\nUsing provided topic: \"{topic}\"", fg="cyan"))

    # 4. Generate Article Content using LLM
    llm_generated_data = _generate_article_from_llm(
        provider=provider,
        model_name_option=model_name_option,
        llm_api_key_option=llm_api_key_option,
        llm_base_url_option=llm_base_url_option,
        topic=topic,
        level_name_for_prompt=level_name_english
    )

    if llm_generated_data is None:
        click.echo("Failed to generate article content from LLM. Aborting.", err=True)
        exit(1)

    # 5. Prepare data for Firestore, using the LLM's output
    click.echo("\nPreparing article data for Firestore...")
    article_title = llm_generated_data.get("title", f"Untitled Article on {topic}")
    article_content = llm_generated_data.get("content", f"Content for {topic} is missing.")
    article_tags_from_llm = llm_generated_data.get("tags", [])

    # Process comprehension questions (now expecting multiple-choice structure)
    llm_comprehension_questions_raw = llm_generated_data.get("comprehension_questions", None)
    has_questions = False
    # processed_llm_questions will store the list of dicts conforming to ComprehensionQuestionItem
    # after Pydantic validation (which happens in _generate_article_from_llm) and further validation here.
    processed_llm_questions = []

    if llm_comprehension_questions_raw and isinstance(llm_comprehension_questions_raw, list):
        # llm_comprehension_questions_raw should be a list of dicts if Pydantic validation passed.
        # Each dict should conform to ComprehensionQuestionItem's structure.
        valid_questions_for_firestore = []
        for q_data in llm_comprehension_questions_raw: # q_data is a dict from the LLM (e.g. from ComprehensionQuestionItem.model_dump())
            if not (isinstance(q_data, dict) and 
                    q_data.get("question") and 
                    isinstance(q_data.get("choices"), list) and 
                    q_data.get("correct_choice_id")):
                click.echo(click.style(f"  Warning: Skipping malformed question data from LLM: {q_data}", fg="yellow"), err=True)
                continue

            choice_ids = [choice.get('id') for choice in q_data.get('choices', []) if isinstance(choice, dict) and choice.get('id')]
            if q_data.get('correct_choice_id') in choice_ids:
                valid_questions_for_firestore.append(q_data)
            else:
                click.echo(click.style(f"  Warning: Question \"{q_data.get('question', 'Unknown Question')}\" has a correct_choice_id \"{q_data.get('correct_choice_id')}\" not found in its choices. Skipping this question.", fg="yellow"), err=True)
        
        processed_llm_questions = valid_questions_for_firestore
        if processed_llm_questions:
            has_questions = True
            click.echo(f"  Successfully processed {len(processed_llm_questions)} multiple-choice comprehension questions from LLM output.")
        elif llm_comprehension_questions_raw: # LLM provided questions, but none were valid after our checks
             click.echo("  Comprehension questions field was present in LLM output, but no questions remained after validation (e.g., correct_choice_id mismatch or malformed data).")
        # If llm_comprehension_questions_raw was empty list initially, no special message here.
    elif llm_comprehension_questions_raw is not None: # It was present but not a list as expected
        click.echo(click.style(f"  Warning: 'comprehension_questions' field from LLM was not a list as expected. Received: {llm_comprehension_questions_raw}", fg="yellow"), err=True)
    # If llm_comprehension_questions_raw was None, nothing is printed here.

    # Validate and clean tags
    if not isinstance(article_tags_from_llm, list) or not all(isinstance(tag, str) for tag in article_tags_from_llm):
        click.echo(f"Warning: LLM 'tags' field was not a list of strings. Received: {article_tags_from_llm}. Using topic as default tag.", err=True)
        processed_tags = [topic.lower().replace(" ", "-")]
    else:
        processed_tags = [tag.strip().lower() for tag in article_tags_from_llm if tag.strip()]

    # Add provider and model info to tags for traceability
    processed_tags.append(f"llm-provider:{provider.lower()}")
    if model_name_option:
         processed_tags.append(f"llm-model:{model_name_option.lower().replace('/','-').replace(':','-')}") # Sanitize model name
    processed_tags = sorted(list(set(processed_tags))) # Deduplicate and sort

    firestore_article_data = {
        'title': article_title,
        'content': article_content,
        'levelIds': [level_id],
        'tags': processed_tags,   # Array of strings
        'createdAt': firestore.SERVER_TIMESTAMP,  # Corrected
        'updatedAt': firestore.SERVER_TIMESTAMP,  # Corrected
        'scrapedAt': firestore.SERVER_TIMESTAMP, # Corrected (for "content generated at")
        'sourceUrl': f"llm_generated/{provider.lower()}/topic_{topic.lower().replace(' ', '_').replace('/', '_')}", # Basic slug
        'hasComprehensionQuestions': has_questions, # This field remains in the main article doc
        # The 'comprehensionQuestions' list is REMOVED from the main article document
    }

    click.echo(f"  Title: {firestore_article_data['title']}")
    click.echo(f"  Tags: {firestore_article_data['tags']}")
    if has_questions:
        click.echo(f"  Multiple-Choice Questions to be saved in subcollection: {len(processed_llm_questions)} found.")
    else:
        click.echo("  No valid multiple-choice questions generated or processed to be saved.")
    # click.echo(f"  Content Preview: {firestore_article_data['content'][:100]}...") # Optional preview

    # 6. Add to Firestore
    try:
        article_collection_ref = firestore_db.collection('articles')
        _timestamp, new_doc_ref = article_collection_ref.add(firestore_article_data) # new_doc_ref is the DocumentReference
        article_firestore_id = new_doc_ref.id
        click.echo(f"\nArticle '{firestore_article_data['title']}' added successfully to 'articles' collection with ID: {article_firestore_id}.")

        # If questions were generated, add them to a 'questions' subcollection
        if has_questions and processed_llm_questions:
            questions_subcollection_ref = new_doc_ref.collection('questions')
            click.echo(f"  Adding {len(processed_llm_questions)} multiple-choice questions to 'questions' subcollection for article ID {article_firestore_id}...")
            for idx, q_data in enumerate(processed_llm_questions): # q_data is a dict from LLM (validated by Pydantic and here)
                
                # Transform LLM choice structure to Firestore choice structure
                firestore_choices = []
                for choice_item_data in q_data.get("choices", []): # choice_item_data is a dict like ChoiceItem
                    firestore_choices.append({
                        "id": choice_item_data.get("id", f"unknown_choice_{idx}_{firestore_choices.count}"), # e.g., "A"
                        "textEnglish": choice_item_data.get("text", "N/A"),
                        "textTraditionalChinese": "" # Placeholder
                    })

                question_document_data = {
                    "_id": f"mcq{idx + 1}", # Custom ID for multiple choice questions
                    "questionTextEnglish": q_data.get("question", "N/A"),
                    "questionTextTraditionalChinese": "",  # Placeholder
                    "choices": firestore_choices, # Array of choice objects for Firestore
                    "correctAnswer": {"choiceId": q_data.get("correct_choice_id")}, # References ID from choices
                    "explanationEnglish": "Multiple-choice question and answer options generated by LLM.", # Placeholder
                    "explanationTraditionalChinese": "", # Placeholder
                    "order": idx + 1,
                    "points": 10,  # Default points for MCQ
                    "questionType": "multiple_choice", # Explicitly set
                }
                q_doc_timestamp, q_doc_ref_actual = questions_subcollection_ref.add(question_document_data)
                click.echo(f"    Added MCQ {idx + 1} ('_id': \"mcq{idx+1}\") with Firestore ID: {q_doc_ref_actual.id}")
            click.echo(f"  Successfully added {len(processed_llm_questions)} multiple-choice questions to the subcollection.")

    except Exception as e:
        click.echo(f"Error adding article or questions to Firestore: {e}", err=True)
        # Consider more sophisticated error handling if article is created but questions fail.
        exit(1)

if __name__ == '__main__':
    # For direct execution, ensure FIREBASE_SERVICE_ACCOUNT_KEY_PATH is set,
    # or pass --key-path. Also set LLM provider options.
    # Example:
    # export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
    # export OPENAI_API_KEY="your_openai_key"
    # python english-language-helper/cli/llm_article_generator.py --topic "The Importance of Sleep" --level-order 1 --provider openai --model gpt-3.5-turbo
    generate_article()
