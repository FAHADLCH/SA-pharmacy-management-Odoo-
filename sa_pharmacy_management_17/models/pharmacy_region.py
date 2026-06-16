# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PharmacyRegion(models.Model):
    """Regional regulatory & localisation profile.

    PharmaCore is a global product. A region profile bundles the
    market-specific defaults a pharmacy needs (controlled-substance
    classification scheme, receipt language & paper, temperature unit,
    mandatory regulatory footer, narcotics register rules, ...) so the
    same module can be deployed in any country by picking one profile.
    """

    _name = 'pharmacy.region'
    _description = 'Pharmacy Regional Profile'
    _order = 'sequence, name'

    name = fields.Char(string='Region', required=True, translate=True)
    code = fields.Char(
        string='Code', required=True,
        help="Short ISO-like code, e.g. US, EU, GB, PK, AE, GLOBAL.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    flag_emoji = fields.Char(string='Flag')

    control_scheme = fields.Selection([
        ('dea', 'US DEA Schedules (I–V)'),
        ('uk', 'UK Misuse of Drugs (Class A/B/C)'),
        ('eu', 'EU / INCB Narcotic Tables'),
        ('who', 'WHO Model List'),
        ('custom', 'Custom / Local Authority'),
    ], string='Controlled-Substance Scheme', default='who', required=True)
    narcotic_register_required = fields.Boolean(
        string='Narcotics Register Mandatory', default=True,
        help="Force a controlled-substance register entry on every dispense "
             "of a scheduled item.")
    rx_validity_days = fields.Integer(
        string='Default Rx Validity (days)', default=180,
        help="Legal shelf-life of a prescription in this market.")
    max_controlled_validity_days = fields.Integer(
        string='Controlled Rx Validity (days)', default=30)

    temperature_unit = fields.Selection([
        ('c', 'Celsius (°C)'),
        ('f', 'Fahrenheit (°F)'),
    ], string='Temperature Unit', default='c')
    receipt_paper = fields.Selection([
        ('thermal_80', 'Thermal 80 mm'),
        ('thermal_58', 'Thermal 58 mm'),
        ('a4', 'A4 / Letter'),
    ], string='Default Receipt Format', default='thermal_80')
    currency_id = fields.Many2one('res.currency', string='Default Currency')
    language_code = fields.Char(
        string='Receipt Language', default='en_US',
        help="Locale code used when printing patient-facing documents.")

    regulatory_footer = fields.Text(
        string='Regulatory Footer',
        translate=True,
        help="Mandatory legal text printed at the bottom of receipts and "
             "labels in this region.")
    tax_inclusive = fields.Boolean(
        string='Prices Include Tax', default=False)
    require_patient_id_for_controlled = fields.Boolean(
        string='Require Patient ID for Controlled', default=True)

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('code_uniq', 'unique(code)',
         'A region with this code already exists.'),
    ]

    def name_get(self):
        result = []
        for region in self:
            label = region.name
            if region.flag_emoji:
                label = '%s %s' % (region.flag_emoji, label)
            result.append((region.id, label))
        return result

    def action_apply_region(self):
        """Push this profile's defaults into the active configuration."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('sa_pharmacy.region_id', self.id)
        params.set_param('sa_pharmacy.region_code', self.code or '')
        params.set_param('sa_pharmacy.control_scheme', self.control_scheme)
        params.set_param('sa_pharmacy.temperature_unit', self.temperature_unit)
        params.set_param('sa_pharmacy.receipt_paper', self.receipt_paper)
        params.set_param(
            'sa_pharmacy.regulatory_footer', self.regulatory_footer or '')
        params.set_param(
            'sa_pharmacy.rx_validity_days', self.rx_validity_days or 0)
        params.set_param(
            'sa_pharmacy.narcotic_register',
            '1' if self.narcotic_register_required else '0')
        if self.currency_id and self.env.company.currency_id != self.currency_id:
            # Non-destructive: only record the preference, never force-switch
            # a live company currency.
            params.set_param(
                'sa_pharmacy.preferred_currency_id', self.currency_id.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Region applied',
                'message': '%s profile is now active.' % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def _get_active_region(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.region_id')
        if param:
            region = self.browse(int(param)).exists()
            if region:
                return region
        return self.search([('code', '=', 'GLOBAL')], limit=1) \
            or self.search([], limit=1)
