import re

def parse_filename(filename_string):
    """
    Parses a video filename string to extract code, actors, and title.

    Args:
        filename_string (str): The video filename (including extension).

    Returns:
        dict: A dictionary containing the extracted parts:
              "code": str or None
              "actors": list of str
              "title": str or None
              "original_filename": str
    """
    original_filename = filename_string
    filename_no_ext = filename_string.rsplit('.', 1)[0] # Remove extension for easier parsing

    extracted_code = None
    extracted_actors = []
    extracted_title = None

    # Regex for code:
    # Pattern 1: [ANYTHING-REASONABLE-IN-BRACKETS] (e.g., [ABC-123], [XYZ_007], [CODE789])
    code_pattern1 = r"\[([\w.-]+)\]" # Allows word chars, dots, hyphens within brackets
    # Pattern 2: COMPANY-CODE or COMPANY_CODE (e.g., XYZ-007, Publisher_CODE)
    # Requires a structure like WORD-DIGITS or WORD_DIGITS. At least one digit is required.
    # Allows for multiple words before the hyphen/underscore e.g. LONG_COMPANY_NAME-123
    # Removed \b at the end as it prevented matching if code was followed by underscore.
    code_pattern2 = r"((?:[A-Z][A-Za-z0-9]*_)*[A-Z][A-Za-z0-9]*[-_][A-Za-z0-9]*\d[A-Za-z0-9]*)"


    match_code1 = re.search(code_pattern1, filename_no_ext)
    if match_code1:
        extracted_code = match_code1.group(1)
        # Remove the matched code from the string to simplify further parsing
        filename_no_ext = filename_no_ext.replace(match_code1.group(0), "").strip()
    else:
        match_code2 = re.search(code_pattern2, filename_no_ext)
        if match_code2:
            potential_code = match_code2.group(1)
            # Filter out common series/episode patterns (e.g., _ep01, -part2)
            # Check if the potential code ends with an episode/part marker followed by numbers.
            if not re.search(r"[_.-](?:ep|episode|part|vol|chapter|sc)[_.-]?\d+$", potential_code, re.IGNORECASE):
                extracted_code = potential_code
                filename_no_ext = filename_no_ext.replace(match_code2.group(0), "").strip()
            else: # Code looked like an episode/part, so don't extract it as code
                pass # extracted_code remains None or its value from code_pattern1

    # Regex for actors:
    # This is a challenging part and will be kept simple for now.
    # It tries to find names that are often at the end, sometimes after " - ".
    # Regex for actors:
    # Pattern 1: " - Actor Name1, Actor Name2" or " - Actor Name1 & Actor Name2" or " - SingleActorName"
    # Looks for a hyphen separator, then capitalized words (potentially with spaces, underscores, or dots)
    # separated by common delimiters like ',', '&'.
    actor_pattern_dash_separator = r"\s-\s+((?:[A-Z][\w\s'.-]+?)(?:\s*[,&]\s*[A-Z][\w\s'.-]+?)*)$"

    # Pattern 2: Underscore or space separated actors at the end of the string if no clear " - " separator
    # This is more heuristic. Looks for sequences of capitalized words, possibly joined by underscores.
    # Example: Cool_Movie_Clip_ActorA_ActorB.mp4 -> ActorA, ActorB
    # Example: Movie Title Actor One Actor Two.mp4 -> Actor One, Actor Two
    # This pattern attempts to identify segments that are likely actor names.
    # It looks for words starting with a capital letter, possibly containing more capital letters (Initials)
    # or hyphens (Jean-Claude).
    actor_pattern_suffix_heuristic = r"((?:[A-Z][a-zA-Z'-]+(?:_[A-Z][a-zA-Z'-]+)*)(?:[\s_]+(?:[A-Z][a-zA-Z'-]+(?:_[A-Z][a-zA-Z'-]+)*))*)$"


    working_string = filename_no_ext # String to be progressively shortened

    # Attempt to find actors using the " - " separator first
    match_actors_dash = re.search(actor_pattern_dash_separator, working_string)
    if match_actors_dash:
        actor_string = match_actors_dash.group(1)
        # Remove the matched actor string from the working_string for title extraction
        working_string = working_string[:match_actors_dash.start()].strip(" -_.")
        # Split actor string by comma or ampersand, then clean up each name
        extracted_actors = [name.strip().replace("_", " ") for name in re.split(r"\s*[,&]\s*", actor_string)]
    else:
        # If no " - " separator, try the heuristic suffix pattern
        # Split the string by common separators (space, underscore, dot)
        # and evaluate the last few parts if they look like names.
        parts = re.split(r"[_\s.]+", working_string)
        potential_actor_segments = []
        # Heuristic: check the last 1 to 4 segments
        # This needs to be conservative to avoid grabbing title parts.
        # Only consider segments that are capitalized or common actor patterns.
        num_parts_to_check = min(len(parts), 4)
        for i in range(1, num_parts_to_check + 1):
            segment = " ".join(parts[-i:]) # e.g., "Actor", "Actor B", "Actor C D"
            # A simple check: if it contains at least one capitalized word.
            # More robust: use a regex that matches actor-like names.
            # This is still very basic.
            if re.search(r"\b[A-Z][a-z']+\b", segment): # Basic check for capitalized word
                 # Check if it's not a common non-actor word (very basic list)
                if not any(kw in segment.lower() for kw in ['part', 'ep', 'the', 'clip']):
                    # If a potential segment is found, try to match it more formally
                    # This is tricky; for now, let's assume if the last part(s) look like names, they are.
                    # The `actor_pattern_suffix_heuristic` can be too greedy if not anchored.
                    # Let's try to match the whole end of the string for actors if no dash separator

                    # Re-join parts to form a string to test suffix pattern on
                    # This is a bit redundant if we are already iterating parts
                    # Let's refine this:
                    pass # Placeholder for a better suffix actor extraction


        # Revised Suffix Actor Extraction:
        # Try to match known actor patterns at the end of the string.
        # This will be an iterative process.
        # Consider words like "Actor", "Actress" as keywords to help.
        # For now, let's try a simpler approach: if the last few words are capitalized.

        # Simplified Suffix Actor Extraction:
        # Only attempts to find actors if they appear at the very end of the string (after code removal),
        # matching patterns like "_ActorName", " ActorName", "_ActorA_ActorB", or " ActorA ActorB".
        # This is intentionally conservative to reduce false positives from title words.
        else:
            # working_string is filename_no_ext after code removal.
            # Regex tries to capture one or two capitalized words at the end, preceded by a space or underscore.
            # Group 1 captures the whole actor string (e.g., "ActorA_ActorB" or "ActorName").
            suffix_actor_match = re.search(r"[_\s](([A-Z][a-z']+|[A-Z])(?:[_\s]([A-Z][a-z']+|[A-Z]))?)$", working_string)

            if suffix_actor_match:
                actor_candidate_str = suffix_actor_match.group(1) # The matched actor(s) string part e.g. "ActorA_ActorB" or "ActorName"

                # Filter 1: Broad filter for the whole candidate string
                # Avoid common filename suffixes that are not actors like "_Part1", " The_End", "final"
                is_blacklisted_candidate = False
                if re.search(r"(?:Part|Ep|Vol|Chapter|Scene|The|An|A)[_\s]?\d+$", actor_candidate_str, re.IGNORECASE):
                    is_blacklisted_candidate = True
                if actor_candidate_str.lower() in ['final', 'extended', 'uncut', 'remastered', 'official', 'trailer', 'movie', 'film', 'ost', 'soundtrack']:
                    is_blacklisted_candidate = True

                if not is_blacklisted_candidate:
                    name_parts = re.split(r"[_\s]+", actor_candidate_str)
                    valid_name_parts = []

                    # Filter 2: Per-word filter for parts of names
                    # Each part should look like a name and not be a common stop-word (unless it's a single initial)
                    individual_word_blacklist = ['in', 'on', 'of', 'a', 'an', 'the', 'is', 'at', 'to', 'and', 'or', 'but', 'vs', 'vs.']

                    for part in name_parts:
                        is_valid_part = False
                        if re.fullmatch(r"[A-Z]", part): # Single uppercase letter (Initial)
                            is_valid_part = True
                        elif re.fullmatch(r"[A-Z][a-z']+", part): # Capitalized word
                            if part.lower() not in individual_word_blacklist:
                                is_valid_part = True

                        if is_valid_part:
                            valid_name_parts.append(part)
                        else: # Invalid part encountered, means the whole candidate is likely not an actor string
                            valid_name_parts = [] # Discard all parts for this candidate
                            break

                    if valid_name_parts:
                        # Decide how to group the valid_name_parts
                        final_actors_suffix = []
                        # suffix_actor_match.group(0) includes the separator, e.g., "_ActorA_ActorB"
                        # If original separator included an underscore and we have multiple valid parts,
                        # assume they are distinct actors or parts of a name that were underscore_separated.
                        if len(valid_name_parts) > 1 and "_" in suffix_actor_match.group(0):
                            final_actors_suffix.extend(valid_name_parts) # Treat as potentially separate if underscore was involved
                        elif valid_name_parts: # Single valid part, or space-separated parts that form one name.
                            final_actors_suffix.append(" ".join(valid_name_parts))

                        if final_actors_suffix:
                            extracted_actors = final_actors_suffix
                            working_string = working_string[:suffix_actor_match.start(0)].strip(" _-.")
            # If no suffix actor match or filtered out, working_string remains as is.

    # Title is what's left in 'working_string' after removing code and actors
    # Clean up common separators like dots, underscores, leading/trailing hyphens

    # Remove any leftover actor strings if actors were extracted by suffix (less precise)
    # This is a bit dangerous, as it might remove parts of the title if actor extraction was too greedy.
    # For now, the working_string should already have actors removed if they were found.

    title_candidate = working_string.strip()

    # General cleanup for title: replace multiple spaces/underscores, strip unwanted chars
    extracted_title = re.sub(r"[._]", " ", title_candidate) # Replace dots/underscores with spaces
    extracted_title = re.sub(r"-\s*-", "-", extracted_title) # double dash to single
    extracted_title = re.sub(r"\s+", " ", extracted_title).strip(" -") # Normalize spaces and strip

    if not extracted_title and not extracted_code and not extracted_actors and filename_no_ext:
        # If nothing else was extracted, the whole filename (no ext) is the title
        extracted_title = filename_no_ext.replace("_"," ").strip()
    elif not extracted_title and extracted_code and not extracted_actors:
        # If only code was found, and title is empty, it implies there was no title string.
        extracted_title = None


    # Post-processing: if title is just the code, set title to None
    if extracted_title and extracted_code and extracted_title.lower() == extracted_code.lower():
        extracted_title = None

    return {
        "code": extracted_code,
        "actors": list(set(extracted_actors)), # Remove duplicates
        "title": extracted_title if extracted_title else None,
        "original_filename": original_filename
    }

if __name__ == '__main__':
    test_filenames = [
        "[ABC-123] The Video Title - Actor Name1, Actor Name2.mp4",
        "XYZ-007 Another Movie - SingleActor.avi",
        "[DEF-456] Third.Title.ActorX.mkv",
        "Publisher_CODE_Yet_Another_Film_Actor_A_Actor_B.mp4",
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
        "Film Title With Spaces - Actor One, Actor Two & Actor Three.mkv"
    ]

    for filename in test_filenames:
        result = parse_filename(filename)
        print(f"Original: {filename}")
        print(f"Parsed:   {result}\n")

    # Example with more complex actor names
    # print(parse_filename("[COMP-001] My Awesome Movie - John B. Goode, Mary Jane Watson.mp4"))
    # print(parse_filename("Film_With_Actor_J_P_Morgan.mp4"))
    # print(parse_filename("Film_With_Actor_Jean-Claude_Van_Damme.mp4")) # This will be hard
    # print(parse_filename("My_Video_Title_AB_CD_EF.mp4")) #Potential actors AB, CD, EF
    # print(parse_filename("My_Video_Title_ActorA_B_ActorC_D.mp4")) #Potential actors A B, C D
    # print(parse_filename("My_Film_With_Actor_MA_PhD.mp4")) # MA, PhD could be mistaken for actors
    # print(parse_filename("My_Video_With_Acronym_NASA_And_Actor_XYZ.mp4"))

    print("\n--- Testing specific cases ---")
    print(f"Test: [C-007] The.Title - Actor.Name.mp4 -> {parse_filename('[C-007] The.Title - Actor.Name.mp4')}")
    print(f"Test: Publisher_CODE_The_Movie_Actress_Actor.mp4 -> {parse_filename('Publisher_CODE_The_Movie_Actress_Actor.mp4')}")
    print(f"Test: Just A Title - Some_Actor.mov -> {parse_filename('Just A Title - Some_Actor.mov')}")
    print(f"Test: My_Movie_ActorFullName.mp4 -> {parse_filename('My_Movie_ActorFullName.mp4')}")
    print(f"Test: [CODE-1] Title - Actor1,Actor2.mp4 -> {parse_filename('[CODE-1] Title - Actor1,Actor2.mp4')}")
    print(f"Test: Film Title - Actor A, Actor B.mkv -> {parse_filename('Film Title - Actor A, Actor B.mkv')}")
    print(f"Test: Movie Clip.mp4 -> {parse_filename('Movie Clip.mp4')}")
    print(f"Test: [XYZ-123].mp4 -> {parse_filename('[XYZ-123].mp4')}") # Should be code, no title
    print(f"Test: ActorNameOnly.mp4 -> {parse_filename('ActorNameOnly.mp4')}")
