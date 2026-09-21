# -*- coding: utf-8 -*-
{
    'name': 'Multi-Unit Packaging & Barcode Resolver',
    'summary': 'Resolve unit, inner-pack, and master-pack barcodes during stock operations',
    'description': """
Multi-Unit Packaging & Barcode Resolver

Uses Odoo 19's unified UoM and product.uom packaging barcode models to let
warehouse users scan individual units, inner boxes, and master pallets against
the same product. Scans are converted into the product stock UoM, applied to
incoming receipts and outgoing/internal transfers, and checked for quantity
mismatches before an incoming receipt is validated.
    """,
    'author': 'SARANG T',
    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'icon': 'multi_unit_barcode_resolver/static/description/icon.svg',
    'depends': ['stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_uom_views.xml',
        'views/stock_picking_views.xml',
        'views/multi_unit_barcode_scan_views.xml',
    ],
    'demo': [],
    'application': False,
    'installable': True,
    'auto_install': False,
}
