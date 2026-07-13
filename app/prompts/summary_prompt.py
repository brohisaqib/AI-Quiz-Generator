from langchain_core.prompts import PromptTemplate

# Prompt to generate an educational summary from video transcription
summary_system_prompt = (
    "You are an expert educator and technical writer. Your task is to analyze the provided "
    "transcription of a video and create a detailed, highly structured, and educational summary.\n\n"
    "Guidelines:\n"
    "1. Focus on core concepts, key definitions, and actionable takeaways.\n"
    "2. Group information into logical sections with clear markdown headings.\n"
    "3. Use bullet points for readability and highlight technical terminology.\n"
    "4. Retain all crucial facts, equations, or names mentioned, keeping the explanation concise yet comprehensive.\n"
    "5. Ensure the summary is engaging and easy to study from.\n\n"
    "Transcription:\n{transcription}\n\n"
    "Provide the educational summary below:"
)

SUMMARY_PROMPT = PromptTemplate(
    input_variables=["transcription"],
    template=summary_system_prompt
)
