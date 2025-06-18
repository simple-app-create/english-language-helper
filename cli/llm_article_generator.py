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
class LLMArticleOutput(BaseModel):
    title: Annotated[str, Field(min_length=1)]  # Title must not be empty
    content: Annotated[str, Field(min_length=1)] # Content must not be empty
    # Tags can be an empty list, but if tags exist, they must be non-empty strings.
    tags: Annotated[List[Annotated[str, Field(min_length=1)]], Field(min_length=0)]

# --- LLM Configuration & System Prompt ---
LLM_SYSTEM_PROMPT = """
You are an expert content creator and linguist specializing in crafting clear, engaging, and educational articles for English language learners. Your goal is to generate an article based on a given topic and target reading level.

**Instructions:**
1.  **Target Audience:** The article is for English language learners at the specified reading level. Use vocabulary, sentence structures, and concepts appropriate for this level.
2.  **Content:** The article should be informative, well-structured, and factually accurate. It needs an introduction, body, and conclusion.
3.  **Output Format:** YOU MUST PROVIDE YOUR RESPONSE STRICTLY AS A VALID JSON OBJECT with the following keys:
    *   `"title"` (string): A concise and engaging title for the article.
    *   `"content"` (string): The full text of the article. Paragraphs MUST be separated by a double newline character (`\\n\\n`).
    *   `"tags"` (array of strings): A list of 3-5 relevant lowercase keywords. Include the main topic.

**Input Variables (will be provided in the user prompt):**
*   `topic`: The subject of the article.
*   `level_name`: The descriptive name of the target reading level.

**Your Task:**
Generate the article based on the provided topic and level_name, returning it in the specified JSON format.
"""

# --- LLM Interaction Stubs (to be implemented next) ---
def _call_openai_llm(api_key, base_url, model, system_prompt, user_prompt):
    """
    Calls OpenAI or an OpenAI-compatible LLM to generate article content.
    Returns a dictionary like {"title": ..., "content": ..., "tags": ...} or None if an error occurs.
    """
    click.echo(f"  Attempting to call OpenAI/Compatible LLM: model={model}, base_url={base_url or 'default OpenAI endpoint'}")
    response_content: str = ""  # Initialize for Pyright
    raw_llm_output: dict = {}   # Initialize for Pyright
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url # Will be None for official OpenAI, set for local endpoints
        )

        # Explicitly type messages for clarity, though dicts often work due to Pydantic models in openai lib
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # For newer models that support JSON mode reliably:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"} # Request JSON output
        )

        response_content = response.choices[0].message.content
        if not response_content:
            click.echo("  LLM returned empty content.", err=True)
            return None

        # Attempt to parse and validate the JSON response
        raw_llm_output = json.loads(response_content)
        validated_data = LLMArticleOutput(**raw_llm_output)
        return validated_data.model_dump() # Return as a dictionary

    except json.JSONDecodeError as e:
        click.echo(f"  Error decoding JSON response from OpenAI LLM: {e}. Response was: {response_content}", err=True)
        return None
    except ValidationError as e:
        click.echo(f"  OpenAI LLM response failed Pydantic validation: {e}", err=True)
        # It's helpful to log the raw data that caused the validation error
        if 'raw_llm_output' in locals():
            click.echo(f"  Raw response causing validation error: {raw_llm_output}", err=True)
        else: # Should not happen if json.loads succeeded
            click.echo(f"  Raw response content (could not parse as JSON but attempted Pydantic): {response_content}", err=True)
        return None
    except APIConnectionError as e:
        click.echo(f"  OpenAI API Connection Error: {e}", err=True)
        return None
    except RateLimitError as e:
        click.echo(f"  OpenAI API Rate Limit Exceeded: {e}", err=True)
        return None
    except APIStatusError as e: # Catch other API errors
        click.echo(f"  OpenAI API Status Error (code {e.status_code}): {e.message}", err=True)
        return None
    except Exception as e:
        click.echo(f"  An unexpected error occurred while calling the OpenAI LLM: {e}", err=True)
        # import traceback # For more detailed debugging if needed
        # click.echo(traceback.format_exc(), err=True)
        return None

def _call_gemini_llm(api_key, model, system_prompt, user_prompt):
    """
    Calls Google Gemini LLM to generate article content.
    Returns a dictionary like {"title": ..., "content": ..., "tags": ...} or None if an error occurs.
    """
    click.echo(f"  Attempting to call Gemini LLM: model={model}")
    response_text_for_error = "N/A" # Initialize for error reporting
    raw_llm_output: dict = {} # Initialize for Pyright
    try:
        genai.configure(api_key=api_key)

        # Gemini uses 'system_instruction' and specific generation_config for JSON
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )

        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config=generation_config
        )

        response = gemini_model.generate_content(user_prompt)
        response_text_for_error = response.text # Store for potential error message

        if not response.text:
            click.echo("  Gemini LLM returned empty text content.", err=True)
            return None
            
        # Attempt to parse and validate the JSON response
        raw_llm_output = json.loads(response.text)
        validated_data = LLMArticleOutput(**raw_llm_output)
        return validated_data.model_dump() # Return as a dictionary

    except json.JSONDecodeError as e:
        click.echo(f"  Error decoding JSON response from Gemini LLM: {e}. Response text was: {response_text_for_error}", err=True)
        return None
    except ValidationError as e:
        click.echo(f"  Gemini LLM response failed Pydantic validation: {e}", err=True)
        if 'raw_llm_output' in locals():
             click.echo(f"  Raw response causing validation error: {raw_llm_output}", err=True)
        else: # Should not happen if json.loads succeeded
            click.echo(f"  Raw response text (could not parse as JSON but attempted Pydantic): {response_text_for_error}", err=True)
        return None
    except google_exceptions.GoogleAPIError as e: # Catch specific Google API errors
        click.echo(f"  Google Gemini API Error: {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"  An unexpected error occurred while calling the Gemini LLM: {e}", err=True)
        # import traceback
        # click.echo(traceback.format_exc(), err=True)
        return None

# --- New LLM Interaction Functions for Local LLMs ---
def _call_lmstudio_llm(api_key_option, base_url_option, model_name_option, system_prompt, user_prompt):
    """
    Calls an LM Studio instance (expected to be OpenAI-compatible).
    """
    click.echo(f"  Configuring for LM Studio: model={model_name_option or 'default/loaded in LMStudio'}")
    
    effective_base_url = base_url_option or "http://localhost:1234/v1" # Common LMStudio default
    # LMStudio typically doesn't require an API key when serving locally via its OpenAI-compatible endpoint.
    effective_api_key = api_key_option or "not-needed-for-lmstudio" 
    effective_model = model_name_option or "local-model" # Placeholder if server ignores it

    return _call_openai_llm(
        api_key=effective_api_key,
        base_url=effective_base_url,
        model=effective_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

def _call_ollama_llm(api_key_option, base_url_option, model_name_option, system_prompt, user_prompt):
    """
    Calls an Ollama instance (assuming an OpenAI-compatible endpoint, e.g., via a wrapper).
    For native Ollama API, a different implementation would be needed using the 'ollama' library.
    """
    click.echo(f"  Configuring for Ollama (OpenAI-compatible mode): model={model_name_option or 'not specified, server default'}")

    effective_base_url = base_url_option or "http://localhost:11434/v1" 
    effective_api_key = api_key_option or "not-needed-for-ollama" # Typically no API key for local Ollama
    
    if not model_name_option:
        click.echo("  Warning: --model is highly recommended for Ollama to specify the model tag (e.g., 'llama2:7b'). Using a generic placeholder.", err=True)
        effective_model = "local-model" 
    else:
        effective_model = model_name_option

    return _call_openai_llm(
        api_key=effective_api_key,
        base_url=effective_base_url,
        model=effective_model, 
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

# --- Core LLM Generation Logic ---
def _generate_article_from_llm(provider, model_name_option, llm_api_key_option, llm_base_url_option, topic, level_name_for_prompt):
    """
    Generates article content (title, content, tags) using the specified LLM provider.
    Returns a dictionary like {"title": ..., "content": ..., "tags": ...} or None if generation fails.
    """
    click.echo(f"\nAttempting to generate article using {provider.upper()} for topic '{topic}' at level '{level_name_for_prompt}'.")
    user_prompt = f"Generate an article on the topic '{topic}' for the '{level_name_for_prompt}' reading level."
    llm_output_data = None

    try:
        if provider == 'openai':
            current_api_key = llm_api_key_option or os.environ.get("OPENAI_API_KEY")
            if not current_api_key:
                 click.echo("Error: API key for OpenAI is required. Set --llm-api-key or OPENAI_API_KEY environment variable.", err=True)
                 return None
            effective_model = model_name_option or "gpt-3.5-turbo" # Default for OpenAI
            llm_output_data = _call_openai_llm(
                api_key=current_api_key,
                base_url=None, # OpenAI uses default base_url
                model=effective_model,
                system_prompt=LLM_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        elif provider == 'lmstudio':
            llm_output_data = _call_lmstudio_llm(
                api_key_option=llm_api_key_option,
                base_url_option=llm_base_url_option,
                model_name_option=model_name_option,
                system_prompt=LLM_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        elif provider == 'ollama':
            llm_output_data = _call_ollama_llm(
                api_key_option=llm_api_key_option,
                base_url_option=llm_base_url_option,
                model_name_option=model_name_option,
                system_prompt=LLM_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        elif provider == 'gemini':
            effective_model = model_name_option or "gemini-1.5-flash-latest" # Default for Gemini
            current_api_key = llm_api_key_option or os.environ.get("GOOGLE_API_KEY")
            if not current_api_key:
                click.echo("Error: API key for Gemini is required. Set --llm-api-key or GOOGLE_API_KEY environment variable.", err=True)
                return None
            llm_output_data = _call_gemini_llm(
                api_key=current_api_key,
                model=effective_model,
                system_prompt=LLM_SYSTEM_PROMPT, # Gemini's SDK handles system prompt
                user_prompt=user_prompt
            )
        else:
            # This case should ideally be caught by Click's Choice validation
            click.echo(f"Provider '{provider}' is not supported in _generate_article_from_llm.", err=True) # Updated error message slightly
            return None

        if not llm_output_data or not isinstance(llm_output_data, dict) or not all(k in llm_output_data for k in ["title", "content", "tags"]):
            click.echo(f"LLM ({provider.upper()}) did not return the expected JSON structure (title, content, tags). Response: {llm_output_data}", err=True)
            return None
        
        click.echo(f"LLM ({provider.upper()}) content generated successfully.") # Removed "(from stub/placeholder)"
        return llm_output_data

    except Exception as e:
        # Log the full exception for debugging if necessary
        # import traceback
        # click.echo(traceback.format_exc(), err=True)
        click.echo(f"Error during LLM interaction with {provider.upper()}: {e}", err=True)
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
        level_name_english = level_doc.get('nameEnglish', f"Level Order {level_order_num}") # Default if nameEnglish is missing
        click.echo(f"Using levelId: '{level_id}' (Name: '{level_name_english}') for order {level_order_num}.")
        return level_id, level_name_english
    except Exception as e:
        click.echo(f"Error querying 'levels' collection: {e}", err=True)
        return None, None

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
    required=True, 
    help='The topic for the article to be generated.'
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
    required=True, 
    help='The LLM provider to use for article generation.'
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

    # 3. Generate Article Content using LLM
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

    # 4. Prepare data for Firestore, using the LLM's output
    click.echo("\nPreparing article data for Firestore...")
    article_title = llm_generated_data.get("title", f"Untitled Article on {topic}")
    article_content = llm_generated_data.get("content", f"Content for {topic} is missing.")
    article_tags_from_llm = llm_generated_data.get("tags", [])

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
        'hasComprehensionQuestions': False, # Default, can be updated later if questions are generated
    }
    click.echo(f"  Title: {firestore_article_data['title']}")
    click.echo(f"  Tags: {firestore_article_data['tags']}")
    # click.echo(f"  Content Preview: {firestore_article_data['content'][:100]}...") # Optional preview

    # 5. Add to Firestore
    try:
        article_collection_ref = firestore_db.collection('articles')
        # add() returns a tuple (timestamp, DocumentReference)
        _timestamp, new_doc_ref = article_collection_ref.add(firestore_article_data)
        article_firestore_id = new_doc_ref.id
        click.echo(f"\nArticle '{firestore_article_data['title']}' added successfully to 'articles' collection with ID: {article_firestore_id}.")
    except Exception as e:
        click.echo(f"Error adding article to Firestore: {e}", err=True)
        exit(1)

if __name__ == '__main__':
    # For direct execution, ensure FIREBASE_SERVICE_ACCOUNT_KEY_PATH is set,
    # or pass --key-path. Also set LLM provider options.
    # Example:
    # export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
    # export OPENAI_API_KEY="your_openai_key"
    # python english-language-helper/cli/llm_article_generator.py --topic "The Importance of Sleep" --level-order 1 --provider openai --model gpt-3.5-turbo
    generate_article()