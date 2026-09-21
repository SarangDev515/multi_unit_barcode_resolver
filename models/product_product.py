# -*- coding: utf-8 -*-
from odoo import _, api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def resolve_multi_unit_barcode(self, barcode, company=None):
        """Resolve a unit or Odoo 19 product.uom packaging barcode.

        The returned quantity is always expressed in the product's stock UoM,
        which makes it safe for stock.move and stock.move.line operations.
        """
        barcode = (barcode or '').strip()
        if not barcode:
            return {'status': 'unknown', 'message': _('A barcode is required.')}

        company = company or self.env.company
        company_domain = [('company_id', 'in', [False, company.id])]
        product = self.search(
            [('barcode', '=', barcode)] + company_domain,
            order='company_id desc, id', limit=1,
        )
        if product:
            return {
                'status': 'matched',
                'source': 'unit',
                'barcode': barcode,
                'product': product,
                'product_id': product.id,
                'uom': product.uom_id,
                'uom_id': product.uom_id.id,
                'packaging': self.env['product.uom'],
                'packaging_id': False,
                'packaging_level': 'unit',
                'quantity': 1.0,
                'base_quantity': 1.0,
                'message': _('%(product)s: 1 %(uom)s', product=product.display_name, uom=product.uom_id.name),
            }

        packaging = self.env['product.uom'].search(
            [('barcode', '=', barcode)] + company_domain,
            order='company_id desc, id', limit=1,
        )
        if not packaging:
            return {
                'status': 'unknown',
                'barcode': barcode,
                'message': _('No product or packaging uses barcode %s.', barcode),
            }

        product = packaging.product_id
        base_quantity = packaging.uom_id._compute_quantity(
            1.0, product.uom_id, rounding_method='HALF-UP',
        )
        level_label = dict(self.env['product.uom']._fields['packaging_level'].selection).get(
            packaging.packaging_level, packaging.packaging_level,
        )
        return {
            'status': 'matched',
            'source': 'packaging',
            'barcode': barcode,
            'product': product,
            'product_id': product.id,
            'uom': packaging.uom_id,
            'uom_id': packaging.uom_id.id,
            'packaging': packaging,
            'packaging_id': packaging.id,
            'packaging_level': packaging.packaging_level,
            'quantity': 1.0,
            'base_quantity': base_quantity,
            'message': _(
                '%(product)s: 1 %(level)s = %(quantity)s %(uom)s',
                product=product.display_name,
                level=level_label,
                quantity=base_quantity,
                uom=product.uom_id.name,
            ),
        }
