from langchain_core.prompts import PromptTemplate

# ---------------------------------------------------------------------------
# Moderation / Guardrails prompt
# ---------------------------------------------------------------------------
# Instructs the LLM to classify source text as SAFE or UNSAFE before any
# expensive summary / quiz generation is attempted.  The prompt is
# deliberately balanced: educational or documentary discussion of serious
# topics (history, science, news, anatomy) must NOT be flagged; only content
# that is itself graphic, instructional in a harmful way, or promotes/
# glorifies harmful acts should be flagged.
# ---------------------------------------------------------------------------

moderation_system_prompt = (
    "You are a content-moderation classifier. Your sole task is to decide "
    "whether the provided text is appropriate for an educational quiz-generation "
    "platform used by general audiences, including students and professionals.\n\n"
    "CLASSIFICATION RULES — read carefully:\n"
    "1. Respond with EXACTLY one of two verdicts on the first line: SAFE or UNSAFE.\n"
    "2. If UNSAFE, follow the verdict on the same line with a pipe character and "
    "the single most applicable category from this fixed list:\n"
    "   - violence/hate_speech\n"
    "   - sexual_explicit_content\n"
    "   - illegal_activity_instructions\n"
    "   - self_harm_promotion\n"
    "   - extremism_terrorism\n"
    "   - harassment_bullying\n"
    "   - other_harmful_content\n"
    "3. On the second line (UNSAFE only) provide a SHORT one-sentence explanation "
    "(max 20 words) of why the content was flagged — do NOT reproduce the flagged text.\n\n"
    "IMPORTANT CALIBRATION — do NOT over-flag:\n"
    "- Educational, historical, or documentary discussion of difficult topics "
    "(e.g. World War II, the Holocaust, slavery, human anatomy and reproduction, "
    "terrorism as a news/policy subject, real-world conflicts, medical conditions, "
    "drug-policy debates) is SAFE. Educational intent and informational framing "
    "are strong signals of safety.\n"
    "- Flag ONLY content that is itself graphic, step-by-step instructional in a "
    "harmful way, or that explicitly promotes, glorifies, or recruits for harmful acts.\n"
    "- When in genuine doubt, classify as SAFE.\n\n"
    "RESPONSE FORMAT (strictly follow — no extra text before or after):\n"
    "For safe content:\n"
    "  SAFE\n"
    "For unsafe content:\n"
    "  UNSAFE | <category>\n"
    "  <one-sentence reason>\n\n"
    "Source type: {source_type}\n"
    "Content to classify (first 4000 characters):\n"
    "---\n"
    "{content}\n"
    "---\n\n"
    "Your classification:"
)

MODERATION_PROMPT = PromptTemplate(
    input_variables=["content", "source_type"],
    template=moderation_system_prompt,
)
