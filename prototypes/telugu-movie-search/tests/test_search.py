"""Unit tests for the functional core — no mocks needed, pure functions."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.engine import build_index, parse_query, search, suggest
from search.text import levenshtein, phonetic_key, tokenize


@pytest.fixture(scope="module")
def index():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "movies.json")
    with open(path, encoding="utf-8") as f:
        return build_index(json.load(f))


def titles(response):
    return [r["title"] for r in response["results"]]


# ------------------------------------------------------------------ text


def test_tokenize_lowercases_and_folds_accents():
    assert tokenize("Baahubali: The Beginning!") == ["baahubali", "the", "beginning"]
    assert tokenize("Naïve café") == ["naive", "cafe"]


def test_phonetic_key_collapses_transliteration_variants():
    assert phonetic_key("baahubali") == phonetic_key("bahubali")
    assert phonetic_key("keeravani") == phonetic_key("kiravani")
    assert phonetic_key("tamannaah") == phonetic_key("tamanna")
    assert phonetic_key("sukumar") != phonetic_key("rajamouli")


def test_levenshtein():
    assert levenshtein("pushpa", "pushpa") == 0
    assert levenshtein("pushpa", "pushpha") == 1
    assert levenshtein("abc", "xyz") == 3
    assert levenshtein("short", "muchlongerword") == 3  # capped


# ----------------------------------------------------------------- query


def test_parse_query_extracts_filters():
    parsed = parse_query('action director:"S. S. Rajamouli" after:2010')
    assert parsed.terms == ["action"]
    assert ("director", "s. s. rajamouli") in parsed.filters
    assert ("after", "2010") in parsed.filters


# ---------------------------------------------------------------- search


def test_exact_title_search_ranks_match_first(index):
    response = search(index, "pokiri")
    assert titles(response)[0] == "Pokiri"


def test_title_match_outranks_plot_match(index):
    # "jersey" appears in the Jersey title and in its plot only.
    assert titles(search(index, "jersey"))[0] == "Jersey"


def test_transliteration_variant_matches(index):
    response = search(index, "bahubali")
    assert titles(response)[0].startswith("Baahubali")
    assert response["total"] >= 2  # both parts


def test_typo_yields_did_you_mean(index):
    response = search(index, "rajamowli")
    assert response["did_you_mean"] == "rajamouli"
    assert any("Rajamouli" in r["director"] for r in response["results"])


def test_multi_term_query(index):
    response = search(index, "rajamouli prabhas")
    top3 = titles(response)[:3]
    assert any(t.startswith("Baahubali") for t in top3)


def test_actor_search_returns_their_films(index):
    response = search(index, "mahesh babu")
    assert response["total"] >= 5
    assert all("Mahesh Babu" in r["cast"] for r in response["results"][:5])


def test_year_filter(index):
    response = search(index, "year:2017")
    assert response["total"] > 0
    assert all(r["year"] == 2017 for r in response["results"])


def test_before_after_filters(index):
    classics = search(index, "before:1990")
    assert all(r["year"] < 1990 for r in classics["results"])
    recent = search(index, "genre:comedy after:2015")
    assert recent["total"] > 0
    for r in recent["results"]:
        assert r["year"] > 2015
        assert "Comedy" in r["genres"]


def test_director_filter_combined_with_terms(index):
    response = search(index, "director:rajamouli fantasy")
    assert all("Rajamouli" in r["director"] for r in response["results"])


def test_filter_only_query_ranked_by_rating(index):
    response = search(index, "genre:classic")
    ratings = [r["rating"] for r in response["results"]]
    assert ratings == sorted(ratings, reverse=True)


def test_snippet_highlights_query_terms(index):
    response = search(index, "waterfall")
    top = response["results"][0]
    assert "<b>waterfall</b>" in top["snippet"]


def test_empty_and_nonsense_queries(index):
    assert search(index, "")["total"] == 0
    assert search(index, "xqzwvk")["results"] == []


def test_pagination(index):
    page1 = search(index, "genre:action", limit=5, offset=0)
    page2 = search(index, "genre:action", limit=5, offset=5)
    assert len(page1["results"]) == 5
    assert not set(titles(page1)) & set(titles(page2))
    assert page1["total"] == page2["total"]


# --------------------------------------------------------------- suggest


def test_suggest_matches_title_prefix(index):
    assert any("Mahanati" in s for s in suggest(index, "maha"))
    assert any("Mahesh Babu" in s for s in suggest(index, "mahe"))


def test_suggest_empty_prefix(index):
    assert suggest(index, "") == []
    assert suggest(index, "   ") == []


def test_suggest_caps_results(index):
    assert len(suggest(index, "a")) <= 8
