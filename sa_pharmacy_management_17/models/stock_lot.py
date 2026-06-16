# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    days_to_expiry = fields.Integer(
        string='Days to Expiry', compute='_compute_expiry_state',
        store=True)
    expiry_state = fields.Selection([
        ('none', 'No Expiry'),
        ('expired', 'Expired'),
        ('critical', 'Critical (≤ 30 days)'),
        ('warning', 'Near Expiry (≤ 90 days)'),
        ('ok', 'Valid'),
    ], string='Expiry Status', compute='_compute_expiry_state',
        store=True, default='none')
    on_hand_qty = fields.Float(
        string='On Hand', compute='_compute_on_hand_qty',
        search='_search_on_hand_qty')

    @api.depends('expiration_date')
    def _compute_expiry_state(self):
        today = fields.Date.context_today(self)
        critical = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.critical_days', default='30')
        warning = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.warning_days', default='90')
        try:
            critical_days = int(critical)
            warning_days = int(warning)
        except (TypeError, ValueError):
            critical_days, warning_days = 30, 90
        for lot in self:
            if not lot.expiration_date:
                lot.days_to_expiry = 0
                lot.expiry_state = 'none'
                continue
            delta = (lot.expiration_date.date() - today).days
            lot.days_to_expiry = delta
            if delta < 0:
                lot.expiry_state = 'expired'
            elif delta <= critical_days:
                lot.expiry_state = 'critical'
            elif delta <= warning_days:
                lot.expiry_state = 'warning'
            else:
                lot.expiry_state = 'ok'

    def _compute_on_hand_qty(self):
        groups = self.env['stock.quant']._read_group(
            [('lot_id', 'in', self.ids),
             ('location_id.usage', '=', 'internal')],
            ['lot_id'], ['quantity:sum'])
        mapped = {lot.id: qty for lot, qty in groups}
        for lot in self:
            lot.on_hand_qty = mapped.get(lot.id, 0.0)

    @api.model
    def _search_on_hand_qty(self, operator, value):
        comparators = {
            '>': lambda q: q > value, '>=': lambda q: q >= value,
            '<': lambda q: q < value, '<=': lambda q: q <= value,
            '=': lambda q: q == value, '!=': lambda q: q != value,
        }
        if operator not in comparators:
            return []
        groups = self.env['stock.quant']._read_group(
            [('location_id.usage', '=', 'internal'), ('lot_id', '!=', False)],
            ['lot_id'], ['quantity:sum'])
        compare = comparators[operator]
        matched = [lot.id for lot, qty in groups if compare(qty)]
        return [('id', 'in', matched)]

    @api.model
    def _cron_check_expiry(self):
        """Scan medicine lots, flag near-expiry stock and notify managers."""
        today = fields.Date.context_today(self)
        warning = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.warning_days', default='90')
        try:
            warning_days = int(warning)
        except (TypeError, ValueError):
            warning_days = 90
        lots = self.search([
            ('product_id.is_medicine', '=', True),
            ('expiration_date', '!=', False),
        ])
        lots._compute_expiry_state()
        flagged = lots.filtered(
            lambda l: l.on_hand_qty > 0 and l.days_to_expiry <= warning_days)
        group = self.env.ref(
            'sa_pharmacy_management.group_pharmacy_manager',
            raise_if_not_found=False)
        if not group or not flagged:
            return
        template = self.env.ref(
            'sa_pharmacy_management.mail_template_near_expiry',
            raise_if_not_found=False)
        if template:
            for user in group.users:
                if user.partner_id.email:
                    template.with_context(
                        flagged_lots=flagged,
                        scan_date=today,
                    ).send_mail(user.id, force_send=False)
