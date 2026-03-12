"""Tests for static Copart make/model catalog generation helpers."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap.modules.search.catalog_builder import (  # noqa: E402
    build_catalog,
    build_official_model_index,
    extract_catalog_candidates,
    match_model_to_make,
)


SAMPLE_KEYWORDS = {
    "ford": {
        "text": "manufacturer_make_desc",
        "filterQuery": 'lot_make_desc:"FORD" OR manufacturer_make_desc:"FORD"',
        "type": "MAKE_MODEL",
    },
    "toyota": {
        "text": "manufacturer_make_desc",
        "filterQuery": 'lot_make_desc:"TOYOTA" OR manufacturer_make_desc:"TOYOTA"',
        "type": "MAKE_MODEL",
    },
    "mustangmache": {
        "text": "manufacturer_model_desc",
        "filterQuery": 'lot_model_desc:"MUSTANG MACH-E" OR manufacturer_model_desc:"MUSTANG MACH-E"',
        "type": "MAKE_MODEL",
    },
    "camry": {
        "text": "manufacturer_model_desc",
        "filterQuery": 'lot_model_desc:"CAMRY" OR lot_model_group:"CAMRY" OR manufacturer_model_desc:"CAMRY"',
        "type": "MAKE_MODEL",
    },
    "corollacr": {
        "text": "lot_model_group",
        "filterQuery": 'lot_model_group:"COROLLA CR"',
        "type": "MAKE_MODEL",
    },
    "300": {
        "text": "manufacturer_model_desc",
        "filterQuery": 'lot_model_desc:"300" OR manufacturer_model_desc:"300"',
        "type": "MAKE_MODEL",
    },
    "2025": {
        "text": "2025",
        "filterQuery": 'lot_year:"2025"',
        "type": "YEAR",
    },
}


def test_extract_catalog_candidates_splits_makes_models_and_years() -> None:
    candidates = extract_catalog_candidates(SAMPLE_KEYWORDS)

    assert [item["name"] for item in candidates["makes"]] == ["FORD", "TOYOTA"]
    assert [item["name"] for item in candidates["models"]] == ["300", "CAMRY", "COROLLA CR", "MUSTANG MACH-E"]
    assert candidates["years"] == [2025]


def test_match_model_to_make_returns_exact_unique_match() -> None:
    official_index = build_official_model_index(
        {"ford": ["Mustang Mach-E"], "toyota": ["Camry"]},
        {"ford": "FORD", "toyota": "TOYOTA"},
    )
    model = {
        "aliases": ["MUSTANG MACH-E"],
        "normalized_aliases": ["MUSTANGMACHE"],
    }

    matched_make, confidence, candidates = match_model_to_make(model, official_index)

    assert matched_make == "ford"
    assert confidence == "exact_unique"
    assert candidates == []


def test_match_model_to_make_returns_fuzzy_unique_match() -> None:
    official_index = build_official_model_index(
        {"toyota": ["Corolla Cross"], "ford": ["Mustang"]},
        {"toyota": "TOYOTA", "ford": "FORD"},
    )
    model = {
        "aliases": ["COROLLA CR"],
        "normalized_aliases": ["COROLLACR"],
    }

    matched_make, confidence, candidates = match_model_to_make(model, official_index)

    assert matched_make == "toyota"
    assert confidence == "fuzzy_unique"
    assert candidates == []


def test_match_model_to_make_marks_ambiguous_exact_models_unassigned() -> None:
    official_index = build_official_model_index(
        {"chrysler": ["300"], "rover": ["300"]},
        {"chrysler": "CHRYSLER", "rover": "ROVER"},
    )
    model = {
        "aliases": ["300"],
        "normalized_aliases": ["300"],
    }

    matched_make, confidence, candidates = match_model_to_make(model, official_index)

    assert matched_make is None
    assert confidence == "ambiguous_exact"
    assert candidates == ["chrysler", "rover"]


def test_build_catalog_groups_assigned_and_unassigned_models() -> None:
    candidates = extract_catalog_candidates(SAMPLE_KEYWORDS)
    official_index = build_official_model_index(
        {"ford": ["Mustang Mach-E", "300"], "toyota": ["Camry", "Corolla Cross", "300"]},
        {"ford": "FORD", "toyota": "TOYOTA"},
    )

    catalog = build_catalog(candidates, official_index, "/tmp/keywords.json")

    ford = next(item for item in catalog["makes"] if item["slug"] == "ford")
    toyota = next(item for item in catalog["makes"] if item["slug"] == "toyota")

    assert [item["name"] for item in ford["models"]] == ["MUSTANG MACH-E"]
    assert [item["name"] for item in toyota["models"]] == ["CAMRY", "COROLLA CR"]
    assert [item["name"] for item in catalog["unassigned_models"]] == ["300"]
    assert catalog["summary"]["assigned_model_count"] == 3
    assert catalog["summary"]["unassigned_model_count"] == 1


def test_build_official_model_index_collapses_make_aliases() -> None:
    official_index = build_official_model_index(
        {"toyota": ["Camry", "Corolla"], "toyo": ["Camry", "Corolla"], "honda": ["Civic"]},
        {"toyota": "TOYOTA", "toyo": "TOYO", "honda": "HONDA"},
    )

    assert official_index["toyota"]["aliases"] == ["toyo"]
    assert official_index["toyo"]["make_name"] == "TOYOTA"
    assert official_index["honda"]["aliases"] == []


def test_build_catalog_applies_manual_overrides() -> None:
    candidates = extract_catalog_candidates(
        {
            "tesla": {
                "text": "manufacturer_make_desc",
                "filterQuery": 'lot_make_desc:"TESLA" OR manufacturer_make_desc:"TESLA"',
                "type": "MAKE_MODEL",
            },
            "model3": {
                "text": "manufacturer_model_desc",
                "filterQuery": 'lot_model_desc:"MODEL 3" OR manufacturer_model_desc:"MODEL 3"',
                "type": "MAKE_MODEL",
            },
        }
    )
    official_index = build_official_model_index({"tesla": []}, {"tesla": "TESLA"})

    catalog = build_catalog(candidates, official_index, "/tmp/keywords.json", manual_overrides={"model3": "tesla"})

    tesla = next(item for item in catalog["makes"] if item["slug"] == "tesla")
    assert tesla["models"][0]["name"] == "MODEL 3"
    assert tesla["models"][0]["confidence"] == "manual_override"
