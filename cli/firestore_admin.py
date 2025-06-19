"""CLI tool for managing English Language Helper data in Firestore."""

from typing import Optional

import click
from firebase_admin import firestore
from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR, validate_db_client, parse_publication_date, check_article_exists

# SERVICE_ACCOUNT_KEY_ENV_VAR is now imported from firestore_utils
# Global db client is now managed within get_firestore_client or passed via ctx.obj

@click.group()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR, # Now imported from firestore_utils
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to the Firebase service account key JSON file. Can also be set via the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable.',
    required=False, # get_firestore_client will handle if it's truly missing (from path or env var)
)
@click.pass_context
def cli(ctx: click.Context, key_path: Optional[str]) -> None:
    """A CLI tool to manage English Language Helper data in Firestore.
    
    Args:
        ctx: Click context object for passing data between commands
        key_path: Path to Firebase service account key JSON file
        
    Returns:
        None
        
    Raises:
        SystemExit: If Firestore initialization fails
    """
    # Firebase initialization is now handled by get_firestore_client
    firestore_client = get_firestore_client(key_path=key_path) 
    
    if firestore_client is None:
        # get_firestore_client already prints detailed errors
        click.echo("Failed to initialize Firestore. Exiting.", err=True)
        ctx.exit(1)
        
    ctx.obj = firestore_client # Store the client in the context object for subcommands
    # click.echo("Firebase Admin SDK initialized successfully via utils and client stored in context.", err=True) # Optional debug

@cli.command()
@click.pass_context
def check_db_connection(ctx: click.Context) -> None:
    """Check if the database connection is working.
    
    Args:
        ctx: Click context containing Firestore client
        
    Returns:
        None
        
    Raises:
        SystemExit: If database connection test fails
    """
    db = ctx.obj # Get client from context
    validate_db_client(db, ctx)
    
    try:
        articles_ref = db.collection('articles') # Assuming 'articles' is a valid collection
        # Use stream() for iterators and list() to consume and actually perform the read.
        docs = articles_ref.limit(1).stream() 
        list(docs) 
        click.echo("Successfully connected to Firestore and can perform reads.")
    except Exception as e:
        click.echo(f"Connected to Firestore, but encountered an error performing a test read: {e}", err=True)
        click.echo("Please ensure your service account has the necessary permissions (e.g., 'roles/datastore.user').", err=True)

@cli.command()
@click.argument('article_id')
@click.argument('title')
@click.option(
    '--content-file',
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help='Path to a file containing the article content. If not provided, content will be empty.'
)
@click.option(
    '--level-ids',
    required=True,
    type=str,
    help='Comma-separated string of level IDs (e.g., "gsat_english,cap_junior_high").'
)
@click.option('--source-url', type=str, default="", help='The original URL of the article.')
@click.option('--source-name', type=str, default="", help='The name of the website or publication.')
@click.option(
    '--publication-date-str', # Renamed to avoid confusion with datetime object if parsed
    type=str,
    help='Original publication date of the article as a string (e.g., "YYYY-MM-DD").'
)
@click.option('--author', type=str, default="", help='Author of the article.')
@click.option(
    '--tags',
    type=str,
    help='Comma-separated tags for the article (e.g., history,science).'
)
@click.option('--summary-english', type=str, default="", help='A brief English summary.')
@click.option('--summary-traditional-chinese', type=str, default="", help='A brief Traditional Chinese summary.')
@click.option('--estimated-reading-time', type=int, help='Estimated reading time in minutes.')
@click.option(
    '--has-comprehension-questions',
    is_flag=True, # Makes it a boolean flag
    default=False,
    help='Set this flag if the article has comprehension questions.'
)
@click.pass_context
def add_article(ctx: click.Context, article_id: str, title: str, 
                content_file: Optional[str], level_ids: str,
                source_url: str, source_name: str, publication_date_str: Optional[str], 
                author: str, tags: Optional[str], summary_english: str, 
                summary_traditional_chinese: str, estimated_reading_time: Optional[int],
                has_comprehension_questions: bool) -> None:
    """Add or update a reading article in the 'articles' collection.
    
    Args:
        ctx: Click context containing Firestore client
        article_id: Unique identifier for the article
        title: Article title
        content_file: Path to file containing article content
        level_ids: Comma-separated string of level IDs
        source_url: Original URL of the article
        source_name: Name of the website or publication
        publication_date_str: Publication date as YYYY-MM-DD string
        author: Article author
        tags: Comma-separated tags for the article
        summary_english: Brief English summary
        summary_traditional_chinese: Brief Traditional Chinese summary
        estimated_reading_time: Estimated reading time in minutes
        has_comprehension_questions: Whether article has comprehension questions
        
    Returns:
        None
        
    Raises:
        SystemExit: If article creation fails
    """
    db = ctx.obj # Get client from context
    validate_db_client(db, ctx)

    # Initialize article_data with all fields from the schema
    article_data = {
        'title': title,
        'sourceUrl': source_url,
        'sourceName': source_name,
        'content': "", # Default, updated if content_file is provided
        'scrapedAt': firestore.SERVER_TIMESTAMP, # Assuming CLI adds "scraped" content
        'publicationDate': None, # Default, updated if publication_date_str is valid
        'levelIds': [level_id.strip() for level_id in level_ids.split(',') if level_id.strip()],
        'author': author,
        'tags': [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else [],
        'summaryEnglish': summary_english,
        'summaryTraditionalChinese': summary_traditional_chinese,
        'estimatedReadingTimeMinutes': estimated_reading_time, # click handles type or default None
        'hasComprehensionQuestions': has_comprehension_questions,
        'createdAt': firestore.SERVER_TIMESTAMP,
        'updatedAt': firestore.SERVER_TIMESTAMP
    }

    if content_file:
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                article_data['content'] = f.read()
        except Exception as e:
            click.echo(f"Error reading content file: {e}", err=True)
            ctx.exit(1) # Exit if content file can't be read
    
    article_data['publicationDate'] = parse_publication_date(publication_date_str)

    # Ensure estimated_reading_time is an int or None, not 0 if not provided
    if estimated_reading_time is None:
        article_data['estimatedReadingTimeMinutes'] = None # Or a default like 0 if you prefer
    else:
        article_data['estimatedReadingTimeMinutes'] = estimated_reading_time


    try:
        doc_ref = db.collection('articles').document(article_id)
        # Using .set() will create the document if it doesn't exist, or overwrite it if it does.
        doc_ref.set(article_data)
        click.echo(f"Article '{title}' (ID: '{article_id}') added/updated successfully.")
        click.echo("Data written:")
        for key, value in article_data.items():
            if value == firestore.SERVER_TIMESTAMP:
                click.echo(f"  {key}: Server Timestamp (will be set by Firestore)")
            else:
                click.echo(f"  {key}: {value}")
    except Exception as e:
        click.echo(f"Error processing article: {e}", err=True)
        ctx.exit(1) # Exit on error

@cli.command()
@click.argument('article_id')
@click.pass_context
def list_article_questions(ctx: click.Context, article_id: str) -> None:
    """List all comprehension questions for a specific article.
    
    Args:
        ctx: Click context containing Firestore client
        article_id: Unique identifier of the article
        
    Returns:
        None
        
    Raises:
        SystemExit: If article not found or query fails
    """
    db = ctx.obj
    validate_db_client(db, ctx)

    try:
        exists, article_doc = check_article_exists(db, article_id)
        
        if not exists:
            click.echo(f"Article '{article_id}' not found.", err=True)
            ctx.exit(1)
        
        click.echo(f"Article: {article_doc.get('title')}")
        click.echo("-" * 40)
        
        article_ref = db.collection('articles').document(article_id)
        questions = list(article_ref.collection('questions').stream())
        
        for i, q_doc in enumerate(questions, 1):
            q = q_doc.to_dict()
            click.echo(f"Q{i}: {q.get('questionTextEnglish')}")
            
            for choice in q.get('choices', []):
                marker = " ✓" if choice['id'] == q.get('correctAnswer') else ""
                click.echo(f"  {choice['id']}: {choice['text']}{marker}")
            click.echo()
        
        click.echo(f"Total: {len(questions)} questions")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)

if __name__ == '__main__':
    cli()