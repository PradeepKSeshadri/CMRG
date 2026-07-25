#!/usr/bin/env python3
"""
Refresh CMRG publication citations + profile stats from Google Scholar.

Usage:
    python tools/update_pubs.py            # dry-run: report only, writes nothing
    python tools/update_pubs.py --apply    # write refreshed citations + scholar.json

Setup (once):
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r tools/requirements.txt

What it does (curation-safe):
  * Fetches your Scholar profile (ID below).
  * Classifies every paper into a camp: journal / preprint / conference-talk,
    by venue string (with a manual OVERRIDES map for edge cases).
  * Matches Scholar papers to your existing entries by title and UPDATES ONLY
    the citation count in journals.json / conferences.json.
  * Refreshes scholar.json (total citations, h-index, i10-index, count).
  * Writes any *new* Scholar papers (not yet on the site) to
    tools/pubs_new_review.json, grouped by camp, for you to place manually.

What it never touches: your thumbnails, tags, descriptions, links, ordering,
or which camp a curated entry lives in (the file it's in wins).

Google Scholar has no API and can rate-limit/CAPTCHA automated access. This is
meant to be run occasionally by hand; if a run is blocked, just try again later.
"""
import argparse, json, os, re, sys, difflib

SCHOLAR_ID = "KQNT0mwAAAAJ"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Venue-string hints for camp classification.
CONF_HINTS = ["conference", "symposium", "proceedings", "meeting", "congress",
              "workshop", "colloquium", "bulletin of the american physical",
              "aps ", "aps march", "aps division", "global physics summit",
              "shock compression of condensed matter", "scitech", "aviation",
              "annual", "biennial", "abstracts"]
PRE_HINTS = ["arxiv", "preprint", "ssrn", "researchsquare", "research square",
             "techrxiv", "biorxiv", "chemrxiv"]

# Manual overrides when the venue heuristic gets a specific paper wrong.
# Map a distinctive lowercase title substring -> "journal" | "preprint" | "conference".
OVERRIDES = {
    # "physics-aware recurrent convolutional neural networks for modeling":"journal",
}

def classify(venue, title=""):
    t = (title or "").lower()
    for sub, camp in OVERRIDES.items():
        if sub in t:
            return camp
    v = (venue or "").lower()
    if any(h in v for h in PRE_HINTS):
        return "preprint"
    if any(h in v for h in CONF_HINTS):
        return "conference"
    return "journal"

def norm(title):
    t = re.sub(r':\s*[A-Z]\.?\s*[A-Za-z]+ et al\.?\s*$', '', title or '')  # strip "…: C. Okafor et al."
    return re.sub(r'[^a-z0-9]+', ' ', t.lower()).strip()

def best_match(ntitle, index, threshold=0.82):
    best, ratio = None, 0.0
    for key, obj in index:
        r = difflib.SequenceMatcher(None, ntitle, key).ratio()
        if r > ratio:
            ratio, best = r, obj
    return (best, ratio) if ratio >= threshold else (None, ratio)

def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)

def save(name, data):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def fetch_scholar():
    try:
        from scholarly import scholarly
    except ImportError:
        sys.exit("scholarly not installed. Run: pip install -r tools/requirements.txt")
    a = scholarly.search_author_id(SCHOLAR_ID)
    a = scholarly.fill(a, sections=["basics", "indices", "counts", "publications"])
    pubs = []
    for p in a.get("publications", []):
        b = p.get("bib", {})
        venue = b.get("citation") or b.get("journal") or b.get("venue") or ""
        title = b.get("title", "")
        pubs.append({"title": title, "year": str(b.get("pub_year", "")), "venue": venue,
                     "citations": p.get("num_citations", 0), "camp": classify(venue, title)})
    return {"total_citations": a.get("citedby", 0), "h_index": a.get("hindex", 0),
            "i10_index": a.get("i10index", 0), "num_pubs": len(pubs), "pubs": pubs}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    journals = load("journals.json")
    conferences = load("conferences.json")
    scholar_meta = load("scholar.json")

    print(f"Fetching Google Scholar profile {SCHOLAR_ID} …")
    sc = fetch_scholar()
    print(f"  total citations {sc['total_citations']} | h-index {sc['h_index']} | "
          f"i10 {sc['i10_index']} | {sc['num_pubs']} papers\n")
    pubs = sc["pubs"]

    # Curated site entries across both camps: (camp, obj, normalized_title, current_citations)
    site = []
    for e in journals["publications"]:
        cur = int(re.search(r'\d+', e["card"].get("citation", "0") or "0").group() or 0)
        site.append(("journal", e, norm(e["card"].get("card-heading", "")), cur))
    for i in conferences["items"]:
        site.append(("conf", i, norm(i.get("title", "")), i.get("citations", 0)))

    # Score every (site entry, scholar paper) pair, then assign greedily 1-to-1 by
    # descending similarity so a paper never updates two entries (or vice versa).
    pairs = []
    for si, (_, _, nt, _) in enumerate(site):
        for pj, p in enumerate(pubs):
            r = difflib.SequenceMatcher(None, nt, norm(p["title"])).ratio()
            if r >= 0.82:
                # rank by rounded similarity, then by citation count, so the canonical
                # record wins over Scholar's 0-citation duplicate listings of the same paper
                pairs.append((round(r, 2), p["citations"], si, pj))
    pairs.sort(reverse=True)
    site_taken, pub_taken, match = set(), set(), {}
    for _rank, _cit, si, pj in pairs:
        if si in site_taken or pj in pub_taken:
            continue
        site_taken.add(si); pub_taken.add(pj); match[si] = pj

    changed = []
    for si, (camp, obj, nt, cur) in enumerate(site):
        if si not in match:
            continue
        new = pubs[match[si]]["citations"]
        if new != cur:
            title = (obj["card"]["card-heading"] if camp == "journal" else obj["title"])[:60]
            changed.append((camp, cur, new, title))
        if camp == "journal":
            obj["card"]["citation"] = f"{new} citations"
        else:
            obj["citations"] = new

    new_items = {"journal": [], "preprint": [], "conference": []}
    for pj, p in enumerate(pubs):
        if pj not in pub_taken:
            new_items.setdefault(p["camp"], []).append(p)

    scholar_meta.update({"total_citations": sc["total_citations"], "h_index": sc["h_index"],
                         "i10_index": sc["i10_index"], "num_pubs": sc["num_pubs"]})

    # ---- report ----
    print(f"Citation updates: {len(changed)}")
    for camp, old, new, title in sorted(changed, key=lambda x: -x[2]):
        print(f"  [{camp:5}] {old:>3} -> {new:<3}  {title}")
    total_new = sum(len(v) for v in new_items.values())
    print(f"\nNew papers on Scholar not on the site: {total_new}")
    for camp, items in new_items.items():
        for p in sorted(items, key=lambda x: -x["citations"]):
            print(f"  [{camp:11}] {p['year']} {p['citations']:>3}c  {p['venue'][:30]:30s} | {p['title'][:50]}")

    if args.apply:
        save("journals.json", journals)
        save("conferences.json", conferences)
        save("scholar.json", scholar_meta)
        review = {"generated_from": SCHOLAR_ID, "new_items": new_items}
        save(os.path.join("tools", "pubs_new_review.json"), review)
        print("\nAPPLIED: journals.json, conferences.json, scholar.json updated; "
              "new papers written to tools/pubs_new_review.json for you to place.")
    else:
        print("\nDRY-RUN: nothing written. Re-run with --apply to save.")

if __name__ == "__main__":
    main()
