from pydantic import BaseModel, Field, field_validator
from typing import List

class QuizQuestion(BaseModel):
    """Pydantic model representing a single quiz question."""
    
    question: str = Field(description="The question text itself based on the content of the transcript or summary.")
    options: List[str] = Field(description="List of exactly 4 options for the multiple choice question.")
    answer: str = Field(description="The correct option from the options list. Must match one of the items in the options list exactly.")
    explanation: str = Field(description="Explanation of why this answer is correct based on the transcript.")
    difficulty: str = Field(default="Easy", description="The difficulty level of the question: Easy, Medium, or Hard.")
    topic: str = Field(description="The specific subtopic or concept from the video that this question tests.")

    @field_validator("options")
    @classmethod
    def validate_options_count(cls, value: List[str]) -> List[str]:
        if len(value) != 4:
            raise ValueError("There must be exactly 4 options.")
        return value

    @field_validator("answer")
    @classmethod
    def validate_answer_in_options(cls, value: str, info) -> str:
        options = info.data.get("options")
        if options and value not in options:
            raise ValueError(f"The correct answer '{value}' must be one of the options: {options}")
        return value

class QuizResponse(BaseModel):
    """Pydantic model representing the quiz itself."""
    
    title: str = Field(description="A suitable, catchy and educational title for the quiz.")
    questions: List[QuizQuestion] = Field(description="List of questions generated for the quiz.")

class QuizEvaluation(BaseModel):
    """Pydantic model representing the G-Eval scores for the generated quiz."""
    
    score: float = Field(description="Overall quality score of the quiz from 0.0 to 10.0.")
    feedback: str = Field(description="Detailed pedagogical feedback assessing relevance, clarity, difficulty, coverage, and suggestions for improvement.")

