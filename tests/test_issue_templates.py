import re
from pathlib import Path

import yaml

TEMPLATE_DIR = Path(__file__).parents[1] / ".github" / "ISSUE_TEMPLATE"
FORM_PATHS = sorted(TEMPLATE_DIR.glob("*.yml"))
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_RE = re.compile(r"[A-Za-z]")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_bilingual(value: str, location: str) -> None:
    assert ENGLISH_RE.search(value), f"{location} has no English copy"
    assert CHINESE_RE.search(value), f"{location} has no Chinese copy"


def test_issue_forms_keep_user_facing_copy_bilingual() -> None:
    for path in FORM_PATHS:
        if path.name == "config.yml":
            continue

        form = load_yaml(path)
        assert_bilingual(form["name"], f"{path.name}: name")
        assert_bilingual(form["description"], f"{path.name}: description")

        if title := form.get("title"):
            assert_bilingual(title, f"{path.name}: title")

        for field in form["body"]:
            attributes = field["attributes"]
            if field["type"] == "markdown":
                assert_bilingual(attributes["value"], f"{path.name}: markdown introduction")
                continue

            assert_bilingual(attributes["label"], f"{path.name}: {field['id']} label")
            if description := attributes.get("description"):
                assert_bilingual(description, f"{path.name}: {field['id']} description")
            for option in attributes.get("options", []):
                assert_bilingual(option, f"{path.name}: {field['id']} option")


def test_issue_chooser_has_no_english_only_blank_issue() -> None:
    config = load_yaml(TEMPLATE_DIR / "config.yml")

    assert config["blank_issues_enabled"] is False
    for link in config["contact_links"]:
        assert_bilingual(link["name"], f"contact link {link['url']}: name")
        assert_bilingual(link["about"], f"contact link {link['url']}: about")


def test_feature_request_form_has_a_small_required_core() -> None:
    form = load_yaml(TEMPLATE_DIR / "feature-request.yml")
    fields = {field.get("id"): field for field in form["body"] if field.get("id")}

    assert form["labels"] == ["new feature"]
    # Issue #388: keep the form to two fields, both required, so it never asks
    # for a third or fourth item.
    assert set(fields) == {"feature", "value"}
    assert all(fields[field_id]["validations"]["required"] for field_id in fields)


def test_issue_forms_ask_for_at_most_two_fields() -> None:
    # Issue #388: every form should collect at most two input fields, so a
    # contributor never faces three or four boxes to fill.
    for path in FORM_PATHS:
        if path.name == "config.yml":
            continue
        form = load_yaml(path)
        field_ids = [field.get("id") for field in form["body"] if field.get("id")]
        assert len(field_ids) <= 2, f"{path.name} has {len(field_ids)} fields"
