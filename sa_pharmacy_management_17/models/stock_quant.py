# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    lot_expiration_date = fields.Datetime(
        related='lot_id.expiration_date', store=True, index=True,
        string='Batch Expiry')

    @api.model
    def _get_removal_strategy_domain_order(self, domain, removal_strategy, qty):
        """Add FEFO (First-Expiry-First-Out) ordering (Odoo 17).

        Native Odoo ships FIFO, LIFO, Closest and Least-Packages strategies
        only. Pharmacies legally and operationally require First-Expiry-First-
        Out so the batch closest to its expiry date is always picked first.
        NULL expiry dates sort last (PostgreSQL default for ASC).
        """
        if removal_strategy == 'fefo':
            return domain, 'lot_expiration_date asc, in_date asc, id'
        return super()._get_removal_strategy_domain_order(
            domain, removal_strategy, qty)

    def _get_removal_strategy_sort_key(self, removal_strategy):
        if removal_strategy == 'fefo':
            return (lambda q: (q.lot_expiration_date or q.in_date, q.id)), False
        return super()._get_removal_strategy_sort_key(removal_strategy)
