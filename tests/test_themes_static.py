"""Category browsing shares the homepage catalog and search, without a generator."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def browse(payload, **options):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    process = subprocess.run(
        [node, str(ROOT / "tests/themes_catalog_harness.mjs")],
        input=json.dumps({"payload": payload, **options}),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(process.stdout)


def test_category_browse_preserves_the_full_catalog_and_shared_search():
    payload = json.loads((ROOT / "site/data/benchmark-index.json").read_text())
    for category in ("", "Agents"):
        result = browse(
            payload, queries=["HLE", "weather forecasting", "模型评测", "Agents"], category=category
        )
        assert set(result["keys"]) == {row["key"] for row in payload["benchmarks"]}
        assert all(case["actual"] == case["homepage"] for case in result["queries"])
        labels = [name for name, _ in result["categories"]]
        assert len(labels) <= 12
        assert not {"Unsupported", "不支持"}.intersection(labels)


def test_menu_limit_and_quality_exclusion_do_not_hide_records_or_rare_categories():
    rows = [
        dict(
            key=str(i),
            slug=str(i),
            name=f"Benchmark {i}",
            source="test",
            categories=[f"RareCategory{i}"],
        )
        for i in range(18)
    ]
    rows += [
        dict(
            key="quality",
            slug="quality",
            name="Quality benchmark",
            source="test",
            categories=["Unsupported", "不支持"],
        )
    ]
    payload = dict(schema_version=1, count=len(rows), benchmarks=rows)
    result = browse(payload, queries=["RareCategory17", "Quality benchmark"])
    assert set(result["keys"]) == {row["key"] for row in rows}
    assert len(result["categories"]) == 12
    offered = {name for name, _ in result["categories"]}
    omitted = next(
        row
        for row in rows
        if row["categories"][0].startswith("RareCategory") and row["categories"][0] not in offered
    )
    rare_search = browse(payload, queries=[omitted["categories"][0]])
    assert omitted["key"] in rare_search["queries"][0]["actual"]
    assert all(case["actual"] == case["homepage"] and case["actual"] for case in result["queries"])


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "count": 0, "benchmarks": []},
        {"schema_version": 1, "count": 1, "benchmarks": []},
        {"schema_version": 1, "count": 1, "benchmarks": [{}]},
    ],
)
def test_invalid_catalog_is_an_error_instead_of_a_partial_population(payload):
    assert "error" in browse(payload)


@pytest.mark.parametrize("http_status", [200, 503])
def test_catalog_load_failure_finishes_the_error_state_without_using_unloaded_data(http_status):
    result = browse(
        {"schema_version": 1, "count": 1, "benchmarks": [{}]},
        bootError=True,
        httpStatus=http_status,
    )
    assert "could not be loaded" in result["status"]
    assert result["role"] == "alert"
    assert result["ledger"] == "Catalog unavailable; coverage could not be verified."
    assert result["cards"] == 0
    assert result["disabled"]
