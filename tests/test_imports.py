"""Smoke test: the package and all subpackages import."""

import importlib

import pytest

SUBPACKAGES = [
    "datasets",
    "ingestion",
    "retrieval",
    "graph",
    "evaluation",
    "agents",
    "utils",
    "studies",
    "studies.ladrag",
]


def test_package_imports():
    pkg = importlib.import_module("multimodal_document_extraction")
    assert pkg.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    importlib.import_module(f"multimodal_document_extraction.{name}")
