"""Listening activity CLI tool for adding audio-based activities to Firestore."""

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
    'audio_url',
    type=str,
    required=True,
)
@click.argument(
    'title',
    type=str,
    required=True,
)
@click.option(
    '--level',
    type=click.IntRange(1, 18),
    required=True,
    help='The target difficulty level (1-18) for the listening activity.'
)
@click.option(
    '--transcript-file',
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help='Optional path to a file containing the transcript for the audio.'
)
@click.option(
    '--tags',
    type=str,
    help='Optional comma-separated tags for the listening activity (e.g., podcast, news).'
)
def add_listening_activity(
    key_path: Optional[str], 
    audio_url: str, 
    title: str, 
    level: int, 
    transcript_file: Optional[str], 
    tags: Optional[str]
) -> None:
    """Add a new listening activity to the 'activities' collection in Firestore.
    
    Args:
        key_path: Path to Firebase service account key JSON file
        audio_url: URL of the audio file for the listening activity
        title: Title of the listening activity
        level: Target difficulty level (1-18) for the listening activity
        transcript_file: Optional path to file containing audio transcript
        tags: Optional comma-separated tags for the activity
        
    Returns:
        None
        
    Raises:
        SystemExit: If Firestore initialization fails or file operations fail
    """
    # 1. Initialize Firestore client
    firestore_db = get_firestore_client(key_path)
    if firestore_db is None:
        click.echo("Failed to initialize Firestore client. Aborting.", err=True)
        exit(1)

    click.echo(f"Adding listening activity: '{title}' from {audio_url} for level {level}...")

    # --- Read Transcript Content ---
    transcript_content = _read_transcript_file(transcript_file)
    
    # --- Add to Firestore ---
    _add_activity_to_firestore(firestore_db, audio_url, title, level, transcript_content, tags)


def _read_transcript_file(transcript_file: Optional[str]) -> str:
    """Read transcript content from file if provided.
    
    Args:
        transcript_file: Optional path to transcript file
        
    Returns:
        Transcript content as string (empty if no file provided)
        
    Raises:
        SystemExit: If file reading fails
    """
    if not transcript_file:
        return ""
        
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            content = f.read()
        click.echo("Transcript file read successfully.")
        return content
    except Exception as e:
        click.echo(f"Error reading transcript file: {e}", err=True)
        exit(1)


def _add_activity_to_firestore(
    db: Any, 
    audio_url: str, 
    title: str, 
    level: int, 
    transcript_content: str, 
    tags: Optional[str]
) -> None:
    """Add the listening activity data to Firestore.
    
    Args:
        db: Initialized Firestore client
        audio_url: URL of the audio file
        title: Activity title
        level: Difficulty level
        transcript_content: Audio transcript text
        tags: Comma-separated tags string
        
    Returns:
        None
        
    Raises:
        SystemExit: If Firestore write operation fails
    """
    doc_ref = db.collection('activities').document()
    activity_id = doc_ref.id

    activity_data = {
        'activity_type': 'listening',
        'title': title,
        'audioUrl': audio_url,
        'level': level,
        'transcript': transcript_content,
        'tags': [tag.strip() for tag in tags.split(',')] if tags else [],
        'publishedAt': firestore.SERVER_TIMESTAMP,
    }

    try:
        doc_ref.set(activity_data)
        click.echo(f"Listening activity '{title}' added successfully with ID '{activity_id}' in the 'activities' collection.")
    except Exception as e:
        click.echo(f"Error adding listening activity to Firestore: {e}", err=True)
        exit(1)


if __name__ == '__main__':
    add_listening_activity()