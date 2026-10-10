"""Generic invented tables verify arithmetic; no park-specific implementation."""
from copy import deepcopy

import pytest

from parkguide.table_math import derive_table_difference, select_named_table_rows


def context(chunk="c1", rows=None, header=None, doc="d1", start=10):
    header = header or "| Place | Distance from Rim (mi/km) | Elevation (ft/m) | DW |"
    rows = rows or ["| Aspen Point | 3/4.8 | 5220/1591 | |", "| Birch Ridge | 1.5/2.4 | 6120/1865 | |"]
    return {"chunk_id": chunk, "doc_id": doc, "content_hash": "source-hash", "source_span": [{"start": start, "end": start + 100, "kind": "table_header"}],
            "text": "Heading: Invented trail\n\n" + header + "\n| --- | --- | --- | --- |\n" + "\n".join(rows)}


def history(*texts):
    return [{"role": "user", "content": text} for text in texts]


def test_relative_reference_uses_prior_user_row_exact_cells_and_original_id():
    ctx = context(); before = deepcopy(ctx)
    result = derive_table_difference("How much farther from the rim is Aspen Point than that spot?", history("How far is Birch Ridge from the rim?", "Does it have drinking water?"), [ctx])
    assert result["trace"]["equation"] == "3 - 1.5 = 1.5 mi"
    assert result["claim"]["evidence_ids"] == ["c1"]
    assert result["trace"]["column"] == "Distance from Rim (mi/km)" and result["trace"]["unit_role"] == "primary"
    assert result["trace"]["operands"][0]["source_cell"] == "3/4.8"
    assert ctx == before


def test_explicit_metric_unit_selects_paired_source_values_without_conversion():
    result = derive_table_difference("How much farther in kilometers is Aspen Point than Birch Ridge?", [], [context()])
    assert result["trace"]["equation"] == "4.8 - 2.4 = 2.4 km"
    assert result["trace"]["unit_role"] == "paired" and result["trace"]["column_units"] == ["mi", "km"]


def test_elevation_does_not_accidentally_use_distance_column():
    result = derive_table_difference("What is the difference in elevation between Aspen Point and Birch Ridge?", [], [context()])
    assert result["trace"]["equation"] == "6120 - 5220 = 900 ft"
    assert result["trace"]["column"] == "Elevation (ft/m)"
    assert result["trace"]["operation"] == "absolute_difference"
    assert [operand["value"] for operand in result["trace"]["operands"]] == ["5220", "6120"]


def test_less_direction_subtracts_larger_reference_from_smaller_target_correctly():
    result = derive_table_difference("How many less dollars does A have than B?", [], [context(header="| Place | Funds (USD) | Extra | Note |", rows=["| A | 1.1 | | |", "| B | 3.3 | | |"] )])
    assert result["trace"]["equation"] == "3.3 - 1.1 = 2.2 USD"
    assert result["trace"]["operation"] == "second_minus_first"


@pytest.mark.parametrize("question", [
    "How much farther is Birch Ridge than Aspen Point?",
    "What is the difference between Aspen Point and Birch Ridge?",
    "How much farther in feet is Aspen Point than Birch Ridge?",
    "How much farther is Missing Point than Birch Ridge?",
    "How far is Aspen Point?",
])
def test_conflicting_direction_ambiguous_column_missing_unit_or_entity_fail_closed(question):
    assert derive_table_difference(question, [], [context()]) is None


def test_conflicting_duplicate_values_fail_even_in_different_table_chunk():
    other = context("c2", rows=["| Aspen Point | 8/12.8 | 5220/1591 | |"])
    assert derive_table_difference("How much farther is Aspen Point than Birch Ridge?", [], [context(), other]) is None


def test_same_table_split_rows_can_combine_while_different_tables_cannot():
    a = context("a", rows=["| Aspen Point | 3/4.8 | 5220/1591 | |"])
    b = context("b", rows=["| Birch Ridge | 1.5/2.4 | 6120/1865 | |"])
    result = derive_table_difference("How much farther is Aspen Point than Birch Ridge?", [], [a, b])
    assert result["claim"]["evidence_ids"] == ["a", "b"]
    b["source_span"][0]["start"] = 999
    assert derive_table_difference("How much farther is Aspen Point than Birch Ridge?", [], [a, b]) is None


def test_no_header_unit_is_never_inferred_from_numbers_or_question():
    ctx = context(header="| Place | Distance | Elevation | DW |")
    assert derive_table_difference("How much farther in miles is Aspen Point than Birch Ridge?", [], [ctx]) is None


def test_assistant_named_row_does_not_resolve_user_reference():
    assert derive_table_difference("How much farther is Aspen Point than that spot?", [{"role": "assistant", "content": "Birch Ridge"}], [context()]) is None


def test_named_selector_returns_actual_row_witness_without_mutating_ranks():
    ctx = context(); original = deepcopy(ctx)
    rows = select_named_table_rows([ctx], ["How far is Birch Ridge?", "Does it have water in that table?"])
    assert len(rows) == 1 and rows[0]["row_label"] == "Birch Ridge" and rows[0]["chunk_id"] == "c1"
    assert ctx == original


def test_reverse_word_order_cannot_reverse_target_and_reference_silently():
    assert derive_table_difference("How much farther than Aspen Point is Birch Ridge?", [], [context()]) is None


def test_unsupported_units_decline_without_unit_guessing():
    ctx = context(header="| Place | Count (visitors) | Extra | Note |", rows=["| A | 1 | | |", "| B | 3 | | |"])
    assert derive_table_difference("How many more visitors does B have than A?", [], [ctx]) is None
