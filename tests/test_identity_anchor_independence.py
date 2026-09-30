"""One repeated artifact cannot warrant an equivalence between benchmarks."""

import pytest
import yaml

from benchmark_radar.catalog_identity import IdentityError, load_identity


@pytest.mark.parametrize(
    "anchors",
    [
        ["gh:owner/repo", "gh:owner/repo"],
        ["gh:Owner/Repo", "gh:owner/repo"],
        ["gh:owner/repo", " gh:owner/repo "],
    ],
)
def test_equivalence_needs_two_distinct_artifacts(tmp_path, anchors):
    # Repeating one artifact used to satisfy len(anchors) >= 2 and authorize
    # identity inheritance between otherwise distinct benchmark records.
    path = tmp_path / "identity.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "equivalent": [{"group_id": "g", "members": ["a", "b"], "anchors": anchors}],
            }
        )
    )
    records = [{"key": key, "slug": key, "name": key, "source": key} for key in ("a", "b")]
    with pytest.raises(IdentityError, match="two independent anchors"):
        load_identity(records, path)


def test_two_different_artifacts_still_authorize_equivalence(tmp_path):
    path = tmp_path / "identity.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "equivalent": [
                    {
                        "group_id": "g",
                        "members": ["a", "b"],
                        "anchors": ["arxiv:2311.12022", "gh:idavidrein/gpqa"],
                    }
                ],
            }
        )
    )
    records = [{"key": key, "slug": key, "name": key, "source": key} for key in ("a", "b")]
    assert load_identity(records, path).siblings_for("a")[0]["key"] == "b"


@pytest.mark.parametrize("anchors", ["gh:owner/repo", ["gh:owner/repo", None], [1, 2]])
def test_anchor_counts_cannot_come_from_scalar_characters_or_non_identifiers(tmp_path, anchors):
    path = tmp_path / "identity.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "equivalent": [{"group_id": "g", "members": ["a", "b"], "anchors": anchors}],
            }
        )
    )
    records = [{"key": key, "slug": key, "name": key, "source": key} for key in ("a", "b")]
    with pytest.raises(IdentityError, match="anchors must be a list of non-empty identifiers"):
        load_identity(records, path)
