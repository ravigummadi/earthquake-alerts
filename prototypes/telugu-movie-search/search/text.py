"""Pure text-processing functions: tokenization, transliteration
normalization, and edit distance. No I/O, no state.

Telugu movie titles and names reach English spelling through romanized
transliteration, so the same word has many valid spellings (Baahubali /
Bahubali, Keeravani / Kiravani). `phonetic_key` collapses those variants
onto one canonical key so the index can match them all.
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Order matters: digraphs before single letters.
_PHONETIC_RULES = [
    ("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"),
    ("bh", "b"), ("ch", "c"), ("dh", "d"), ("gh", "g"), ("jh", "j"),
    ("kh", "k"), ("ph", "p"), ("sh", "s"), ("th", "t"), ("zh", "l"),
    ("w", "v"), ("z", "j"),
]


def fold_accents(text: str) -> str:
    """Strip diacritics: 'Naïve' -> 'Naive'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, accents folded."""
    return _TOKEN_RE.findall(fold_accents(text).lower())


def phonetic_key(token: str) -> str:
    """Canonical key for transliteration variants.

    bahubali / baahubali -> 'babali' (same key), keeravani / kiravani
    -> 'kiravani'. Applies digraph folding, then collapses repeated
    letters and trailing vowel noise.
    """
    key = token
    for src, dst in _PHONETIC_RULES:
        key = key.replace(src, dst)
    # Collapse runs of the same letter: 'tamannaah' -> 'tamanah'.
    key = re.sub(r"(.)\1+", r"\1", key)
    # Trailing 'h' is silent in romanization: 'tamannah' ~ 'tamanna'.
    if len(key) > 2 and key.endswith("h"):
        key = key[:-1]
    return key


def levenshtein(a: str, b: str, cap: int = 3) -> int:
    """Edit distance, short-circuiting at `cap` (returns cap if >= cap)."""
    if abs(len(a) - len(b)) >= cap:
        return cap
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cost = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(cost)
            best = min(best, cost)
        if best >= cap:
            return cap
        prev = cur
    return min(prev[-1], cap)
