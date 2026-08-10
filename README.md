# Collated BOM Exporter (InvenTree plugin)

Adds a "Collated BOM Exporter" option to the standard InvenTree BOM export
dialog. It rolls every occurrence of a part into a single line with a true total
quantity for building one of the top-level assembly.

Built for Marcus and the workshop at Contour3D.

## What it does

- Walks the whole BOM tree and multiplies quantities down through it. A screw
  used four times inside a sub-assembly that is itself used twice comes out as
  eight.
- Collates identical parts across every sub-assembly into one line, so you never
  see the same part listed in several places.
- Optionally hides the sub-assembly lines and keeps only the components you pull
  from the shelf. Their quantities are still rolled into the parts.
- If stock data is included, each line shows current stock, the shortfall, and
  whether there is enough on hand. That tells you if the build is possible right
  now.
- If pricing is included, each line shows the supplier, supplier SKU, a unit
  price and a line total, with the order quantity rounded up to the supplier
  pack / minimum order size. Need 5, sold in packs of 10 -> order 10. A grand
  total sits at the bottom.
- Exports to any format InvenTree supports, including CSV and Excel.

## Columns

Part, IPN, Description, BOM Level, Total Quantity Required, then:

- Stock columns (when "Stock data" is ticked): Current Stock, Shortfall, Enough
  In Stock.
- Pricing columns (when "Pricing" is ticked): Supplier, Supplier SKU, Pack Size,
  Order Qty, Unit Price, Line Total.

Followed by BOM Lines and Reference. With pricing on, a TOTAL row is added at the
bottom.

## Where the pack size and price come from

- **Pack size** is read from the part's supplier records: the native pack
  quantity first, then the supplier order multiple. If neither is set it
  defaults to 1 (round up to the next whole unit). To get the "packs of 10"
  behaviour, set the pack quantity or order multiple on the relevant supplier
  part in InvenTree.
- **Unit price** uses InvenTree's own computed BOM pricing (minimum), falling
  back to the cheapest supplier price break. Parts with no price recorded leave
  the price and line total blank so you can spot the gap.
- **Order Qty** is the shortfall (when stock is known) or the full requirement,
  rounded up to the pack size. The line total is Unit Price x Order Qty.

## Requirements

- InvenTree 0.17.0 or newer. The data export plugin framework this relies on was
  added in that release. On older versions the plugin will not load.
- Plugins enabled on the server (`INVENTREE_PLUGINS_ENABLED=True`, or the
  "Enable plugins" server setting).

## Install

There are two ways in. Pick whichever suits how the server is run.

### Option A: single file (quickest)

1. Copy `collated_bom_exporter.py` into the server's plugin directory (the path
   set by `INVENTREE_PLUGIN_DIR`, often `.../inventree-data/plugins/`).
2. In InvenTree, go to Settings > Plugins, reload the plugin list, find
   "Collated BOM Exporter" and enable it.
3. Restart the server if it asks you to.

### Option B: pip package (tidier, survives upgrades)

From this folder on the server (or point pip at the git repo):

```bash
pip install .
```

Then reload and enable it under Settings > Plugins, same as above.

## Use it

1. Open the assembly (for example the 3D printer) and go to its BOM tab.
2. Click Export.
3. In the dialog, choose **Collated BOM Exporter** as the exporter (it sits
   alongside the default "BOM Exporter").
4. Set the options:
   - **Components only**: on to hide sub-assembly lines, off to keep them.
   - **Levels**: 0 for the full explosion, or a number to stop at a depth.
   - **Stock data**: on to include the current stock and shortfall columns.
   - **Pricing**: on to include supplier, order quantity, unit price and line
     total, plus the grand total row.
   - **Round up to pack size**: on to round the order quantity up to the
     supplier pack / minimum order size.
5. Pick CSV or Excel and export.

## A note on the standalone tool

There is also a small standalone web tool
(`inventree-collated-bom-collator`) that does the same collation from an exported
CSV and produces a branded PDF. The plugin is the one-click path for everyday
use. The web tool is handy when you want the tidy PDF, since InvenTree data
exports do not produce PDF directly.
