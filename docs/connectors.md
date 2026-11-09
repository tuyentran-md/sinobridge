# Writing a source connector

Connectors bring Chinese material into SinoBridge. There are two kinds:

| kind | input | returns |
|---|---|---|
| `document` | a reference string (path, URL, ID...) | `(raw_bytes, blocks, warnings, provenance)` |
| `search` | `(query, language, limit)` | list of bibliographic records |

`blocks` is a list of `(location, kind, text)`:

- `location` must let a human find the passage again in the original: `page:3:block:2`, `line:120`,
  `post:4790012345`, `cue:00:01:02.000-->00:01:04.500`, `chapter2.xhtml#block:7`.
- `kind` is `heading`, `paragraph`, `table` or `cue`.
- `raw_bytes` are the exact bytes the blocks came from; their SHA-256 identifies the source revision.

`provenance` is a dict stored in `project.json` (e.g. `{"origin": "weibo-export", "account": "...", "exported": "2026-11-01"}`).
Records from search connectors should use the keys `title, authors, year, journal, doi, url, oa_url, abstract, language,
provider, provider_id`.

## Registering a plugin

```python
# my_package/connectors.py
from sinobridge.sources import Connector

def open_weibo_export(ref: str):
    ...  # parse a user's own Weibo data export
    return raw, blocks, warnings, {"origin": "weibo-export"}

def connectors():
    return [Connector(
        name="weibo-export", kind="document", access="user-provided",
        description="Weibo personal data export (.json)",
        handles=lambda ref: ref.endswith(".weibo.json"),
        open=open_weibo_export,
    )]
```

```toml
# my_package/pyproject.toml
[project.entry-points."sinobridge.sources"]
weibo = "my_package.connectors:connectors"
```

After `pip install my_package`, `sinobridge sources` lists it and `sinobridge ingest x.weibo.json ...` uses it
(or force it with `--connector weibo-export`).

## Rules for connectors in this repository

Pull requests adding connectors are welcome when they:

1. use official APIs, open data, user-exported files or a single user-requested public page;
2. never ship credentials, reuse browser cookies, solve CAPTCHAs, rotate IPs or otherwise defeat access controls;
3. honor robots.txt and provider terms; no bulk crawling;
4. keep exact locations and declare extraction limits in `warnings`;
5. include tests with small synthetic fixtures (no copyrighted text).

Licensed-access connectors (e.g. an institution's CNKI API) belong in separate packages owned by whoever holds
the license; this repository only defines the interface.
