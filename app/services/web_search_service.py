"""
Web Search Service.

Stage: Input Pre-processing (topic-based quiz generation).

Uses the ``duckduckgo-search`` package (no API key required) to retrieve
relevant search results for a given topic, then combines titles and snippets
into a single text block suitable for the downstream summary → quiz pipeline.
"""

from duckduckgo_search import DDGS

from app.utils.logger import get_logger

logger = get_logger("web_search_service")


class WebSearchService:
    """Service to retrieve web search results for a topic using DuckDuckGo (no API key)."""

    def search_topic(self, topic: str, max_results: int = 5) -> str:
        """
        Search DuckDuckGo for a topic and combine results into a single text block.

        Each result's title and body snippet are concatenated with clear
        separators so the downstream LLM pipeline receives rich, multi-source
        context rather than a single short excerpt.

        Args:
            topic: The search query / topic string. Must be non-empty.
            max_results: Maximum number of search results to fetch (default 5).

        Returns:
            A single string combining result titles and body snippets,
            suitable for passing to ``SummaryService.generate_summary()``.

        Raises:
            ValueError: If ``topic`` is empty or whitespace-only, or if
                DuckDuckGo returns no results for the query.
        """
        if not topic or not topic.strip():
            logger.error("Empty topic provided for web search.")
            raise ValueError(
                "Topic cannot be empty. Please provide a specific topic to search for."
            )

        topic = topic.strip()
        logger.info(
            f"Performing DuckDuckGo search for topic: '{topic}' "
            f"(max_results={max_results})"
        )

        import time
        import random

        results = []
        max_attempts = 4
        last_error = None

        for attempt in range(max_attempts):
            try:
                # Add a small delay between requests if not the first attempt
                if attempt > 0:
                    sleep_time = random.uniform(2.0, 4.0) * attempt
                    logger.info(f"Search retry {attempt}/{max_attempts - 1} for '{topic}' - Sleeping for {sleep_time:.2f}s...")
                    time.sleep(sleep_time)

                with DDGS() as ddgs:
                    results = list(
                        ddgs.text(
                            topic,
                            max_results=max_results,
                            safesearch="moderate",
                        )
                    )
                if results:
                    break
            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                logger.warning(
                    f"DuckDuckGo search attempt {attempt + 1}/{max_attempts} failed for '{topic}': {err_str}"
                )
                if "Ratelimit" in err_str or "202" in err_str or "429" in err_str:
                    continue

        if not results:
            logger.warning(
                f"DuckDuckGo search failed or rate-limited for topic '{topic}'. "
                f"Attempting fallback search via Wikipedia API..."
            )
            try:
                import requests
                headers = {"User-Agent": "AIQuizGenerator/2.0.0 (contact@example.com)"}
                wiki_url = "https://en.wikipedia.org/w/api.php"
                
                # Use list=search to get matching page IDs and spelling suggestions
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": topic,
                    "srlimit": max_results,
                    "format": "json",
                    "utf8": 1,
                }
                res = requests.get(wiki_url, params=search_params, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    search_info = data.get("query", {}).get("searchinfo", {})
                    search_results = data.get("query", {}).get("search", [])
                    
                    # If empty but spelling suggestion exists, search using the suggestion
                    if not search_results and "suggestion" in search_info:
                        suggestion = search_info["suggestion"]
                        logger.info(f"No Wikipedia results for '{topic}'. Retrying with suggestion: '{suggestion}'")
                        search_params["srsearch"] = suggestion
                        res = requests.get(wiki_url, params=search_params, headers=headers, timeout=10)
                        if res.status_code == 200:
                            data = res.json()
                            search_results = data.get("query", {}).get("search", [])
                            
                    if search_results:
                        page_ids = [str(item["pageid"]) for item in search_results]
                        extract_params = {
                            "action": "query",
                            "pageids": "|".join(page_ids),
                            "prop": "extracts",
                            "exintro": 1,
                            "explaintext": 1,
                            "format": "json",
                        }
                        extract_res = requests.get(wiki_url, params=extract_params, headers=headers, timeout=10)
                        if extract_res.status_code == 200:
                            pages = extract_res.json().get("query", {}).get("pages", {})
                            results = []
                            for page_id, page_data in pages.items():
                                title = page_data.get("title", "")
                                extract = page_data.get("extract", "").strip()
                                if title and extract:
                                    results.append({
                                        "title": title,
                                        "body": extract,
                                        "href": f"https://en.wikipedia.org/?curid={page_id}"
                                    })
                            logger.info(f"Wikipedia fallback search succeeded. Retrieved {len(results)} items.")
            except Exception as wiki_exc:
                logger.error(f"Wikipedia fallback search failed: {wiki_exc}", exc_info=True)

        if not results:
            if last_error:
                logger.error(
                    f"DuckDuckGo and Wikipedia searches failed for topic '{topic}': {last_error}",
                    exc_info=True,
                )
                raise ValueError(
                    f"Failed to retrieve search results for topic '{topic}' due to rate limits or connection constraints. "
                    f"Please wait a moment and try again. Detail: {last_error}"
                ) from last_error
            else:
                logger.warning(f"No search results found for topic: '{topic}'")
                raise ValueError(
                    f"No search results found for topic: '{topic}'. "
                    f"Please try a more specific or different topic."
                )

        logger.info(f"Retrieved {len(results)} search result(s) for topic: '{topic}'")

        # Combine results into a structured text block
        text_parts: list[str] = [
            f"Topic: {topic}\n"
            f"The following information was gathered from {len(results)} web sources.\n"
        ]

        for idx, result in enumerate(results, start=1):
            title: str = result.get("title", "").strip()
            body: str = result.get("body", "").strip()
            href: str = result.get("href", "")

            if not title and not body:
                logger.warning(f"Result {idx} has no title or body; skipping.")
                continue

            section = f"[Source {idx}]"
            if title:
                section += f"\nTitle: {title}"
            if body:
                section += f"\n{body}"

            text_parts.append(section)
            logger.info(
                f"Result {idx}/{len(results)}: '{title[:60]}...' "
                f"({len(body)} chars)"
                if len(title) > 60
                else f"Result {idx}/{len(results)}: '{title}' ({len(body)} chars)"
            )

        combined_text = "\n\n".join(text_parts).strip()

        if not combined_text or len(combined_text) < 50:
            logger.error(
                f"Search results for '{topic}' were too sparse to be useful."
            )
            raise ValueError(
                f"Search results for '{topic}' did not contain enough content. "
                f"Please try a different or more descriptive topic."
            )

        logger.info(
            f"Web search text block assembled. "
            f"Total length: {len(combined_text)} characters."
        )
        return combined_text
