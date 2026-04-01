"""Helpers for building static make/model catalogs from provider and local sources."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any, Iterable


MAKE_TEXT_FIELDS = frozenset(("manufacturer_make_desc", "lot_make_desc"))
MODEL_TEXT_FIELDS = frozenset(("manufacturer_model_desc", "lot_model_group", "lot_model_desc"))
FIELD_VALUE_PATTERN = re.compile(
    r'(manufacturer_make_desc|lot_make_desc|manufacturer_model_desc|lot_model_group|lot_model_desc):"([^"]+)"'
)
NON_ALNUM_PATTERN = re.compile(r"[^A-Z0-9]+")
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def load_keyword_payload(path: Path) -> dict[str, dict[str, Any]]:
    raw = path.read_text()
    start = raw.find("{")
    if start < 0:
        raise ValueError("Could not locate JSON payload in Copart keywords file.")
    payload = json.loads(raw[start:])
    if not isinstance(payload, dict):
        raise ValueError("Copart keywords payload must be a JSON object.")
    return payload


def load_market_source_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Market catalog payload must be a JSON object.")
    makes = payload.get("makes")
    if not isinstance(makes, list):
        raise ValueError("Market catalog payload must contain a 'makes' list.")
    return payload


def extract_catalog_candidates(payload: dict[str, dict[str, Any]]) -> dict[str, Any]:
    makes: dict[str, dict[str, str]] = {}
    models: list[dict[str, Any]] = []
    years: list[int] = []

    for slug, item in payload.items():
        item_type = str(item.get("type") or "")
        text_field = str(item.get("text") or "")
        filter_query = str(item.get("filterQuery") or "")
        values = _extract_field_values(filter_query)

        if item_type == "YEAR":
            year = _parse_year(item.get("text"))
            if year is not None:
                years.append(year)
            continue

        if item_type != "MAKE_MODEL":
            continue

        if text_field in MAKE_TEXT_FIELDS:
            names = values.get("lot_make_desc") or values.get("manufacturer_make_desc") or []
            if names:
                display_name = names[0]
                normalized = normalize_name(display_name)
                existing = makes.get(slug)
                if existing is None or len(existing["name"]) < len(display_name):
                    makes[slug] = {
                        "slug": slug,
                        "name": display_name,
                        "normalized_name": normalized,
                        "filter_query": filter_query,
                    }
            continue

        if text_field in MODEL_TEXT_FIELDS:
            model_names = _collect_model_names(values)
            if not model_names:
                continue
            models.append(
                {
                    "slug": slug,
                    "name": model_names[0],
                    "aliases": model_names,
                    "normalized_aliases": [normalize_name(value) for value in model_names if normalize_name(value)],
                    "filter_query": filter_query,
                    "text_field": text_field,
                }
            )

    return {
        "makes": sorted(makes.values(), key=lambda item: item["name"]),
        "models": sorted(models, key=lambda item: item["name"]),
        "years": sorted(set(years)),
    }


def build_catalog(
    candidates: dict[str, Any],
    official_models_by_make: dict[str, dict[str, Any]],
    source_keywords_path: str,
    manual_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    make_entries = list(candidates["makes"])
    model_entries = list(candidates["models"])
    years = list(candidates["years"])
    overrides = manual_overrides or {}

    makes_by_slug: dict[str, dict[str, Any]] = {}
    for make in make_entries:
        official_entry = official_models_by_make.get(make["slug"], {})
        canonical_slug = official_entry.get("canonical_slug") or make["slug"]
        if canonical_slug not in makes_by_slug:
            makes_by_slug[canonical_slug] = {
                "slug": canonical_slug,
                "name": official_entry.get("make_name") or make["name"],
                "source": "copart_keywords+nhtsa_vpic",
                "nhtsa_make_name": official_entry.get("make_name") or make["name"],
                "aliases": [],
                "copart_make_slugs": [],
                "filter_queries": [],
                "models": [],
            }
        catalog_make = makes_by_slug[canonical_slug]
        if make["slug"] not in catalog_make["copart_make_slugs"]:
            catalog_make["copart_make_slugs"].append(make["slug"])
        if make["filter_query"] not in catalog_make["filter_queries"]:
            catalog_make["filter_queries"].append(make["filter_query"])
        if make["slug"] != canonical_slug and make["slug"] not in catalog_make["aliases"]:
            catalog_make["aliases"].append(make["slug"])

    unassigned_models: list[dict[str, Any]] = []
    exact_matches = 0
    fuzzy_matches = 0

    for model in model_entries:
        override_make_slug = overrides.get(model["slug"])
        if override_make_slug:
            matched_make_slug = override_make_slug
            confidence = "manual_override"
            candidate_make_slugs = []
        else:
            matched_make_slug, confidence, candidate_make_slugs = match_model_to_make(model, official_models_by_make)
        model_record = {
            "slug": model["slug"],
            "name": model["name"],
            "aliases": model["aliases"],
            "filter_query": model["filter_query"],
        }
        if matched_make_slug is None:
            model_record["confidence"] = confidence
            if candidate_make_slugs:
                model_record["candidate_makes"] = candidate_make_slugs
            unassigned_models.append(model_record)
            continue

        model_record["confidence"] = confidence
        makes_by_slug[matched_make_slug]["models"].append(model_record)
        if confidence == "exact_unique":
            exact_matches += 1
        elif confidence == "fuzzy_unique":
            fuzzy_matches += 1

    makes = sorted(makes_by_slug.values(), key=lambda item: item["name"])
    for make in makes:
        make["aliases"].sort()
        make["copart_make_slugs"].sort()
        make["filter_queries"].sort()
        make["models"].sort(key=lambda item: item["name"])

    return {
        "source_keywords_path": source_keywords_path,
        "source_reference": "https://vpic.nhtsa.dot.gov/api/",
        "matching_strategy": {
            "exact": "Normalized Copart model alias equals normalized official NHTSA model name for exactly one make.",
            "fuzzy": "Token-prefix match against official NHTSA model name for exactly one make.",
            "manual_override": "Model was assigned through the local manual overrides file.",
            "unassigned": "No unique make match was found; review manually.",
        },
        "summary": {
            "make_count": len(makes),
            "model_count": len(model_entries),
            "assigned_model_count": exact_matches + fuzzy_matches,
            "exact_match_count": exact_matches,
            "fuzzy_match_count": fuzzy_matches,
            "unassigned_model_count": len(unassigned_models),
            "year_count": len(years),
        },
        "years": years,
        "makes": makes,
        "unassigned_models": sorted(unassigned_models, key=lambda item: item["name"]),
    }


def build_catalog_from_market_source(
    payload: dict[str, Any],
    source_path: str,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    makes_by_slug: dict[str, dict[str, Any]] = {}
    used_make_slugs: set[str] = set()
    total_models = 0

    for make_entry in sorted(payload.get("makes") or [], key=lambda item: str(item.get("make") or "")):
        raw_make_name = str(make_entry.get("make") or "").strip()
        if not raw_make_name:
            continue
        make_slug = _unique_slug(raw_make_name, used_make_slugs)
        model_entries = _build_market_models(make_entry.get("models") or [])
        total_models += len(model_entries)
        makes_by_slug[make_slug] = {
            "slug": make_slug,
            "name": raw_make_name,
            "source": "local_us_market_catalog",
            "aliases": [],
            "copart_make_slugs": [make_slug],
            "filter_queries": [_build_filter_query(("lot_make_desc", "manufacturer_make_desc"), [raw_make_name])],
            "models": model_entries,
        }

    year_values = _extract_market_years(payload.get("meta") or {})
    generated_value = generated_at or datetime.now(timezone.utc)
    return {
        "source_keywords_path": source_path,
        "source_reference": "local_us_market_catalog",
        "matching_strategy": {
            "exact": "Catalog is built directly from the curated local US-market make/model source.",
            "fuzzy": "No fuzzy provider/NHTSA matching is used for this catalog source.",
            "manual_override": "Model aliases are collapsed from duplicate source rows when names normalize identically.",
            "unassigned": "All listed models are assigned directly to their source make.",
        },
        "summary": {
            "make_count": len(makes_by_slug),
            "model_count": total_models,
            "assigned_model_count": total_models,
            "exact_match_count": total_models,
            "fuzzy_match_count": 0,
            "unassigned_model_count": 0,
            "year_count": len(year_values),
        },
        "years": year_values,
        "makes": [makes_by_slug[slug] for slug in sorted(makes_by_slug, key=lambda item: makes_by_slug[item]["name"])],
        "unassigned_models": [],
        "manual_override_count": 0,
        "generated_at": generated_value.isoformat().replace("+00:00", "Z"),
    }


def match_model_to_make(
    model: dict[str, Any],
    official_models_by_make: dict[str, dict[str, Any]],
) -> tuple[str | None, str, list[str]]:
    exact_matches: set[str] = set()
    fuzzy_matches: set[str] = set()

    aliases = list(model.get("aliases") or [])
    normalized_aliases = [value for value in model.get("normalized_aliases") or [] if value]

    for make_slug, official_entry in official_models_by_make.items():
        canonical_slug = official_entry.get("canonical_slug") or make_slug
        official_models = official_entry.get("models") or []
        official_normalized = official_entry.get("normalized_models") or set()

        if any(alias in official_normalized for alias in normalized_aliases):
            exact_matches.add(canonical_slug)
            continue

        if _has_unique_fuzzy_match(aliases, official_models):
            fuzzy_matches.add(canonical_slug)

    if len(exact_matches) == 1:
        return next(iter(exact_matches)), "exact_unique", []
    if len(exact_matches) > 1:
        return None, "ambiguous_exact", sorted(exact_matches)
    if len(fuzzy_matches) == 1:
        return next(iter(fuzzy_matches)), "fuzzy_unique", []
    if len(fuzzy_matches) > 1:
        return None, "ambiguous_fuzzy", sorted(fuzzy_matches)
    return None, "unmatched", []


def build_official_model_index(models_by_make: dict[str, Iterable[str]], make_names: dict[str, str]) -> dict[str, dict[str, Any]]:
    raw_entries: list[dict[str, Any]] = []
    for make_slug, models in models_by_make.items():
        unique_models = sorted({str(model).strip() for model in models if str(model).strip()})
        raw_entries.append(
            {
                "slug": make_slug,
                "make_name": make_names.get(make_slug) or make_slug,
                "models": unique_models,
                "normalized_models": {normalize_name(model) for model in unique_models if normalize_name(model)},
                "normalized_make_name": normalize_name(make_names.get(make_slug) or make_slug),
            }
        )

    index: dict[str, dict[str, Any]] = {}
    for alias_group in _group_make_aliases(raw_entries):
        canonical = alias_group[0]
        aliases = [entry["slug"] for entry in alias_group[1:]]
        canonical_entry = {
            "canonical_slug": canonical["slug"],
            "make_name": canonical["make_name"],
            "models": canonical["models"],
            "normalized_models": canonical["normalized_models"],
            "aliases": aliases,
        }
        index[canonical["slug"]] = canonical_entry
        for alias in alias_group[1:]:
            index[alias["slug"]] = canonical_entry
    return index


def normalize_name(value: str) -> str:
    return NON_ALNUM_PATTERN.sub("", str(value).upper())


def _collect_model_names(values: dict[str, list[str]]) -> list[str]:
    ordered_names: list[str] = []
    for field_name in ("manufacturer_model_desc", "lot_model_group", "lot_model_desc"):
        for value in values.get(field_name, []):
            if value not in ordered_names:
                ordered_names.append(value)
    return ordered_names


def _build_market_models(raw_models: Iterable[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    used_model_slugs: set[str] = set()
    for raw_model in raw_models:
        model_name = str(raw_model).strip()
        if not model_name:
            continue
        normalized_name = normalize_name(model_name)
        if not normalized_name:
            continue
        existing = grouped.get(normalized_name)
        if existing is None:
            grouped[normalized_name] = {
                "slug": _unique_slug(model_name, used_model_slugs),
                "name": model_name,
                "aliases": [model_name],
            }
            continue
        if model_name not in existing["aliases"]:
            existing["aliases"].append(model_name)

    models: list[dict[str, Any]] = []
    for item in grouped.values():
        models.append(
            {
                "slug": item["slug"],
                "name": item["name"],
                "aliases": item["aliases"],
                "filter_query": _build_filter_query(
                    ("lot_model_desc", "lot_model_group", "manufacturer_model_desc"),
                    item["aliases"],
                ),
                "confidence": "source_exact",
            }
        )
    return sorted(models, key=lambda item: item["name"])


def _build_filter_query(field_names: tuple[str, ...], values: Iterable[str]) -> str:
    variants = _expand_filter_variants(values)
    clauses = [f'{field_name}:"{_escape_filter_value(value)}"' for field_name in field_names for value in variants]
    return " OR ".join(clauses)


def _expand_filter_variants(values: Iterable[str]) -> list[str]:
    variants: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text not in variants:
            variants.append(text)
        upper = text.upper()
        if upper != text and upper not in variants:
            variants.append(upper)
    return variants


def _extract_market_years(meta: dict[str, Any]) -> list[int]:
    years = meta.get("years")
    if not isinstance(years, dict):
        return []
    year_from = years.get("from")
    year_to = years.get("to")
    if not isinstance(year_from, int) or not isinstance(year_to, int):
        return []
    if year_from > year_to:
        year_from, year_to = year_to, year_from
    return list(range(year_from, year_to + 1))


def _unique_slug(value: str, used_slugs: set[str]) -> str:
    base_slug = _slugify(value)
    slug = base_slug
    suffix = 2
    while slug in used_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    used_slugs.add(slug)
    return slug


def _slugify(value: str) -> str:
    normalized = SLUG_PATTERN.sub("-", str(value).strip().lower()).strip("-")
    return normalized or "item"


def _escape_filter_value(value: str) -> str:
    return str(value).replace('"', '\\"')


def _extract_field_values(filter_query: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for field_name, field_value in FIELD_VALUE_PATTERN.findall(filter_query):
        values.setdefault(field_name, [])
        if field_value not in values[field_name]:
            values[field_name].append(field_value)
    return values


def _has_unique_fuzzy_match(candidate_aliases: list[str], official_models: list[str]) -> bool:
    for candidate in candidate_aliases:
        candidate_tokens = _tokenize(candidate)
        if not candidate_tokens:
            continue
        for official_model in official_models:
            official_tokens = _tokenize(official_model)
            if _token_prefix_match(candidate_tokens, official_tokens):
                return True
    return False


def _token_prefix_match(candidate_tokens: list[str], official_tokens: list[str]) -> bool:
    if len(candidate_tokens) != len(official_tokens):
        return False
    for candidate_token, official_token in zip(candidate_tokens, official_tokens):
        if candidate_token == official_token:
            continue
        if official_token.startswith(candidate_token):
            continue
        return False
    return True


def _tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"[^A-Z0-9]+", str(value).upper()) if token]


def _parse_year(value: Any) -> int | None:
    try:
        year = int(str(value))
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def _group_make_aliases(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: list[list[dict[str, Any]]] = []
    used_slugs: set[str] = set()

    sorted_entries = sorted(entries, key=lambda item: (len(item["normalized_make_name"]), item["make_name"]), reverse=True)
    for entry in sorted_entries:
        if entry["slug"] in used_slugs:
            continue
        group = [entry]
        used_slugs.add(entry["slug"])
        for candidate in sorted_entries:
            if candidate["slug"] in used_slugs:
                continue
            if candidate["normalized_models"] != entry["normalized_models"]:
                continue
            if not _looks_like_make_alias(entry["normalized_make_name"], candidate["normalized_make_name"]):
                continue
            group.append(candidate)
            used_slugs.add(candidate["slug"])
        grouped.append(group)
    return grouped


def _looks_like_make_alias(primary_name: str, candidate_name: str) -> bool:
    if not primary_name or not candidate_name:
        return False
    if len(candidate_name) < 4:
        return False
    return primary_name.startswith(candidate_name) or candidate_name.startswith(primary_name)
