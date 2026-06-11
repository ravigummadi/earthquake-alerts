# Telugu Movie Search

A self-contained, Google-style search engine over Telugu cinema — built end-to-end
with **zero dependencies** (Python 3.11 stdlib only).

```bash
python3 app.py
# → http://localhost:8000
```

![architecture](#) Follows the repo's **Functional Core, Imperative Shell** pattern:

```
telugu-movie-search/
├── app.py              # imperative shell: stdlib HTTP server (3 routes)
├── search/             # functional core: pure, no I/O
│   ├── text.py         #   tokenizer, transliteration phonetic keys, edit distance
│   └── engine.py       #   inverted index, BM25 ranking, filters, snippets, suggest
├── static/index.html   # Google-style UI (vanilla JS, no build step)
├── data/movies.json    # curated catalog of 80 real Telugu films (1951–2025)
└── tests/              # 20 unit tests, no mocks
```

## What the engine does

| Feature | Example |
|---|---|
| BM25 ranking with field weights | title hit outranks plot hit for `jersey` |
| Transliteration matching | `bahubali`, `kiravani` → Baahubali, Keeravani |
| Typo tolerance + did-you-mean | `rajamowli` → "Did you mean: *rajamouli*" |
| Query operators | `director:rajamouli after:2010`, `genre:comedy`, `actor:prabhas`, `year:2018`, `before:1990`, `music:keeravani` |
| Highlighted snippets | query terms wrapped in `<b>` in plot excerpts |
| Autosuggest | prefix match over titles, directors, cast — ranked by rating |
| Knowledge panel | confident top hit gets a Google-style info card |
| Pagination & deep links | `/?q=genre:action&offset=10` is shareable |

## API

```
GET /api/search?q=<query>&limit=10&offset=0
GET /api/suggest?q=<prefix>
GET /health
```

## Tests

```bash
python3 -m pytest tests/ -v
```
