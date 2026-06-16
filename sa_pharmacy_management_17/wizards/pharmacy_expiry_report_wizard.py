# -*- coding: utf-8 -*-
from odoo import fields, models


class PharmacyExpiryReportWizard(models.TransientModel):
    _name = 'pharmacy.expiry.report.wizard'
    _description = 'Near-Expiry Stock Report Wizard'

    horizon_days = fields.Integer(
        string='Horizon (days)', default=90, required=True,
        help="List medicine batches expiring within this many days.")
    include_expired = fields.Boolean(
        string='Include Already Expired', default=True)

    def action_open_report(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        lots = self.env['stock.lot'].search([
            ('product_id.is_medicine', '=', True),
            ('expiration_date', '!=', False),
        ])
        result = lots.filtered(
            lambda l: l.on_hand_qty > 0
            and l.days_to_expiry <= self.horizon_days
            and (self.include_expired or l.days_to_expiry >= 0))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Near-Expiry Batches',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', result.ids)],
            'context': {'search_default_group_expiry': 1},
        }
