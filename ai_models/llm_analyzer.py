import ollama
import logging
from typing import Optional, Dict, List, Any

# Configure module-level logger
logger = logging.getLogger(__name__)
# Note: BasicConfig for the root logger (if no handlers are present) will be set
# in the __main__ block for direct script execution, or by the application using this module.
if not logging.getLogger().handlers: # Add a basic handler if no handlers are configured
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )


DEFAULT_OLLAMA_MODEL: str = "llama3"
DEFAULT_OLLAMA_HOST: str = "http://localhost:11434"

ollama_client: Optional[ollama.Client] = None


def configure_ollama_client(host: str = DEFAULT_OLLAMA_HOST) -> bool:
    """
    Configures the global Ollama client for a given host.

    Attempts to connect to the Ollama server at the specified host and initializes
    the global `ollama_client` if successful.

    Args:
        host (str): The URL of the Ollama server (e.g., "http://localhost:11434").
                    Defaults to `DEFAULT_OLLAMA_HOST`.

    Returns:
        bool: True if the client was successfully configured, False otherwise.
    """
    global ollama_client
    try:
        logger.info(f"Attempting to configure Ollama client for host: {host}")
        temp_client = ollama.Client(host=host)
        temp_client.list()  # Perform a lightweight call to check connectivity
        ollama_client = temp_client  # If successful, assign to global client
        # Accessing protected member _host for logging purposes
        logger.info(
            f"Successfully connected to Ollama at {ollama_client._host}. Global client configured."
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to connect to Ollama at {host}. Error: {e}", exc_info=True
        )
        logger.error(
            "Please ensure Ollama is running, accessible, and a model is available/pulled."
        )
        ollama_client = None
        return False


def generate_ollama_response(
    prompt: str, model: str = DEFAULT_OLLAMA_MODEL, host: Optional[str] = None
) -> Optional[str]:
    """
    Generates a response from an Ollama model for a given prompt.

    It can use a pre-configured global client, a temporary client for a specified host,
    or attempt to configure the global client if not already set up.

    Args:
        prompt (str): The prompt to send to the LLM.
        model (str): The name of the Ollama model to use (e.g., "llama3").
                     Defaults to `DEFAULT_OLLAMA_MODEL`.
        host (Optional[str]): The specific Ollama host URL to use for this request.
                              If None, uses the globally configured client or default host.
                              Defaults to None.

    Returns:
        Optional[str]: The content of the LLM's response as a string,
                       or None if an error occurs.
    """
    global ollama_client
    current_client_to_use: Optional[ollama.Client] = None
    client_host_info: str = "N/A"

    if host:
        logger.info(
            f"Host parameter provided: '{host}'. Attempting to use a temporary client for this host."
        )
        try:
            temp_local_client = ollama.Client(host=host)
            temp_local_client.list()  # Verify connection to this specific host
            current_client_to_use = temp_local_client
            client_host_info = host  # Store host for logging
            logger.info(f"Successfully created temporary client for host: {host}")
        except Exception as e:
            logger.error(
                f"Failed to connect to specified Ollama host '{host}'. Error: {e}",
                exc_info=True,
            )
            return None  # Critical failure for this specific host request
    else:
        if not ollama_client:
            logger.warning(
                "Global Ollama client not configured. Attempting to configure with default host."
            )
            if configure_ollama_client(DEFAULT_OLLAMA_HOST):
                current_client_to_use = ollama_client
                if ollama_client:  # Check if configure_ollama_client was successful
                    # Accessing protected member _host for logging purposes
                    client_host_info = ollama_client._host
            else:
                logger.error(
                    "Failed to configure default Ollama client. Cannot generate response."
                )
                return None
        else:
            current_client_to_use = ollama_client
            # Accessing protected member _host for logging purposes
            client_host_info = ollama_client._host
            logger.debug(
                f"Using pre-configured global Ollama client for host: {client_host_info}"
            )

    if not current_client_to_use:
        logger.error("No valid Ollama client available to generate response.")
        return None

    try:
        logger.info(
            f"Sending prompt to Ollama model '{model}' via host '{client_host_info}':\n{prompt[:200]}..."
        )
        response: Dict[str, Any] = current_client_to_use.chat(
            model=model, messages=[{"role": "user", "content": prompt}]
        )
        response_content: Optional[str] = response.get("message", {}).get("content")
        if response_content is None:
            logger.error(
                f"Ollama response did not contain 'message.content' for model '{model}'. Full response: {response}"
            )
            return None

        logger.info(f"Received response from Ollama model '{model}'.")
        return response_content.strip()
    except Exception as e:
        logger.error(
            f"Error communicating with Ollama model '{model}' via host '{client_host_info}': {e}",
            exc_info=True,
        )
        error_str_lower = str(e).lower()
        if (
            "model not found" in error_str_lower
            or "models are available" in error_str_lower
            or "pull it" in error_str_lower
            or "status code 404" in error_str_lower
        ):
            logger.error(
                f"Model '{model}' not found or not accessible on host '{client_host_info}'. "
                f"Ensure model is pulled in Ollama (e.g., `ollama pull {model}`)."
            )
        return None


def analyze_text_with_llm(
    text_to_analyze: str, task_description: str, model: str = DEFAULT_OLLAMA_MODEL
) -> Optional[str]:
    """
    Analyzes a given text using an LLM to perform a specific task.

    Constructs a prompt by combining the task description and the text to be analyzed,
    then calls `generate_ollama_response` to get the LLM's analysis.

    Args:
        text_to_analyze (str): The text content to be analyzed by the LLM.
        task_description (str): A description of the task for the LLM to perform
                                (e.g., "Extract keywords:", "Summarize this text:").
        model (str): The name of the Ollama model to use.
                     Defaults to `DEFAULT_OLLAMA_MODEL`.

    Returns:
        Optional[str]: The LLM's response as a string, or None if an error occurs.
    """
    if not text_to_analyze or not text_to_analyze.strip():
        logger.warning("analyze_text_with_llm called with empty text_to_analyze.")
        return None
    if not task_description or not task_description.strip():
        logger.warning("analyze_text_with_llm called with empty task_description.")
        return None

    prompt = f'{task_description}\n\n---\nText to analyze:\n"""{text_to_analyze}\n"""\n\nResponse:'
    return generate_ollama_response(prompt, model)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # force=True to override any root logger config from imports
    )
    logger = logging.getLogger(__name__) # Ensure __main__ logger uses the same name for consistency

    logger.info(
        f"--- Testing llm_analyzer.py with default host: {DEFAULT_OLLAMA_HOST} ---"
    )

    client_configured_for_tests = configure_ollama_client()

    if client_configured_for_tests and ollama_client:
        logger.info(
            f"--- Ollama client configured for tests. Target host: {ollama_client._host} ---"
        )  # Accessing protected member for logging

        logger.info("\n--- Test 1: Simple Question ---")
        prompt1 = (
            "What is the capital of France? Respond with only the name of the capital."
        )
        response1 = generate_ollama_response(prompt1)
        if response1:
            logger.info(f"Test 1 Prompt: {prompt1}")
            logger.info(f"Test 1 Response: {response1}")
        else:
            logger.warning(
                f"Test 1 Failed: No response for model {DEFAULT_OLLAMA_MODEL}."
            )

        logger.info(
            "\n--- Test 2: Title Suggestion (using analyze_text_with_llm) ---"
        )
        video_desc_title = (
            "A video showcasing the process of baking sourdough bread from scratch, "
            "including starter maintenance, mixing, shaping, and baking."
        )
        task_title = (
            "Suggest a concise and informative title for a video based on the "
            "following description. The title should be suitable for a video platform. "
            "Respond with only the title."
        )
        suggested_title = analyze_text_with_llm(video_desc_title, task_title)
        if suggested_title:
            logger.info(f"Test 2 Video Description: {video_desc_title}")
            logger.info(f"Test 2 Suggested Title: {suggested_title}")
        else:
            logger.warning(
                f"Test 2 Failed: No title suggestion for model {DEFAULT_OLLAMA_MODEL}."
            )

        logger.info("\n--- Test 3: Model Not Available ---")
        response3 = generate_ollama_response(
            "Test prompt for non-existent model.",
            model="non_existent_model_12345",
        )
        if not response3:
            logger.info(
                "Test 3 Passed: Correctly failed to get response for non-existent model."
            )
        else:
            logger.error(
                f"Test 3 FAILED: Unexpectedly got response for non-existent model: {response3}"
            )
    else:
        logger.warning(
            "\nOllama client could not be configured with default host. "
            "Skipping tests requiring an active client."
        )
        logger.warning(
            f"Please ensure Ollama is running, '{DEFAULT_OLLAMA_MODEL}' model is pulled, "
            f"and Ollama is accessible at {DEFAULT_OLLAMA_HOST}."
        )

    logger.info(
        "\n--- Test 4: Ollama Host Not Available (using explicit bad host) ---"
    )
    bad_host = "http://localhost:12345"
    response4 = generate_ollama_response(
        "Test prompt for bad host.", host=bad_host, model=DEFAULT_OLLAMA_MODEL
    )
    if not response4:
        logger.info(
            f"Test 4 Passed: Correctly failed to get response from unavailable Ollama host {bad_host}."
        )
    else:
        logger.error(
            f"Test 4 FAILED: Unexpectedly got response from bad host {bad_host}: {response4}"
        )

    logger.info(
        "\n--- Test 5: Using default client after a failed temporary host attempt (if default client was configured) ---"
    )
    if client_configured_for_tests and ollama_client:
        prompt5 = "Does the default client connection persist after a failed temporary host attempt?"
        # First, make a call to a bad host that will fail
        generate_ollama_response(
            "This call to bad host will fail.",
            host=bad_host,
            model=DEFAULT_OLLAMA_MODEL,
        )
        logger.info("Made a call to a bad host. Now testing default client...")
        # Then, make a call without specifying host, relying on the global client
        response5 = generate_ollama_response(prompt5, model=DEFAULT_OLLAMA_MODEL)
        if response5:
            logger.info(f"Test 5 Prompt: {prompt5}")
            logger.info(
                f"Test 5 Response: {response5} (using default client at {ollama_client._host})"
            )  # Accessing protected member for logging
        else:
            logger.warning(
                f"Test 5 Failed: No response using default client for model {DEFAULT_OLLAMA_MODEL} "
                "after temporary host failure."
            )
    else:
        logger.info(
            "Skipping Test 5 as default Ollama client was not configured initially."
        )

    logger.info("\n--- End of llm_analyzer.py tests ---")
```
