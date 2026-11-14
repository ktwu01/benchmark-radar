"""Share-card creator cleanup (issue #1162). Each case is a value a committed
daily snapshot carried before the cleanup."""

from benchmark_radar.creator_names import clean_creators, decode_latex, split_institutions


def test_latex_escapes_decode_without_eating_the_next_word():
    assert decode_latex("Kiant\\'e Fernandez") == "Kianté Fernandez"
    assert decode_latex("\\'I\\~nigo Zubeldia") == "Íñigo Zubeldia"
    assert decode_latex("$\\tau$-bench") == "τ-bench"


def test_spelling_variants_and_abbreviations_merge_into_the_fullest_name():
    authors = [
        "Yu-Meng Ma",
        "A. Gustafson",
        "Jennifer Mankoff",
        "Yumeng Ma",
        "Aaron Gustafson",
        "Jennifer C. Mankoff",
        "Christopher R\\'e",
        "Christopher Ré",
    ]
    assert clean_creators(authors, [])["authors"] == [
        "Yu-Meng Ma",
        "Aaron Gustafson",
        "Jennifer C. Mankoff",
        "Christopher Ré",
    ]


def test_an_initial_shared_by_two_people_does_not_merge():
    authors = ["Wei Zhang", "Wen Zhang", "W. Zhang"]
    assert clean_creators(authors, [])["authors"] == authors


def test_affiliation_in_an_author_value_moves_to_institutions():
    creators = clean_creators(["Yangze Liu (Shandong University)", "Yangze Liu"], [])
    assert creators == {"authors": ["Yangze Liu"], "affiliations": ["Shandong University"]}


def test_truncated_value_is_closed():
    assert clean_creators(["Anonymous Author(s"], [])["authors"] == ["Anonymous Author(s)"]


def test_joined_institutions_split_and_whole_names_stay_whole():
    assert split_institutions("Stanford University Cornell University") == [
        "Stanford University",
        "Cornell University",
    ]
    assert split_institutions(
        "University of Science and Technology of China Tsinghua University"
    ) == ["University of Science and Technology of China", "Tsinghua University"]
    for whole in (
        "University College London",
        "Massachusetts Institute of Technology",
        "The Hong Kong University of Science and Technology",
        "Stanford University School of Medicine",
        "Max Planck Institute for Intelligent Systems",
    ):
        assert split_institutions(whole) == [whole]


def test_contact_debris_and_bare_addresses_leave_the_institution_list():
    affiliations = [
        "\\addr Department of Computer Science",
        "Nashville, TN 37235, USA",
        "Shanghai Artificial Intelligence Laboratory {zhangshao,hushuyue}@pjlab.org.cn",
        "KAIST Correspondence: someone@example.com",
        "Department of Pediatrics, Hospital Sepaco, São Paulo, SP 04102-900, Brazil",
    ]
    assert clean_creators([], affiliations)["affiliations"] == [
        "Department of Computer Science",
        "Shanghai Artificial Intelligence Laboratory",
        "KAIST",
        "Department of Pediatrics, Hospital Sepaco, São Paulo, SP 04102-900, Brazil",
    ]


def test_a_person_listed_as_an_institution_is_not_repeated():
    creators = clean_creators(["Jackson Wang"], ["Jackson Wang", "Hugging Face"])
    assert creators == {"authors": ["Jackson Wang"], "affiliations": ["Hugging Face"]}
    creators = clean_creators(
        ["Chia-Jung Lee", "Vanessa Murdock"],
        ["Chia-Jung Lee, Vanessa Murdock", "Amazon Responsible AI"],
    )
    assert creators["affiliations"] == ["Amazon Responsible AI"]
