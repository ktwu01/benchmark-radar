"""The NeMo document's title must not rename the checkpoint it measured."""

from benchmark_radar.benchmark_scores import load_scores
from benchmark_radar.catalog_reports import normalize_reports
from benchmark_radar.model_cards import load_registry


def test_nemo_base_scores_keep_their_identity_in_the_instruct_document():
    # The release post explicitly calls these Base evaluations. The July 18
    # Base README independently prints the same values as the Instruct card.
    # A document title identifies evidence, not every model scored inside it.
    source_id = "mistral_nemo_instruct_2407_model_card"
    normalized = normalize_reports(load_registry(), load_scores())
    rows = [row for row in normalized["score_observations"] if row["source_id"] == source_id]
    assert rows
    assert {row["organization"] for row in rows} == {"Mistral"}
    assert {row["model_name"] for row in rows} == {"Mistral-Nemo-Base-2407"}
    assert {row["model_id"] for row in rows} == {'["Mistral","Mistral-Nemo-Base-2407"]'}
    assert {row["reported_by"] for row in rows} == {"self_reported"}
    documents = [
        document
        for record in normalized["source_records"]
        for document in record["documents"]
        if document["source_id"] == source_id
    ]
    assert documents
    assert {document["organization"] for document in documents} == {"Mistral"}
    assert {document["model_name"] for document in documents} == {"Mistral-Nemo-Instruct-2407"}
