# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PharmacyReorderWizard(models.TransientModel):
    """AI demand-forecast & smart reorder planner."""

    _name = 'pharmacy.reorder.wizard'
    _description = 'AI Smart Reorder Planner'

    horizon_days = fields.Integer(string='Plan Horizon (days)', default=30)
    history_days = fields.Integer(string='Sales History (days)', default=90)
    only_shortfall = fields.Boolean(
        string='Only Items Needing Reorder', default=True)
    line_ids = fields.One2many(
        'pharmacy.reorder.line', 'wizard_id', string='Forecast')

    def action_compute(self):
        self.ensure_one()
        service = self.env['pharmacy.ai.service']
        medicines = self.env['product.product'].search([
            ('is_medicine', '=', True),
        ])
        self.line_ids.unlink()
        rows = []
        for product in medicines:
            data = service.forecast_reorder(
                product, self.horizon_days, self.history_days)
            if self.only_shortfall and data['suggested_qty'] <= 0:
                continue
            rows.append((0, 0, {
                'product_id': product.id,
                'daily_velocity': data['daily_velocity'],
                'projected_demand': data['projected_demand'],
                'on_hand': data['on_hand'],
                'near_expiry': data['near_expiry'],
                'suggested_qty': data['suggested_qty'],
            }))
        self.line_ids = rows
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pharmacy.reorder.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PharmacyReorderLine(models.TransientModel):
    _name = 'pharmacy.reorder.line'
    _description = 'AI Reorder Forecast Line'
    _order = 'suggested_qty desc'

    wizard_id = fields.Many2one(
        'pharmacy.reorder.wizard', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Medicine')
    daily_velocity = fields.Float(string='Avg/Day')
    projected_demand = fields.Float(string='Projected Demand')
    on_hand = fields.Float(string='On Hand')
    near_expiry = fields.Float(string='Near-Expiry')
    suggested_qty = fields.Float(string='Suggested Reorder')
