"""Precision contract for the science-domain routing tags.

These tests lock the red lines from the issue #511 plan: a tag is a
routing signal derived from a record's own text, ordinary neural-network
papers stay untagged, acronyms are word anchored, and the auto-generated
PathMap hypothesis records that mention the blood-brain barrier do not
count as neuroscience evidence. Positive cases use real titles from
``data/snapshots/`` so the rules are anchored to the corpus they serve.
"""

from __future__ import annotations

from benchmark_radar.science_domains import (
    SCIENCE_DOMAINS,
    derive_science_domains,
    science_domains_for_record,
)


def test_real_corpus_neuroscience_titles_are_tagged():
    # Titles observed verbatim in data/snapshots/.
    assert derive_science_domains(
        "LibriBrain100: One Hundred Hours of Broad and Deep MEG Data "
        "for Neural Speech Decoding at Scale"
    ) == ["neuroscience"]
    assert derive_science_domains(
        "BrainBench: Benchmarking Large Language Models for Comprehensive EEG Understanding"
    ) == ["neuroscience"]
    assert derive_science_domains(
        "CORAL: A Benchmark for Structure-aware and Brain-wide "
        "Neuron Reconstruction in Light Microscopy"
    ) == ["neuroscience"]
    assert derive_science_domains(
        "Test-Time Adaptation for EEG Foundation Models: A Systematic Study"
    ) == ["neuroscience"]


def test_interface_strong_signals_tag_in_every_spelling():
    # "Brain Computer Interface" without the hyphen is the spelling the
    # in-silico BCI benchmark title in the corpus actually uses; the
    # machine variant and the en-dash form come from the domain review.
    assert derive_science_domains(
        "Intent Drift in LLM-Assisted Brain Computer Interface Communication"
    ) == ["neuroscience"]
    assert derive_science_domains(
        "A benchmark for brain-computer interface decoding robustness"
    ) == ["neuroscience"]
    assert derive_science_domains("High-accuracy brain–machine interface control") == [
        "neuroscience"
    ]


def test_brain_to_naming_family_tags():
    # Brain2Text / Brain2Voice / Brain2Qwerty and any future brain2X
    # variant, plus the "brain-to-text" spelling. These are exactly the
    # names "brain\b" cannot reach, because digits keep "brain" and "2"
    # inside one word.
    assert derive_science_domains("Brain2Qwerty: fMRI-to-Keyboard Decoding") == ["neuroscience"]
    assert derive_science_domains("A Brain2Text decoding system evaluation") == ["neuroscience"]
    assert derive_science_domains("Toward brain-to-voice speech synthesis") == ["neuroscience"]
    # The spaced family form is real BCI work too, not a metaphor.
    assert derive_science_domains("Brain-to-brain interface experiments") == ["neuroscience"]


def test_bci_vocabulary_tags_without_neuroscience_word_overlap():
    # MOABB arrives as a repository title; the domain evidence lives in
    # the summary, which is exactly how the shared derivation reads it.
    assert science_domains_for_record(
        {
            "title": "NeuroTechX/moabb",
            "summary": "The mother of all BCI benchmarks: motor imagery "
            "pipelines evaluated across many datasets.",
        }
    ) == ["neuroscience"]
    assert derive_science_domains("SSVEP and P300 spellers evaluated offline") == ["neuroscience"]


def test_domain_review_vocabulary_tags():
    # Terms supplied in the issue #511 domain review, plus the full
    # technique names behind the acronyms.
    assert derive_science_domains("A speech neuroprosthesis benchmark for word classification") == [
        "neuroscience"
    ]
    assert derive_science_domains("Decoding from chronic Utah array recordings") == ["neuroscience"]
    assert derive_science_domains("Whole-brain calcium imaging dataset") == ["neuroscience"]
    assert derive_science_domains("Optogenetic stimulation protocols") == ["neuroscience"]
    assert derive_science_domains("Seizure onset zone localization from sEEG") == ["neuroscience"]
    assert derive_science_domains("fnirs-based motor imagery classification") == ["neuroscience"]
    assert derive_science_domains(
        "Electroencephalography sleep staging, electrocorticographic control"
    ) == ["neuroscience"]


def test_full_technique_names_tag_on_their_own():
    # Codex review, PR #647: the word-start lookbehind stops the bare
    # "encephalograph" stem matching inside "electroencephalography", so
    # both full technique names must be explicit patterns. The earlier
    # test above passed only via its electrocorticographic clause.
    assert derive_science_domains("Electroencephalography sleep staging") == ["neuroscience"]
    assert derive_science_domains("Magnetoencephalography source localization") == ["neuroscience"]


def test_artificial_spiking_architectures_do_not_tag():
    # Codex review, PR #647: "spiking neural networks" and
    # "spiking-inspired" describe artificial models (live records:
    # HazeSpikeMamba dehazing, Twin Network Augmentation on CIFAR), so
    # only tissue-level spiking phrases remain.
    assert derive_science_domains("HazeSpikeMamba: Spiking-Inspired Dehazing") == []
    assert derive_science_domains("Twin Network Augmentation for Spiking Neural Networks") == []
    # Biological spiking still tags.
    assert derive_science_domains("Spike sorting for large-scale recordings") == ["neuroscience"]
    assert derive_science_domains("Latent structure in spike trains") == ["neuroscience"]


def test_neuromorphic_framing_and_species_descriptions_do_not_tag():
    # Codex review, PR #647: brain-inspired computing is the agent-as-brain
    # metaphor class, and species-description genre markers (a fungal
    # taxonomy record mentioning "cortical cells of roots") are not
    # neuroscience regardless of vocabulary overlap.
    assert (
        derive_science_domains("Pathway's brain-inspired architecture development on SageMaker")
        == []
    )
    assert derive_science_domains("A brain-like computing substrate") == []
    assert (
        derive_science_domains("Reflexicalyptra gen. nov., a fungus with cortical cells in roots")
        == []
    )


def test_neural_network_papers_are_not_tagged():
    # The single highest-volume false-positive source: "neural" is never
    # a trigger on its own, only compounds like "neural decoding" are.
    assert (
        derive_science_domains(
            "A Survey of Benchmarking Neural Network Training at Scale",
            "We evaluate neural networks and deep learning optimizers.",
        )
        == []
    )
    assert derive_science_domains("Scaling Laws for Neural Language Models") == []


def test_acronym_terms_are_word_anchored():
    # Only compound words like megabyte/megapixel are closed out here;
    # the acronym-vs-project disambiguation has its own test below.
    assert derive_science_domains("Training megabyte-scale models efficiently") == []
    assert derive_science_domains("Streaming megapixel video datasets") == []
    assert derive_science_domains("A MEG study of cortical oscillations") == ["neuroscience"]


def test_meg_acronym_requires_a_recording_collocate():
    # Codex round 2: "meg-initiative/meg-inspect-eval" is an AI-evaluation
    # package, not magnetoencephalography, so bare MEG no longer tags.
    assert (
        derive_science_domains(
            "meg-initiative/meg-inspect-eval",
            "Executable Inspect AI evaluation package for MEG behavioral and safety metrics.",
        )
        == []
    )
    # The real sense sits next to recording/data words (LibriBrain100
    # says "Broad and Deep MEG Data").
    assert derive_science_domains("LibriBrain100: MEG Data for Decoding") == ["neuroscience"]
    assert derive_science_domains("Source localization with MEG recordings") == ["neuroscience"]


def test_cardiac_and_metaphorical_senses_do_not_tag():
    # Codex round 2: cardiac electrophysiology is the other big user of
    # the stem, and the estimator metaphor uses singular "neural signal".
    assert (
        derive_science_domains(
            "ECGQuest: Benchmarking Language Models for Electrocardiography",
            "Interpretation requires cardiology, electrophysiology, and ECG waveform knowledge.",
        )
        == []
    )
    assert (
        derive_science_domains(
            "Does Machine Learning Beat the GARCH Benchmark?",
            "The model's neural signal is volatility filtering in disguise.",
        )
        == []
    )
    # Plural neural signals is the neuroscience sense; an EEG record that
    # merely mentions ECG artifacts keeps its tag.
    assert derive_science_domains("Decoding of neural signals during speech") == ["neuroscience"]
    assert derive_science_domains("EEG preprocessing with ECG artifact removal") == ["neuroscience"]


def test_architecture_prose_does_not_tag():
    # Found in a corpus audit: three distinct mechanisms by which
    # non-neuro records said "neuron"/"brain". Layer-size talk, the
    # Spanish neural-network name, and brainstorming are all closed out.
    assert (
        derive_science_domains(
            "基于自适应图神经网络的动态量子算法",
            "The adapter tunes the connection weights and neuron counts.",
        )
        == []
    )
    assert (
        derive_science_domains(
            "Active noise control dataset",
            "El sistema implementa una red neuronal autorregresiva no lineal.",
        )
        == []
    )
    assert (
        derive_science_domains(
            "Logo Generator: Persona Specification",
            "Through structured brand discovery, brainstorm unique logo concepts.",
        )
        == []
    )


def test_closed_compound_benchmark_names_still_tag():
    # "BrainBench" is one word, so the right-edge-anchored "brain" cannot
    # reach it; the name is an explicit pattern instead.
    assert derive_science_domains("BrainBench: EEG Understanding") == ["neuroscience"]


def test_product_and_metaphor_uses_do_not_tag():
    # Live-corpus audit (September window): bare "cortex" only ever named
    # the Snowflake product, and "the LLM acts as the brain of..." used
    # brain as a metaphor for computation.
    assert (
        derive_science_domains(
            "curious-bigcat/snowflake-cortex-dbx-genie-agents-benchmark",
            "A benchmark for Snowflake Cortex agent workflows.",
        )
        == []
    )
    assert (
        derive_science_domains(
            "ReactHuman: A Physics-Grounded Benchmark",
            "The evaluated MLLM acts as the brain of a simulated humanoid.",
        )
        == []
    )


def test_cortical_compounds_still_tag_without_bare_cortex():
    # Dropping bare "cortex" must not drop real neuro uses of the family:
    # cortical folding, corticospinal tracts.
    assert derive_science_domains("Representation learning of human cortical folding patterns") == [
        "neuroscience"
    ]
    assert derive_science_domains("Tractography of the corticospinal tract") == ["neuroscience"]


def test_blood_brain_barrier_hypothesis_records_are_not_tagged():
    # PathMap auto-generates hypothesis "datasets" whose only neuro word
    # is the barrier phrase; the whole-domain veto keeps them untagged.
    assert (
        derive_science_domains(
            "Dataset: Hypothesis: Intranasal delivery exploits the "
            "blood-brain barrier to bypass systemic transport."
        )
        == []
    )
    assert derive_science_domains("Predicting blood brain barrier permeability") == []


def test_published_domain_order_is_the_single_merged_facet():
    # BCI folded into neuroscience: the bci-only records were a handful
    # per month, too few to power a filter of their own.
    assert SCIENCE_DOMAINS == ("neuroscience",)
    # Multiple vocabulary hits still yield one deterministic tag.
    assert derive_science_domains("EEG-based motor imagery BCI dataset") == ["neuroscience"]


def test_empty_and_missing_text_derive_no_domains():
    assert derive_science_domains("") == []
    assert science_domains_for_record({}) == []
    assert science_domains_for_record({"title": None, "summary": None}) == []


def test_derivation_is_deterministic():
    title = "Neural decoding benchmarks for spiking networks"
    first = derive_science_domains(title, "connectome-scale evaluation")
    assert first == derive_science_domains(title, "connectome-scale evaluation")
    assert first == ["neuroscience"]
