import sys
import os

# --- Path setup for direct execution AND for when imported by other modules ---
# This allows the script to be run directly for testing, resolving imports for sibling modules,
# and ensures that when imported, 'ai_models' is correctly identified as a package if the
# project root is in sys.path.
SCRIPT_DIR_FOR_PATH = os.path.dirname(os.path.abspath(__file__)) # ai_models directory
PROJECT_ROOT_FOR_PATH = os.path.dirname(SCRIPT_DIR_FOR_PATH) # Project root (/app)
if PROJECT_ROOT_FOR_PATH not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FOR_PATH)

import logging
from typing import Dict, List, Optional, Any # Added typing imports

# Absolute imports, assuming project root is now in sys.path
from ai_models.llm_analyzer import (
    analyze_text_with_llm,
    configure_ollama_client,
    ollama_client, # This is the global client instance from llm_analyzer
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_HOST
)
from ai_models.network_search import search_web

# Configure module-level logger
logger = logging.getLogger(__name__)
# Note: Actual logging setup (basicConfig) will be done by the application
# or in the __main__ block for direct script execution.


# --- Prompt Constants ---
PROMPT_TEXT_IDENTIFY_PUBLISHER: str = (
    "Identify the most prominent publisher, company, or studio name from the following text. "
    "Respond with only the name. If no clear publisher, company, or studio is mentioned, respond with 'None'."
)
PROMPT_TEXT_EXTRACT_ACTORS: str = (
    "Extract all actor or distinct person names from the following text. "
    "List each full name on a new line. If no names are clearly identifiable, respond with 'None'."
)
PROMPT_TEXT_SUGGEST_TITLE: str = (
    "Based on the following text, suggest a concise and clean title suitable for a video. "
    "Respond with only the title. If the text itself seems like a good title, you can repeat it or slightly refine it."
)
PROMPT_AUDIO_EXTRACT_ACTORS: str = (
    "Extract all clearly identifiable person names mentioned in the following transcribed audio. "
    "List each full name on a new line. If no names are mentioned, respond with 'None'."
)

def enhance_textual_metadata(text_input: str, original_filename: str = "") -> Dict[str, Any]:
    """
    Enhances textual metadata using LLM (if available) and network search.

    Args:
        text_input (str): The primary text to analyze (e.g., from filename parsing, OCR).
        original_filename (str, optional): The original filename, used as a hint for
                                           title suggestion logic. Defaults to "".

    Returns:
        Dict[str, Any]: A dictionary containing various extracted and suggested metadata.
    """
    results: Dict[str, Any] = {
        "llm_suggested_title": None,
        "llm_identified_actors": [],
        "llm_identified_publisher": None,
        "network_search_actor_results": [],
        "network_search_publisher_results": [],
    }

    if not ollama_client:
        logger.warning("Ollama client not available for enhance_textual_metadata. LLM-based enhancements will be skipped.")
        return results

    if text_input and text_input.strip():
        publisher_name_llm = analyze_text_with_llm(text_input, PROMPT_TEXT_IDENTIFY_PUBLISHER)
        if publisher_name_llm and publisher_name_llm.strip().lower() not in ['none', 'n/a', '']:
            results["llm_identified_publisher"] = publisher_name_llm.strip()
            logger.info(f"LLM identified publisher: {results['llm_identified_publisher']}")
            pub_search_results = search_web(f"{results['llm_identified_publisher']} official website or information", max_results=1)
            if pub_search_results:
                results["network_search_publisher_results"] = pub_search_results
        else:
            logger.info("LLM did not identify a distinct publisher from text_input.")

        actors_text_llm = analyze_text_with_llm(text_input, PROMPT_TEXT_EXTRACT_ACTORS)
        if actors_text_llm and actors_text_llm.strip().lower() not in ['none', 'n/a', '']:
            identified_actors = [name.strip() for name in actors_text_llm.split('\n') if name.strip() and len(name.strip().split()) >= 2]
            if identified_actors:
                results["llm_identified_actors"] = identified_actors
                logger.info(f"LLM identified actors: {results['llm_identified_actors']}")
                for actor_name in results["llm_identified_actors"][:2]:
                    actor_search_results = search_web(f"{actor_name} actor filmography or profile", max_results=1)
                    if actor_search_results:
                        results["network_search_actor_results"].extend(actor_search_results)
            else:
                logger.info("LLM response for actors parsed to empty list (e.g., names were single words).")
        else:
            logger.info("LLM did not identify distinct actors from text_input.")

        if len(text_input.split()) > 4 and not (original_filename and "[" in original_filename and "]" in original_filename):
            suggested_title_llm = analyze_text_with_llm(text_input, PROMPT_TEXT_SUGGEST_TITLE)
            if suggested_title_llm and suggested_title_llm.strip().lower() not in ['none', 'n/a', '']:
                results["llm_suggested_title"] = suggested_title_llm.strip()
                logger.info(f"LLM suggested title: {results['llm_suggested_title']}")
            else:
                logger.info("LLM did not suggest a distinct title.")
    else:
        logger.info("enhance_textual_metadata received empty text_input. Skipping LLM analysis.")

    return results

def analyze_transcribed_audio(transcribed_text: str) -> Dict[str, Any]:
    """
    Analyzes transcribed audio text using LLM to extract mentioned names and keywords.
    """
    results: Dict[str, Any] = {
        "llm_mentioned_actors_audio": [],
        "llm_keywords_audio": []
    }
    if not ollama_client:
        logger.warning("Ollama client not available for analyze_transcribed_audio. Skipping LLM-based audio analysis.")
        return results

    if not transcribed_text or not transcribed_text.strip():
        logger.info("analyze_transcribed_audio called with empty transcribed_text.")
        return results

    actors_text_llm = analyze_text_with_llm(transcribed_text, PROMPT_AUDIO_EXTRACT_ACTORS)
    if actors_text_llm and actors_text_llm.strip().lower() not in ['none', 'n/a', '']:
        mentioned_actors = [name.strip() for name in actors_text_llm.split('\n') if name.strip() and len(name.strip().split()) >= 2]
        if mentioned_actors:
            results["llm_mentioned_actors_audio"] = mentioned_actors
            logger.info(f"LLM identified audio mentioned actors: {results['llm_mentioned_actors_audio']}")
        else:
            logger.info("LLM response for audio actors parsed to empty list.")
    else:
        logger.info("LLM did not identify distinct actors from audio transcript.")
    return results

if __name__ == '__main__':
    # Configure logging for direct script execution
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        force=True)

    logger.info("--- Testing Content Analysis Module (ai_models/content_analysis.py) ---")

    # Explicitly configure client here for testing.
    if not ollama_client:
        logger.info("Attempting to configure Ollama Client for testing via content_analysis.py __main__...")
        configure_ollama_client() # Uses imported version from llm_analyzer

    if ollama_client:
        logger.info(f"Ollama client appears to be configured (Host: {ollama_client._host}). Proceeding with tests that require Ollama.") # Accessing protected member

        test_input_1 = "TechReview_XYZ123: A deep dive into the latest gadget from InnovateCorp, featuring exclusive interviews with senior engineer Dr. Emily Carter and lead designer John Smith. We discuss its market impact. Release date is next month."
        logger.info(f"\n--- Test 1: enhance_textual_metadata with input: '{test_input_1}' ---")
        analysis_results_1 = enhance_textual_metadata(test_input_1, "TechReview_XYZ123.mp4")
        logger.info("Analysis Results 1:")
        for key, value in analysis_results_1.items():
            logger.info(f"  {key}: {value}")

        test_input_2 = "A short artistic film about a lonely robot discovering a flower in a post-apocalyptic wasteland. Directed by Ann Other. Music by The Lonely Synth Band. Visuals by PixelDream Studios."
        logger.info(f"\n--- Test 2: enhance_textual_metadata with input: '{test_input_2}' ---")
        analysis_results_2 = enhance_textual_metadata(test_input_2, "lonely_robot.mov")
        logger.info("Analysis Results 2:")
        for key, value in analysis_results_2.items():
            logger.info(f"  {key}: {value}")

        transcribed_audio_1 = "Welcome back to 'Tech Talks'. In today's episode, we are thrilled to have guest speakers Dr. Alpha Beta and also Professor Gamma Delta joining us. They will be talking about the future of neural networks and machine learning applications."
        logger.info(f"\n--- Test 3: analyze_transcribed_audio with input: '{transcribed_audio_1}' ---")
        audio_analysis_1 = analyze_transcribed_audio(transcribed_audio_1)
        logger.info("Audio Analysis Results 1:")
        for key, value in audio_analysis_1.items():
            logger.info(f"  {key}: {value}")

        test_input_no_person = "This video shows a beautiful landscape with mountains and rivers. No people are featured."
        logger.info(f"\n--- Test 4: enhance_textual_metadata with no clear persons/actors: '{test_input_no_person}' ---")
        analysis_results_4 = enhance_textual_metadata(test_input_no_person, "landscape_scenery.mp4")
        logger.info("Analysis Results 4:")
        for key, value in analysis_results_4.items():
            logger.info(f"  {key}: {value}")
    else:
        logger.warning("\nOllama client is not available or configured. Skipping tests that require Ollama.")
        logger.warning(f"Please ensure Ollama is running, a model (e.g., '{DEFAULT_OLLAMA_MODEL}') is pulled, and Ollama is accessible (usually at {DEFAULT_OLLAMA_HOST}).")

    logger.info("\n--- Network Search Only Test (does not require Ollama) ---")
    test_search_query = "history of documentary filmmaking"
    logger.info(f"--- Test 5: Direct network search for '{test_search_query}' ---")
    search_results = search_web(test_search_query, max_results=2)
    if search_results is not None:
        logger.info(f"Search Results for '{test_search_query}':")
        for i, res in enumerate(search_results):
            logger.info(f"  Result {i+1}: Title: {res.get('title')}, URL: {res.get('href')}")
    else:
        logger.warning(f"Search failed for '{test_search_query}'.")

    logger.info("\n--- End of Content Analysis Module Tests ---")
