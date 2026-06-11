"""Functional core of the search engine.

Builds an in-memory inverted index over the movie catalog and answers
queries with BM25-ranked results. Pure: the index is plain data built
from a list of movie dicts; searching never mutates it.

Features:
- BM25 ranking with per-field weights (title matches outrank plot matches)
- Transliteration-aware matching via phonetic keys (bahubali -> Baahubali)
- Typo tolerance via bounded edit distance, with "did you mean" rewrites
- Query filters: year:2017, after:2015, before:2000, genre:action,
  director:rajamouli, actor:prabhas, music:keeravani
- Highlighted snippets and prefix-based autosuggest
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .text import levenshtein, phonetic_key, tokenize

FIELD_WEIGHTS = {
    "title": 5.0,
    "cast": 2.5,
    "director": 2.5,
    "music": 2.0,
    "genres": 2.0,
    "plot": 1.0,
}

# BM25 parameters: k1 controls term-frequency saturation, b controls
# document-length normalization.
BM25_K1 = 1.4
BM25_B = 0.6

_FILTER_RE = re.compile(
    r'\b(year|after|before|genre|director|actor|music)\s*:\s*("[^"]+"|\S+)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Index:
    movies: dict[int, dict]
    postings: dict[str, dict[int, float]]   # token -> {doc_id: weighted tf}
    phonetic: dict[str, set[str]]           # phonetic key -> tokens
    doc_len: dict[int, float]               # weighted token count per doc
    avg_doc_len: float
    vocab: list[str] = field(default_factory=list)


def doc_fields(movie: dict) -> dict[str, str]:
    return {
        "title": movie["title"],
        "cast": " ".join(movie["cast"]),
        "director": movie["director"],
        "music": movie["music"],
        "genres": " ".join(movie["genres"]),
        "plot": movie["plot"],
    }


def build_index(movies: list[dict]) -> Index:
    postings: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    phonetic: dict[str, set[str]] = defaultdict(set)
    doc_len: dict[int, float] = {}

    for movie in movies:
        doc_id = movie["id"]
        total = 0.0
        for fname, text in doc_fields(movie).items():
            weight = FIELD_WEIGHTS[fname]
            for token in tokenize(text):
                postings[token][doc_id] += weight
                phonetic[phonetic_key(token)].add(token)
                total += weight
        # Year is searchable but unweighted-light.
        year_tok = str(movie["year"])
        postings[year_tok][doc_id] += 1.0
        doc_len[doc_id] = total

    avg = sum(doc_len.values()) / len(doc_len) if doc_len else 1.0
    return Index(
        movies={m["id"]: m for m in movies},
        postings={t: dict(d) for t, d in postings.items()},
        phonetic=dict(phonetic),
        doc_len=doc_len,
        avg_doc_len=avg,
        vocab=sorted(postings),
    )


# ---------------------------------------------------------------- query


@dataclass(frozen=True)
class ParsedQuery:
    terms: list[str]
    filters: list[tuple[str, str]]


def parse_query(raw: str) -> ParsedQuery:
    filters = [
        (key.lower(), value.strip('"').lower())
        for key, value in _FILTER_RE.findall(raw)
    ]
    rest = _FILTER_RE.sub(" ", raw)
    return ParsedQuery(terms=tokenize(rest), filters=filters)


def passes_filters(movie: dict, filters: list[tuple[str, str]]) -> bool:
    for key, value in filters:
        if key == "year" and str(movie["year"]) != value:
            return False
        if key == "after" and not (value.isdigit() and movie["year"] > int(value)):
            return False
        if key == "before" and not (value.isdigit() and movie["year"] < int(value)):
            return False
        if key == "genre" and value not in {g.lower() for g in movie["genres"]}:
            return False
        if key == "director" and value not in movie["director"].lower():
            return False
        if key == "actor" and not any(value in c.lower() for c in movie["cast"]):
            return False
        if key == "music" and value not in movie["music"].lower():
            return False
    return True


# ------------------------------------------------------------- matching


def match_term(index: Index, term: str) -> tuple[dict[int, float], str | None]:
    """Resolve one query term to postings.

    Returns (postings, correction). Tries exact, then phonetic
    (transliteration variants, full credit), then fuzzy edit distance
    (half credit) which also yields a "did you mean" correction.
    """
    if term in index.postings:
        return index.postings[term], None

    variants = index.phonetic.get(phonetic_key(term))
    if variants:
        merged: dict[int, float] = defaultdict(float)
        for tok in variants:
            for doc_id, tf in index.postings[tok].items():
                merged[doc_id] = max(merged[doc_id], tf)
        return dict(merged), min(variants, key=lambda t: levenshtein(term, t))

    max_dist = 1 if len(term) <= 5 else 2
    best_tok, best_dist = None, max_dist + 1
    for tok in index.vocab:
        dist = levenshtein(term, tok, cap=best_dist)
        if dist < best_dist:
            best_tok, best_dist = tok, dist
            if dist == 1:
                break
    if best_tok is None:
        return {}, None
    halved = {d: tf * 0.5 for d, tf in index.postings[best_tok].items()}
    return halved, best_tok


def bm25(index: Index, tf: float, doc_id: int, n_docs_with_term: int) -> float:
    n = len(index.movies)
    idf = math.log(1 + (n - n_docs_with_term + 0.5) / (n_docs_with_term + 0.5))
    norm = 1 - BM25_B + BM25_B * index.doc_len[doc_id] / index.avg_doc_len
    return idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norm)


# -------------------------------------------------------------- snippets


def make_snippet(movie: dict, terms: set[str], max_len: int = 200) -> str:
    """Plot snippet with query terms wrapped in <b> tags."""
    text = movie["plot"]
    if len(text) > max_len:
        cut = text[:max_len]
        text = cut[: cut.rfind(" ")] + "…"
    if not terms:
        return text
    keys = {phonetic_key(t) for t in terms}

    def mark(match: re.Match) -> str:
        word = match.group(0)
        low = word.lower()
        if low in terms or phonetic_key(low) in keys:
            return f"<b>{word}</b>"
        return word

    return re.sub(r"[A-Za-z0-9]+", mark, text)


# ---------------------------------------------------------------- search


def search(index: Index, raw_query: str, limit: int = 10, offset: int = 0) -> dict:
    """Full search pipeline: parse -> match -> rank -> snippet."""
    parsed = parse_query(raw_query)
    if not parsed.terms and not parsed.filters:
        return {"query": raw_query, "total": 0, "offset": 0,
                "results": [], "did_you_mean": None}

    corrections: dict[str, str] = {}
    scores: Counter = Counter()
    matched_terms: set[str] = set(parsed.terms)

    for term in parsed.terms:
        postings, correction = match_term(index, term)
        if correction:
            corrections[term] = correction
            matched_terms.add(correction)
        for doc_id, tf in postings.items():
            scores[doc_id] += bm25(index, tf, doc_id, len(postings))

    if parsed.terms:
        candidates = scores.most_common()
    else:
        # Filter-only query (e.g. "genre:action after:2020"): rank by rating.
        candidates = [
            (m["id"], m["rating"]) for m in
            sorted(index.movies.values(), key=lambda m: -m["rating"])
        ]

    hits = [
        (doc_id, score)
        for doc_id, score in candidates
        if passes_filters(index.movies[doc_id], parsed.filters)
    ]

    results = []
    for doc_id, score in hits[offset:offset + limit]:
        movie = index.movies[doc_id]
        results.append({
            **movie,
            "score": round(score, 3),
            "snippet": make_snippet(movie, matched_terms),
        })

    did_you_mean = None
    if corrections:
        did_you_mean = " ".join(corrections.get(t, t) for t in parsed.terms)
        if tokenize(did_you_mean) == parsed.terms:
            did_you_mean = None

    return {
        "query": raw_query,
        "total": len(hits),
        "offset": offset,
        "results": results,
        "did_you_mean": did_you_mean,
    }


def suggest(index: Index, prefix: str, limit: int = 8) -> list[str]:
    """Search-as-you-type: titles and people whose words start with the
    typed prefix, best-rated first."""
    terms = tokenize(prefix)
    if not terms:
        return []
    last = terms[-1]
    ranked: list[tuple[float, str]] = []
    for movie in index.movies.values():
        names = [movie["title"], movie["director"], *movie["cast"]]
        for name in names:
            words = tokenize(name)
            if any(w.startswith(last) for w in words):
                label = name if name == movie["title"] else f'{name} — {movie["title"]}'
                ranked.append((movie["rating"], label))
                break
    ranked.sort(key=lambda pair: -pair[0])
    seen: set[str] = set()
    out = []
    for _, label in ranked:
        if label not in seen:
            seen.add(label)
            out.append(label)
        if len(out) == limit:
            break
    return out
