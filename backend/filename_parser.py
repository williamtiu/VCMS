import re
import logging
from typing import Tuple, List, Optional, Dict, Any

# Configure logging for the module.
# If this module is imported, the application's logging config will likely take precedence.
# If run directly, this basicConfig will apply.
logger = logging.getLogger(__name__)
if not logger.handlers: # Add handler only if no other handlers are configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


# --- Regex Patterns ---
# Pattern for codes in square brackets, e.g., [ABC-123], [XYZ.789]
# Allows word characters (alphanumeric + underscore), dots, and hyphens within brackets.
CODE_PATTERN_BRACKETS = re.compile(r"\[([\w.-]+)\]")

# Pattern for codes like COMPANY-CODE123 or COMPANY_CODE_001 (not in brackets).
# Requires a word part (letters, numbers, underscores), then a hyphen or underscore,
# then a part containing at least one digit.
# Example: XYZ-007, PUBLISHER_CODE-123A
CODE_PATTERN_NO_BRACKETS = re.compile(r"((?:[A-Z][A-Za-z0-9]*_)*[A-Z][A-Za-z0-9]*[-_][A-Za-z0-9]*\d[A-Za-z0-9]*)")

# Pattern for actors separated by " - " (dash with spaces).
# Allows names with word characters, spaces, apostrophes, dots, and hyphens.
# Handles multiple actors separated by comma (,) or ampersand (&).
# Example: " - Actor One, Actor J. Two & Dr. Third-Name"
ACTOR_PATTERN_DASH_SEPARATOR = re.compile(r"\s-\s+((?:[A-Z][\w\s'.-]+?)(?:\s*[,&]\s*[A-Z][\w\s'.-]+?)*)$")

# Suffix actor pattern: attempts to find one or two capitalized words/initials at the end of a string,
# preceded by a space or underscore. This is a conservative heuristic.
# Group 1 captures the actor string part (e.g., "ActorZ" or "ActorA_ActorB").
# Example: "_ActorZ", " ActorA_ActorB", " Actor C"
ACTOR_PATTERN_SUFFIX_HEURISTIC = re.compile(r"[_\s](([A-Z][a-z']+|[A-Z])(?:[_\s]([A-Z][a-z']+|[A-Z]))?)$")

# List of common words (lowercase) that are unlikely to be actor names, especially if they are single parts.
# Used by suffix heuristic.
COMMON_NON_ACTOR_WORDS = [
    'in', 'on', 'of', 'a', 'an', 'the', 'is', 'at', 'to', 'and', 'or', 'but', 'vs', 'vs.',
    'part', 'ep', 'episode', 'vol', 'volume', 'chapter', 'scene', 'official', 'trailer',
    'movie', 'film', 'video', 'clip', 'final', 'extended', 'uncut', 'remastered', 'ost',
    'soundtrack', 'dvd', 'hd', 'sd', 'bd', 'cd' # Also common media terms
]
# Pattern to filter out whole candidate strings that look like common non-actor suffixes (e.g., "Part_1", "The_End")
COMMON_SUFFIX_NON_ACTOR_PATTERN = re.compile(r"(?:Part|Ep|Vol|Chapter|Scene|The|An|A)[_\s]?\d+$", re.IGNORECASE)


def _extract_code(filename_part: str) -> Tuple[Optional[str], str]:
    """
    Extracts a code (bracketed or non-bracketed) from the beginning or anywhere in the filename part.
    Bracketed codes are prioritized.

    Args:
        filename_part (str): The part of the filename to search for a code.

    Returns:
        Tuple[Optional[str], str]: (extracted_code, remaining_filename_part)
    """
    extracted_code: Optional[str] = None
    remaining_filename_part: str = filename_part

    # Try bracketed code first (searches anywhere in the string)
    match_bracket_code = CODE_PATTERN_BRACKETS.search(filename_part)
    if match_bracket_code:
        extracted_code = match_bracket_code.group(1)
        # Remove the matched part (group 0 includes brackets) from the string
        remaining_filename_part = filename_part.replace(match_bracket_code.group(0), "", 1).strip(" _-.")
        logger.debug(f"Extracted bracketed code: '{extracted_code}', remaining: '{remaining_filename_part}'")
        return extracted_code, remaining_filename_part

    # If no bracketed code, try non-bracketed code (searches anywhere)
    # This pattern is more likely to have false positives if not handled carefully.
    # We ensure it's not part of common series/episode markers.
    match_no_bracket_code = CODE_PATTERN_NO_BRACKETS.search(filename_part)
    if match_no_bracket_code:
        potential_code = match_no_bracket_code.group(1)
        # Filter out common series/episode patterns (e.g., _ep01, -part2)
        if not re.search(r"[_.-](?:ep|episode|part|vol|chapter|sc)[_.-]?\d+$", potential_code, re.IGNORECASE):
            extracted_code = potential_code
            remaining_filename_part = filename_part.replace(match_no_bracket_code.group(0), "", 1).strip(" _-.")
            logger.debug(f"Extracted non-bracketed code: '{extracted_code}', remaining: '{remaining_filename_part}'")
            return extracted_code, remaining_filename_part
        else:
            logger.debug(f"Potential non-bracketed code '{potential_code}' filtered out as episode/part marker.")

    logger.debug(f"No code extracted from: '{filename_part}'")
    return None, filename_part


def _extract_actors_dash_separated(filename_part: str) -> Tuple[List[str], str]:
    """
    Extracts actors from a filename part assuming they are at the end, separated by " - ".

    Args:
        filename_part (str): The filename part to process.

    Returns:
        Tuple[List[str], str]: (list_of_actor_names, remaining_filename_part)
    """
    actors: List[str] = []
    remaining_filename_part: str = filename_part

    match = ACTOR_PATTERN_DASH_SEPARATOR.search(filename_part)
    if match:
        actor_string = match.group(1)
        remaining_filename_part = filename_part[:match.start()].strip(" _-.")
        # Split actor string by comma or ampersand, then clean up each name
        actors = [name.strip().replace("_", " ") for name in re.split(r"\s*[,&]\s*", actor_string) if name.strip()]
        logger.debug(f"Extracted dash-separated actors: {actors}, remaining: '{remaining_filename_part}'")
    else:
        logger.debug("No dash-separated actors found.")

    return actors, remaining_filename_part


def _extract_actors_suffix_heuristic(filename_part: str) -> Tuple[List[str], str]:
    """
    Extracts actors from the suffix of a filename part using heuristics.
    This is conservative and looks for 1-2 capitalized words/initials at the very end.

    Args:
        filename_part (str): The filename part to process.

    Returns:
        Tuple[List[str], str]: (list_of_actor_names, remaining_filename_part)
    """
    extracted_actors: List[str] = []
    remaining_filename_part: str = filename_part

    match = ACTOR_PATTERN_SUFFIX_HEURISTIC.search(filename_part)
    if match:
        actor_candidate_str: str = match.group(1) # The matched actor(s) string part e.g. "ActorA_ActorB" or "ActorName"
        logger.debug(f"Suffix heuristic matched candidate: '{actor_candidate_str}' from separator '{match.group(0)}'")

        # Filter 1: Broad filter for the whole candidate string (e.g., "_Part1", " The_End")
        is_blacklisted_candidate: bool = False
        if COMMON_SUFFIX_NON_ACTOR_PATTERN.search(actor_candidate_str):
            is_blacklisted_candidate = True
            logger.debug(f"Candidate '{actor_candidate_str}' blacklisted by COMMON_SUFFIX_NON_ACTOR_PATTERN.")
        if actor_candidate_str.lower() in COMMON_NON_ACTOR_WORDS: # Also check if the whole string is a common word
            is_blacklisted_candidate = True
            logger.debug(f"Candidate '{actor_candidate_str}' blacklisted as a common non-actor word.")

        if not is_blacklisted_candidate:
            name_parts: List[str] = [p for p in re.split(r"[_\s]+", actor_candidate_str) if p] # Split and remove empty
            valid_name_parts: List[str] = []

            for part in name_parts:
                is_valid_part = False
                if re.fullmatch(r"[A-Z]", part): # Single uppercase letter (Initial)
                    is_valid_part = True
                elif re.fullmatch(r"[A-Z][a-z']+", part): # Capitalized word
                    if part.lower() not in COMMON_NON_ACTOR_WORDS:
                        is_valid_part = True
                    else:
                        logger.debug(f"Part '{part}' filtered by individual word blacklist.")

                if is_valid_part:
                    valid_name_parts.append(part)
                else:
                    logger.debug(f"Part '{part}' deemed invalid. Discarding candidate '{actor_candidate_str}'.")
                    valid_name_parts = []
                    break

            if valid_name_parts:
                # Grouping logic
                if len(valid_name_parts) > 1 and "_" in match.group(0): # match.group(0) has the separator
                    extracted_actors.extend(valid_name_parts)
                elif valid_name_parts:
                    extracted_actors.append(" ".join(valid_name_parts))

                if extracted_actors:
                    remaining_filename_part = filename_part[:match.start(0)].strip(" _-.") # Use start(0) for whole match
                    logger.debug(f"Extracted suffix heuristic actors: {extracted_actors}, remaining: '{remaining_filename_part}'")

    if not extracted_actors: # ensure logging if no actors found by this heuristic specifically
        logger.debug(f"No suffix heuristic actors extracted from: '{filename_part}'")

    return extracted_actors, remaining_filename_part


def _normalize_title(title_candidate: str, extracted_code: Optional[str]) -> Optional[str]:
    """
    Normalizes and cleans the title string.

    Args:
        title_candidate (str): The raw title string.
        extracted_code (Optional[str]): The code extracted from the filename, if any.

    Returns:
        Optional[str]: The cleaned title, or None if empty or only contained the code.
    """
    if not title_candidate:
        logger.debug("Title candidate is empty.")
        return None

    # Replace common separators (dots, underscores) with spaces
    # Preserve hyphens as they can be part of titles.
    normalized_title: str = re.sub(r"[._]", " ", title_candidate)
    # Consolidate multiple spaces into one
    normalized_title = re.sub(r"\s+", " ", normalized_title).strip(" -") # Also strip leading/trailing hyphens here

    # If the normalized title is the same as the code, it's likely not a real title.
    if extracted_code and normalized_title.lower() == extracted_code.lower():
        logger.debug(f"Normalized title '{normalized_title}' matched extracted code '{extracted_code}'. Setting title to None.")
        return None

    if not normalized_title: # Check if empty after stripping
        logger.debug("Title became empty after normalization.")
        return None

    logger.debug(f"Normalized title: '{normalized_title}' from candidate: '{title_candidate}'")
    return normalized_title


def parse_filename(filename_string: str) -> Dict[str, Any]:
    """
    Parses a video filename string to extract code, actors, and title using helper functions.

    Args:
        filename_string (str): The video filename (including extension).

    Returns:
        Dict[str, Any]: A dictionary containing the extracted parts:
                        "code": str or None
                        "actors": list of str (unique names)
                        "title": str or None
                        "original_filename": str
    """
    logger.info(f"Parsing filename: '{filename_string}'")
    if not filename_string or filename_string.startswith('.'): # Basic check for empty or hidden files
        logger.warning(f"Invalid or empty filename provided: '{filename_string}'")
        return {
            "code": None, "actors": [], "title": None,
            "original_filename": filename_string
        }

    filename_base: str = filename_string.rsplit('.', 1)[0] # Remove extension
    if not filename_base: # If filename was just ".ext"
        logger.warning(f"Filename without extension is empty for: '{filename_string}'")
        return {
            "code": None, "actors": [], "title": None,
            "original_filename": filename_string
        }

    # Step 1: Extract Code
    extracted_code, remainder_after_code = _extract_code(filename_base)

    # Step 2: Extract Actors (Dash Separated first)
    actors_dash, remainder_after_dash_actors = _extract_actors_dash_separated(remainder_after_code)

    # Step 3: Extract Actors (Suffix Heuristic if no dash actors found)
    actors_suffix: List[str] = []
    remainder_after_suffix_actors: str = remainder_after_dash_actors # Initialize with previous remainder

    if not actors_dash: # Only run suffix if dash separator didn't yield actors
        actors_suffix, remainder_after_suffix_actors = _extract_actors_suffix_heuristic(remainder_after_dash_actors)

    # Combine actor lists and ensure uniqueness (case-insensitive for uniqueness check, preserve first encountered case)
    # Using a dict to preserve order and uniqueness based on lowercase name
    combined_actors_map: Dict[str, str] = {}
    for actor_name in actors_dash + actors_suffix:
        if actor_name.lower() not in combined_actors_map:
            combined_actors_map[actor_name.lower()] = actor_name

    final_actors_list: List[str] = list(combined_actors_map.values())
    logger.debug(f"Combined and unique actors: {final_actors_list}")

    # Step 4: Normalize Title from the final remainder
    # The remainder used for title is from the step that last extracted actors, or from code extraction if no actors.
    title_candidate: str = remainder_after_suffix_actors # This holds the correct remainder
    extracted_title = _normalize_title(title_candidate, extracted_code)

    # Fallback title if everything else fails (e.g. filename was just code)
    if not extracted_title and not final_actors_list and extracted_code and filename_base.lower() == extracted_code.lower():
        extracted_title = None # Code was the entire filename, no separate title
    elif not extracted_title and filename_base and not final_actors_list and not extracted_code:
        # If nothing was extracted, the whole original filename_base (cleaned) is the title
        extracted_title = _normalize_title(filename_base, None)


    result = {
        "code": extracted_code,
        "actors": final_actors_list,
        "title": extracted_title,
        "original_filename": filename_string
    }
    logger.info(f"Parsed result for '{filename_string}': {result}")
    return result


if __name__ == '__main__':
    # Configure more verbose logging for direct script execution
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s', force=True)

    test_filenames = [
        "[ABC-123] The Video Title - Actor Name1, Actor Name2.mp4",
        "XYZ-007 Another Movie - SingleActor.avi",
        "[DEF-456] Third.Title.ActorX.mkv", # ActorX might be suffix
        "Publisher_CODE_A.Film.About.Stuff_Actor_One_Actor_Two.webm", # CODE might be company code
        "Just A Title - Some Actor.mov",
        "Cool_Movie_Clip_UnknownActor.webm", # UnknownActor might be suffix
        "ANOTHER_CODE-001_A_Different_Film_With_Actors_Like_Actor_One_And_Actor_Two.mkv",
        "[GHI-789] Title.With.Dots - Actor1 & Actor2.mp4",
        "MyMovie_ActorZ.mp4", # ActorZ as suffix
        "Series_Name_Ep_01_Title_Part_Actor_Person_Actress_Another.mp4", # Suffix actors
        "CODE123_Title_With_Underscores_Actor_One_Actor_Two.mkv", # CODE123 might be code
        "NoCodeTitle_ActorName.mp4", # ActorName as suffix
        "JustATitleNoActors.mp4",
        "[ONLYCODE-001].mp4",
        "Actor_Only_In_Name.mp4", # Suffix actors
        "MOVIE_TITLE_ActressA_ActorB_ActorC.mp4", # Suffix actors
        "Film Title With Spaces - Actor One, Actor Two & Actor Three.mkv",
        "[XYZ789] Another Great Film.mkv", # Test from unit tests (suffix actor "Great Film")
        "My Show S01E02 - Specific Episode.mp4", # Test from unit tests
        "[SHOW-01] My Show S01E02 - Specific Episode.mp4", # Test from unit tests
        "Movie_Title_Actor_J_R.mkv", # Test from unit tests (suffix J_R)
        "CODE123.mp4" # Test from unit tests (code without separator)
    ]

    for filename in test_filenames:
        logger.debug(f"\n--- Testing filename: {filename} ---")
        result = parse_filename(filename)
        print(f"Original: {filename}\nParsed:   {result}\n")

    logger.info("--- Filename Parser Tests Complete ---")
