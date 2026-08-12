# Repository instructions

## Updating Wikidot source files

The files under `sources/` are checked-in snapshots of official SCP tag-list
pages. When updating them, use the local `wikidot.py` fork through the
`wikidot-py-operations` skill; do not use `curl`, ad-hoc HTTP requests, or web
search results as the source of page text.

For public reads, fetch the page source with the repository-pinned wrapper and
the high-level API:

```bash
/home/roku/.codex/skills/wikidot-py-operations/scripts/wikidot-python - <<'PY'
from pathlib import Path
import wikidot

output_dir = Path("/tmp/scp-jp-tag-sources")
output_dir.mkdir(exist_ok=True)
pages = {
    "fragment:tag-list-basic": "fragment-basic.txt",
    "fragment:tag-list-series": "fragment-series.txt",
    "fragment:tag-list-universe": "fragment-universe.txt",
    "fragment:tag-list-event": "fragment-event.txt",
    "fragment:tag-list-unused": "fragment-unused.txt",
    "fragment:tag-list-faq": "fragment-faq.txt",
}

with wikidot.Client() as client:
    site = client.site.get("scp-jp")
    for fullname, filename in pages.items():
        page = site.page.get(fullname)
        (output_dir / filename).write_text(page.source.wiki_text, encoding="utf-8")
PY
```

Read the page manifest first so that all included fragments are covered. Review
the fetched text and apply repository changes with `apply_patch`. Preserve the
official source attribution and keep source snapshots free of accidental
secrets or unrelated edits.

After updating source snapshots, regenerate and validate the derived files:

```bash
python scripts/parse_sources.py
python scripts/build_dict.py
python -m pytest -q
git -c core.whitespace=cr-at-eol diff --check
```

The parser reads `sources/jp/fragment-*.txt`, so newly included JP fragments
must use that filename pattern. Do not edit generated `data/` files by hand;
the committed dictionaries under `dictionaries/` are the publication output.
