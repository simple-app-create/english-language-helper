# schemas.py
from datetime import datetime
from typing import Literal, Optional, List, Union, Annotated
from pydantic import BaseModel, HttpUrl, Field, model_validator


# --- Common Reusable Models ---
class LocalizedString(BaseModel):
    """A string that has localized versions."""

    en: str
    zh_tw: str


class DifficultyDetail(BaseModel):
    """Detailed difficulty level of a question."""

    stage: str  # e.g., "JUNIOR_HIGH", "SENIOR_HIGH", "ELEMENTARY" (actual values TBD)
    grade: int  # e.g., 1, 2, 3 representing grade within the stage
    level: int  # Overall difficulty level, e.g., 1-10 scale
    name: LocalizedString  # Human-readable name, e.g., "Junior High - Grade 1"


class ChoiceDetail(BaseModel):
    """A single choice in a multiple-choice question."""

    text: str
    isCorrect: bool


# --- Base Question Model ---
# Contains fields truly common to all question types after discrimination.
# `questionType` itself will be a Literal in each specific model.
class QuestionBase(BaseModel):
    """Base model for all question types, containing common fields."""

    difficulty: DifficultyDetail
    learningObjectives: List[str] = Field(
        default_factory=list, description="Tags like 'Past Tense', 'TOEIC Vocabulary'"
    )
    questionText: Optional[str] = Field(
        None, description="The main prompt or question for the student."
    )
    explanation: Optional[LocalizedString] = Field(
        None, description="Explanation for the correct answer."
    )
    createdAt: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of creation in UTC."
    )
    updatedAt: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of last update in UTC."
    )

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            # Ensure datetime is encoded in ISO format with 'Z'
            datetime: lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if dt.tzinfo is None
            else dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        }


# --- Specific Question Type Models ---


class FillInTheBlankQuestion(QuestionBase):
    """Schema for a 'Fill in the Blank' question."""

    questionType: Literal["FILL_IN_THE_BLANK"]
    answerInputType: Literal["MULTIPLE_CHOICE", "TEXT_INPUT"]
    sentenceTemplate: str = Field(
        description="Sentence with a ___ placeholder for the blank."
    )
    choices: Optional[List[ChoiceDetail]] = Field(
        None, description="List of choices if answerInputType is MULTIPLE_CHOICE."
    )
    acceptableAnswers: Optional[List[str]] = Field(
        None,
        description="List of acceptable string answers if answerInputType is TEXT_INPUT.",
    )

    @model_validator(mode="after")
    def check_answers_logic(self) -> "FillInTheBlankQuestion":
        """Validate that choices/acceptableAnswers match answerInputType."""
        if self.answerInputType == "MULTIPLE_CHOICE":
            if self.choices is None:
                raise ValueError(
                    "For FILL_IN_THE_BLANK with MULTIPLE_CHOICE, 'choices' must be provided."
                )
            if self.acceptableAnswers is not None:
                raise ValueError(
                    "For FILL_IN_THE_BLANK with MULTIPLE_CHOICE, 'acceptableAnswers' must not be provided."
                )
        elif self.answerInputType == "TEXT_INPUT":
            if self.acceptableAnswers is None:
                raise ValueError(
                    "For FILL_IN_THE_BLANK with TEXT_INPUT, 'acceptableAnswers' must be provided."
                )
            if self.choices is not None:
                raise ValueError(
                    "For FILL_IN_THE_BLANK with TEXT_INPUT, 'choices' must not be provided."
                )
        return self


class TranslationQuestion(QuestionBase):
    """Schema for a 'Sentence Translation' question."""

    questionType: Literal["TRANSLATION"]
    sourceSentence: str = Field(description="The sentence to be translated.")
    sourceLanguage: Literal["EN", "ZH_TW"] = Field(
        description="Language of the sourceSentence."
    )
    # For translation, the answer is typically text input.
    # The `explanation` field would contain the correct translation or notes.
    # `acceptableAnswers` could be used if specific variations are allowed, but not explicitly in schema.


class PictureDescriptionQuestion(QuestionBase):
    """Schema for a 'Picture Description' question."""

    questionType: Literal["PICTURE_DESCRIPTION"]
    imageUrl: HttpUrl = Field(description="URL of the image to be described.")
    # Answer is typically text input. `explanation` would cover key points.


class ReadingComprehensionQuestion(QuestionBase):
    """Schema for a 'Reading Comprehension' question, tied to a passage."""

    questionType: Literal["READING_COMPREHENSION"]
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
        """Validate that either choices or acceptableAnswers is provided, but not both."""
        if self.choices is not None and self.acceptableAnswers is not None:
            raise ValueError(
                "For READING_COMPREHENSION, 'choices' and 'acceptableAnswers' cannot both be provided."
            )
        if self.choices is None and self.acceptableAnswers is None:
            raise ValueError(
                "For READING_COMPREHENSION, either 'choices' or 'acceptableAnswers' must be provided."
            )
        return self


class ListeningComprehensionQuestion(QuestionBase):
    """Schema for a 'Listening Comprehension' question, tied to an audio asset."""

    questionType: Literal["LISTENING_COMPREHENSION"]
    contentAssetId: str = Field(
        description="ID of the AssetDocument (e.g., an audio clip)."
    )
    choices: Optional[List[ChoiceDetail]] = Field(
        None, description="List of choices if this is a multiple-choice question."
    )
    acceptableAnswers: Optional[List[str]] = Field(
        None, description="List of acceptable answers if this is a text-input question."
    )

    @model_validator(mode="after")
    def check_answers_logic(self) -> "ListeningComprehensionQuestion":
        """Validate that either choices or acceptableAnswers is provided, but not both."""
        if self.choices is not None and self.acceptableAnswers is not None:
            raise ValueError(
                "For LISTENING_COMPREHENSION, 'choices' and 'acceptableAnswers' cannot both be provided."
            )
        if self.choices is None and self.acceptableAnswers is None:
            raise ValueError(
                "For LISTENING_COMPREHENSION, either 'choices' or 'acceptableAnswers' must be provided."
            )
        return self


class SpellingCorrectionQuestion(QuestionBase):
    """Schema for a 'Spelling Correction' question."""

    questionType: Literal["SPELLING_CORRECTION"]
    answerInputType: Literal["MULTIPLE_CHOICE", "TEXT_INPUT"]
    choices: Optional[List[ChoiceDetail]] = Field(
        None, description="List of choices if answerInputType is MULTIPLE_CHOICE."
    )
    incorrectSpelling: Optional[str] = Field(
        None,
        description="The incorrectly spelled word if answerInputType is TEXT_INPUT.",
    )
    acceptableAnswers: Optional[List[str]] = Field(
        None,
        description="List of acceptable correct spellings if answerInputType is TEXT_INPUT.",
    )

    @model_validator(mode="after")
    def check_spelling_correction_logic(self) -> "SpellingCorrectionQuestion":
        """Validate that fields match answerInputType for Spelling Correction."""
        if self.answerInputType == "MULTIPLE_CHOICE":
            if self.choices is None:
                raise ValueError(
                    "For SPELLING_CORRECTION with MULTIPLE_CHOICE, 'choices' must be provided."
                )
            if self.incorrectSpelling is not None:
                raise ValueError(
                    "For SPELLING_CORRECTION with MULTIPLE_CHOICE, 'incorrectSpelling' must not be provided."
                )
            if self.acceptableAnswers is not None:
                raise ValueError(
                    "For SPELLING_CORRECTION with MULTIPLE_CHOICE, 'acceptableAnswers' must not be provided."
                )
            # Ensure at least one choice is marked as correct
            if not any(choice.isCorrect for choice in self.choices):
                raise ValueError(
                    "For SPELLING_CORRECTION with MULTIPLE_CHOICE, at least one choice must be marked as correct."
                )
        elif self.answerInputType == "TEXT_INPUT":
            if self.incorrectSpelling is None:
                raise ValueError(
                    "For SPELLING_CORRECTION with TEXT_INPUT, 'incorrectSpelling' must be provided."
                )
            if self.acceptableAnswers is None or not self.acceptableAnswers:
                raise ValueError(
                    "For SPELLING_CORRECTION with TEXT_INPUT, 'acceptableAnswers' must be provided and non-empty."
                )
            if self.choices is not None:
                raise ValueError(
                    "For SPELLING_CORRECTION with TEXT_INPUT, 'choices' must not be provided."
                )
        return self


# --- Discriminated Union for all Question Types ---
# This allows Pydantic to determine the correct model based on the 'questionType' field.
QuestionDocument = Annotated[
    Union[
        FillInTheBlankQuestion,
        TranslationQuestion,
        PictureDescriptionQuestion,
        ReadingComprehensionQuestion,
        ListeningComprehensionQuestion,
        SpellingCorrectionQuestion,
    ],
    Field(discriminator="questionType"),
]


# --- Asset Models ---
# `assetId` is the Firestore document ID, not a field within the document data itself.
class AssetBase(BaseModel):
    """Base model for content assets."""

    # assetType: Will be Literal in specific models
    title: LocalizedString
    source: Optional[str] = Field(
        None,
        description="Source of the content, e.g., 'Studio Classroom', '2024 University GSAT'.",
    )
    createdAt: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of creation in UTC."
    )

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            datetime: lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if dt.tzinfo is None
            else dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        }


class PassageAsset(AssetBase):
    """Schema for a reading passage asset."""

    assetType: Literal["PASSAGE"]
    content: str = Field(description="The full text of the reading passage.")


class AudioAsset(AssetBase):
    """Schema for an audio asset."""

    assetType: Literal["AUDIO"]
    audioUrl: HttpUrl = Field(description="URL to the audio file in Cloud Storage.")
    durationSeconds: int = Field(description="Duration of the audio in seconds.", gt=0)


# --- Discriminated Union for all Asset Types ---
AssetDocument = Annotated[
    Union[
        PassageAsset,
        AudioAsset,
    ],
    Field(discriminator="assetType"),
]

# Example Usage (for testing or understanding)
if __name__ == "__main__":
    # Example: Fill in the Blank - Multiple Choice
    fitb_mc_data = {
        "questionType": "FILL_IN_THE_BLANK",
        "difficulty": {
            "stage": "JUNIOR_HIGH",
            "grade": 1,
            "level": 7,
            "name": {"en": "Junior High - Grade 1", "zh_tw": "國中一年級"},
        },
        "learningObjectives": ["Vocabulary", "Present Simple"],
        "questionText": "Choose the correct word to complete the sentence.",
        "explanation": {
            "en": "'runs' is correct because the subject is singular.",
            "zh_tw": "主詞是單數，所以用 'runs'。",
        },
        "sentenceTemplate": "He ___ to school every day.",
        "answerInputType": "MULTIPLE_CHOICE",
        "choices": [
            {"text": "run", "isCorrect": False},
            {"text": "runs", "isCorrect": True},
            {"text": "running", "isCorrect": False},
        ],
        "createdAt": "2023-01-01T12:00:00Z",  # Example timestamp
        "updatedAt": "2023-01-01T12:00:00Z",
    }
    question_doc = FillInTheBlankQuestion(**fitb_mc_data)
    print("Parsed FITB MC Question:")
    print(question_doc.model_dump_json(indent=2))

    # Example: Reading Comprehension - Text Input
    rc_ti_data = {
        "questionType": "READING_COMPREHENSION",
        "difficulty": {
            "stage": "SENIOR_HIGH",
            "grade": 2,
            "level": 8,
            "name": {"en": "Senior High - Grade 2", "zh_tw": "高中二年級"},
        },
        "contentAssetId": "passage_xyz123",
        "questionText": "What is the main idea of the second paragraph?",
        "acceptableAnswers": [
            "The impact of technology on communication.",
            "Technology's effect on how people communicate.",
        ],
        "explanation": {
            "en": "The paragraph discusses how smartphones and social media changed communication.",
            "zh_tw": "該段落討論了智能手機和社交媒體如何改變了溝通方式。",
        },
        "createdAt": "2023-01-02T14:30:00Z",
        "updatedAt": "2023-01-02T15:00:00Z",
    }
    rc_question = ReadingComprehensionQuestion(**rc_ti_data)
    print("\nParsed Reading Comp TI Question:")
    print(rc_question.model_dump_json(indent=2))

    # Example: Passage Asset
    passage_data = {
        "assetType": "PASSAGE",
        "title": {"en": "The History of Computers", "zh_tw": "計算機的歷史"},
        "source": "Tech Magazine",
        "content": "Computers have evolved significantly over the past century...",
        "createdAt": "2023-01-03T10:00:00Z",
    }
    asset_doc = PassageAsset(**passage_data)
    print("\nParsed Passage Asset:")
    print(asset_doc.model_dump_json(indent=2))

    # Example: Spelling Correction - Multiple Choice
    sc_mc_data = {
        "questionType": "SPELLING_CORRECTION",
        "difficulty": {
            "stage": "ELEMENTARY",
            "grade": 5,
            "level": 3,
            "name": {"en": "Elementary - Grade 5", "zh_tw": "國小五年級"},
        },
        "learningObjectives": ["Vocabulary", "Spelling"],
        "questionText": "Choose the correctly spelled word.",
        "answerInputType": "MULTIPLE_CHOICE",
        "choices": [
            {"text": "recieve", "isCorrect": False},
            {"text": "receive", "isCorrect": True},
            {"text": "receeve", "isCorrect": False},
            {"text": "reciver", "isCorrect": False},
        ],
        "explanation": {
            "en": "The correct spelling is 'receive'. Remember 'i before e except after c'.",
            "zh_tw": "正確的拼寫是 'receive'。請記住 'i before e except after c' 這個規則。",
        },
        "createdAt": "2023-01-04T10:00:00Z",
        "updatedAt": "2023-01-04T10:00:00Z",
    }
    sc_mc_question = SpellingCorrectionQuestion(**sc_mc_data)
    print("\nParsed Spelling Correction MC Question:")
    print(sc_mc_question.model_dump_json(indent=2))

    # Example: Spelling Correction - Text Input
    sc_ti_data = {
        "questionType": "SPELLING_CORRECTION",
        "difficulty": {
            "stage": "JUNIOR_HIGH",
            "grade": 1,
            "level": 4,
            "name": {"en": "Junior High - Grade 1", "zh_tw": "國中一年級"},
        },
        "learningObjectives": ["Spelling"],
        "questionText": "Correct the spelling of the given word.",
        "incorrectSpelling": "acomodate",
        "answerInputType": "TEXT_INPUT",
        "acceptableAnswers": ["accommodate"],
        "explanation": {
            "en": "The word 'accommodate' has double 'c' and double 'm'.",
            "zh_tw": "單字 'accommodate' 有兩個 'c' 和兩個 'm'。",
        },
        "createdAt": "2023-01-05T11:00:00Z",
        "updatedAt": "2023-01-05T11:00:00Z",
    }
    sc_ti_question = SpellingCorrectionQuestion(**sc_ti_data)
    print("\nParsed Spelling Correction TI Question:")
    print(sc_ti_question.model_dump_json(indent=2))
