# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMultiUnitBarcodeResolver(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.product'].create({
            'name': 'Barcode Resolver Test Product',
            'is_storable': True,
            'barcode': '8900000000011',
            'uom_id': cls.unit.id,
        })
        cls.inner_uom = cls.env['uom.uom'].create({
            'name': 'Test Inner Box (12)',
            'relative_factor': 12,
            'relative_uom_id': cls.unit.id,
        })
        cls.master_uom = cls.env['uom.uom'].create({
            'name': 'Test Master Pallet (144)',
            'relative_factor': 144,
            'relative_uom_id': cls.unit.id,
        })
        cls.product.write({'uom_ids': [Command.link(cls.inner_uom.id), Command.link(cls.master_uom.id)]})
        cls.inner_pack = cls.env['product.uom'].create({
            'product_id': cls.product.id,
            'uom_id': cls.inner_uom.id,
            'barcode': '8900000000127',
            'packaging_level': 'inner',
        })
        cls.master_pack = cls.env['product.uom'].create({
            'product_id': cls.product.id,
            'uom_id': cls.master_uom.id,
            'barcode': '8900000001447',
            'packaging_level': 'master',
        })

    def _make_receipt(self, demand=24):
        picking_type = self.env.ref('stock.picking_type_in')
        supplier = self.env.ref('stock.stock_location_suppliers')
        stock = self.env.ref('stock.stock_location_stock')
        return self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': supplier.id,
            'location_dest_id': stock.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': demand,
                'product_uom': self.unit.id,
                'location_id': supplier.id,
                'location_dest_id': stock.id,
            })],
        })

    def test_resolves_product_and_packaging_barcodes(self):
        unit_result = self.env['product.product'].resolve_multi_unit_barcode('8900000000011')
        self.assertEqual(unit_result['product'], self.product)
        self.assertEqual(unit_result['base_quantity'], 1.0)
        self.assertEqual(unit_result['packaging_level'], 'unit')

        inner_result = self.env['product.product'].resolve_multi_unit_barcode('8900000000127')
        self.assertEqual(inner_result['product'], self.product)
        self.assertEqual(inner_result['packaging'], self.inner_pack)
        self.assertEqual(inner_result['base_quantity'], 12.0)
        self.assertEqual(inner_result['packaging_level'], 'inner')

        master_result = self.env['product.product'].resolve_multi_unit_barcode('8900000001447')
        self.assertEqual(master_result['base_quantity'], 144.0)
        self.assertEqual(master_result['packaging_level'], 'master')

    def test_scan_converts_package_to_stock_units(self):
        receipt = self._make_receipt(demand=24)
        result = receipt._apply_multi_unit_barcode('8900000000127')
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(receipt.move_ids.quantity, 12.0)
        self.assertEqual(receipt.multi_unit_scan_count, 1)
        self.assertEqual(receipt.multi_unit_scan_status, 'partial')

        receipt._apply_multi_unit_barcode('8900000000127')
        self.assertEqual(receipt.move_ids.quantity, 24.0)
        self.assertEqual(receipt.multi_unit_scan_status, 'matched')

    def test_over_scan_is_logged_without_changing_done_quantity(self):
        receipt = self._make_receipt(demand=24)
        receipt._apply_multi_unit_barcode('8900000000127')
        result = receipt._apply_multi_unit_barcode('8900000001447')
        self.assertEqual(result['status'], 'discrepancy')
        self.assertEqual(receipt.move_ids.quantity, 12.0)
        self.assertEqual(receipt.multi_unit_scan_status, 'discrepancy')

    def test_incoming_validation_blocks_scan_discrepancy(self):
        receipt = self._make_receipt(demand=24)
        receipt._apply_multi_unit_barcode('8900000000127')
        with self.assertRaises(UserError):
            receipt.button_validate()
