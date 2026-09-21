# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MultiUnitBarcodeScanWizard(models.TransientModel):
    _name = 'multi.unit.barcode.scan.wizard'
    _description = 'Multi-Unit Barcode Scan Wizard'

    picking_id = fields.Many2one(
        'stock.picking', string='Transfer', required=True, readonly=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    barcode = fields.Char(
        string='Barcode', required=True,
        help='Scan the individual unit, inner-box, or master-pallet barcode.',
    )
    scan_quantity = fields.Float(
        string='Number of Packages', default=1.0, required=True,
        help='Use a value greater than one when scanning identical packages.',
    )
    last_result = fields.Text(string='Last Result', readonly=True)
    last_result_type = fields.Selection([
        ('matched', 'Matched'),
        ('partial', 'Partially Applied'),
        ('discrepancy', 'Discrepancy'),
        ('unknown', 'Unknown Barcode'),
    ], string='Result Type', readonly=True)

    def action_scan(self):
        self.ensure_one()
        result = self.picking_id._apply_multi_unit_barcode(
            self.barcode, self.scan_quantity,
        )
        self.write({
            'last_result': result['message'],
            'last_result_type': result['status'],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scan Packaging Barcode'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
