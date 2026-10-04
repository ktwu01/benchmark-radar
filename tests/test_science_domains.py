"""Precision and recall contract for the science-domain routing tags.

Each row is ``(title, summary)``. Add a regression case as one row in the
table it belongs to, grouped under the rule it exercises. Titles quoted
from ``data/snapshots/`` keep the rules anchored to the corpus they serve.
"""

from __future__ import annotations

import pytest

from benchmark_radar.science_domains import (
    SCIENCE_DOMAINS,
    derive_science_domains,
    science_domains_for_record,
)

TAGGED = [
    # Corpus titles: MEG, EEG, brain-wide reconstruction, iEEG decoding.
    (
        "LibriBrain100: One Hundred Hours of Broad and Deep MEG Data "
        "for Neural Speech Decoding at Scale",
        "",
    ),
    ("BrainBench: Benchmarking Large Language Models for Comprehensive EEG Understanding", ""),
    (
        "CORAL: A Benchmark for Structure-aware and Brain-wide "
        "Neuron Reconstruction in Light Microscopy",
        "",
    ),
    ("Test-Time Adaptation for EEG Foundation Models: A Systematic Study", ""),
    ("iMINDBench: iEEG Multi-Institution Neural Decoding Benchmark", ""),
    (
        "Robot assistants during high mental workload",
        "Neural activity measured through electroencephalography (EEG) and behavioral performance.",
    ),
    (
        "Retrospective comparison of AI algorithms",
        "Detection of intracranial hemorrhage (ICH) in the emergency radiology department.",
    ),
    # Interface spellings: spaced, hyphenated, en-dashed, machine variant.
    ("Intent Drift in LLM-Assisted Brain Computer Interface Communication", ""),
    ("A benchmark for brain-computer interface decoding robustness", ""),
    ("High-accuracy brain–machine interface control", ""),
    # Brain-to-X family: digits close the "brain\b" boundary.
    ("Brain2Qwerty: fMRI-to-Keyboard Decoding", ""),
    ("A Brain2Text decoding system evaluation", ""),
    ("Toward brain-to-voice speech synthesis", ""),
    ("Brain-to-brain interface experiments", ""),
    # BCI vocabulary, including evidence that lives only in the summary.
    (
        "NeuroTechX/moabb",
        "The mother of all BCI benchmarks: motor imagery pipelines evaluated across many datasets.",
    ),
    ("SSVEP and P300 spellers evaluated offline", ""),
    ("EEG-based motor imagery BCI dataset", ""),
    # Domain-review vocabulary and full technique names.
    ("A speech neuroprosthesis benchmark for word classification", ""),
    ("Decoding from chronic Utah array recordings", ""),
    ("Whole-brain calcium imaging dataset", ""),
    ("Optogenetic stimulation protocols", ""),
    ("Seizure onset zone localization from sEEG", ""),
    ("fnirs-based motor imagery classification", ""),
    ("Electroencephalography sleep staging", ""),
    ("Magnetoencephalography source localization", ""),
    ("Electrocorticographic control of a cursor", ""),
    # Biological spiking, plural neural signals, MEG with a recording word.
    ("Spike sorting for large-scale recordings", ""),
    ("Latent structure in spike trains", ""),
    ("Decoding of neural signals during speech", ""),
    ("A MEG study of cortical oscillations", ""),
    ("Source localization with MEG recordings", ""),
    # Closed-compound name and cortical compounds without bare "cortex".
    ("BrainBench: EEG Understanding", ""),
    ("Representation learning of human cortical folding patterns", ""),
    ("Tractography of the corticospinal tract", ""),
    # Masks drop only the matched phrase, so an incidental mention of a
    # masked phrase or a cardiac word leaves the rest of the record tagged.
    (
        "EEG-Bench: cortical decoding of visual evoked potentials",
        "A neuroscience benchmark for EEG. Subjects were screened with electrocardiography.",
    ),
    (
        "EEG-Bench: cortical decoding of visual evoked potentials",
        "A neuroscience benchmark for EEG. Drug delivery across the blood-brain barrier "
        "is out of scope.",
    ),
    ("EEG preprocessing with ECG artifact removal", ""),
    (
        "Using Brain Organoids to Explore Human Neurobiology",
        "Organoids of different parts of the brain like hypothalamic and retinal tissue.",
    ),
    ("Single-neuron electrophysiology benchmark", "Interventional forecasting of outcomes."),
]

NOT_TAGGED = [
    # Bare "neural"/"neuron" never tag: architecture prose and the
    # Spanish neural-network name.
    (
        "A Survey of Benchmarking Neural Network Training at Scale",
        "We evaluate neural networks and deep learning optimizers.",
    ),
    ("Scaling Laws for Neural Language Models", ""),
    (
        "基于自适应图神经网络的动态量子算法",
        "The adapter tunes the connection weights and neuron counts.",
    ),
    (
        "Active noise control dataset",
        "El sistema implementa una red neuronal autorregresiva no lineal.",
    ),
    # Artificial spiking architectures.
    ("HazeSpikeMamba: Spiking-Inspired Dehazing", ""),
    ("Twin Network Augmentation for Spiking Neural Networks", ""),
    # Acronyms are word anchored and need a recording collocate.
    ("Training megabyte-scale models efficiently", ""),
    ("Streaming megapixel video datasets", ""),
    (
        "meg-initiative/meg-inspect-eval",
        "Executable Inspect AI evaluation package for MEG behavioral and safety metrics.",
    ),
    (
        "Clinical usability of an explainable AI decision support tool",
        "Eastern cooperative oncology group performance status (ECOG PS) "
        "and neutrophil-to-lymphocyte ratio.",
    ),
    # "brainstorm" and bare "cortex" (a product name).
    (
        "Logo Generator: Persona Specification",
        "Through structured brand discovery, brainstorm unique logo concepts.",
    ),
    (
        "curious-bigcat/snowflake-cortex-dbx-genie-agents-benchmark",
        "A benchmark for Snowflake Cortex agent workflows.",
    ),
    # Masked metaphors: brain as computation.
    (
        "ReactHuman: A Physics-Grounded Benchmark",
        "The evaluated MLLM acts as the brain of a simulated humanoid.",
    ),
    ("Pathway's brain-inspired architecture development on SageMaker", ""),
    ("A brain-like computing substrate", ""),
    (
        "Where Should Agents Live? Energy-Memory Characterization",
        "While the biological brain accomplishes complex cognition on an "
        "exceptionally modest energy budget.",
    ),
    (
        "FluctlightDB: A Memory Model of Data for AI Agents",
        "We claim no new neuroscience and no new transformer. The provenance-conflict "
        "suite scores 18% top-1 when all pairs share one brain.",
    ),
    # Masked non-neuro senses: hormone, drug delivery, barrier, orthopedics.
    (
        "Preliminary comparative evaluation of an immunofluorescence point-of-care system",
        "N-terminal pro-brain natriuretic peptide (NT-proBNP), D-dimer "
        "and hs-CRP from serum samples.",
    ),
    (
        "CUBOSOMES: A REVIEW",
        "Advanced applications in cancer therapy, brain targeting, gene delivery, and vaccines.",
    ),
    ("Predicting blood brain barrier permeability", ""),
    (
        "Fragility fracture risk prediction using quantitative MRI",
        "Parameters correlate with trabecular deterioration and cortical porosity beyond BMD.",
    ),
    # Corticosteroids are excluded from the "cortic" stem.
    (
        "Real-World Effectiveness of Risankizumab in Refractory Crohn's Disease",
        "Remission without systemic corticosteroids was assessed at weeks 8-12.",
    ),
    (
        "Beyond the Skin: Ocular Manifestations in Hidradenitis Suppurativa",
        "Treated with topical or systemic corticosteroids.",
    ),
    # Cardiac context disarms "electrophysiolog" (and only that term).
    (
        "ECGQuest: Benchmarking Language Models for Electrocardiography",
        "Interpretation requires cardiology, electrophysiology, and ECG waveform knowledge.",
    ),
    ("Interventional electrophysiology in Bulgaria in 2025", "Data from the electronic registry."),
    (
        "Novel Biatrial Epicardial Mesh for the Prevention of Postoperative Atrial Fibrillation",
        "Atrial electrophysiology was assessed after surgery.",
    ),
    (
        "Does Machine Learning Beat the GARCH Benchmark?",
        "The model's neural signal is volatility filtering in disguise.",
    ),
    # Genre vetoes: the whole record, whatever vocabulary it borrows.
    (
        "Dataset: Neuroinflammatory astrocyte subtypes in the mouse brain",
        "Gut-brain axis mediator to reduce microglia activation - PathMap Experiment #000127.",
    ),
    ("Reflexicalyptra gen. nov., a fungus with cortical cells in roots", ""),
    (
        "A REVIEW ON ANALYTICAL METHOD DEVELOPMENT AND VALIDATION OF PIRACETAM",
        "Widely used for cognitive impairment, cortical myoclonus, and vertigo.",
    ),
]


@pytest.mark.parametrize(("title", "summary"), TAGGED)
def test_tagged(title, summary):
    assert derive_science_domains(title, summary) == ["neuroscience"]


@pytest.mark.parametrize(("title", "summary"), NOT_TAGGED)
def test_not_tagged(title, summary):
    assert derive_science_domains(title, summary) == []


def test_published_domains_and_missing_text():
    assert SCIENCE_DOMAINS == ("neuroscience",)
    assert science_domains_for_record({}) == []
    assert science_domains_for_record({"title": None, "summary": None}) == []
