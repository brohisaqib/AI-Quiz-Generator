from langchain_groq import ChatGroq
from app.config.settings import Config
from app.prompts.quiz_prompt import QUIZ_PROMPT
from app.schemas.quiz import QuizResponse
from app.utils.logger import get_logger
from app.utils.openai_error_handler import handle_openai_exception, OpenAIServiceError

logger = get_logger("quiz_service")

class QuizService:
    """Service to generate multiple choice quizzes using LangChain structured output (Groq)."""

    def __init__(self) -> None:
        api_key = Config.GROQ_API_KEY
        if not api_key:
            logger.error("Groq API key is missing in quiz service setup")
            raise ValueError("Groq API key is not configured. Please add GROQ_API_KEY to your .env file.")

        # Initialize the LangChain LLM (Groq-hosted Llama model)
        self.llm = ChatGroq(
            model=Config.GROQ_CHAT_MODEL,
            temperature=0.5,
            groq_api_key=api_key,
            max_tokens=4096
        )

        # Use JSON mode for structured output — more reliable than function/tool-calling
        # for large, complex JSON structures like a multi-question quiz.
        self.structured_llm = self.llm.with_structured_output(QuizResponse, method="json_mode")

        self.prompt = QUIZ_PROMPT.partial(format_instructions="")

        self.chain = self.prompt | self.structured_llm

    def generate_quiz(self, summary: str, transcription: str, difficulty: str = "Intermediate") -> QuizResponse:
        """
        Generate multiple choice questions based on summary and transcription.

        Args:
            summary: The generated educational summary.
            transcription: The original transcript text of the video.
            difficulty: Quiz difficulty level — "Beginner", "Intermediate", or "Advanced".
                        Defaults to "Intermediate". Invalid values are silently clamped.

        Returns:
            A QuizResponse Pydantic model containing the title and questions.

        Raises:
            ValueError: If input is invalid.
            OpenAIServiceError: If the Groq call fails (rate limit, auth, timeout, etc.).
        """
        if not summary or not transcription:
            logger.error("Empty summary or transcription provided for quiz generation")
            raise ValueError("Both summary and transcription content are required for quiz generation")

        # Validate difficulty — clamp to safe default on invalid input
        valid_difficulties = {"Beginner", "Intermediate", "Advanced"}
        if not difficulty or difficulty.strip() not in valid_difficulties:
            difficulty = "Intermediate"
        difficulty = difficulty.strip()

        # Truncate transcript to keep total prompt size within Groq's TPM limits
        max_transcript_chars = 4000
        transcription_excerpt = transcription[:max_transcript_chars]

        logger.info(f"Generating educational quiz with structured output (Groq) — difficulty: {difficulty}")

        try:
            quiz_response: QuizResponse = self.chain.invoke({
                "summary": summary,
                "transcription": transcription_excerpt,
                "difficulty_level": difficulty,
            })

            if not quiz_response.questions:
                raise ValueError("Quiz generation returned a quiz with no questions")

            logger.info(f"Quiz generation success. Title: '{quiz_response.title}', Questions: {len(quiz_response.questions)}")
            return quiz_response

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Quiz generation or output validation failed: {str(e)}", exc_info=True)
            raise handle_openai_exception(e, context="Quiz generation")