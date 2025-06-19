"""Web scraper CLI tool for adding articles to Firestore."""

from typing import Optional, Any

import click
from firebase_admin import firestore

from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR


@click.command()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to the Firebase service account key JSON file. Can also be set via the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable.',
)
@click.argument(
    'url',
    type=str,
    required=True,
)
@click.option(
    '--level',
    type=click.IntRange(1, 18),
    required=True,
    help='The target reading level (1-18) for the article. Automatic detection can be added later.'
)
def add_scraped_article(key_path: Optional[str], url: str, level: int) -> None:
    """Scrape content from a URL and add it as a new article to Firestore.
    
    Args:
        key_path: Path to Firebase service account key JSON file
        url: URL of the article to scrape
        level: Target reading level (1-18) for the article
        
    Returns:
        None
        
    Raises:
        SystemExit: If Firestore initialization fails or scraping fails
    """
    # 1. Initialize Firestore client using the utility function
    firestore_db = get_firestore_client(key_path)
    if firestore_db is None:
        click.echo("Failed to initialize Firestore client. Aborting.", err=True)
        exit(1)

    click.echo(f"Attempting to scrape article from: {url}")

    # --- Placeholder for Web Scraping Logic ---
    # 2. Fetch content from the URL
    #    - Use a library like `requests` to get the HTML content.
    #    - Handle potential errors (network issues, 404, etc.).
    #    - Add headers if necessary to mimic a browser.

    html_content = ""  # Placeholder for fetched HTML

    # 3. Parse the HTML and extract article data
    #    - Use a library like `BeautifulSoup` to parse the HTML tree.
    #    - Identify the article title, content, maybe author, publication date (if available).
    #    - Clean the extracted text (remove ads, navigation, etc.).
    #    - This requires specific parsing logic for the target website(s).
    #    - Consider using libraries like `trafilatura` or `goose3` for general article extraction.

    scraped_title = "Scraped Article Title (Placeholder)"
    scraped_content = f"This is placeholder content scraped from {url}.\n\nDetails: Target Level - {level}"
    scraped_tags: list[str] = []

    if not scraped_content:
        click.echo("Could not scrape article content. Aborting.")
        exit(1)

    click.echo("Article content scraped (placeholder).")

    # --- Preview Content ---
    _preview_content(scraped_title, scraped_content)

    # --- Confirmation Step ---
    if not click.confirm('Do you want to add this article to Firestore?'):
        click.echo("Article not added to Firestore.")
        return

    # --- Add to Firestore ---
    _add_to_firestore(firestore_db, scraped_title, scraped_content, scraped_tags, level, url)


def _preview_content(title: str, content: str) -> None:
    """Display a preview of the scraped content.
    
    Args:
        title: Article title
        content: Article content
        
    Returns:
        None
    """
    click.echo("\n--- Preview ---")
    click.echo(f"Title: {title}")
    click.echo("Content:")
    
    preview_length = 500
    display_content = content[:preview_length] + ('...' if len(content) > preview_length else '')
    click.echo(display_content)
    click.echo("--- End Preview ---\n")


def _add_to_firestore(db: Any, title: str, content: str, 
                     tags: list[str], level: int, url: str) -> None:
    """Add the scraped article to Firestore.
    
    Args:
        db: Initialized Firestore client
        title: Article title
        content: Article content
        tags: List of article tags
        level: Reading level
        url: Source URL
        
    Returns:
        None
        
    Raises:
        SystemExit: If Firestore write operation fails
    """
    doc_ref = db.collection('articles').document()
    article_id = doc_ref.id

    article_data = {
        'title': title,
        'content': content,
        'level': level,
        'tags': tags,
        'publishedAt': firestore.SERVER_TIMESTAMP,
        'source': 'web_scraper',
        'sourceUrl': url
    }

    try:
        doc_ref.set(article_data)
        click.echo(f"Article '{title}' added successfully with ID '{article_id}'.")
    except Exception as e:
        click.echo(f"Error adding article to Firestore: {e}", err=True)
        exit(1)


if __name__ == '__main__':
    add_scraped_article()