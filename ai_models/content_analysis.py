import sys
import os

# Ensure project root is in sys.path for absolute imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # This should be /app

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
# Absolute imports assuming project root (/app) is in sys.path
from ai_models.llm_analyzer import (
    analyze_text_with_llm,
    configure_ollama_client,
    ollama_client,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_HOST # Added import
)
from ai_models.network_search import search_web # fetch_url_content is not directly used here yet, but good to have

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attempt to configure Ollama client when this module is loaded.
# This will only succeed if an Ollama server is running and accessible.
if not ollama_client: # Check if already configured (e.g. by another module's earlier import)
    logging.info("content_analysis.py: Attempting to initialize Ollama client via module load...")
    configure_ollama_client() # Uses default host from llm_analyzer

def enhance_textual_metadata(text_input: str, original_filename: str = "") -> dict:
    """
    Enhances textual metadata using LLM and network search.
    """
    results = {
        "llm_suggested_title": None,
        "llm_identified_actors": [],
        "llm_identified_publisher": None,
        "network_search_actor_results": [], # Store list of dicts from search_web
        "network_search_publisher_results": [], # Store list of dicts from search_web
    }

    if not ollama_client:
        logging.warning("Ollama client not available for enhance_textual_metadata. Skipping LLM-based enhancements.")
        return results

    # Publisher Identification
    task_publisher = "Identify the most prominent publisher, company, or studio name from the following text. Respond with only the name. If no clear publisher, company, or studio is mentioned, respond with 'None'."
    publisher_name_llm = analyze_text_with_llm(text_input, task_publisher)
    if publisher_name_llm and publisher_name_llm.strip().lower() not in ['none', 'n/a', '']:
        results["llm_identified_publisher"] = publisher_name_llm.strip()
        logging.info(f"LLM identified publisher: {results['llm_identified_publisher']}")
        pub_search_results = search_web(f"{results['llm_identified_publisher']} official website or information", max_results=1) # Changed to 1 result for publisher
        if pub_search_results:
            results["network_search_publisher_results"] = pub_search_results
    else:
        logging.info("LLM did not identify a distinct publisher.")

    # Actor Identification
    task_actors = "Extract all actor or distinct person names from the following text. List each full name on a new line. If no names are clearly identifiable, respond with 'None'."
    actors_text_llm = analyze_text_with_llm(text_input, task_actors)
    if actors_text_llm and actors_text_llm.strip().lower() not in ['none', 'n/a', '']:
        identified_actors = [name.strip() for name in actors_text_llm.split('\n') if name.strip() and len(name.strip().split()) >=2] # Require at least two words for a name
        results["llm_identified_actors"] = identified_actors
        logging.info(f"LLM identified actors: {results['llm_identified_actors']}")
        for actor_name in results["llm_identified_actors"][:2]: # Limit searches to first 2 actors for now
            actor_search_results = search_web(f"{actor_name} actor filmography or profile", max_results=1)
            if actor_search_results: # search_web returns list or None
                results["network_search_actor_results"].extend(actor_search_results)
    else:
        logging.info("LLM did not identify distinct actors.")

    # Title Suggestion
    # Avoid asking for title if text_input is very short or already looks like a structured title (e.g., from filename parser)
    if len(text_input.split()) > 4 and not (original_filename and "[" in original_filename and "]" in original_filename):
        task_title = "Based on the following text, suggest a concise and clean title suitable for a video. Respond with only the title. If the text itself seems like a good title, you can repeat it or slightly refine it."
        suggested_title_llm = analyze_text_with_llm(text_input, task_title)
        if suggested_title_llm and suggested_title_llm.strip().lower() not in ['none', 'n/a', '']:
            results["llm_suggested_title"] = suggested_title_llm.strip()
            logging.info(f"LLM suggested title: {results['llm_suggested_title']}")
        else:
            logging.info("LLM did not suggest a distinct title.")

    return results

def analyze_transcribed_audio(transcribed_text: str) -> dict:
    """
    Analyzes transcribed audio text using LLM.
    """
    results = {
        "llm_mentioned_actors_audio": [],
        "llm_keywords_audio": [] # Placeholder for future keyword extraction
    }
    if not ollama_client:
        logging.warning("Ollama client not available for analyze_transcribed_audio. Skipping LLM-based audio analysis.")
        return results

    task_audio_actors = "Extract all clearly identifiable person names mentioned in the following transcribed audio. List each full name on a new line. If no names are mentioned, respond with 'None'."
    actors_text_llm = analyze_text_with_llm(transcribed_text, task_audio_actors)
    if actors_text_llm and actors_text_llm.strip().lower() not in ['none', 'n/a', '']:
        results["llm_mentioned_actors_audio"] = [name.strip() for name in actors_text_llm.split('\n') if name.strip() and len(name.strip().split()) >=2]
        logging.info(f"LLM identified audio mentioned actors: {results['llm_mentioned_actors_audio']}")
    else:
        logging.info("LLM did not identify distinct actors from audio.")

    # Example for keywords (can be enabled later)
    # task_keywords = "Extract the main keywords or topics (max 5) from the following text. List them separated by commas. If no clear keywords, respond with 'None'."
    # keywords_llm = analyze_text_with_llm(transcribed_text, task_keywords)
    # if keywords_llm and keywords_llm.strip().lower() not in ['none', 'n/a', '']:
    #     results["llm_keywords_audio"] = [k.strip() for k in keywords_llm.split(',') if k.strip()]
    #     logging.info(f"LLM identified audio keywords: {results['llm_keywords_audio']}")
    # else:
    #     logging.info("LLM did not identify distinct keywords from audio.")

    return results

if __name__ == '__main__':
    # The sys.path modification is now at the top of the file.
    print("--- Testing Content Analysis Module ---")

    # Explicitly configure client here for testing, as the module-level one might
    # not have access to the modified sys.path immediately in all Python versions
    # or execution contexts if it runs before this __main__ block's path setup.
    # However, with path setup at top, module-level configure_ollama_client() should be fine.
    # This explicit call here ensures it for direct script execution for tests.
    if not ollama_client: # Check if module-level load succeeded
        print("Ollama client not configured at module load. Attempting explicit configuration for tests...")
        configure_ollama_client()
    elif ollama_client:
        print(f"Ollama client already configured from module load (Host: {ollama_client._host}).")


    if ollama_client:
        print(f"Ollama client appears to be configured (Host: {ollama_client._host}). Proceeding with tests that require Ollama.")

        test_input_1 = "TechReview_XYZ123: A deep dive into the latest gadget from InnovateCorp, featuring exclusive interviews with senior engineer Dr. Emily Carter and lead designer John Smith. We discuss its market impact. Release date is next month."
        print(f"\n--- Test 1: enhance_textual_metadata with input: '{test_input_1}' ---")
        analysis_results_1 = enhance_textual_metadata(test_input_1, "TechReview_XYZ123.mp4")
        print("Analysis Results 1:")
        for key, value in analysis_results_1.items():
            print(f"  {key}: {value}")

        test_input_2 = "A short artistic film about a lonely robot discovering a flower in a post-apocalyptic wasteland. Directed by Ann Other. Music by The Lonely Synth Band. Visuals by PixelDream Studios."
        print(f"\n--- Test 2: enhance_textual_metadata with input: '{test_input_2}' ---")
        analysis_results_2 = enhance_textual_metadata(test_input_2, "lonely_robot.mov") # original_filename might influence title suggestion
        print("Analysis Results 2:")
        for key, value in analysis_results_2.items():
            print(f"  {key}: {value}")

        transcribed_audio_1 = "Welcome back to 'Tech Talks'. In today's episode, we are thrilled to have guest speakers Dr. Alpha Beta and also Professor Gamma Delta joining us. They will be talking about the future of neural networks and machine learning applications."
        print(f"\n--- Test 3: analyze_transcribed_audio with input: '{transcribed_audio_1}' ---")
        audio_analysis_1 = analyze_transcribed_audio(transcribed_audio_1)
        print("Audio Analysis Results 1:")
        for key, value in audio_analysis_1.items():
            print(f"  {key}: {value}")

        test_input_no_person = "This video shows a beautiful landscape with mountains and rivers. No people are featured."
        print(f"\n--- Test 4: enhance_textual_metadata with no clear persons/actors: '{test_input_no_person}' ---")
        analysis_results_4 = enhance_textual_metadata(test_input_no_person, "landscape_scenery.mp4")
        print("Analysis Results 4:")
        for key, value in analysis_results_4.items():
            print(f"  {key}: {value}")

    else:
        print("\nOllama client is not available or configured. Skipping tests that require Ollama.")
        print(f"Please ensure Ollama is running, a model (e.g., '{DEFAULT_OLLAMA_MODEL}') is pulled, and Ollama is accessible (usually at {DEFAULT_OLLAMA_HOST}).")

    print("\n--- Network Search Only Test (does not require Ollama) ---")
    test_search_query = "history of documentary filmmaking"
    print(f"--- Test 5: Direct network search for '{test_search_query}' ---")
    search_results = search_web(test_search_query, max_results=2)
    if search_results is not None:
        print(f"Search Results for '{test_search_query}':")
        for i, res in enumerate(search_results):
            print(f"  Result {i+1}: Title: {res.get('title')}, URL: {res.get('href')}")
    else:
        print(f"Search failed for '{test_search_query}'.")

    print("\n--- End of Content Analysis Module Tests ---")
