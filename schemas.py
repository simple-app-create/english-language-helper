# english-language-helper/schemas.py
"""
Pydantic models for defining the structure of exam questions and related assets.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional, Any, Dict, Union

from pydantic import BaseModel, Field, model_validator, field_validator


# --- Primitive/Shared Schemas ---


class LocalizedString(BaseModel):
    """A string that has localized versions."""

    en: str
    zh_tw: str


class DifficultyDetail(BaseModel):
    """Detailed difficulty level of a question or asset."""

    stage: str  # e.g., "JUNIOR_HIGH", "SENIOR_HIGH", "ELEMENTARY"
    grade: int  # e.g., 1, 2, 3 representing grade within the stage
    level: int  # Overall difficulty level, e.g., 1-10 scale
    name: LocalizedString  # Human-readable name, e.g., "Junior High - Grade 1"


class ChoiceDetail(BaseModel):
    """A single choice in a multiple-choice question."""

    text: str
    isCorrect: bool


# --- Base Schemas for Questions & Assets ---


class QuestionBase(BaseModel):
    """Base model for all question types, containing common fields."""

    # Firestore document ID will be generated separately and not part of this model
    # questionId: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique ID for the question.")
    difficulty: DifficultyDetail
    learningObjectives: List[str] = Field(
        default_factory=list, description="Tags like 'Past Tense', 'TOEIC Vocabulary'"
    )
    questionText: Optional[str] = Field(
        None,
        description="The main prompt or question for the student (can be LocalizedString in some cases).",
    )
    explanation: Optional[LocalizedString] = Field(
        None, description="Explanation for the correct answer."
    )
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of creation in UTC.",
    )
    updatedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last update in UTC.",
    )
    # Common field for question types to ensure type safety during DB queries/parsing
    questionType: str  # Will be overridden by Literal in specific question types

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")}
        validate_assignment = True  # Ensure values are validated on assignment


class AssetBase(BaseModel):
    """Base model for content assets like passages, audio files, or images."""

    assetId: str = Field(
        description="Unique ID for the asset, typically a UUID hex string."
    )
    title: LocalizedString
    description: Optional[LocalizedString] = Field(
        None, description="A short description of the asset."
    )
    difficulty: DifficultyDetail  # Difficulty level associated with the asset itself
    learningObjectives: List[str] = Field(
        default_factory=list, description="Learning objectives covered by this asset."
    )
    tags: List[str] = Field(
        default_factory=list, description="Keywords or tags associated with the asset."
    )
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] = Field(
        "DRAFT", description="Publication status of the asset."
    )
    version: int = Field(1, description="Version number of the asset.")
    source: Optional[str] = Field(
        None,
        description="Source of the content, e.g., 'Studio Classroom', '2024 University GSAT'.",
    )
    createdBy: Optional[str] = Field(
        None, description="Identifier of the user/process that created this asset."
    )
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of creation in UTC.",
    )
    updatedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last update in UTC.",
    )
    # Common field for asset types
    assetType: str  # Will be overridden by Literal in specific asset types

    class Config:
        """Pydantic model configuration."""

        json_encoders = {datetime: lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")}
        validate_assignment = True


# --- Specific Question Type Schemas ---


class FillInTheBlankQuestion(QuestionBase):
    """Schema for a 'Fill in the Blank' question."""

    questionType: Literal["FILL_IN_THE_BLANK"] = "FILL_IN_THE_BLANK"
    questionText: (
        str  # Overriding to make it mandatory and not LocalizedString for this type
    )
    # Example: "The quick brown fox {0} over the lazy dog."
    # Blanks are identified by placeholders like {0}, {1}, etc.
    # Or, if blanks are implicit (e.g., represented by underscores in questionText),
    # then acceptableAnswers would correspond to these blanks in order.

    acceptableAnswers: List[List[str]] = Field(
        description="List of lists of acceptable answers. Each inner list corresponds to a blank. "
        "e.g., [['jumps', 'jumped'], ['sleeping', 'lazy']]"
    )
    # If allowing multiple correct answers for a single blank:
    # Example: "The color of the sky is {0} or sometimes {1}."
    # acceptableAnswers = [["blue"], ["gray", "grey"]]

    @model_validator(mode="after")
    def check_answers_logic(self) -> "FillInTheBlankQuestion":
        if not self.acceptableAnswers or not all(self.acceptableAnswers):
            raise ValueError(
                "For FILL_IN_THE_BLANK, 'acceptableAnswers' must be a non-empty list, "
                "and each inner list (for each blank) must also be non-empty."
            )
        # Optional: Add validation to check if number of answer lists matches number of blanks in questionText
        return self


class TranslationQuestion(QuestionBase):
    """Schema for a 'Translation' question."""

    questionType: Literal["TRANSLATION"] = "TRANSLATION"
    sourceText: LocalizedString = Field(description="The text to be translated.")
    targetLanguage: Literal["en", "zh_tw"] = Field(
        description="The language to translate into."
    )
    acceptableTranslations: List[str] = Field(
        description="List of acceptable translations in the target language."
    )


class PictureDescriptionQuestion(QuestionBase):
    """Schema for a 'Picture Description' question."""

    questionType: Literal["PICTURE_DESCRIPTION"] = "PICTURE_DESCRIPTION"
    imageAssetId: str = Field(
        description="ID of the AssetDocument representing the image."
    )
    # questionText is inherited, e.g., "Describe what you see in the picture."
    # Evaluation would typically be manual or AI-assisted based on keywords/rubrics.
    suggestedKeywords: Optional[List[str]] = Field(
        None, description="Keywords that might be expected in the description."
    )


class ReadingComprehensionQuestion(QuestionBase):
    """Schema for a 'Reading Comprehension' question, tied to a passage."""

    questionType: Literal["READING_COMPREHENSION"] = "READING_COMPREHENSION"
    contentAssetId: str = Field(
        description="ID of the AssetDocument (e.g., a reading passage)."
    )
    choices: Optional[List[ChoiceDetail]] = Field(
        None, description="List of choices if this is a multiple-choice question."
    )
    acceptableAnswers: Optional[List[str]] = Field(
        None, description="List of acceptable answers if this is a text-input question."
    )

    @model_validator(mode="after")
    def check_answers_logic(self) -> "ReadingComprehensionQuestion":
        if self.choices is not None and self.acceptableAnswers is not None:
            raise ValueError(
                "For READING_COMPREHENSION, 'choices' and 'acceptableAnswers' cannot both be provided."
            )
        if self.choices is None and self.acceptableAnswers is None:
            raise ValueError(
                "For READING_COMPREHENSION, either 'choices' or 'acceptableAnswers' must be provided."
            )
        if self.choices is not None:
            correct_choices_count = sum(
                1 for choice in self.choices if choice.isCorrect
            )
            if correct_choices_count != 1:
                raise ValueError(
                    "For multiple-choice READING_COMPREHENSION questions, exactly one choice must be correct."
                )
        return self


class ListeningComprehensionQuestion(QuestionBase):
    """Schema for a 'Listening Comprehension' question, tied to an audio asset."""

    questionType: Literal["LISTENING_COMPREHENSION"] = "LISTENING_COMPREHENSION"
    audioAssetId: str = Field(
        description="ID of the AssetDocument (e.g., an audio clip)."
    )
    # questionText is inherited, e.g., "What is the main topic of the conversation?"
    choices: Optional[List[ChoiceDetail]] = Field(
        None, description="List of choices if this is a multiple-choice question."
    )
    acceptableAnswers: Optional[List[str]] = Field(
        None, description="List of acceptable answers if this is a text-input question."
    )

    @model_validator(mode="after")
    def check_answers_logic(self) -> "ListeningComprehensionQuestion":
        if self.choices is not None and self.acceptableAnswers is not None:
            raise ValueError(
                "For LISTENING_COMPREHENSION, 'choices' and 'acceptableAnswers' cannot both be provided."
            )
        if self.choices is None and self.acceptableAnswers is None:
            raise ValueError(
                "For LISTENING_COMPREHENSION, either 'choices' or 'acceptableAnswers' must be provided."
            )
        if self.choices is not None:
            correct_choices_count = sum(
                1 for choice in self.choices if choice.isCorrect
            )
            if correct_choices_count != 1:
                raise ValueError(
                    "For multiple-choice LISTENING_COMPREHENSION questions, exactly one choice must be correct."
                )
        return self


class SpellingCorrectionQuestion(QuestionBase):
    """Schema for a 'Spelling Correction' question."""

    questionType: Literal["SPELLING_CORRECTION"] = "SPELLING_CORRECTION"
    # questionText is inherited: "Choose the correctly spelled word" or "Identify the misspelled word in the sentence below:"
    # If the task is to choose the correct word from a list:
    wordChoices: Optional[List[str]] = Field(
        None,
        description="List of words, one of which is correctly spelled (or one misspelled).",
    )
    correctWord: Optional[str] = Field(
        None,
        description="The correctly spelled word among the choices, or the correct spelling if sentence-based.",
    )
    # If the task is to identify and correct a misspelled word in a sentence:
    sentenceWithMisspelledWord: Optional[str] = Field(
        None, description="A sentence containing one misspelled word."
    )
    misspelledWordInSentence: Optional[str] = Field(
        None,
        description="The specific word that is misspelled in the sentence (if applicable).",
    )
    # correctWord field would then hold the correct spelling of misspelledWordInSentence

    @model_validator(mode="after")
    def check_spelling_correction_logic(self) -> "SpellingCorrectionQuestion":
        if self.wordChoices and self.sentenceWithMisspelledWord:
            raise ValueError(
                "For SPELLING_CORRECTION, provide 'wordChoices' (and 'correctWord') OR "
                "'sentenceWithMisspelledWord' (and 'misspelledWordInSentence', 'correctWord'), but not both types."
            )
        if self.wordChoices:
            if not self.correctWord:
                raise ValueError(
                    "If 'wordChoices' is provided, 'correctWord' must also be provided."
                )
            if self.correctWord not in self.wordChoices:
                # This validation might be too strict if LLM generates near-misses or if correctWord is a normalized form.
                # For now, assuming direct presence.
                # Consider a more flexible validation if necessary.
                # raise ValueError("'correctWord' must be one of the 'wordChoices'.")
                pass  # Relaxing this for now
        elif self.sentenceWithMisspelledWord:
            if not self.misspelledWordInSentence or not self.correctWord:
                raise ValueError(
                    "If 'sentenceWithMisspelledWord' is provided, "
                    "'misspelledWordInSentence' and 'correctWord' must also be provided."
                )
            # Could add validation: misspelledWordInSentence should be in sentenceWithMisspelledWord
            # if self.misspelledWordInSentence not in self.sentenceWithMisspelledWord.split():
            #     raise ValueError("'misspelledWordInSentence' must appear in 'sentenceWithMisspelledWord'.")
        else:
            raise ValueError(
                "For SPELLING_CORRECTION, either 'wordChoices' or 'sentenceWithMisspelledWord' setup must be provided."
            )
        return self


# --- Specific Asset Type Schemas ---


class PassageAsset(AssetBase):
    """Schema for a reading passage asset."""

    assetType: Literal["PASSAGE"] = "PASSAGE"
    content: str = Field(description="The full text of the reading passage.")
    # wordCount: Optional[int] = Field(None, description="Approximate word count of the passage.")
    # readabilityScore: Optional[Dict[str, float]] = Field(None, description="Readability scores, e.g., Flesch-Kincaid.")


class AudioAsset(AssetBase):
    """Schema for an audio asset."""

    assetType: Literal["AUDIO"] = "AUDIO"
    audioUrl: str = Field(description="URL to the audio file (e.g., path in GCS).")
    durationSeconds: Optional[float] = Field(
        None, description="Duration of the audio in seconds."
    )
    transcript: Optional[str] = Field(
        None, description="Full transcript of the audio content, if available."
    )
    speakerInfo: Optional[List[str]] = Field(
        None, description="Information about speakers, if multiple."
    )


class ImageAsset(AssetBase):
    """Schema for an image asset."""

    assetType: Literal["IMAGE"] = "IMAGE"
    imageUrl: str = Field(description="URL to the image file (e.g., path in GCS).")
    # altText: Optional[LocalizedString] = Field(None, description="Alternative text for accessibility.")


# Union type for all question models - useful for type hinting or processing generic question lists
AnyQuestionType = Union[
    FillInTheBlankQuestion,
    TranslationQuestion,
    PictureDescriptionQuestion,
    ReadingComprehensionQuestion,
    ListeningComprehensionQuestion,
    SpellingCorrectionQuestion,
]

# Union type for all asset models
AnyAssetType = Union[
    PassageAsset,
    AudioAsset,
    ImageAsset,
]

# --- Top-Level Model for GenAI Response ---


class GeneratedReadingMaterial(BaseModel):
    """
    Represents the complete JSON structure returned by the GenAI process
    for reading comprehension material.
    """

    passageAsset: PassageAsset
    questions_list: List[
        AnyQuestionType
    ]  # AnyQuestionType will be defined shortly after

    class Config:
        """Pydantic model configuration."""

        validate_assignment = True
        # json_encoders are handled by child models like AssetBase, QuestionBase


# Example of how to use UTC for default_factory if needed more broadly
# def now_utc():
# return datetime.now(timezone.utc)
