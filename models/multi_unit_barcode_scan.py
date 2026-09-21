# -*- coding: utf-8 -*-
from odoo import fields, models


class MultiUnitBarcodeScan(models.Model):
    _name = 'multi.unit.barcode.scan'
    _description = 'Multi-Unit Barcode Scan'
    _order = 'scanned_at desc, id desc'

    picking_id = fields.Many2one('stock.picking', string='Transfer', required=True, ondelete='cascade', index=True)
    barcode = fields.Char(string='Scanned Barcode', required=True, index=True)
    product_id = fields.Many2one('product.product', string='Product', index=True)
    uom_id = fields.Many2one('uom.uom', string='Scan UoM')
    packaging_id = fields.Many2one('product.uom', string='Packaging Barcode')
    packaging_level = fields.Selection([
        ('unit', 'Single Unit'),
        ('inner', 'Inner Box'),
        ('master', 'Master Carton / Pallet'),
    ], string='Packaging Level')
    package_count = fields.Float(string='Packages Scanned', default=1.0, required=True)
    scanned_quantity = fields.Float(string='Stock Units', digits='Product Unit', required=True)
    status = fields.Selection([
        ('matched', 'Matched'),
        ('partial', 'Partially Applied'),
        ('discrepancy', 'Discrepancy'),
        ('unknown', 'Unknown Barcode'),
    ], required=True, default='matched', index=True)
    message = fields.Text(string='Result')
    scanned_by = fields.Many2one('res.users', string='Scanned By', required=True, default=lambda self: self.env.user)
    scanned_at = fields.Datetime(string='Scanned At', required=True, default=fields.Datetime.now, index=True)
