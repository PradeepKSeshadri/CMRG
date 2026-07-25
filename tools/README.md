# Publication tools

## `update_pubs.py` — refresh citations & stats from Google Scholar

Run occasionally (e.g. monthly) to pull current citation counts and profile
metrics into the site. **Curation-safe**: it only updates citation numbers on
entries you already have, plus `scholar.json` (total citations, h-index,
i10-index). New papers are *reported*, not auto-added — they land in
`tools/pubs_new_review.json` for you to place by hand.

```bash
# one-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt

# see what would change (writes nothing)
python tools/update_pubs.py

# apply: update journals.json, conferences.json, scholar.json
python tools/update_pubs.py --apply
```

Then review `git diff`, curate any new items from `tools/pubs_new_review.json`
(add thumbnail/tags/description, drop what you don't want), and commit.

**Notes**
- Camp classification (journal / preprint / conference-talk) is by venue string.
  Fix edge cases in the `OVERRIDES` map at the top of the script — those persist
  across runs. Also, the file an entry lives in *is* its camp, so moving an entry
  between `journals.json` and `conferences.json` sticks.
- Google Scholar has no API and can throttle/CAPTCHA bots. If a run is blocked,
  try again later. ResearchGate can't be automated (no API); use it as a manual
  cross-check.
- Scholar ID is set at the top of `update_pubs.py` (`SCHOLAR_ID`).
