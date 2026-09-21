# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    multi_unit_scan_ids = fields.One2many(
        'multi.unit.barcode.scan', 'picking_id', string='Packaging Scans', copy=False,
    )
    multi_unit_scan_count = fields.Integer(
        string='Packaging Scan Count', compute='_compute_multi_unit_scan_status',
    )
    multi_unit_scan_status = fields.Selection([
        ('not_scanned', 'Not Scanned'),
        ('partial', 'Partially Scanned'),
        ('matched', 'Matched'),
        ('discrepancy', 'Discrepancy'),
    ], string='Scan Status', compute='_compute_multi_unit_scan_status')
    multi_unit_scanned_quantity = fields.Float(
        string='Scanned Stock Units', compute='_compute_multi_unit_scan_status',
        digits='Product Unit',
    )
    multi_unit_discrepancy_message = fields.Text(
        string='Packaging Discrepancy', compute='_compute_multi_unit_scan_status',
    )

    @api.depends('multi_unit_scan_ids', 'multi_unit_scan_ids.status', 'multi_unit_scan_ids.scanned_quantity', 'move_ids', 'move_ids.product_uom_qty', 'move_ids.product_uom', 'move_ids.state')
    def _compute_multi_unit_scan_status(self):
        for picking in self:
            scans = picking.multi_unit_scan_ids
            picking.multi_unit_scan_count = len(scans)
            picking.multi_unit_scanned_quantity = sum(
                scan.scanned_quantity for scan in scans if scan.status in ('matched', 'partial')
            )
            if not scans:
                picking.multi_unit_scan_status = 'not_scanned'
                picking.multi_unit_discrepancy_message = False
                continue

            messages = scans.filtered(lambda scan: scan.status in ('unknown', 'discrepancy')).mapped('message')
            has_hard_discrepancy = bool(messages)
            expected_by_product = defaultdict(float)
            scanned_by_product = defaultdict(float)
            for move in picking.move_ids.filtered(lambda move: move.state != 'cancel'):
                expected_by_product[move.product_id.id] += move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, round=False,
                )
            for scan in scans.filtered(lambda scan: scan.product_id and scan.status in ('matched', 'partial')):
                scanned_by_product[scan.product_id.id] += scan.scanned_quantity

            for product_id, scanned_qty in scanned_by_product.items():
                expected_qty = expected_by_product.get(product_id, 0.0)
                product = self.env['product.product'].browse(product_id)
                if float_compare(scanned_qty, expected_qty, precision_rounding=product.uom_id.rounding) > 0:
                    has_hard_discrepancy = True
                    messages.append(_('%(product)s is over-scanned: %(scanned)s scanned vs %(expected)s expected.',
                                      product=product.display_name, scanned=scanned_qty, expected=expected_qty))
            for product_id, expected_qty in expected_by_product.items():
                scanned_qty = scanned_by_product.get(product_id, 0.0)
                if scanned_qty and float_compare(
                    scanned_qty, expected_qty,
                    precision_rounding=self.env['product.product'].browse(product_id).uom_id.rounding,
                ) < 0:
                    product = self.env['product.product'].browse(product_id)
                    messages.append(_('%(product)s is short: %(scanned)s scanned vs %(expected)s expected.',
                                      product=product.display_name, scanned=scanned_qty, expected=expected_qty))

            picking.multi_unit_discrepancy_message = '\n'.join(dict.fromkeys(messages)) or False
            if has_hard_discrepancy:
                picking.multi_unit_scan_status = 'discrepancy'
            elif all(
                float_compare(
                    scanned_by_product.get(product_id, 0.0), expected_qty,
                    precision_rounding=self.env['product.product'].browse(product_id).uom_id.rounding,
                ) == 0
                for product_id, expected_qty in expected_by_product.items()
            ):
                picking.multi_unit_scan_status = 'matched'
            else:
                picking.multi_unit_scan_status = 'partial'

    def action_open_multi_unit_barcode_scan_wizard(self):
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            raise UserError(_('A completed or cancelled transfer cannot be scanned.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scan Packaging Barcode'),
            'res_model': 'multi.unit.barcode.scan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
                'default_scan_quantity': 1.0,
            },
        }

    def _apply_multi_unit_barcode(self, barcode, package_count=1.0):
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            raise UserError(_('A completed or cancelled transfer cannot be scanned.'))
        if package_count <= 0:
            raise UserError(_('The number of packages must be greater than zero.'))

        resolution = self.env['product.product'].resolve_multi_unit_barcode(barcode)
        product = resolution.get('product')
        base_quantity = resolution.get('base_quantity', 0.0) * package_count
        if not product:
            self.env['multi.unit.barcode.scan'].create({
                'picking_id': self.id,
                'barcode': barcode or '',
                'package_count': package_count,
                'scanned_quantity': 0.0,
                'status': 'unknown',
                'message': resolution['message'],
            })
            return {'status': 'unknown', 'message': resolution['message']}

        moves = self.move_ids.filtered(
            lambda move: move.product_id == product and move.state != 'cancel'
        )
        if not moves:
            message = _('%(product)s is not part of transfer %(transfer)s.',
                         product=product.display_name, transfer=self.display_name)
            self.env['multi.unit.barcode.scan'].create({
                'picking_id': self.id,
                'barcode': barcode,
                'product_id': product.id,
                'uom_id': resolution['uom_id'],
                'packaging_id': resolution.get('packaging_id') or False,
                'packaging_level': resolution.get('packaging_level'),
                'package_count': package_count,
                'scanned_quantity': base_quantity,
                'status': 'discrepancy',
                'message': message,
            })
            return {'status': 'discrepancy', 'message': message}

        expected_quantity = sum(
            move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id, round=False)
            for move in moves
        )
        already_scanned = sum(
            scan.scanned_quantity for scan in self.multi_unit_scan_ids
            if scan.product_id == product and scan.status in ('matched', 'partial')
        )
        if float_compare(
            already_scanned + base_quantity, expected_quantity,
            precision_rounding=product.uom_id.rounding,
        ) > 0:
            message = _(
                '%(product)s would be over-scanned: %(new_total)s stock units scanned vs %(expected)s expected.',
                product=product.display_name,
                new_total=already_scanned + base_quantity,
                expected=expected_quantity,
            )
            status = 'discrepancy'
        else:
            remaining = base_quantity
            for move in moves.sorted('id'):
                move_done = move.product_uom._compute_quantity(move.quantity, product.uom_id, round=False)
                move_expected = move.product_uom._compute_quantity(move.product_uom_qty, product.uom_id, round=False)
                increment = min(remaining, max(move_expected - move_done, 0.0))
                if product.uom_id.compare(increment, 0.0) > 0:
                    move._set_quantity_done(
                        move.quantity + product.uom_id._compute_quantity(increment, move.product_uom, round=False)
                    )
                    move.move_line_ids.filtered(lambda line: not line.picked).picked = True
                    remaining -= increment
                if product.uom_id.is_zero(remaining):
                    break
            status = 'matched'
            message = _(
                '%(product)s: %(packages)s package(s) applied as %(quantity)s %(uom)s.',
                product=product.display_name,
                packages=package_count,
                quantity=base_quantity,
                uom=product.uom_id.name,
            )

        self.env['multi.unit.barcode.scan'].create({
            'picking_id': self.id,
            'barcode': barcode,
            'product_id': product.id,
            'uom_id': resolution['uom_id'],
            'packaging_id': resolution.get('packaging_id') or False,
            'packaging_level': resolution.get('packaging_level'),
            'package_count': package_count,
            'scanned_quantity': base_quantity,
            'status': status,
            'message': message,
        })
        return {
            'status': status,
            'message': message,
            'product_id': product.id,
            'scanned_quantity': base_quantity,
        }

    def button_validate(self):
        incoming_with_scan_issue = self.filtered(
            lambda picking: picking.picking_type_code == 'incoming'
            and picking.multi_unit_scan_count
            and picking.multi_unit_scan_status != 'matched'
        )
        if incoming_with_scan_issue:
            details = '\n'.join(
                '%s: %s' % (picking.display_name, picking.multi_unit_discrepancy_message or _('all expected products have not been scanned'))
                for picking in incoming_with_scan_issue
            )
            raise UserError(_(
                'Resolve the multi-unit barcode discrepancy before validating the receipt:\n%s', details,
            ))
        return super().button_validate()
