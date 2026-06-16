# -*- coding: utf-8 -*-
from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    lot_expiration_date = fields.Datetime(
        related='lot_id.expiration_date', store=True, index=True,
        string='Batch Expiry')

    def _get_removal_strategy_order(self, removal_strategy):
        """Add FEFO (First-Expiry-First-Out) removal ordering (Odoo 18).

        Native Odoo ships FIFO, LIFO, Closest and Least-Packages strategies
        only. Pharmacies legally and operationally require First-Expiry-First-
        Out so the batch closest to its expiry date is always picked first.
        NULL expiry dates sort last so non-tracked / undated stock never jumps
        ahead of a dated batch.
        """
        if removal_strategy == 'fefo':
            return 'lot_expiration_date ASC NULLS LAST, in_date ASC, id'
        return super()._get_removal_strategy_order(removal_strategy)
