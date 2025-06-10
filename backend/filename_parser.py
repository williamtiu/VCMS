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
ACTOR_PATTERN_DASH_SEPARATOR = re.compile(r"\s-\s+((?:[A-Z][\w\s'.-]*?)(?:\s*[,&]\s*[A-Z][\w\s'.-]*?)*)$")

# Suffix actor pattern: attempts to find one or more capitalized words/initials at the end of a string,
# preceded by a space or underscore.
# Group 1 captures the full actor string (e.g., "Actor One_Actor Two", "ActorZ").
# Example: "_ActorZ", " ActorA_ActorB", " Actor C", "_Actor_One_Actor_Two"
# This is the regex specified in the prompt.
ACTOR_PATTERN_SUFFIX_HEURISTIC = re.compile(r"[_\s](([A-Z][a-z']+|[A-Z])(?:[_\s]([A-Z][a-z']+|[A-Z]))*)$")

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
    match_no_bracket_code = CODE_PATTERN_NO_BRACKETS.search(filename_part)
    if match_no_bracket_code:
        potential_code = match_no_bracket_code.group(1)
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
    actors: List[str] = []
    remaining_filename_part: str = filename_part
    match = ACTOR_PATTERN_DASH_SEPARATOR.search(filename_part)
    if match:
        actor_string = match.group(1)
        remaining_filename_part = filename_part[:match.start()].strip(" _-.")
        actors = [name.strip().replace("_", " ") for name in re.split(r"\s*[,&]\s*", actor_string) if name.strip()]
        logger.debug(f"Extracted dash-separated actors: {actors}, remaining: '{remaining_filename_part}'")
    else:
        logger.debug("No dash-separated actors found.")
    return actors, remaining_filename_part


def _extract_actors_suffix_heuristic(filename_part: str) -> Tuple[List[str], str]:
    extracted_actors: List[str] = []
    remaining_filename_part: str = filename_part

    match = ACTOR_PATTERN_SUFFIX_HEURISTIC.search(filename_part)
    if match:
        actor_candidate_str: str = match.group(1) # Group 1 is the actor(s) string
        logger.debug(f"Suffix heuristic matched candidate: '{actor_candidate_str}' from full match '{match.group(0)}'")

        if COMMON_SUFFIX_NON_ACTOR_PATTERN.search(actor_candidate_str):
            logger.debug(f"Candidate '{actor_candidate_str}' blacklisted by COMMON_SUFFIX_NON_ACTOR_PATTERN.")
            return [], filename_part

        # Split the actor_candidate_str by underscore or space to get individual parts
        name_parts = [p for p in re.split(r"[_\s]+", actor_candidate_str) if p]

        if not name_parts:
            return [], filename_part

        valid_name_parts = []
        all_parts_valid = True
        for part in name_parts:
            is_initial = bool(re.fullmatch(r"[A-Z]", part))
            is_cap_word = bool(re.fullmatch(r"[A-Z][a-z']+", part)) # Allows only letters and apostrophe

            if is_initial: # Initials are always valid if they are single uppercase letters
                valid_name_parts.append(part)
            elif is_cap_word:
                if part.lower() not in COMMON_NON_ACTOR_WORDS:
                    valid_name_parts.append(part)
                else: # Capitalized word is a common non-actor word
                    logger.debug(f"Part '{part}' in candidate '{actor_candidate_str}' is a common word and invalidates the candidate.")
                    all_parts_valid = False
                    break
            else: # Part is not a valid initial or capitalized word (e.g. "Jean-Luc", "word", "W.")
                logger.debug(f"Part '{part}' in candidate '{actor_candidate_str}' is invalid (format or structure).")
                all_parts_valid = False
                break

        if all_parts_valid:
            extracted_actors.extend(valid_name_parts) # Add all validated parts as separate actors
            remaining_filename_part = filename_part[:match.start(0)].strip(" _-.")
            logger.debug(f"Extracted suffix heuristic actors: {extracted_actors}, remaining: '{remaining_filename_part}'")
        else:
            # If any part is invalid, the entire suffix candidate is rejected.
            logger.debug(f"Candidate '{actor_candidate_str}' rejected due to invalid part(s).")
            return [], filename_part

    if not extracted_actors:
        logger.debug(f"No suffix heuristic actors extracted from: '{filename_part}'")
    return extracted_actors, remaining_filename_part


def _normalize_title(title_candidate: str, extracted_code: Optional[str]) -> Optional[str]:
    if not title_candidate:
        logger.debug("Title candidate is empty.")
        return None
    normalized_title: str = re.sub(r"[._]", " ", title_candidate)
    normalized_title = re.sub(r"\s+", " ", normalized_title).strip(" -")
    if extracted_code and normalized_title.lower() == extracted_code.lower():
        logger.debug(f"Normalized title '{normalized_title}' matched extracted code '{extracted_code}'. Setting title to None.")
        return None
    if not normalized_title:
        logger.debug("Title became empty after normalization.")
        return None
    logger.debug(f"Normalized title: '{normalized_title}' from candidate: '{title_candidate}'")
    return normalized_title


def parse_filename(filename_string: str) -> Dict[str, Any]:
    logger.info(f"Parsing filename: '{filename_string}'")
    if not filename_string or filename_string.startswith('.'):
        logger.warning(f"Invalid or empty filename provided: '{filename_string}'")
        return {"code": None, "actors": [], "title": None, "original_filename": filename_string}

    filename_base: str = filename_string.rsplit('.', 1)[0]
    if not filename_base:
        logger.warning(f"Filename without extension is empty for: '{filename_string}'")
        return {"code": None, "actors": [], "title": None, "original_filename": filename_string}

    extracted_code, remainder_after_code = _extract_code(filename_base)
    actors_dash, remainder_after_dash_actors = _extract_actors_dash_separated(remainder_after_code)

    actors_suffix: List[str] = []
    remainder_after_suffix_actors: str = remainder_after_dash_actors

    if not actors_dash:
        actors_suffix, remainder_after_suffix_actors = _extract_actors_suffix_heuristic(remainder_after_dash_actors)

    combined_actors_map: Dict[str, str] = {}
    for actor_name in actors_dash + actors_suffix:
        if actor_name.lower() not in combined_actors_map:
            combined_actors_map[actor_name.lower()] = actor_name

    final_actors_list: List[str] = list(combined_actors_map.values())
    logger.debug(f"Combined and unique actors: {final_actors_list}")

    title_candidate: str = remainder_after_suffix_actors
    extracted_title = _normalize_title(title_candidate, extracted_code)

    if not extracted_title and not final_actors_list and extracted_code and filename_base.lower() == extracted_code.lower():
        extracted_title = None
    elif not extracted_title and filename_base and not final_actors_list and not extracted_code:
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
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s', force=True)
    test_filenames = [
        "[ABC-123] The Video Title - Actor Name1, Actor Name2.mp4",
        "XYZ-007 Another Movie - SingleActor.avi",
        "[DEF-456] Third.Title.ActorX.mkv",
        "Publisher_CODE_A.Film.About.Stuff_Actor_One_Actor_Two.webm",
        "Just A Title - Some Actor.mov",
        "Cool_Movie_Clip_UnknownActor.webm",
        "ANOTHER_CODE-001_A_Different_Film_With_Actors_Like_Actor_One_And_Actor_Two.mkv",
        "[GHI-789] Title.With.Dots - Actor1 & Actor2.mp4",
        "MyMovie_ActorZ.mp4",
        "Series_Name_Ep_01_Title_Part_Actor_Person_Actress_Another.mp4",
        "CODE123_Title_With_Underscores_Actor_One_Actor_Two.mkv",
        "NoCodeTitle_ActorName.mp4",
        "JustATitleNoActors.mp4",
        "[ONLYCODE-001].mp4",
        "Actor_Only_In_Name.mp4",
        "MOVIE_TITLE_ActressA_ActorB_ActorC.mp4",
        "Film Title With Spaces - Actor One, Actor Two & Actor Three.mkv",
        "[XYZ789] Another Great Film.mkv",
        "My Show S01E02 - Specific Episode.mp4",
        "[SHOW-01] My Show S01E02 - Specific Episode.mp4",
        "Movie_Title_Actor_J_R.mkv",
        "CODE123.mp4"
    ]
    for filename in test_filenames:
        logger.debug(f"\n--- Testing filename: {filename} ---")
        result = parse_filename(filename)
        print(f"Original: {filename}\nParsed:   {result}\n")
    logger.info("--- Filename Parser Tests Complete ---")
