from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.config.settings import Config
from app.prompts.summary_prompt import SUMMARY_PROMPT
from app.utils.logger import get_logger
from app.utils.openai_error_handler import handle_openai_exception, OpenAIServiceError

logger = get_logger("summary_service")

class SummaryService:
    """Service to generate educational summaries from video transcripts using LangChain and Groq (Llama)."""

    def __init__(self) -> None:
        api_key = Config.GROQ_API_KEY
        if not api_key:
            logger.error("Groq API key is missing in summary service setup")
            raise ValueError("Groq API key is not configured. Please add GROQ_API_KEY to your .env file.")

        # Initialize LangChain LLM (Groq-hosted Llama model)
        self.llm = ChatGroq(
            model=Config.GROQ_CHAT_MODEL,
            temperature=0.3,
            groq_api_key=api_key
        )

        # Build LangChain pipeline
        self.chain = SUMMARY_PROMPT | self.llm | StrOutputParser()

    def generate_summary(self, transcription: str) -> str:
        """
        Generate a structured educational summary from a transcription.

        Args:
            transcription: The full transcription text of the video.

        Returns:
            The generated markdown summary.

        Raises:
            ValueError: If transcription is empty.
            OpenAIServiceError: If the Groq call fails (rate limit, auth, timeout, etc.).
            RuntimeError: If summary generation fails for any other reason.
        """
        if not transcription or not transcription.strip():
            logger.error("Empty transcription provided for summarization")
            raise ValueError("Transcription content is empty")

        logger.info("Generating educational summary using LangChain and Groq")

        try:
            summary = self.chain.invoke({"transcription": transcription})
            summary_clean = summary.strip()

            if not summary_clean:
                raise ValueError("LLM returned an empty summary response")

            logger.info(f"Summary generation success. Length: {len(summary_clean)} characters.")
            return summary_clean

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}", exc_info=True)
            raise handle_openai_exception(e, context="Summary generation")