"""Collated BOM exporter plugin for InvenTree.

Adds a "Collated BOM Exporter" option to the standard BOM export dialog. Where
the built-in exporter lists the same part once per sub-assembly it appears in,
this one rolls every occurrence of a part into a single line with a true total
quantity for building one of the top-level assembly. Quantities are multiplied
down through the BOM tree, so a screw used four times inside a sub-assembly that
is itself used twice comes out as eight.

If stock data is included, each line also shows current stock, the shortfall and
whether there is enough on hand. If pricing is included, each line shows the
supplier, a unit price and a line total, with the order quantity rounded up to
the supplier pack / minimum order size (need 5, sold in packs of 10 -> order
10). A grand total sits at the bottom.

Requires InvenTree 0.17.0 or newer (the data export plugin framework).
"""

from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import rest_framework.serializers as serializers

from InvenTree.helpers import normalize
from part.models import BomItem
from part.serializers import BomItemSerializer
from plugin import InvenTreePlugin
from plugin.mixins import DataExportMixin


ZERO = Decimal(0)
ONE = Decimal(1)


def _dec(value, default=ZERO):
    """Coerce anything to a Decimal without ever raising."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _round_up_to_pack(quantity, pack_size):
    """Round quantity up to the next whole multiple of pack_size.

    A pack_size of 10 with a need of 5 gives 10; a need of 11 gives 20. A
    pack_size of 1 (or missing) rounds up to the next whole unit.
    """
    quantity = _dec(quantity)
    pack_size = _dec(pack_size, ONE)

    if quantity <= ZERO:
        return ZERO
    if pack_size <= ZERO:
        pack_size = ONE

    packs = (quantity / pack_size).to_integral_value(rounding="ROUND_CEILING")
    return packs * pack_size


class CollatedBomOptionsSerializer(serializers.Serializer):
    """User-facing options shown in the BOM export dialog."""

    components_only = serializers.BooleanField(
        default=True,
        label=_('Components only'),
        help_text=_(
            'Exclude sub-assembly lines, keep only the parts you pull from the '
            'shelf. Sub-assembly quantities are still rolled into their parts.'
        ),
    )

    export_levels = serializers.IntegerField(
        default=0,
        label=_('Levels'),
        help_text=_('How many levels deep to explode. Zero means all levels.'),
        min_value=0,
    )

    export_stock_data = serializers.BooleanField(
        default=True,
        label=_('Stock data'),
        help_text=_('Include current stock, shortfall and a buildable flag.'),
    )

    export_pricing = serializers.BooleanField(
        default=True,
        label=_('Pricing'),
        help_text=_(
            'Include supplier, unit price, order quantity and line total, plus '
            'a grand total row.'
        ),
    )

    round_to_packs = serializers.BooleanField(
        default=True,
        label=_('Round up to pack size'),
        help_text=_(
            'Round the order quantity up to the supplier pack / minimum order '
            'size where it is recorded against the part.'
        ),
    )


class CollatedBomExporterPlugin(DataExportMixin, InvenTreePlugin):
    """Export a BOM with identical parts collated into one line each."""

    NAME = 'Collated BOM Exporter'
    SLUG = 'collated-bom-exporter'
    TITLE = _('Collated BOM Exporter')
    DESCRIPTION = _(
        'Exports a BOM with duplicate parts collated across sub-assemblies into '
        'a single line each, with true total quantities, a stock check and '
        'pack-rounded order pricing.'
    )
    VERSION = '0.2.0'
    AUTHOR = _('Contour3D')

    ExportOptionsSerializer = CollatedBomOptionsSerializer

    def supports_export(self, model_class: type, user, *args, **kwargs) -> bool:
        """Offer this exporter only for BOM data."""
        return (
            model_class == BomItem
            and kwargs.get('serializer_class') == BomItemSerializer
        )

    def generate_filename(self, model_class, export_format: str) -> str:
        """Name the output file."""
        date = timezone.now().date().isoformat()
        return f'InvenTree_Collated_BOM_{date}.{export_format}'

    def prefetch_queryset(self, queryset):
        """Reduce query count when walking the tree."""
        return queryset.prefetch_related('sub_part')

    def export_data(
        self, queryset, serializer_class, headers, context, output, **kwargs
    ):
        """Walk the BOM tree, collate by part, and return one row per part."""
        self.serializer_class = serializer_class

        # Cache the chosen options for use here and in update_headers.
        self.components_only = context.get('components_only', True)
        self.export_levels = context.get('export_levels', 0)
        self.export_stock_data = context.get('export_stock_data', True)
        self.export_pricing = context.get('export_pricing', True)
        self.round_to_packs = context.get('round_to_packs', True)

        # part id -> collated row
        self.collated: "OrderedDict[int, dict]" = OrderedDict()

        queryset = self.prefetch_queryset(queryset)
        for bom_item in queryset:
            self._process(bom_item, level=1, multiplier=ONE, **kwargs)

        rows = list(self.collated.values())
        grand_total = ZERO

        # Finalise derived fields now that totals are complete.
        for row in rows:
            total = _dec(row['_total'])
            row['total_quantity'] = normalize(total)
            row['bom_level'] = row['_level']

            available = row.get('_available')
            short = None
            if available is not None:
                short = total - _dec(available)
                if short < ZERO:
                    short = ZERO

            if self.export_stock_data:
                if available is None:
                    row['available_stock'] = ''
                    row['shortfall'] = ''
                    row['buildable'] = ''
                else:
                    row['available_stock'] = normalize(_dec(available))
                    row['shortfall'] = normalize(short) if short > ZERO else 0
                    row['buildable'] = _('No') if short > ZERO else _('Yes')

            if self.export_pricing:
                # Order the shortfall where we know stock, otherwise the whole
                # requirement. Round up to the pack size if asked.
                need = short if short is not None else total
                pack = _dec(row.get('_pack'), ONE) if self.round_to_packs else ONE
                order_qty = (
                    _round_up_to_pack(need, pack)
                    if self.round_to_packs
                    else need
                )

                unit_price = row.get('_unit_price')
                row['supplier'] = row.get('_supplier', '')
                row['supplier_sku'] = row.get('_sku', '')
                row['pack_size'] = normalize(pack)
                row['order_quantity'] = normalize(order_qty)

                if unit_price is not None:
                    line_total = _dec(unit_price) * _dec(order_qty)
                    grand_total += line_total
                    row['unit_price'] = normalize(_dec(unit_price))
                    row['line_total'] = normalize(line_total)
                else:
                    row['unit_price'] = ''
                    row['line_total'] = ''

            row['reference'] = ', '.join(sorted(r for r in row['_refs'] if r))

        # Buyable-first when we know stock, then by name; otherwise by name.
        if self.export_stock_data:
            rows.sort(
                key=lambda r: (
                    _dec(r.get('shortfall') or 0) <= ZERO,
                    str(r.get('part', '')).lower(),
                )
            )
        else:
            rows.sort(key=lambda r: str(r.get('part', '')).lower())

        # Strip the private working fields before returning.
        for row in rows:
            for key in ('_total', '_available', '_refs', '_level', '_pack',
                        '_unit_price', '_supplier', '_sku'):
                row.pop(key, None)

        # Grand total row at the bottom.
        if self.export_pricing:
            total_row = {key: '' for key in headers.keys()}
            total_row['part'] = str(_('TOTAL'))
            total_row['line_total'] = normalize(grand_total)
            rows.append(total_row)

        return rows

    def _process(
        self,
        bom_item: BomItem,
        level: int,
        multiplier: Decimal,
        **kwargs,
    ) -> None:
        """Recursively process one BOM item and its children."""
        part = bom_item.sub_part
        total = _dec(bom_item.quantity) * multiplier
        is_assembly = bool(part.assembly)

        include = not (self.components_only and is_assembly)
        if include:
            self._accumulate(bom_item, part, total, level)

        # Recurse into sub-assemblies unless we have hit the level limit.
        if is_assembly and (self.export_levels <= 0 or level < self.export_levels):
            sub_items = part.get_bom_items()
            sub_items = self.prefetch_queryset(sub_items)
            sub_items = BomItemSerializer.annotate_queryset(sub_items)
            for item in sub_items.all():
                self._process(
                    item,
                    level=level + 1,
                    multiplier=multiplier * _dec(bom_item.quantity),
                    **kwargs,
                )

    def _accumulate(self, bom_item: BomItem, part, total: Decimal, level: int) -> None:
        """Add this occurrence into the collated row for its part."""
        key = part.pk
        existing = self.collated.get(key)

        if existing:
            existing['_total'] += total
            existing['occurrences'] += 1
            existing['_level'] = min(existing['_level'], level)
            if bom_item.reference:
                existing['_refs'].add(bom_item.reference)
            return

        row: dict = {
            'part': part.name,
            'ipn': part.IPN or '',
            'description': part.description or '',
            'occurrences': 1,
            '_total': total,
            '_level': level,
            '_refs': {bom_item.reference} if bom_item.reference else set(),
        }

        # Pull stock and pricing from the BOM serializer once (InvenTree
        # annotates available_stock and pricing onto the queryset).
        if self.export_stock_data or self.export_pricing:
            data = self.serializer_class(bom_item, exporting=True).data

            if self.export_stock_data:
                available = data.get('available_stock')
                row['_available'] = available if available is not None else None

            if self.export_pricing:
                row['_unit_price'] = self._unit_price(data)
                supplier, sku, pack = self._supplier_info(part)
                row['_supplier'] = supplier
                row['_sku'] = sku
                row['_pack'] = pack

        self.collated[key] = row

    @staticmethod
    def _unit_price(serializer_data) -> "Decimal | None":
        """Per-unit price from InvenTree's computed BOM pricing.

        Uses the minimum price where available, falling back to the maximum.
        """
        for field in ('pricing_min', 'pricing_max'):
            value = serializer_data.get(field)
            if value is not None:
                price = _dec(value, default=None) if value is not None else None
                if price is not None and price > ZERO:
                    return price
        return None

    @staticmethod
    def _supplier_info(part):
        """Cheapest supplier name, SKU and pack / minimum order size for a part.

        Returns ('', '', 1) when no supplier is recorded, so the export never
        fails on an incompletely set up part.
        """
        try:
            supplier_parts = list(part.supplier_parts.all())
        except Exception:
            supplier_parts = []

        if not supplier_parts:
            return '', '', ONE

        best = None
        best_price = None
        for sp in supplier_parts:
            price = CollatedBomExporterPlugin._cheapest_price(sp)
            if price is None:
                continue
            if best_price is None or price < best_price:
                best_price = price
                best = sp

        # Fall back to the first supplier so the buyer still has a lead.
        if best is None:
            best = supplier_parts[0]

        supplier = getattr(best, 'supplier', None)
        name = getattr(supplier, 'name', '') or ''
        sku = getattr(best, 'SKU', '') or ''
        pack = CollatedBomExporterPlugin._pack_size(best)
        return name, sku, pack

    @staticmethod
    def _cheapest_price(supplier_part):
        """Lowest per-unit price across a supplier part's price breaks."""
        breaks = []
        for attr in ('pricebreaks', 'price_breaks'):
            manager = getattr(supplier_part, attr, None)
            if manager is not None:
                try:
                    breaks = list(manager.all())
                    break
                except Exception:
                    breaks = []

        pack = CollatedBomExporterPlugin._pack_size(supplier_part)
        pack = pack if pack > ZERO else ONE

        cheapest = None
        for pb in breaks:
            raw = getattr(pb, 'price', None)
            if raw is None:
                continue
            price = _dec(raw, default=None)
            if price is None:
                continue
            per_unit = price / pack
            if cheapest is None or per_unit < cheapest:
                cheapest = per_unit
        return cheapest

    @staticmethod
    def _pack_size(supplier_part):
        """Pack / minimum order multiple for a supplier part (defaults to 1)."""
        for attr in ('pack_quantity_native', 'multiple'):
            raw = getattr(supplier_part, attr, None)
            if raw is None:
                continue
            value = _dec(raw, default=None)
            if value is not None and value > ZERO:
                return value
        return ONE

    def update_headers(self, headers, context, **kwargs):
        """Replace the default columns with the collated column set."""
        columns: "OrderedDict[str, str]" = OrderedDict()
        columns['part'] = _('Part')
        columns['ipn'] = _('IPN')
        columns['description'] = _('Description')
        columns['bom_level'] = _('BOM Level')
        columns['total_quantity'] = _('Total Quantity Required')

        if self.export_stock_data:
            columns['available_stock'] = _('Current Stock')
            columns['shortfall'] = _('Shortfall')
            columns['buildable'] = _('Enough In Stock')

        if self.export_pricing:
            columns['supplier'] = _('Supplier')
            columns['supplier_sku'] = _('Supplier SKU')
            columns['pack_size'] = _('Pack Size')
            columns['order_quantity'] = _('Order Qty')
            columns['unit_price'] = _('Unit Price')
            columns['line_total'] = _('Line Total')

        columns['occurrences'] = _('BOM Lines')
        columns['reference'] = _('Reference')
        return columns
