# Research Compass · Prototype Design Spec

## Visual system

- Canvas: `#F8FAFC`; Navy: `#142B43`; Teal: `#287D8E`; Soft Blue: `#EAF3F5`.
- 1440 × 900 desktop canvas; content max width 1200 px; narrower views use tighter outer padding, wrapped query text, and vertically flowing evidence content.
- System sans-serif typography, compact headings, native Streamlit forms, bordered containers, buttons, links, and expanders.
- Shared top navigation shows the product name and the active step across Intent Studio, Research Paths, and Evidence & Next.

## Interaction notes

1. **AI Intent Studio** foregrounds free-text input, source → target method roles, editable intent, and an explicit planning-source state. The “载入已验证 Golden Case” control loads read-only historical records for prototype review and makes no API call; it is visibly marked Snapshot.
2. **Research Path Explorer** presents up to three path cards in a responsive column layout. Query strings remain readable; selecting a path reveals its saved/live result state. Abstracts can be expanded, with the first result open by default. Switching to a cached path preserves prior results.
3. **Evidence & Next Steps** separates Evidence Landscape, candidate questions (each marked 待验证), and Next Search. Source excerpts link to the paper; Research Plan Summary remains selectable with Streamlit’s copy control.

## Prototype data disclosure

The screenshots use the Golden Case’s previously recorded **real Qwen response** (`qwen-03`) and **real OpenAlex V1 retrieval snapshot**. Both are historical snapshots, not live calls during M2. The UI labels this state on every relevant page. No Qwen or OpenAlex request is made by the snapshot loader.

## Browser capture note

The three supplied screenshots are 1440 × 900 pixel browser viewport captures. Visual inspection confirms the app content is laid out across the viewport rather than a smaller capture surrounded by blank padding. Page 1 shows the Golden Case intent preview and rule-mode state; Page 2 shows the three exploration paths; Page 3 shows the path 1 → Card A human-curated Golden Case v2 state. Page 3's card continues below the viewport and is scrollable in the live app.

These are actual Streamlit page renders, not mockups. They use the saved Golden Case history and human-reviewed v2 card data. They do not represent a new Qwen or OpenAlex request, nor a live Qwen result. See `docs/GOLDEN_CASE_V2_EVIDENCE_AUDIT.md` for the human-curation and evidence provenance.

## Files

- `01_AI_Intent_Studio.png`
- `02_Research_Path_Explorer.png`
- `03_Evidence_Next_Steps.png`
- Shared UI source: `../../research_compass/ui_theme.py`
- Snapshot loader source: `../../research_compass/prototype_snapshot.py`
