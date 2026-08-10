---
name: collated-bom-plugin
description: Maintain, fix, reinstall or change Contour3D's InvenTree "Collated BOM Exporter" plugin (repo cwhyte-c3d/BOMCollator, instance inventree.contour3d.au). Use whenever the collated BOM export/download breaks, looks wrong (missing colours, IPN showing, panel error), needs a new column or tweak, or needs updating/reinstalling on InvenTree. Trigger on mentions of the collated BOM, the BOM exporter plugin, the "Collated BOM" tab, or the BOMCollator repo.
---

# Collated BOM Exporter - maintain & fix

An InvenTree plugin for Contour3D. Repo: **https://github.com/cwhyte-c3d/BOMCollator**
(single module `collated_bom_exporter.py`, plus `pyproject.toml`, a standalone
`format_bom_excel.py`, and `FIXING_THIS_PLUGIN.md`). InvenTree instance:
**https://inventree.contour3d.au**. Charlotte can install plugins and restart the
server herself; `git`/push works from her machine (user cwhyte-c3d), `gh` CLI is
not installed.

## What it does

Turns a multi-level BOM into one flat, collated shopping list: duplicate parts
across sub-assemblies rolled into one row with the true total; stock comparison
(current stock, shortfall); pack-rounded order quantities; supplier + pricing
with a grand total; longest-lead-time total; lead time -> estimated delivery.
Columns: Ordered, Part, BOM Level, Total Quantity Required, Current Stock,
Shortfall, Enough In Stock, Supplier, Order Qty, Unit Price, Line Total, Lead
Time (days), Est. Delivery, Recurrences, Description. IPN and Reference dropped.

## Three output paths (critical)

1. **InvenTree Export dialog** (DataExportMixin) - plain data ONLY. Exports use
   tablib, which cannot style cells. The Export button can NEVER produce
   colours/checkboxes. Hard InvenTree limit, not a bug - never try to add colour
   here.
2. **Plugin styled download** (UrlsMixin) at
   `/plugin/collated-bom-exporter/download/<part_id>/` - builds the fully styled
   `.xlsx` with openpyxl (already on any InvenTree). Colours, checkbox, est.
   delivery, totals. Everyday path.
3. **Part-page panel** (UserInterfaceMixin) - a "Collated BOM" tab on each
   assembly part with a Download button. Serves JS from
   `/plugin/collated-bom-exporter/panel.js`.

## Golden rules

- **Pushing to GitHub does NOT update the running InvenTree.** Always reinstall
  + restart after any change.
- **Use SOLID PatternFill for colours**, not conditional formatting alone (CF
  did not render in Charlotte's Excel). Keep a CF rule only as a bonus.
- **Bump `VERSION`** on `CollatedBomExporterPlugin` every change or pip skips it.
- The Export dialog cannot be styled - direct users to the download / part-page
  button for colour.

## Install / update on InvenTree

Run in the InvenTree backend (venv or inside the Docker container):

```bash
pip install --upgrade --force-reinstall "git+https://github.com/cwhyte-c3d/BOMCollator.git"
```

Then: restart server AND worker; confirm the new VERSION in Settings -> Plugins;
enable **"Enable URL integration"** (download) and **"Enable interface
integration"** (part-page tab); hard-refresh the browser (Ctrl+F5).

## Make a change

1. Edit `collated_bom_exporter.py` (server plugin) and/or `format_bom_excel.py`
   (standalone formatter - keep them consistent).
2. **Bump `VERSION`.**
3. `python -m py_compile` both, commit, push.
4. Reinstall + restart on InvenTree.

Styling lives in `_build_workbook_bytes` (download) and mirrors
`format_bom_excel.py`. Collation lives in `_collate_rows` / `_process`. Lead time
is read from the PART first (a "Lead Time (days)" part parameter, or a
`lead_time: 14` note tag), then the supplier.

## Common problems -> fixes

- **Export still shows IPN / no colours** -> user opened InvenTree's raw Export
  file, or plugin not reinstalled. Use the part-page Download button / download
  URL; confirm installed VERSION matches repo.
- **"Failed to load module .../static/plugins/.../panel.js"** -> panel `source`
  must be `/plugin/collated-bom-exporter/panel.js` (served by `serve_panel_js`),
  not a `/static/` path. Ensure URL integration on; hard-refresh.
- **Plugin will not load / MRO error** -> the `UserInterfaceMixin` fallback must
  be an empty class, never `object`.
- **Update did not take** -> `--force-reinstall` + VERSION bump; restart server
  and worker both.
- **Colours not visible** -> apply solid PatternFills, not just conditional
  formatting.
- **Real Excel checkboxes** -> not possible via openpyxl; the Ordered column
  uses a ☐/☑ dropdown that reads as a checkbox.

## Lead time data

Per-PART (different items take different times). Record as a Part parameter
"Lead Time (days)" or a `lead_time: 14` note tag. Parts with none set are
flagged amber with an "Add lead time to the Part" reminder - expected, not an
error.
