import json
from langchain_groq import ChatGroq
from app.config.settings import Config
from app.prompts.evaluation_prompt import EVALUATION_PROMPT
from app.schemas.quiz import QuizResponse, QuizEvaluation
from app.utils.logger import get_logger
from app.utils.openai_error_handler import handle_openai_exception, OpenAIServiceError

logger = get_logger("evaluation_service")

class EvaluationService:
    """Service to evaluate generated quizzes using a G-Eval framework powered by LangChain and Groq (Llama)."""

    def __init__(self) -> None:
        api_key = Config.GROQ_API_KEY
        if not api_key:
            logger.error("Groq API key is missing in evaluation service setup")
            raise ValueError("Groq API key is not configured. Please add GROQ_API_KEY to your .env file.")

        # Initialize the LangChain LLM (Groq-hosted Llama model)
        # We use a lower temperature (0.1) for consistent evaluation scores
        self.llm = ChatGroq(
            model=Config.GROQ_EVAL_MODEL,
            temperature=0.1,
            groq_api_key=api_key,
            max_tokens=2048
        )


        # Use JSON mode for structured output — more reliable than function/tool-calling
        self.structured_llm = self.llm.with_structured_output(QuizEvaluation, method="json_mode")

        self.prompt = EVALUATION_PROMPT.partial(format_instructions="")

        self.chain = self.prompt | self.structured_llm

    def evaluate_quiz(self, transcription: str, summary: str, quiz: QuizResponse) -> QuizEvaluation:
        """
        Evaluate a quiz's quality relative to the transcript and summary using G-Eval.

        Args:
            transcription: The original transcript of the video.
            summary: The generated educational summary.
            quiz: The generated QuizResponse object.

        Returns:
            A QuizEvaluation object containing G-Eval score and feedback.

        Raises:
            ValueError: If input arguments are missing.
            OpenAIServiceError: If the Groq call fails (rate limit, auth, timeout, etc.).
        """
        if not transcription or not summary or not quiz:
            logger.error("Missing input data for quiz evaluation")
            raise ValueError("Transcription, summary, and quiz are required for evaluation")

        # Truncate transcript to keep total prompt size within Groq's TPM limits
        max_transcript_chars = 4000
        transcription_excerpt = transcription[:max_transcript_chars]

        logger.info(f"Running G-Eval evaluation on quiz: '{quiz.title}' using Groq")

        try:
            quiz_dict = {
                "title": quiz.title,
                "questions": [q.model_dump() for q in quiz.questions]
            }
            quiz_json_str = json.dumps(quiz_dict, indent=2)

            metrics: QuizEvaluation = self.chain.invoke({
                "transcription": transcription_excerpt,
                "summary": summary,
                "quiz_json": quiz_json_str
            })

            logger.info(
                f"G-Eval completed successfully. Score: {metrics.score}"
            )
            return metrics

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"G-Eval evaluation failed: {str(e)}", exc_info=True)
            raise handle_openai_exception(e, context="Quiz evaluation")