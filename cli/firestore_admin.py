import os
import click
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime # For potential date parsing

# Define the name of the environment variable
SERVICE_ACCOUNT_KEY_ENV_VAR = 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH'

# Global variable for the Firestore database client
db = None

@click.group()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to the Firebase service account key JSON file. Can also be set via the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable.',
)
@click.pass_context
def cli(ctx, key_path):
    """A CLI tool to manage English Language Helper data in Firestore."""
    global db
    if not key_path:
        click.echo("Error: Firebase service account key path is required.")
        click.echo(f"Please set the '{SERVICE_ACCOUNT_KEY_ENV_VAR}' environment variable or use the '--key-path' command-line option.")
        click.echo(ctx.get_help())
        ctx.exit(1)
    try:
        cred = credentials.Certificate(key_path)
        if not firebase_admin._apps:
             firebase_admin.initialize_app(cred)
        db = firestore.client()
        # click.echo("Firebase Admin SDK initialized successfully.") # Optional
    except Exception as e:
        click.echo(f"Error initializing Firebase: {e}")
        ctx.exit(1)

@cli.command()
def check_db_connection():
    """Checks if the database connection is working."""
    if db:
        try:
            articles_ref = db.collection('articles') # Assuming 'articles' is a valid collection
            docs = articles_ref.limit(1).get()
            click.echo("Successfully connected to Firestore and can perform reads.")
        except Exception as e:
            click.echo(f"Connected to Firestore, but encountered an error performing a test read: {e}")
            click.echo("Please ensure your service account has the necessary permissions (e.g., 'roles/datastore.user').")
    else:
        click.echo("Database not initialized. Ensure Firebase initialization succeeded.")

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
def add_article(article_id, title, content_file, level_ids,
                source_url, source_name, publication_date_str, author,
                tags, summary_english, summary_traditional_chinese,
                estimated_reading_time, has_comprehension_questions):
    """Adds or updates a reading article in the 'articles' collection using the defined schema."""
    if db is None:
        click.echo("Database not initialized. Cannot add article.")
        # Consider using ctx.exit(1) if you pass context to this command
        exit(1)

    # Initialize article_data with all fields from the schema
    article_data = {
        'title': title,
        'sourceUrl': source_url,
        'sourceName': source_name,
        'content': "", # Default, updated if content_file is provided
        'scrapedAt': firestore.FieldValue.server_timestamp(), # Assuming CLI adds "scraped" content
        'publicationDate': None, # Default, updated if publication_date_str is valid
        'levelIds': [level_id.strip() for level_id in level_ids.split(',') if level_id.strip()],
        'author': author,
        'tags': [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else [],
        'summaryEnglish': summary_english,
        'summaryTraditionalChinese': summary_traditional_chinese,
        'estimatedReadingTimeMinutes': estimated_reading_time, # click handles type or default None
        'hasComprehensionQuestions': has_comprehension_questions,
        'createdAt': firestore.FieldValue.server_timestamp(),
        'updatedAt': firestore.FieldValue.server_timestamp()
    }

    if content_file:
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                article_data['content'] = f.read()
        except Exception as e:
            click.echo(f"Error reading content file: {e}")
            return # Stop if content file can't be read
    
    if publication_date_str:
        try:
            # Validate format, then store as string.
            # If you need a Firestore Timestamp, parse to datetime and handle timezones.
            datetime.datetime.strptime(publication_date_str, '%Y-%m-%d')
            article_data['publicationDate'] = publication_date_str
        except ValueError:
            click.echo(f"Warning: --publication-date-str '{publication_date_str}' is not in YYYY-MM-DD format. 'publicationDate' field will be None.")
            article_data['publicationDate'] = None # Or store the malformed string if preferred.

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
            if value == firestore.FieldValue.server_timestamp():
                click.echo(f"  {key}: Server Timestamp (will be set by Firestore)")
            else:
                click.echo(f"  {key}: {value}")
    except Exception as e:
        click.echo(f"Error processing article: {e}")

if __name__ == '__main__':
    cli()