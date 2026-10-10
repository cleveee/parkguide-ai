"""Actual dialogue failure shapes, with no network/model calls."""
from parkguide.chat import resolve_query


def users(*texts):
    return [{"role": "user", "content": text} for text in texts]


def test_third_turn_keeps_table_entity_and_original_subject():
    history = users("According to Grand Canyon's saved South Kaibab table, how far below the rim is Cedar Ridge?", "Does it have drinking water marked in that table?")
    query, filters = resolve_query("How much farther from the rim is Skeleton Point than that spot?", history)
    assert filters == {"parks": ["grca"]}
    assert all(term in query for term in ("Cedar Ridge", "South Kaibab", "drinking water", "Skeleton Point"))


def test_park_then_month_followups_keep_camping_and_current_park():
    query, filters = resolve_query("What about October?", users("Yosemite camping in July 2026?", "What about Yellowstone?"))
    assert filters == {"parks": ["yell"]}
    assert "camping" in query and "October" in query and "2026" in query
    assert "Yosemite" not in query and "July" not in query


def test_date_replacement_removes_old_day_but_inherits_year():
    query, filters = resolve_query("October 3?", users("Yosemite camping on September 25, 2026?"))
    assert filters == {"parks": ["yose"]}
    assert "October 3" in query and "2026" in query
    assert "September" not in query and "25" not in query


def test_new_year_preserves_latest_month_after_two_followups():
    query, filters = resolve_query("How about 2027?", users("Yosemite camping on September 25, 2026?", "October 3?"))
    assert filters == {"parks": ["yose"]}
    assert "camping" in query and "October 3" in query and "2027" in query
    assert "September" not in query and "25" not in query and "2026" not in query


def test_negated_old_park_does_not_enter_filters_or_query():
    query, filters = resolve_query("I meant Yellowstone, not Yosemite.", users("Can I bring a pet to Yosemite?"))
    assert filters == {"parks": ["yell"]}
    assert "pet" in query and "Yosemite" not in query


def test_both_comparison_restores_two_parks_and_subject():
    query, filters = resolve_query("Compare those two distances.", users("What separation does Yosemite recommend when seeing a bear outside a developed area?", "And for a bear in Yellowstone?"))
    assert filters == {"parks": ["yose", "yell"]}
    assert all(term in query for term in ("separation", "bear", "Yosemite", "Yellowstone"))


def test_park_only_reply_inherits_subject_after_clarification():
    query, filters = resolve_query("Yosemite.", users("Where can I reserve a campsite?"))
    assert filters == {"parks": ["yose"]}
    assert "reserve a campsite" in query


def test_new_standalone_subject_does_not_keep_old_camping_or_dates():
    query, filters = resolve_query("Can I bring a pet to Yellowstone?", users("Yosemite camping in July 2026?"))
    assert filters == {"parks": ["yell"]}
    assert "camping" not in query and "July" not in query and "2026" not in query


def test_assistant_generated_numbers_and_names_do_not_enter_query():
    history = users("Yosemite bear viewing?") + [{"role": "assistant", "content": "Invented 9999 yards at Secret Meadow."}]
    query, filters = resolve_query("And in Yellowstone?", history)
    assert filters == {"parks": ["yell"]}
    assert "bear" in query and "9999" not in query and "Secret Meadow" not in query


def test_iso_date_changes_as_complete_calendar_date():
    query, _ = resolve_query("How about 2027-10-03?", users("Yosemite camping on 2026-09-25?"))
    assert "October 3" in query and "2027" in query
    assert "2026" not in query and "09-25" not in query


def test_explicit_comparison_adds_new_park_to_prior_one():
    query, filters = resolve_query("Compare it with Yellowstone.", users("What separation does Yosemite recommend around bears?"))
    assert filters == {"parks": ["yose", "yell"]}
    assert "separation" in query and "Yosemite" in query and "Yellowstone" in query


def test_numeric_calendar_date_replaces_old_date_and_keeps_subject():
    query, filters = resolve_query("10/3/2027?", users("Yosemite camping on 9/25/2026?"))
    assert filters == {"parks": ["yose"]}
    assert "camping" in query and "October 3" in query and "2027" in query
    assert "2026" not in query and "9/25" not in query


def test_abbreviated_month_replaces_old_day():
    query, _ = resolve_query("Oct 3?", users("Yosemite camping on Sep 25, 2026?"))
    assert "Oct 3" in query and "2026" in query
    assert "Sep" not in query and "25" not in query


def test_existential_there_does_not_inherit_an_unrelated_bear_question():
    history = users("How far should I stay from a bear in Yosemite?")
    for question in ("Are there toilets at the visitor center?", "What is there to do with kids?"):
        query, filters = resolve_query(question, history)
        assert filters == {"parks": ["yose"]}
        assert "bear" not in query
        assert "Previous topic" not in query


def test_referential_there_still_inherits_the_previous_place():
    query, filters = resolve_query("Can I bring my dog there?", users("Tell me about Yosemite's Lower Yosemite Fall trail."))
    assert filters == {"parks": ["yose"]}
    assert "Lower Yosemite Fall" in query


def test_place_reply_to_clarification_keeps_the_original_duration_question():
    history = users("How long does it take?") + [
        {"role": "assistant", "content": "Which trail, drive, or activity in Yosemite National Park do you mean?"},
    ]
    query, _ = resolve_query("The walk to Lower Yosemite Fall.", history)
    assert "How long does it take" in query
    assert "Lower Yosemite Fall" in query


def test_new_question_after_clarification_does_not_inherit_the_abandoned_request():
    history = users("How long does it take?") + [
        {"role": "assistant", "content": "Which trail, drive, or activity in Yosemite National Park do you mean?"},
    ]
    query, _ = resolve_query("What are the pet rules?", history)
    assert "How long" not in query


def test_pet_pronoun_and_alternative_plan_keep_the_original_subject():
    history = users("Where may I take my dog at Grand Canyon?", "What if I carry him down an inner canyon trail below the rim?")
    query, filters = resolve_query("Could we ride a park shuttle bus instead?", history)
    assert filters == {"parks": ["grca"]}
    assert "dog" in query and "carry him" in query


def test_named_place_calendar_words_survive_followups_without_becoming_dates():
    for place in ("lower yosemite fall", "May Lake", "Fern Spring"):
        query, filters = resolve_query("How far is it?", users(f"Tell me about {place} in Yosemite."))
        assert filters == {"parks": ["yose"]}
        assert place in query
        assert "Date:" not in query


def test_relative_date_replaces_prior_calendar_in_a_short_followup():
    query, _ = resolve_query("Today?", users("Was Tioga Road open in July 2025 in Yosemite?"))
    assert "Tioga Road open" in query
    assert "July" not in query and "2025" not in query
    assert "Date: Today" in query
