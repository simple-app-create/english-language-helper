"""CLI tool for managing English Language Helper data in Firestore."""

from typing import Optional, Any, Literal

import click
from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR, validate_db_client


@click.group()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to the Firebase service account key JSON file. Can also be set via the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable.',
    required=False,
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
    firestore_client = get_firestore_client(key_path=key_path) 
    
    if firestore_client is None:
        click.echo("Failed to initialize Firestore. Exiting.", err=True)
        ctx.exit(1)
        
    ctx.obj = firestore_client


# Core business logic functions (DRY principle)

def _check_connection_core(db: Any) -> bool:
    """Core logic for checking database connection.
    
    Args:
        db: Firestore database client
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        articles_ref = db.collection('articles')
        docs = articles_ref.limit(1).stream()
        list(docs)
        return True
    except Exception:
        return False



def _list_articles_core(db: Any) -> list[tuple[str, dict[str, Any]]]:
    """Core logic for listing all articles.
    
    Args:
        db: Firestore database client
        
    Returns:
        List of tuples containing (article_id, article_data)
        
    Raises:
        Exception: If query fails
    """
    articles_ref = db.collection('articles')
    return [(doc.id, doc.to_dict()) for doc in articles_ref.stream()]


def _display_article_info(
    article_id: str, 
    article_data: dict[str, Any], 
    mode: Literal['cli_list_item', 'interactive_list_item', 'interactive_detail_view'],
    index: Optional[int] = None
) -> None:
    """Helper function to display article information in various formats.

    Args:
        article_id: The ID of the article.
        article_data: The data dictionary of the article.
        mode: The display mode.
            'cli_list_item': For the `list-articles` CLI command.
            'interactive_list_item': For the listing in interactive mode.
            'interactive_detail_view': For the detailed view in interactive mode.
        index: Optional index for list items.
    """
    if mode == 'cli_list_item':
        if index is None:
            raise ValueError("Index is required for 'cli_list_item' mode.")
        click.echo(f"{index}. ID: {article_id}")
        click.echo(f"   Title: {article_data.get('title', 'N/A')}")
        click.echo(f"   Author: {article_data.get('author', 'N/A')}")
        click.echo(f"   Level IDs: {', '.join(article_data.get('levelIds', []))}")
        click.echo(f"   Has Questions: {'Yes' if article_data.get('hasComprehensionQuestions', False) else 'No'}")
        click.echo(f"   Reading Time: {article_data.get('estimatedReadingTimeMinutes', 'N/A')} minutes")
        click.echo("-" * 40)
    
    elif mode == 'interactive_list_item':
        if index is None:
            raise ValueError("Index is required for 'interactive_list_item' mode.")
        click.echo(f"{index}. {article_data.get('title', 'N/A')}")
        click.echo(f"   ID: {article_id}")
        click.echo(f"   Author: {article_data.get('author', 'N/A')}")
        click.echo(f"   Level: {', '.join(article_data.get('levelIds', []))}")
        click.echo(f"   Questions: {'Yes' if article_data.get('hasComprehensionQuestions', False) else 'No'}")
        click.echo()

    elif mode == 'interactive_detail_view':
        click.echo(f"📄 Title: {article_data.get('title', 'N/A')}")
        click.echo(f"🆔 ID: {article_id}")
        click.echo(f"👤 Author: {article_data.get('author', 'N/A')}")
        click.echo(f"🏷️  Level IDs: {', '.join(article_data.get('levelIds', []))}")
        click.echo(f"🏷️  Tags: {', '.join(article_data.get('tags', []))}")
        click.echo(f"🌐 Source: {article_data.get('sourceName', 'N/A')}")
        click.echo(f"🔗 URL: {article_data.get('sourceUrl', 'N/A')}")
        click.echo(f"📅 Publication Date: {article_data.get('publicationDate', 'N/A')}")
        click.echo(f"⏱️  Reading Time: {article_data.get('estimatedReadingTimeMinutes', 'N/A')} minutes")
        click.echo(f"❓ Has Questions: {'Yes' if article_data.get('hasComprehensionQuestions', False) else 'No'}")
        
        if article_data.get('summaryEnglish'):
            click.echo(f"\n📝 English Summary:")
            click.echo(f"   {article_data.get('summaryEnglish')}")
        
        if article_data.get('summaryTraditionalChinese'):
            click.echo(f"\n📝 Traditional Chinese Summary:")
            click.echo(f"   {article_data.get('summaryTraditionalChinese')}")
        
        content = article_data.get('content', '')
        if content:
            click.echo(f"\n📖 Content Preview:")
            click.echo("-" * 50)
            preview = content[:500]
            if len(content) > 500:
                preview += "..."
            click.echo(preview)


# CLI Commands (thin wrappers around core functions)

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
    db = ctx.obj
    validate_db_client(db, ctx)
    
    if _check_connection_core(db):
        click.echo("Successfully connected to Firestore and can perform reads.")
    else:
        click.echo("Connected to Firestore, but encountered an error performing a test read.", err=True)
        click.echo("Please ensure your service account has the necessary permissions.", err=True)


@cli.command()
@click.pass_context
def list_articles(ctx: click.Context) -> None:
    """List all articles in the database with basic information.
    
    Args:
        ctx: Click context containing Firestore client
        
    Returns:
        None
        
    Raises:
        SystemExit: If query fails
    """
    db = ctx.obj
    validate_db_client(db, ctx)

    try:
        articles = _list_articles_core(db)
        
        if not articles:
            click.echo("No articles found in the database.")
            return
        
        click.echo(f"Found {len(articles)} articles:")
        click.echo("=" * 80)
        
        for i, (article_id, article_data) in enumerate(articles, 1):
            _display_article_info(article_id, article_data, mode='cli_list_item', index=i)
            
    except Exception as e:
        click.echo(f"Error listing articles: {e}", err=True)
        ctx.exit(1)


# Interactive mode functions (use core functions)


def _interactive_check_connection(db: Any) -> None:
    """Interactive mode for checking database connection.
    
    Args:
        db: Firestore database client
        
    Returns:
        None
    """
    click.echo("\n=== Database Connection Test ===")
    
    if _check_connection_core(db):
        click.echo("✓ Successfully connected to Firestore!")
        click.echo("✓ Database permissions are working correctly.")
    else:
        click.echo("✗ Connection test failed", err=True)
        click.echo("Please check your service account permissions.", err=True)


def _interactive_list_and_view_articles(db: Any) -> None:
    """Interactive mode for listing and viewing articles with questions.
    
    Args:
        db: Firestore database client
        
    Returns:
        None
    """
    click.echo("\n=== View Articles ===")
    
    try:
        articles = _list_articles_core(db)
        
        if not articles:
            click.echo("No articles found in the database.")
            return
        
        click.echo(f"\nFound {len(articles)} articles:")
        click.echo("=" * 80)
        
        for i, (article_id, article_data) in enumerate(articles, 1):
            _display_article_info(article_id, article_data, mode='interactive_list_item', index=i)
        
        try:
            selection = click.prompt(
                f"Select an article to view (1-{len(articles)}) or 0 to go back", 
                type=click.IntRange(0, len(articles))
            )
        except click.Abort:
            return
        
        if selection == 0:
            return
        
        selected_id, selected_data = articles[selection - 1]
        
        click.echo("\n" + "=" * 80)
        click.echo("ARTICLE DETAILS")
        click.echo("=" * 80)
        
        _display_article_info(selected_id, selected_data, mode='interactive_detail_view')

        click.echo("\n" + "=" * 80)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """Start interactive mode with menu-driven interface.
    
    Args:
        ctx: Click context containing Firestore client
        
    Returns:
        None
        
    Raises:
        SystemExit: If database client not available
    """
    db = ctx.obj
    validate_db_client(db, ctx)
    
    click.echo("🔥 Firestore Admin - Interactive Mode")
    click.echo("=" * 40)
    
    while True:
        click.echo("\nAvailable Operations:")
        click.echo("1. View Articles & Questions")
        click.echo("2. Check Database Connection")
        click.echo("3. Exit")
        
        try:
            choice = click.prompt("\nSelect an option", type=click.IntRange(1, 3))
        except click.Abort:
            click.echo("\nGoodbye!")
            break
        
        if choice == 1:
            _interactive_list_and_view_articles(db)
        elif choice == 2:
            _interactive_check_connection(db)
        elif choice == 3:
            click.echo("Goodbye!")
            break
        
        if choice != 3:
            click.echo("\nPress Enter to continue...")
            click.getchar()

if __name__ == "__main__":
    cli()