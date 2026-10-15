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

The three PNG files are genuine browser renders saved as 1440 × 900 pixel images. The browser's actual CSS viewport at capture was only 932 × 654, so the visible app occupies only that smaller viewport; the remaining canvas is blank. They are not full 1440 × 900 desktop screenshots and do not validate the full-width desktop layout. This limitation is disclosed rather than filled or represented as a larger browser capture.

The screenshots document the actual Streamlit page states, not a separate mockup. Page 1 and Page 2 use the saved Golden Case history. Page 3 uses the human-curated Golden Case v2 card content. None of the screenshots represents a new Qwen or OpenAlex request.

## Files

- `01_AI_Intent_Studio.png`
- `02_Research_Path_Explorer.png`
- `03_Evidence_Next_Steps.png`
- Shared UI source: `../../research_compass/ui_theme.py`
- Snapshot loader source: `../../research_compass/prototype_snapshot.py`
