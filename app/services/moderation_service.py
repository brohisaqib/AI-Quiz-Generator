"""
Content Moderation Service

Uses the same Groq/LangChain pattern as SummaryService and EvaluationService
to classify source text as SAFE or UNSAFE before the main quiz-generation
pipeline runs.  Keeps moderation isolated in its own LLM call so it can be
tuned or disabled independently without touching any other service.
"""

from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser

from app.config.settings import Config
from app.prompts.moderation_prompt import MODERATION_PROMPT
from app.utils.logger import get_logger

logger = get_logger("moderation_service")

# Maximum characters of source text sent to the moderation LLM.
# Consistent with the truncation already used in evaluation_service.py.
_MODERATION_CHAR_LIMIT: int = 4000


class ModerationService:
    """Classify source text as safe or unsafe before quiz generation begins.

    Uses a dedicated Groq LLM call to evaluate content according to the
    platform's content policy.  Fail-open on parse errors so that a
    transient formatting issue in the LLM response never falsely blocks
    legitimate educational content.
    """

    def __init__(self) -> None:
        api_key = Config.GROQ_API_KEY
        if not api_key:
            logger.error("Groq API key is missing in moderation service setup")
            raise ValueError(
                "Groq API key is not configured. "
                "Please add GROQ_API_KEY to your .env file."
            )

        # Mirror the exact ChatGroq initialisation pattern from summary_service.py.
        # Use GROQ_CHAT_MODEL (fast, cheap) — moderation is a simple binary task.
        self.llm = ChatGroq(
            model=Config.GROQ_CHAT_MODEL,
            temperature=0.0,  # deterministic for classification
            groq_api_key=api_key,
        )

        # Build LangChain pipeline identical to SummaryService
        self.chain = MODERATION_PROMPT | self.llm | StrOutputParser()

    def check_content(self, text: str, source_type: str) -> tuple[bool, str]:
        """Classify content as safe or unsafe for quiz generation.

        Truncates *text* to the first ``_MODERATION_CHAR_LIMIT`` characters
        before sending to the LLM, consistent with how evaluation_service.py
        already truncates transcripts to control token usage.

        Fails **open** on LLM parse errors (returns ``(True, "")`` with a
        WARNING log) so that a formatting hiccup never falsely blocks
        legitimate content.

        Args:
            text: The full source text (transcript, PDF content, web search
                results, etc.) to evaluate.
            source_type: A short label for the content origin, e.g. ``"video"``,
                ``"pdf"``, ``"topic"``, or ``"youtube"``.  Passed to the prompt
                for context.

        Returns:
            A ``(is_safe, reason)`` tuple where:
            - ``is_safe`` is ``True`` when the content is acceptable, or
              ``False`` when the LLM flagged it.
            - ``reason`` is an empty string when safe, or a short human-readable
              explanation when unsafe (never contains the flagged text).

        Raises:
            Exception: Re-raises unexpected LLM / network errors so that the
                caller can handle them according to the existing pipeline
                error-handling conventions.
        """
        if not text or not text.strip():
            logger.warning(
                "ModerationService.check_content called with empty text — "
                "skipping check and returning safe."
            )
            return True, ""

        content_excerpt = text[:_MODERATION_CHAR_LIMIT]

        logger.info(
            "Running content moderation check. source_type=%s, "
            "content_length=%d chars (truncated to %d).",
            source_type,
            len(text),
            len(content_excerpt),
        )

        try:
            raw_response: str = self.chain.invoke(
                {"content": content_excerpt, "source_type": source_type}
            )
        except Exception as e:
            logger.error(
                "Moderation LLM call raised an exception: %s. "
                "Failing open (treating as SAFE) to avoid false rejection.",
                e,
                exc_info=True,
            )
            raise  # let the route's outer except handle it

        return self._parse_response(raw_response, source_type)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(
        self, raw: str, source_type: str
    ) -> tuple[bool, str]:
        """Parse the LLM's raw classification response.

        Expected formats::

            SAFE

            UNSAFE | <category>
            <one-sentence reason>

        Fails open (returns ``(True, "")`` with a WARNING) if the response
        cannot be cleanly parsed, to prevent false positives on format issues.

        Args:
            raw: The raw string returned by the LLM.
            source_type: Used only for log context.

        Returns:
            ``(is_safe, reason)`` tuple.
        """
        if not raw:
            logger.warning(
                "Moderation LLM returned an empty response for source_type=%s. "
                "Failing open (SAFE).",
                source_type,
            )
            return True, ""

        first_line = raw.strip().splitlines()[0].strip().upper()

        if first_line.startswith("SAFE"):
            logger.info(
                "Moderation check PASSED (SAFE). source_type=%s.", source_type
            )
            return True, ""

        if first_line.startswith("UNSAFE"):
            # Extract category from "UNSAFE | <category>"
            category = ""
            if "|" in first_line:
                category = first_line.split("|", 1)[1].strip()

            # Extract reason from the second line if present
            lines = raw.strip().splitlines()
            reason_line = lines[1].strip() if len(lines) > 1 else ""
            reason = reason_line if reason_line else f"Content flagged as: {category or 'harmful'}"

            logger.warning(
                "Moderation check FAILED (UNSAFE). source_type=%s, "
                "category=%s, reason=%s",
                source_type,
                category,
                reason,
            )
            return False, reason

        # Unrecognised verdict — fail open to avoid false blocking
        logger.warning(
            "Moderation LLM returned an unrecognised verdict for source_type=%s: %r. "
            "Failing open (SAFE) to avoid false rejection.",
            source_type,
            raw[:120],
        )
        return True, ""
