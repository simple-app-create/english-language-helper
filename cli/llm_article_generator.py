import click
from .firestore_utils import get_firestore_client, SERVICE_ACCOUNT_KEY_ENV_VAR
from firebase_admin import firestore # For firestore.FieldValue and other specific firestore items
# import datetime # Not strictly needed as we use firestore.FieldValue.server_timestamp()




@click.command()
@click.option(
    '--key-path',
    envvar=SERVICE_ACCOUNT_KEY_ENV_VAR,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help=f'Path to the Firebase service account key JSON file. Can also be set via the {SERVICE_ACCOUNT_KEY_ENV_VAR} environment variable.',
)
@click.option(
    '--topic',
    type=str,
    required=True,
    help='The topic for the article to be generated.'
)
@click.option(
    '--level-order',
    type=click.IntRange(min=1), # min=1, no explicit max for flexibility
    required=True,
    help='The target reading level order (e.g., 1, 2, 3) to map to a levelId from the "levels" collection.'
)
# Future LLM options:
# @click.option('--word-count', type=int, default=500, help='Approximate word count for the article.')
# @click.option('--style', type=click.Choice(['formal', 'informal', 'academic']), default='formal', help='Writing style.')
def generate_article(key_path, topic, level_order):
    """
    Generates a new article (using placeholders for LLM interaction) based on topic
    and level order, and adds it to the 'articles' collection in Firestore.
    """
    firestore_db = get_firestore_client(key_path)
    if firestore_db is None:
        click.echo("Failed to initialize Firestore client. Aborting.", err=True)
        # Consider using click.Context.exit(1) if within a click context managed elsewhere
        # For a simple script, exit(1) is fine.
        exit(1) 

    # 1. Fetch levelId from 'levels' collection based on level_order
    level_id = None
    level_name_english = "Unknown Level" # Default
    try:
        levels_query = firestore_db.collection('levels').where('order', '==', level_order).limit(1)
        levels_docs = list(levels_query.stream()) # Execute the query and get results

        if not levels_docs:
            click.echo(f"Error: No level found in 'levels' collection with order = {level_order}. Please ensure a level with this order exists.", err=True)
            exit(1)
        
        level_doc = levels_docs[0] # Get the first document
        level_id = level_doc.id
        level_name_english = level_doc.get('nameEnglish', level_name_english) # Get name if exists
        click.echo(f"Using levelId: '{level_id}' (Name: '{level_name_english}') for order {level_order}.")

    except Exception as e:
        click.echo(f"Error querying 'levels' collection: {e}", err=True)
        exit(1)

    click.echo(f"Generating article on topic '{topic}' for level order {level_order} (levelId: {level_id})...")

    # --- Placeholder for LLM Interaction ---
    # 2. Call LLM API with topic, level_id (or level_name_english for prompt), word_count, style etc.
    #    This is where you would integrate with an actual LLM service.
    #    The LLM should ideally generate: title, content, and relevant tags.
    
    # Simulate LLM output
    click.echo("Simulating LLM content generation...")
    generated_title = f"Exploring {topic}: An Article for {level_name_english} Learners"
    generated_content = (
        f"This is a placeholder article about '{topic}'. It has been 'generated' by a script "
        f"and is intended for learners at the {level_name_english} level (order: {level_order}, levelId: {level_id}).\n\n"
        f"**Introduction to {topic}**\n"
        f"Start with a captivating introduction that grabs the reader's attention and clearly states the article's purpose.\n\n"
        f"**Key Aspects of {topic}**\n"
        f"Discuss the main points related to '{topic}'. Use clear language appropriate for the target level. "
        f"Consider using examples or simple explanations.\n\n"
        f"**Conclusion**\n"
        f"Summarize the main points and offer a concluding thought or encourage further learning about '{topic}'.\n\n"
        f"This content should be replaced by actual output from an LLM service in a real application."
    )
    # Tags could be derived from topic, LLM output, or a combination
    generated_tags = [tag.strip().lower() for tag in topic.split(',')] + ["llm-generated", level_id]
    generated_tags = list(set(filter(None, generated_tags))) # Remove empty strings and duplicates

    # (Future enhancement: LLM could also generate comprehension questions)
    # generated_questions_data = [
    #     { "_id": "q1", "questionTextEnglish": "What is the main idea of the article?", "questionType": "short_answer", ... },
    #     { "_id": "q2", "questionTextEnglish": "Which of these is mentioned?", "questionType": "multiple_choice", ... }
    # ]
    # has_comprehension_questions = bool(generated_questions_data) if generated_questions_data else False
    has_comprehension_questions = False # Default for now

    if not generated_content or not generated_title:
        click.echo("LLM (placeholder) failed to generate title or content. Aborting.", err=True)
        exit(1)

    click.echo("LLM content (placeholder) generated successfully.")

    # --- Prepare Article Data for Firestore ---
    # 3. Prepare the data structure aligning with your Firestore schema
    # Firestore will auto-generate an ID if .document() is called without an ID
    article_collection_ref = firestore_db.collection('articles')
    
    article_data = {
        'title': generated_title,
        'content': generated_content,
        'levelIds': [level_id],  # Array of strings
        'tags': generated_tags,   # Array of strings
        'createdAt': firestore.FieldValue.server_timestamp(),
        'updatedAt': firestore.FieldValue.server_timestamp(),
        'scrapedAt': firestore.FieldValue.server_timestamp(), # Assuming 'scrapedAt' for LLM generation means 'content_generated_at'
        'sourceUrl': f"llm_generated_by_script/topic_{topic.lower().replace(' ', '_').replace(',', '_')}", # Make a simple slug
        'hasComprehensionQuestions': has_comprehension_questions,
        # 'article_id' is not stored in the document itself, it's the document's name/key.
    }

    # --- Add to Firestore ---
    # 4. Add the prepared data to the 'articles' collection
    try:
        doc_ref = article_collection_ref.add(article_data) # add() returns a tuple (timestamp, DocumentReference)
        article_id = doc_ref[1].id # The DocumentReference is the second element
        click.echo(f"Article '{article_data['title']}' added successfully to 'articles' collection with ID: {article_id}.")

        # (Future enhancement: If questions were generated, add them to the subcollection)
        # if has_comprehension_questions and generated_questions_data:
        #     questions_subcollection_ref = article_collection_ref.document(article_id).collection('questions')
        #     for q_data in generated_questions_data:
        #         q_doc_id = q_data.pop('_id', None) # Use provided ID or let Firestore auto-generate
        #         q_data['createdAt'] = firestore.FieldValue.server_timestamp()
        #         q_data['updatedAt'] = firestore.FieldValue.server_timestamp()
        #         # Add other required fields for questions if any
        #         if q_doc_id:
        #             questions_subcollection_ref.document(q_doc_id).set(q_data)
        #         else:
        #             new_q_ref = questions_subcollection_ref.add(q_data) # Store ref if ID needed
        #     click.echo(f"Added {len(generated_questions_data)} comprehension questions to subcollection for article {article_id}.")

    except Exception as e:
        click.echo(f"Error adding article to Firestore: {e}", err=True)
        exit(1)

if __name__ == '__main__':
    # This makes the script executable from the command line.
    # Ensure FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable is set,
    # or pass --key-path argument.
    # Example:
    # export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/path/to/your/serviceAccountKey.json"
    # python english-language-helper/cli/llm_article_generator.py --topic "Climate Change Effects" --level-order 1
    #
    # To see help:
    # python english-language-helper/cli/llm_article_generator.py --help
    generate_article()