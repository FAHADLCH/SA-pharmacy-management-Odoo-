# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pharmacy_critical_days = fields.Integer(
        string='Critical Expiry Threshold (days)', default=30,
        config_parameter='sa_pharmacy.critical_days')
    pharmacy_warning_days = fields.Integer(
        string='Near-Expiry Threshold (days)', default=90,
        config_parameter='sa_pharmacy.warning_days')
    pharmacy_block_expired = fields.Boolean(
        string='Block Dispensing of Expired Stock', default=True,
        config_parameter='sa_pharmacy.block_expired')
    pharmacy_enforce_fefo = fields.Boolean(
        string='Enforce FEFO on Medicines', default=True,
        config_parameter='sa_pharmacy.enforce_fefo')

    # --- Region / localisation ---
    pharmacy_region_id = fields.Many2one(
        'pharmacy.region', string='Active Region',
        config_parameter='sa_pharmacy.region_id')
    pharmacy_receipt_paper = fields.Selection([
        ('thermal_80', 'Thermal 80 mm'),
        ('thermal_58', 'Thermal 58 mm'),
        ('a4', 'A4 / Letter'),
    ], string='Receipt Format', default='thermal_80',
        config_parameter='sa_pharmacy.receipt_paper')
    pharmacy_regulatory_footer = fields.Char(
        string='Receipt Regulatory Footer',
        config_parameter='sa_pharmacy.regulatory_footer')

    # --- Artificial Intelligence ---
    pharmacy_ai_enabled = fields.Boolean(
        string='Enable AI Decision Support', default=True,
        config_parameter='sa_pharmacy.ai_enabled')
    pharmacy_ai_provider = fields.Selection([
        ('builtin', 'Built-in (offline, no key)'),
        ('openai', 'OpenAI-compatible endpoint'),
    ], string='AI Provider', default='builtin',
        config_parameter='sa_pharmacy.ai_provider')
    pharmacy_ai_endpoint = fields.Char(
        string='AI Endpoint URL',
        default='https://api.openai.com/v1/chat/completions',
        config_parameter='sa_pharmacy.ai_endpoint')
    pharmacy_ai_api_key = fields.Char(
        string='AI API Key',
        config_parameter='sa_pharmacy.ai_api_key')
    pharmacy_ai_model = fields.Char(
        string='AI Model', default='gpt-4o-mini',
        config_parameter='sa_pharmacy.ai_model')

    @api.onchange('pharmacy_region_id')
    def _onchange_pharmacy_region_id(self):
        region = self.pharmacy_region_id
        if region:
            self.pharmacy_receipt_paper = region.receipt_paper
            self.pharmacy_regulatory_footer = region.regulatory_footer

    @api.model
    def set_values(self):
        super().set_values()
        if self.pharmacy_enforce_fefo:
            self._apply_fefo_strategy()
        if self.pharmacy_region_id:
            self.pharmacy_region_id.action_apply_region()

    def _apply_fefo_strategy(self):
        fefo = self.env.ref(
            'sa_pharmacy_management.removal_fefo',
            raise_if_not_found=False)
        if not fefo:
            return
        medicine_categs = self.env['product.category'].search([]).filtered(
            lambda c: self.env['product.template'].search_count([
                ('categ_id', '=', c.id), ('is_medicine', '=', True)]) > 0)
        medicine_categs.write({'removal_strategy_id': fefo.id})
