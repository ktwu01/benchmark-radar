from datetime import UTC, datetime

from benchmark_radar.describe import (
    clean_card_text,
    github_summary,
    huggingface_summary,
    inherited_short_descriptions,
    strip_title_echo,
)


def _at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


def test_card_text_is_stripped_of_markdown_and_front_matter():
    raw = "---\nlicense: mit\n---\n\n# Title\n\n[![badge](x.svg)](y) Real **prose** here."
    assert clean_card_text(raw) == "Title Real prose here."


def test_card_text_truncates_on_a_sentence_boundary():
    body = "First sentence is meaningful. " + "padding word " * 300
    result = clean_card_text(body)
    assert result.startswith("First sentence is meaningful.")
    assert len(result) <= 2_000


def test_card_text_preserves_prose_for_inline_expansion():
    body = " ".join(f"source-word-{index}" for index in range(100))

    result = clean_card_text(body)

    assert len(result) > 400
    assert "source-word-99" in result


def test_empty_card_text_stays_empty():
    assert clean_card_text(None) == ""
    assert clean_card_text("   \n\t ") == ""
    assert clean_card_text("---\nlicense: mit\n---") == ""


def test_title_echo_is_dropped():
    assert strip_title_echo("my-benchmark", "org/my-benchmark") == ""
    assert strip_title_echo("my-benchmark: real detail", "org/my-benchmark") == "real detail"


def test_huggingface_uses_real_card_prose():
    row = {
        "description": "\n\t\n\tsc-splicing-benchmark\n\t\nMUSSEL scored against truth v4.",
        "cardData": {"license": "mit"},
    }
    assert huggingface_summary(row, "depinwang/sc-splicing-benchmark") == (
        "MUSSEL scored against truth v4."
    )


def test_huggingface_space_card_data_keeps_maintainer_description():
    row = {
        "description": "",
        "cardData": {"short_description": "A public benchmark leaderboard."},
    }
    assert huggingface_summary(row, "lab/leaderboard") == "A public benchmark leaderboard."


def test_huggingface_does_not_rewrite_declared_metadata_as_prose():
    row = {
        "description": "",
        "cardData": {
            "task_categories": ["question-answering"],
            "size_categories": ["1K<n<10K"],
            "language": ["en"],
        },
        "tags": ["license:mit", "region:us", "benchmark", "medical"],
    }
    assert huggingface_summary(row, "org/thing") == ""


def test_huggingface_drops_space_template_scaffolding():
    """Regression: three leaderboards duplicated from gradio-templates/leaderboard
    published its placeholder line as their own description and failed the run."""
    row = {
        "description": None,
        "cardData": {"short_description": "Duplicate this leaderboard to initialize your own!"},
    }
    assert huggingface_summary(row, "XLearning-SCU/ARK-Bench-Leaderboard") == ""
    streamlit = {"description": None, "cardData": {"short_description": "Streamlit template space"}}
    assert huggingface_summary(streamlit, "calibrationcomp/calibration_benchmark") == ""


def test_inherited_short_descriptions_names_the_later_owners_copies():
    """The owner who published the line wrote it. A later owner carrying it
    verbatim duplicated the parent Space and describes nothing of its own."""
    inherited = inherited_short_descriptions(
        [
            ("argilla/synthetic-data-generator", "Build datasets using natural language", _at(1)),
            ("tingao/synthetic-data-generator", "Build datasets using natural language", _at(6)),
            ("909ahmed/synthetic-data-generator", "Build datasets using natural language", _at(9)),
            ("vLAR/PhysInOne", "Physical reasoning scored on 12 tasks.", _at(3)),
        ]
    )
    assert inherited == frozenset(
        {"tingao/synthetic-data-generator", "909ahmed/synthetic-data-generator"}
    )


def test_inherited_short_descriptions_keeps_one_owners_matched_pair():
    """A maintainer describing their own dataset and leaderboard with one
    sentence wrote that sentence, so neither copy is inherited."""
    shared = "Multimodal embeddings on 17 knowledge subtypes."
    assert (
        inherited_short_descriptions(
            [
                ("lab/ark-bench", shared, _at(2)),
                ("lab/ark-bench-leaderboard", shared, _at(4)),
                ("lab/ark-bench-annotations", shared, _at(7)),
            ]
        )
        == frozenset()
    )


def test_inherited_short_descriptions_skips_an_undated_repo():
    """The fetcher accepts a row with no `createdAt`. Without a creation date a
    repo cannot be placed as parent or child, so its line is left alone rather
    than deciding authorship from a timestamp that means something else."""
    shared = "Build datasets using natural language"
    assert (
        inherited_short_descriptions(
            [
                ("argilla/synthetic-data-generator", shared, None),
                ("tingao/synthetic-data-generator", shared, _at(6)),
            ]
        )
        == frozenset()
    )


def test_huggingface_returns_empty_when_source_published_nothing():
    """An unlabelled repo must not receive a generated description."""
    assert huggingface_summary({"description": "", "cardData": {}, "tags": []}, "org/bare") == ""
    assert huggingface_summary({}, "org/bare") == ""


def test_github_blank_description_is_not_filled():
    assert github_summary({"description": None}) == ""
    assert github_summary({"description": "A real blurb."}) == "A real blurb."
