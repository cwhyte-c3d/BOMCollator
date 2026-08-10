# Collated BOM Exporter - maintainer / fix-it prompt

Paste everything below to Claude (or hand to whoever maintains InvenTree) if the
plugin breaks, needs a change, or needs reinstalling. It is self-contained.

---

## Context for the assistant

You are helping maintain an **InvenTree plugin** called **Collated BOM Exporter**
for Contour3D. Repo: **https://github.com/cwhyte-c3d/BOMCollator** (single
Python module `collated_bom_exporter.py` plus `pyproject.toml`, a standalone
`format_bom_excel.py`, and this file).

InvenTree instance: **https://inventree.contour3d.au**. The user (Charlotte) can
install plugins and restart the server herself.

### What the plugin does

Turns a multi-level BOM into one flat, collated shopping list. Same part used in
several sub-assemblies is rolled into a single row with the true total quantity.
Adds stock comparison (current stock, shortfall), pack-rounded order quantities,
supplier + pricing with a grand total, a longest-lead-time total, and lead time
-> estimated delivery. Output columns (slim set): Ordered, Part, BOM Level,
Total Quantity Required, Current Stock, Shortfall, Enough In Stock, Supplier,
Order Qty, Unit Price, Line Total, Lead Time (days), Est. Delivery, Recurrences,
Description. IPN and Reference are dropped.

### Three ways it produces a file (IMPORTANT)

1. **InvenTree's Export dialog** (DataExportMixin) - plain data only. InvenTree
   writes exports with tablib, which **cannot style cells**. So the Export
   button can NEVER produce colours/checkboxes. This is a hard InvenTree limit,
   not a bug. Do not try to add colour here; it is impossible.
2. **The plugin's own styled download** (UrlsMixin) at
   `/plugin/collated-bom-exporter/download/<part_id>/`. This builds the fully
   styled `.xlsx` with **openpyxl** (already installed on any InvenTree, since
   tablib uses it) - colours, checkbox column, est. delivery, totals. This is
   the everyday path.
3. **A part-page panel/button** (UserInterfaceMixin) - a "Collated BOM" tab on
   each assembly part with a Download button that hits path 2. Serves a small JS
   module from `/plugin/collated-bom-exporter/panel.js`.

### Golden rules learned the hard way

- **Pushing to GitHub does NOT update the running InvenTree.** The server keeps
  running the installed copy until it is reinstalled AND restarted. Every change
  must be followed by a reinstall + restart (below).
- **Use SOLID `PatternFill` for colours, not conditional formatting alone.**
  Conditional-formatting-only colours did not render in the user's Excel. Solid
  fills always show; keep a CF rule only as a bonus.
- The Export dialog cannot be styled - point users at the download / part-page
  button for anything with colour.
- Bump `VERSION` on the plugin class for every change, or pip may skip the
  update.

## How to install / update the plugin on InvenTree

Run in the InvenTree backend environment (venv, or inside the Docker container):

```bash
pip install --upgrade --force-reinstall "git+https://github.com/cwhyte-c3d/BOMCollator.git"
```

Then:

1. Restart the InvenTree **server and worker**.
2. Confirm the new **VERSION** shows in Settings -> Plugins.
3. In the plugin's settings, enable **"Enable URL integration"** (for the
   download) and **"Enable interface integration"** (for the part-page tab).
4. Hard-refresh the browser (Ctrl+F5) so cached plugin JS reloads.

## How to make a change

1. Edit `collated_bom_exporter.py` (server-side plugin) and/or
   `format_bom_excel.py` (standalone Excel formatter).
2. **Bump `VERSION`** on `CollatedBomExporterPlugin`.
3. Commit and push to the repo.
4. Reinstall + restart on InvenTree (steps above).

Colours/checkbox/est.-delivery live in `_build_workbook_bytes` (the download)
and mirror `format_bom_excel.py`. Collation lives in `_collate_rows` /
`_process`. Lead time is read from the **Part** first (a "Lead Time (days)" part
parameter, or a `lead_time: 14` note tag), then the supplier.

## Common problems and fixes

- **Export still has IPN / no colours** -> the user opened the raw file from
  InvenTree's Export button, or the plugin was not reinstalled. Use the
  part-page Download button / the download URL, and confirm the installed
  VERSION matches the repo.
- **"Failed to load module .../static/plugins/.../panel.js"** -> the panel
  `source` must be `/plugin/collated-bom-exporter/panel.js` (served by
  `serve_panel_js`), NOT a `/static/` path. Confirm "Enable URL integration" is
  on and hard-refresh.
- **Plugin will not load / MRO error** -> the `UserInterfaceMixin` fallback must
  be an empty class, never `object`.
- **Update did not take** -> use `--force-reinstall` and make sure VERSION was
  bumped; restart both server and worker.
- **Colours not visible** -> ensure solid `PatternFill`s are applied (not just
  conditional formatting).

## Lead time data

Lead time is per-PART (different items take different times). Record it as a
Part parameter named "Lead Time (days)" or a `lead_time: 14` tag in the part's
notes. Parts with none set are flagged amber with an "Add lead time to the Part"
reminder - this is expected, not an error.
