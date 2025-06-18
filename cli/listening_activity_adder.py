import click
from firebase_admin import firestore # For firestore.FieldValue
from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR
# Removed os, firebase_admin, credentials imports as they are handled by firestore_utils
# Removed local SERVICE_ACCOUNT_KEY_ENV_VAR, db global, and get_firestore_client function


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
    help='The URL of the audio file for the listening activity.'
)
@click.argument(
    'title',
    type=str,
    required=True,
    help='The title of the listening activity.'
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
# Add more options as needed (e.g., duration, speakers)
def add_listening_activity(key_path, audio_url, title, level, transcript_file, tags):
    """
    Adds a new listening activity to the \'activities\' collection in Firestore.
    """
    # 1. Initialize Firestore client
    firestore_db = get_firestore_client(key_path)
    if firestore_db is None:
        click.echo("Failed to initialize Firestore client. Aborting.", err=True)
        exit(1) # Exit if Firestore initialization failed

    click.echo(f"Adding listening activity: \'{title}\' from {audio_url} for level {level}...")

    # --- Read Transcript Content ---\n
    transcript_content = ""
    if transcript_file:
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_content = f.read()
            click.echo("Transcript file read successfully.")
        except Exception as e:
            click.echo(f"Error reading transcript file: {e}")
            # Decide if you want to exit or continue without transcript
            return # Exit the command on file read error

    # --- Prepare Activity Data ---\n
    # 2. Prepare the data structure for Firestore
    #    - Generate a unique activity ID (using a Firestore auto-ID)
    #    - Include title, audio_url, level, transcript (if available), tags, publishedAt, activity_type

    # Using Firestore auto-ID for simplicity in skeleton
    # Storing listening activities in a separate 'activities' collection
    doc_ref = firestore_db.collection('activities').document() # Creates a document reference with an auto-ID
    activity_id = doc_ref.id # Get the generated ID

    activity_data = {
        'activity_type': 'listening', # Explicitly define the type
        'title': title,
        'audioUrl': audio_url,
        'level': level,
        'transcript': transcript_content, # Store transcript (can be empty string)
        'tags': [tag.strip() for tag in tags.split(',')] if tags else [], # Store tags as a list
        'publishedAt': firestore.FieldValue.server_timestamp(), # Use server timestamp
        # Add other fields like duration, speakers, etc. as needed
    }

    # --- Add to Firestore ---\n
    # 3. Add the prepared data to the \'activities\' collection
    try:
        doc_ref.set(activity_data)
        click.echo(f"Listening activity \'{title}\' added successfully with ID \'{activity_id}\' in the \'activities\' collection.")
    except Exception as e:
        click.echo(f"Error adding listening activity to Firestore: {e}")
        exit(1) # Exit if Firestore write failed


# This allows the command to be run directly or imported into a main CLI group
if __name__ == '__main__':
    add_listening_activity()