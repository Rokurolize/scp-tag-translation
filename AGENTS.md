# Repository instructions

## Updating Wikidot source snapshots

Files under `sources/` are checked-in snapshots of the official SCP tag-list
pages. When updating them, read the Wikidot page source through the repository's
`wikidot.py` fork and the `wikidot-py-operations` skill. Do not use search
results or ad-hoc HTTP requests as the source of page text.

The JP tag-list manifest is the source of truth for the fragments that must be
updated. Preserve the official source attribution and keep unrelated edits out
of the snapshots.

After updating source snapshots, regenerate and validate the published outputs:

```bash
python -m scripts.commands.parse_sources --lang all
python -m scripts.commands.build_branch_dicts_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python -m pytest -q
git diff --check
```

The `data/` directory is intermediate output and is not committed. The
`dictionaries/` directory contains the publication output and must be committed
when source changes alter translations.

Genre tags are omitted only when no explicit JP mapping exists. An explicit
mapping in the JP source, such as `horror -> ホラー`, must remain translatable
after parser or code-health refactors.
