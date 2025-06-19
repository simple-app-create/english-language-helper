# Programming Style Guide

This document defines the preferred programming style for the English Language Helper project.

## Core Philosophy

Write **concise but pythonic** code that is:
- Clean and professional
- Readable but tight
- Efficient without sacrificing clarity
- Reuse functions through importing from other modules if possible
- Follow the DRY (Don't Repeat Yourself) principle
- Group and Separate functions in modules in logical manner

## Python Style Preferences

### 1. Use Python Idioms
- **List comprehensions** over explicit loops when clear
- **enumerate()** for indexed iterations
- **dict.get()** with defaults instead of key checking
- **Unpacking** and **multiple assignment** where appropriate

```python
# Good
questions = [q.to_dict() for q in question_docs]
for i, item in enumerate(items, 1):

# Avoid
questions = []
for q in question_docs:
    questions.append(q.to_dict())
```

### 2. Concise Variable Names
- Use **short but clear** names when context is obvious
- Use **descriptive but concise** names when context is not obvious
- `db` instead of `database_client`
- `q` instead of `question_data` in tight loops
- `ctx` instead of `context`

### 3. Combine Operations
- Chain operations when logical
- Combine assignments and checks
- Use inline conditionals for simple cases

```python
# Good
questions = list(article_ref.collection('questions').stream())
marker = " ✓" if choice['id'] == q.get('correctAnswer') else ""

# Avoid
questions_ref = article_ref.collection('questions')
questions_stream = questions_ref.stream()
questions = list(questions_stream)
```

### 4. Error Handling
- **Concise error messages** without excessive detail
- Early returns/exits to reduce nesting
- Handle the most common case first

```python
# Good
if not db:
    click.echo("Database client not found.", err=True)
    ctx.exit(1)

# Avoid
if db is None:
    click.echo("Database client not found in context. Cannot perform operation.", err=True)
    click.echo("Please ensure Firebase initialization succeeded.", err=True)
```

### 5. Type Hints
- Always use type hints for function parameters and return values
- Use descriptive custom types when appropriate
- Leverage Union/Optional for flexibility
- Import types from collections.abc instead of typing where possible

```python
# Good
def get_article(art_id: str) -> dict[str, Any]:
    """Fetch article from database.

    Args:
        art_id: Unique identifier of article

    Returns:
        Article data as dictionary

    Raises:
        NotFoundError: If article doesn't exist
    """
    return db.collection('articles').document(art_id).get().to_dict()

# Avoid
def get_article(art_id):
    return db.collection('articles').document(art_id).get().to_dict()
```

### 6. Function Documentation
- Every function must have a docstring
- Use Google style docstrings with Args/Returns/Raises sections
- Keep descriptions concise but complete
- Document all parameters, return values and exceptions
- Include type information in descriptions

```python
def process_text(text: str, max_len: int | None = None) -> list[str]:
    """Process and split text into sentences.

    Args:
        text: Raw text to process
        max_len: Optional maximum length per sentence

    Returns:
        List of processed sentences

    Raises:
        ValueError: If text is empty
        MaxLengthError: If sentence exceeds max_len
    """
    if not text:
        raise ValueError("Empty text")
    # Implementation
```

### 7. Function Structure
- Keep functions **focused and short**
- Remove unnecessary comments when code is self-explanatory
- Use meaningful function/variable names instead of comments
- Prefer guard clauses over nested if statements

### 8. Import Style
- Group imports: standard library, third-party, local
- Use specific imports when only using a few items
- Avoid wildcard imports

### 9. String Formatting
- Use **f-strings** for readability
- Keep format strings concise
- Use `.get()` with defaults for dict access in strings

```python
# Good
click.echo(f"Article: {article_doc.get('title')}")
click.echo(f"Q{i}: {q.get('questionTextEnglish')}")

# Avoid
click.echo("Article: {}".format(article_doc.get('title', 'No title')))
```

## Code Organization

### File Structure
- Keep related functionality together
- Use clear, descriptive module names
- Separate concerns (CLI, utils, models)

### Function Length
- **Aim for 15-25 lines** per function
- Break down complex operations into smaller functions
- Each function should do one thing well

## What to Avoid

- Excessive verbosity in variable names
- Unnecessary intermediate variables
- Over-commenting obvious code
- Deeply nested if statements
- Long parameter lists (use objects/dicts instead)
- Repetitive error handling patterns

## Examples

### Before (Untyped & Undocumented)
```python
def process_article_data(doc):
    data = doc.to_dict()
    click.echo(f"Processing: {data.get('title')}")
    return data.get('hasComprehensionQuestions', False)
```

### After (Typed & Documented)
```python
def process_article_data(doc: DocumentSnapshot) -> bool:
    """Process Firestore article document.

    Args:
        doc: Firestore document snapshot

    Returns:
        Whether article has comprehension questions
    """
    data = doc.to_dict()
    click.echo(f"Processing: {data.get('title')}")
    return data.get('hasComprehensionQuestions', False)
```

---

*This style guide should be referenced in future development to maintain consistency across the codebase.*
