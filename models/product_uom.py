# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductUom(models.Model):
    _inherit = 'product.uom'

    packaging_level = fields.Selection([
        ('inner', 'Inner Box'),
        ('master', 'Master Carton / Pallet'),
    ], string='Packaging Level', default='inner', required=True,
       help='Identifies the physical packaging represented by this barcode.')
    units_per_scan = fields.Float(
        string='Stock Units per Scan', compute='_compute_units_per_scan',
        digits='Product Unit', readonly=True,
        help='Quantity converted into the product stock UoM when this barcode is scanned.',
    )

    @api.depends('uom_id', 'product_id', 'product_id.uom_id')
    def _compute_units_per_scan(self):
        for packaging in self:
            if packaging.product_id and packaging.uom_id and packaging.product_id.uom_id:
                packaging.units_per_scan = packaging.uom_id._compute_quantity(
                    1.0, packaging.product_id.uom_id, rounding_method='HALF-UP',
                )
            else:
                packaging.units_per_scan = 0.0

    @api.constrains('packaging_level')
    def _check_packaging_level(self):
        if any(packaging.packaging_level not in ('inner', 'master') for packaging in self):
            raise ValidationError(_('A packaging barcode must be an inner box or a master carton/pallet.'))
