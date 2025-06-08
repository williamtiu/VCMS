import logging
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_MAX_RESULTS = 5 # Default number of search results to fetch

def search_web(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict] | None:
    """
    Performs a web search using DuckDuckGo.

    Args:
        query (str): The search query.
        max_results (int): The maximum number of search results to return.

    Returns:
        list[dict] | None: A list of search result dictionaries (keys: 'title', 'href', 'body'),
                           or None if an error occurs.
                           Example: [{'title': 'Result Title', 'href': 'URL', 'body': 'Snippet'}, ...]
    """
    try:
        logging.info(f"Performing web search for query: '{query}' (max_results: {max_results})")

        # DDGS().text() returns a generator, convert to list if needed, or handle as iterator
        # For this function's return type, we'll collect them into a list.
        results_generator = DDGS().text(keywords=query, max_results=max_results)

        results = []
        if results_generator:
            for r in results_generator:
                results.append(r) # The objects 'r' are already dicts with 'title', 'href', 'body'

        if results:
            logging.info(f"Found {len(results)} results for query '{query}'.")
            return results
        else:
            logging.info(f"No results found for query '{query}'.")
            return []
    except Exception as e:
        logging.error(f"Error during web search for query '{query}': {e}")
        return None

def fetch_url_content(url: str, timeout: int = 10) -> str | None:
    """
    Fetches the textual content of a given URL.

    Args:
        url (str): The URL to fetch.
        timeout (int): Timeout in seconds for the request.

    Returns:
        str | None: The plain text content of the page (extracted using BeautifulSoup),
                           or None if an error occurs or content is not HTML.
    """
    try:
        logging.info(f"Fetching content from URL: {url}")
        headers = {
            'User-Agent': 'VideoManagementBot/1.0 (KHTML, like Gecko; compatible; +http://localhost/botinfo)'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        content_type = response.headers.get('content-type', '').lower()
        if 'html' not in content_type:
            logging.warning(f"Content at {url} is not HTML (type: {content_type}). Skipping text extraction.")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text, normalize whitespace
        text = soup.get_text(separator='\n', strip=True)

        # Further processing to reduce excessive newlines and spaces
        lines = (line.strip() for line in text.splitlines())
        # Break multi-spaced lines into phrases, then join phrases with single space
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk) # Reconstruct text with single spaces

        logging.info(f"Successfully fetched and parsed content from {url} (length: {len(text)}).")
        return text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error parsing content from {url}: {e}")
        return None

if __name__ == '__main__':
    print("--- Testing Network Search Module ---")

    print("\n--- Test 1: Web Search for 'Python programming language' ---")
    search_query1 = "Python programming language"
    results1 = search_web(search_query1, max_results=3)
    if results1 is not None:
        if results1:
            for i, res in enumerate(results1):
                print(f"  Result {i+1}:")
                print(f"    Title: {res.get('title')}")
                print(f"    URL: {res.get('href')}")
                print(f"    Snippet: {res.get('body', '')[:100]}...")
        else:
            print("  No search results found.")
    else:
        print("  Web search failed for Test 1.")

    print("\n--- Test 2: Web Search for an actor ---")
    search_query2 = "Tom Hanks movies"
    results2 = search_web(search_query2, max_results=2)
    if results2 is not None:
        if results2:
            for i, res in enumerate(results2):
                print(f"  Result {i+1}: {res.get('title')} ({res.get('href')})")
        else:
            print("  No search results found.")
    else:
        print("  Web search failed for Test 2.")

    print("\n--- Test 3: Fetch URL Content ---")
    # Use a known, reliable, simple HTML page for this test if possible,
    # as fetching from dynamic search results can be brittle.
    # For now, we'll proceed with the original logic of using the first search result.
    # If results1 is None or empty, this test part will be skipped.
    first_url_to_fetch = None
    if results1 and results1[0] and results1[0].get('href'):
        first_url_to_fetch = results1[0]['href']
        print(f"  Attempting to fetch content from first search result: {first_url_to_fetch}")
        content1 = fetch_url_content(first_url_to_fetch)
        if content1:
            print(f"  Successfully fetched content (first 500 chars):\n{content1[:500]}...")
        else:
            print(f"  Failed to fetch content from {first_url_to_fetch}.")
    else:
        print(f"  Skipping dynamic URL fetch as no prior search results available for Test 3 (URL: {first_url_to_fetch}).")

    print("\n--- Test 4: Fetch URL Content (guaranteed non-HTML) ---")
    url_non_html = "https://raw.githubusercontent.com/googleapis/google-api-python-client/main/README.md" # Raw MD
    content_non_html = fetch_url_content(url_non_html)
    if content_non_html is None:
        print(f"  Correctly handled non-HTML URL: {url_non_html} (returned None).")
    else:
        # It's possible a raw .md file served from raw.githubusercontent might have a text/plain content-type
        # and fetch_url_content would still try to parse it with BeautifulSoup if 'html' is not in content_type.
        # The current check is `if 'html' not in content_type: return None`. So this should be None.
        print(f"  ERROR: Unexpectedly got content from non-HTML URL: {url_non_html}. Content snippet: {str(content_non_html)[:100]}...")

    print("\n--- Test 5: Fetch URL Content (non-existent URL) ---")
    url_bad = "http://thisdomainshouldnotexist123456789abcdef.com/nonexistentpage.html" # Made it more unique
    content_bad = fetch_url_content(url_bad)
    if content_bad is None:
        print(f"  Correctly handled non-existent URL: {url_bad} (returned None).")
    else:
        print(f"  ERROR: Unexpectedly got content from non-existent URL: {url_bad}.")
