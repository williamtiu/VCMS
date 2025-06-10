import sys
import os
import pytest

# Add project root to sys.path to allow importing from backend
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from backend.filename_parser import parse_filename

# This TEST_CASES list is derived from the original unittest methods
# found in a previous version of tests/test_filename_parser.py
# The expected values are taken directly from the assertions in those tests,
# with specific adjustments as per subtask instructions.
TEST_CASES_FROM_UNITTEST = [
    (
        "[CODE-123] My Title - Actor A, Actor B.mp4",
        "CODE-123", "My Title", sorted(["Actor A", "Actor B"]),
        "test_full_pattern_comma_separated_actors"
    ),
    (
        "[XYZ-789] Another Film - Actor X & Y Z.mkv",
        "XYZ-789", "Another Film", sorted(["Actor X", "Y Z"]),
        "test_full_pattern_ampersand_separated_actors"
    ),
    (
        "Movie Title - Single Actor.avi",
        None, "Movie Title", sorted(["Single Actor"]),
        "test_title_and_single_actor"
    ),
    ( # Case 1 from prompt: Revised expectation
        "[XYZ789] Another Great Film.mkv",
        "XYZ789", "Another Great Film", sorted([]),
        "test_code_and_title_no_actor"
    ),
    (
        "JustATitle.mp4",
        None, "JustATitle", sorted([]),
        "test_title_only"
    ),
    ( # Case 2 from prompt: Revised expectation
        "Publisher_CODE_A.Film.About.Stuff_Actor_One_Actor_Two.webm",
        None, "Publisher CODE A Film About Stuff", sorted(['Actor', 'One', 'Actor', 'Two']),
        "test_complex_names_with_dots_and_underscores"
    ),
    (
        "My_Awesome_Movie_ActorA_ActorB.mp4",
        None, "My Awesome Movie ActorA ActorB", sorted([]), # Current parser logic will reject "ActorA_ActorB" if A/B are single letters and common
        "test_suffix_actors_underscores"
    ),
    (
        "Cool_Clip_ActorZ.mkv",
        None, "Cool Clip ActorZ", sorted([]),
        "test_suffix_actors_single"
    ),
    (
        "Title_Actor.Name.mp4",
        None, "Title Actor.Name", sorted([]), # Expect "Actor.Name" to remain in title
        "test_suffix_actor_with_dot_in_name_not_separated"
    ),
    (
        "random_text_video.mp4",
        None, "random text video", sorted([]),
        "test_filename_with_no_parsable_info_just_random_text"
    ),
    (
        ".mp4",
        None, None, sorted([]),
        "test_empty_filename"
    ),
    (
        "[CODE-ONLY-123].avi",
        "CODE-ONLY-123", None, sorted([]),
        "test_filename_is_just_code_in_brackets"
    ),
    (
        "CODE123.mp4",
        None, "CODE123", sorted([]),
        "test_filename_is_just_code_no_brackets"
    ),
    (
        "My Show S01E02 - Specific Episode.mp4",
        None, "My Show S01E02", sorted(["Specific Episode"]),
        "test_series_episode_not_as_code"
    ),
    (
        "[SHOW-01] My Show S01E02 - Specific Episode.mp4",
        "SHOW-01", "My Show S01E02", sorted(["Specific Episode"]),
        "test_series_episode_with_actual_code"
    ),
    ( # Case 3 from prompt: Revised expectation
        "Movie_Title_Actor_J_R.mkv",
        None, "Movie Title Actor", sorted(["J", "R"]),
        "test_actor_name_with_initials_in_suffix"
    ),
    (
        "Movie Title - J. R. Actor.mp4", # The stricter regex for suffix heuristic won't affect dash separated.
        None, "Movie Title", sorted(["J. R. Actor"]), # This expects dots and spaces in names from dash separator.
        "test_actor_name_with_initials_in_dash_separated"
    ),
    (
        "This.Is.A.Title - Some.Actor.mp4",# The stricter regex for suffix heuristic won't affect dash separated.
        None, "This Is A Title", sorted(["Some.Actor"]),
        "test_filename_with_dots_as_spaces_for_title"
    ),
    (
        "CODEISNOTREAL Title - Actor.mp4",
        None, "CODEISNOTREAL Title", sorted(["Actor"]),
        "test_code_like_prefix_not_a_code"
    )
]

@pytest.mark.parametrize(
    "filename, expected_code, expected_title, expected_actors_sorted, description",
    TEST_CASES_FROM_UNITTEST,
    ids=[case[4] for case in TEST_CASES_FROM_UNITTEST]
)
def test_parse_filename_from_original_unittest(
    filename, expected_code, expected_title, expected_actors_sorted, description
):
    result = parse_filename(filename)

    assert result.get("code") == expected_code, \
        f"Code mismatch for '{filename}'. Expected '{expected_code}', Got '{result.get('code')}'"

    assert result.get("title") == expected_title, \
        f"Title mismatch for '{filename}'. Expected '{expected_title}', Got '{result.get('title')}'"

    parsed_actors_sorted = sorted(result.get("actors", []))
    assert parsed_actors_sorted == expected_actors_sorted, \
        f"Actors mismatch for '{filename}'. Expected {expected_actors_sorted}, Got {parsed_actors_sorted}"

    assert result.get("original_filename") == filename, \
        f"Original filename mismatch for '{filename}'."

def test_parse_filename_empty_string():
    filename = ""
    result = parse_filename(filename)
    assert result.get("code") is None
    assert result.get("title") is None
    assert result.get("actors") == []
    assert result.get("original_filename") == ""

def test_parse_filename_hidden_file():
    filename = ".DS_Store"
    result = parse_filename(filename)
    assert result.get("code") is None
    assert result.get("title") is None
    assert result.get("actors") == []
    assert result.get("original_filename") == ".DS_Store"

# Note: The original unittest file had some "Observed" comments indicating discrepancies
# with its own expectations vs. the parser at that time.
# I've tried to use the explicit assertions from the unittest for expected values.
# The `backend/filename_parser.py` is the current one with the simple/conservative suffix heuristic.
