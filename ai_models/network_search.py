import logging
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any

# Configure module-level logger
logger = logging.getLogger(__name__)
# Note: BasicConfig for the root logger will be set in the __main__ block
# or by the application using this module.
if not logging.getLogger().handlers:  # Add a basic handler if no handlers are configured
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )


DEFAULT_MAX_RESULTS: int = 5  # Default number of search results to fetch


def search_web(
    query: str, max_results: int = DEFAULT_MAX_RESULTS
) -> Optional[List[Dict[str, str]]]:
    """
    Performs a web search using DuckDuckGo.

    Args:
        query (str): The search query.
        max_results (int): The maximum number of search results to return.
                           Defaults to `DEFAULT_MAX_RESULTS`.

    Returns:
        Optional[List[Dict[str, str]]]:
            A list of search result dictionaries if successful. Each dictionary
            is expected to have "title", "href", and "body" keys.
            Returns an empty list if no results are found.
            Returns None if an error occurs during the search.
            Example: [{"title": "Result Title", "href": "URL", "body": "Snippet"}, ...]
    """
    if not query or not query.strip():
        logger.warning("Attempted to search with an empty query.")
        return []  # Consistent with "no results found"

    try:
        logger.info(
            f"Performing web search for query: '{query}' (max_results: {max_results})"
        )

        results_generator = DDGS().text(keywords=query, max_results=max_results)

        results: List[Dict[str, str]] = []
        if results_generator:
            for r in results_generator:  # r is Dict[str, str]
                results.append(r)

        if results:
            logger.info(f"Found {len(results)} results for query '{query}'.")
        else:
            logger.info(f"No results found for query '{query}'.")
        return results

    except Exception as e:
        logger.error(
            f"Error during web search for query '{query}': {e}", exc_info=True
        )
        return None  # Indicates a failure in the search operation itself


def fetch_url_content(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetches and extracts plain textual content from a given URL.

    Uses requests to get the URL and BeautifulSoup to parse HTML and extract text.
    Removes script, style, header, footer, nav, and aside tags. Normalizes whitespace.

    Args:
        url (str): The URL to fetch.
        timeout (int): Timeout in seconds for the HTTP request. Defaults to 10.

    Returns:
        Optional[str]: The extracted plain text content of the page.
                       Returns None if:
                       - An HTTP error occurs (4xx or 5xx status code).
                       - The content type is not HTML.
                       - An error occurs during parsing.
                       - The URL is invalid or unreachable.
                       - No text content is extracted after parsing.
    """
    if not url or not url.strip():
        logger.warning("Attempted to fetch content from an empty URL.")
        return None

    try:
        logger.info(f"Fetching content from URL: {url}")
        headers: Dict[str, str] = {
            "User-Agent": "VideoManagementBot/1.0 (KHTML, like Gecko; compatible; +http://localhost/botinfo)"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raise an HTTPError for bad responses

        content_type: Optional[str] = response.headers.get("content-type", "").lower()
        if not content_type or "html" not in content_type:
            logger.warning(
                f"Content at {url} is not HTML (type: {content_type if content_type else 'Unknown'}). "
                "Skipping text extraction."
            )
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        for script_or_style in soup(
            ["script", "style", "header", "footer", "nav", "aside"]
        ):
            script_or_style.decompose()

        text: str = soup.get_text(separator="\n", strip=True)
        lines: List[str] = [line.strip() for line in text.splitlines() if line.strip()]
        text = " ".join(lines)

        if not text:
            logger.warning(f"No text content extracted from {url} after parsing.")
            return None

        logger.info(
            f"Successfully fetched and parsed content from {url} (extracted text length: {len(text)})."
        )
        return text

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching URL {url}: {e}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching URL {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error processing content from {url}: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    logger = logging.getLogger(
        __name__
    )  # Ensure __main__ logger uses the same name for consistency

    logger.info("--- Testing Network Search Module ---")

    logger.info("\n--- Test 1: Web Search for 'Python programming language' ---")
    search_query1: str = "Python programming language"
    results1: Optional[List[Dict[str, str]]] = search_web(
        search_query1, max_results=3
    )
    if results1 is not None:
        if results1:
            for i, res in enumerate(results1):
                logger.info(f"  Result {i+1}:")
                logger.info(f"    Title: {res.get('title')}")
                logger.info(f"    URL: {res.get('href')}")
                logger.info(f"    Snippet: {res.get('body', '')[:100]}...")
        else:
            logger.info("  No search results found for Test 1.")
    else:
        logger.warning("  Web search failed for Test 1 (returned None).")

    logger.info("\n--- Test 2: Web Search for an actor ---")
    search_query2: str = "Tom Hanks movies"
    results2: Optional[List[Dict[str, str]]] = search_web(
        search_query2, max_results=2
    )
    if results2 is not None:
        if results2:
            for i, res in enumerate(results2):
                logger.info(
                    f"  Result {i+1}: {res.get('title')} ({res.get('href')})"
                )
        else:
            logger.info("  No search results found for Test 2.")
    else:
        logger.warning("  Web search failed for Test 2 (returned None).")

    logger.info("\n--- Test 3: Fetch URL Content (from Test 1 results) ---")
    first_url_to_fetch: Optional[str] = None
    if results1 and results1[0] and results1[0].get("href"):
        first_url_to_fetch = results1[0]["href"]
        logger.info(
            f"  Attempting to fetch content from first search result: {first_url_to_fetch}"
        )
        content1: Optional[str] = fetch_url_content(first_url_to_fetch)
        if content1:
            logger.info(
                f"  Successfully fetched content (first 500 chars):\n{content1[:500]}..."
            )
        else:
            logger.warning(f"  Failed to fetch content from {first_url_to_fetch}.")
    else:
        logger.info(
            "  Skipping dynamic URL fetch for Test 3 as no prior search results were available or valid."
        )

    logger.info("\n--- Test 4: Fetch URL Content (guaranteed non-HTML) ---")
    url_non_html: str = (
        "https://raw.githubusercontent.com/googleapis/google-api-python-client/main/README.md"
    )
    content_non_html: Optional[str] = fetch_url_content(url_non_html)
    if content_non_html is None:
        logger.info(
            f"  Test 4 Passed: Correctly handled non-HTML URL: {url_non_html} (returned None)."
        )
    else:
        logger.error(
            f"  Test 4 FAILED: Unexpectedly got content from non-HTML URL: {url_non_html}. "
            f"Snippet: {str(content_non_html)[:100]}..."
        )

    logger.info("\n--- Test 5: Fetch URL Content (non-existent URL) ---")
    url_bad: str = (
        "http://thisdomainshouldreallynotexist123456789abcdef0.com/nonexistentpage.html"
    )
    content_bad: Optional[str] = fetch_url_content(url_bad)
    if content_bad is None:
        logger.info(
            f"  Test 5 Passed: Correctly handled non-existent URL: {url_bad} (returned None)."
        )
    else:
        logger.error(
            f"  Test 5 FAILED: Unexpectedly got content from non-existent URL: {url_bad}."
        )

    logger.info("\n--- End of Network Search Module Tests ---")
```
