import ollama
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_OLLAMA_MODEL = 'llama3'
DEFAULT_OLLAMA_HOST = 'http://localhost:11434'

ollama_client = None

def configure_ollama_client(host=DEFAULT_OLLAMA_HOST):
    global ollama_client
    try:
        logging.info(f"Attempting to configure Ollama client for host {host}...")
        temp_client = ollama.Client(host=host)
        temp_client.list() # Perform a lightweight call on the instance to check connectivity
        ollama_client = temp_client # If successful, assign to global
        logging.info(f"Successfully connected to Ollama at {host}. Client configured.")
    except Exception as e:
        logging.error(f"Failed to connect to Ollama at {host}. Error: {e}")
        logging.error("Please ensure Ollama is running and accessible, and a model is available/pulled.")
        ollama_client = None

def generate_ollama_response(prompt: str, model: str = DEFAULT_OLLAMA_MODEL, host: str = None) -> str | None:
    global ollama_client
    current_client = ollama_client

    # If a specific host is provided for this call, try to use it
    if host and (not ollama_client or ollama_client._host != host): # Check if different from global client or global is None
        try:
            logging.info(f"Attempting to use temporary Ollama client for host: {host}")
            # Create a new client instance for the temporary host
            temp_local_client = ollama.Client(host=host)
            temp_local_client.list() # Perform a lightweight call on the instance
            current_client = temp_local_client # Use this client for the current operation
            logging.info(f"Using temporary Ollama client for host: {host}")
        except Exception as e:
            logging.error(f"Failed to connect to temporary Ollama host {host}. Error: {e}")
            return None

    if not current_client:
        logging.warning("Ollama client is not configured. Attempting last-minute default configuration.")
        # Pass the original default host, not the potentially temporary 'host' variable for this specific call
        configure_ollama_client(DEFAULT_OLLAMA_HOST)
        if not ollama_client: # Check the global client again after attempt
             logging.error("Default Ollama client configuration failed. Cannot generate response.")
             return None
        current_client = ollama_client # Use the now configured global client

    try:
        logging.info(f"Sending prompt to Ollama model '{model}' via client for host '{current_client._host}':\n{prompt[:200]}...")
        response = current_client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt,}]
        )
        response_content = response['message']['content']
        logging.info(f"Received response from Ollama model '{model}'.")
        return response_content.strip()
    except Exception as e:
        logging.error(f"Error communicating with Ollama model '{model}' via host '{current_client._host if current_client else 'N/A'}': {e}")
        if "model not found" in str(e).lower() or \
           "models are available" in str(e).lower() or \
           "pull it" in str(e).lower() or \
           "status code 404" in str(e).lower(): # 404 can also mean model not found on some Ollama versions
            logging.error(f"Model '{model}' not found or not accessible. Ensure model is pulled in Ollama (e.g., `ollama pull {model}`).")
        return None

def analyze_text_with_llm(text_to_analyze: str, task_description: str, model: str = DEFAULT_OLLAMA_MODEL) -> str | None:
    prompt = f"{task_description}\n\n---\nText to analyze:\n\"\"\"{text_to_analyze}\n\"\"\"\n\nResponse:"
    return generate_ollama_response(prompt, model)

if __name__ == '__main__':
    # Initial configuration attempt.
    # The script will try to connect to DEFAULT_OLLAMA_HOST.
    # If this host is not available at script startup, ollama_client will be None.
    # generate_ollama_response has a fallback to try configuring again if client is None.
    configure_ollama_client()

    if ollama_client:
        print(f"--- Ollama client configured. Testing with model: {DEFAULT_OLLAMA_MODEL} on host {ollama_client._host} ---")

        print("\n--- Test 1: Simple Question ---")
        prompt1 = "What is the capital of France? Respond with only the name of the capital."
        response1 = generate_ollama_response(prompt1)
        if response1:
            print(f"Prompt: {prompt1}")
            print(f"Response: {response1}")
        else:
            print(f"Failed to get response for Test 1 using model {DEFAULT_OLLAMA_MODEL}.")

        print("\n--- Test 2: Title Suggestion ---")
        video_desc_title = "A video showcasing the process of baking a sourdough bread from scratch, including starter maintenance, mixing, shaping, and baking."
        task_title = "Suggest a concise and informative title for a video based on the following description. The title should be suitable for a video platform. Respond with only the title."
        suggested_title = analyze_text_with_llm(video_desc_title, task_title)
        if suggested_title:
            print(f"Video Description: {video_desc_title}")
            print(f"Suggested Title: {suggested_title}")
        else:
            print(f"Failed to get title suggestion for Test 2 using model {DEFAULT_OLLAMA_MODEL}.")

        print("\n--- Test 3: Actor Extraction ---")
        text_actors = "The film 'Cosmic Adventure' stars Nova Starlight, Orion Nebula, and introducing Celeste Moon. Produced by Galaxy Pictures."
        task_actors = "Extract all actor names from the following text. List each name on a new line. If multiple actors, separate them by newlines. Do not include any other text or explanation."
        extracted_actors = analyze_text_with_llm(text_actors, task_actors)
        if extracted_actors:
            print(f"Text for Analysis: {text_actors}")
            print(f"Extracted Actors:\n{extracted_actors}")
        else:
            print(f"Failed to extract actors for Test 3 using model {DEFAULT_OLLAMA_MODEL}.")

        print("\n--- Test 4: Publisher Identification ---")
        text_publisher = "This incredible footage was brought to you by NatureVids Inc. and The Wildlife Trust. (c) 2024 NatureVids Incorporated."
        task_publisher = "Identify the main publisher or company name from the following text. Respond with only the most prominent publisher name."
        identified_publisher = analyze_text_with_llm(text_publisher, task_publisher)
        if identified_publisher:
            print(f"Text for Analysis: {text_publisher}")
            print(f"Identified Publisher: {identified_publisher}")
        else:
            print(f"Failed to identify publisher for Test 4 using model {DEFAULT_OLLAMA_MODEL}.")

        print("\n--- Test 5: Model Not Available ---")
        # This test assumes 'non_existent_model_12345' is not a real model.
        response5 = generate_ollama_response("Test prompt for non-existent model.", model="non_existent_model_12345")
        if not response5:
            print("Correctly failed to get response for non-existent model (Test 5).")
        else:
            print(f"ERROR: Unexpectedly got response for non-existent model: {response5}")

    else:
        print(f"Ollama client could not be configured initially for host {DEFAULT_OLLAMA_HOST}. Some tests might try re-configuration.")

    # Test host override / unavailable host explicitly outside the initial if ollama_client check
    # to ensure generate_ollama_response handles this, even if global client is None initially.
    print("\n--- Test 6: Ollama Host Not Available (using explicit bad host) ---")
    # Using a known non-ollama port for testing connection failure to a specific host.
    response6 = generate_ollama_response("Test prompt for bad host.", host="http://localhost:12345")
    if not response6:
        print("Correctly failed to get response from unavailable Ollama host http://localhost:12345 (Test 6).")
    else:
        print(f"ERROR: Unexpectedly got response from bad host http://localhost:12345: {response6}")

    print("\n--- Test 7: Using default client after a failed temporary host attempt (if client was configured) ---")
    if ollama_client: # This test is only meaningful if the global client was configured.
        prompt7 = "Should this still work with the default client?"
        response7 = generate_ollama_response(prompt7) # No host specified, should use global client
        if response7:
            print(f"Prompt: {prompt7}")
            print(f"Response: {response7} (using default client at {ollama_client._host})")
        else:
            print(f"Failed to get response for Test 7 using default client for model {DEFAULT_OLLAMA_MODEL}.")
    else:
        print("Skipping Test 7 as default Ollama client was not configured initially.")

    print("\n--- End of llm_analyzer.py tests ---")
