# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_medicine = fields.Boolean(
        string='Is a Medicine',
        help="Flag this product as a pharmaceutical item to unlock batch "
             "expiry control, prescription rules and clinical screening.")
    medicine_kind = fields.Selection([
        ('branded', 'Branded'),
        ('generic', 'Generic'),
        ('otc', 'OTC / Non-prescription'),
        ('supplement', 'Supplement / Wellness'),
        ('medical_device', 'Medical Device'),
    ], string='Medicine Type', default='branded')

    active_ingredient_ids = fields.Many2many(
        'pharmacy.active.ingredient',
        'pharmacy_product_ingredient_rel',
        'product_id',
        'ingredient_id',
        string='Active Ingredients')
    strength = fields.Char(
        string='Strength',
        help="Dosage strength, e.g. 500 mg, 5 mg/ml, 10 IU.")
    dosage_form = fields.Selection([
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('syrup', 'Syrup / Suspension'),
        ('injection', 'Injection'),
        ('cream', 'Cream / Ointment'),
        ('drops', 'Drops'),
        ('inhaler', 'Inhaler'),
        ('suppository', 'Suppository'),
        ('patch', 'Transdermal Patch'),
        ('powder', 'Powder'),
        ('other', 'Other'),
    ], string='Dosage Form')
    manufacturer_id = fields.Many2one(
        'res.partner', string='Manufacturer',
        domain="[('is_company', '=', True)]")
    therapeutic_class = fields.Char(string='Therapeutic Class')
    atc_code = fields.Char(string='ATC Code')

    prescription_required = fields.Boolean(
        string='Prescription Required (Rx)',
        help="Item may only be dispensed against a validated prescription.")
    is_controlled = fields.Boolean(
        string='Controlled Substance',
        compute='_compute_is_controlled', store=True, readonly=False)
    control_schedule = fields.Selection([
        ('schedule_1', 'Schedule I'),
        ('schedule_2', 'Schedule II'),
        ('schedule_3', 'Schedule III'),
        ('schedule_4', 'Schedule IV'),
        ('schedule_5', 'Schedule V'),
    ], string='Control Schedule')

    storage_condition = fields.Selection([
        ('room', 'Room Temperature (15-25°C)'),
        ('cool', 'Cool (8-15°C)'),
        ('refrigerated', 'Refrigerated (2-8°C)'),
        ('frozen', 'Frozen (< 0°C)'),
        ('dry', 'Dry / Protect from Moisture'),
        ('light', 'Protect from Light'),
    ], string='Storage Condition', default='room')
    max_dispense_qty = fields.Float(
        string='Max Qty per Dispense',
        help="Optional safety cap on the quantity dispensed in a single "
             "transaction. Zero means no limit.")
    requires_counseling = fields.Boolean(
        string='Requires Patient Counseling')

    @api.depends('active_ingredient_ids',
                 'active_ingredient_ids.is_controlled')
    def _compute_is_controlled(self):
        for product in self:
            product.is_controlled = any(
                product.active_ingredient_ids.mapped('is_controlled'))

    @api.onchange('is_medicine')
    def _onchange_is_medicine(self):
        for product in self:
            if product.is_medicine:
                product.tracking = 'lot'
                product.use_expiration_date = True
                product.type = 'product'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_medicine'):
                vals.setdefault('tracking', 'lot')
                vals.setdefault('use_expiration_date', True)
                vals.setdefault('type', 'product')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_medicine'):
            vals.setdefault('tracking', 'lot')
            vals.setdefault('use_expiration_date', True)
        return super().write(vals)

    def action_pharmacy_substitutes(self):
        self.ensure_one()
        return self.product_variant_id.action_pharmacy_substitutes()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_clinical_warnings(self, partner):
        """Return a list of warning dicts for the given patient/partner."""
        self.ensure_one()
        warnings = []
        if not partner:
            return warnings
        ingredients = self.active_ingredient_ids
        patient_allergies = partner.allergy_ids
        allergy_ingredients = patient_allergies.mapped('ingredient_id')
        matched = ingredients & allergy_ingredients
        for ingredient in matched:
            warnings.append({
                'type': 'allergy',
                'severity': 'major',
                'message': "Patient is allergic to %s contained in %s." % (
                    ingredient.name, self.display_name),
            })
        return warnings

    def _pharmacy_qty_expiring_within(self, days):
        """On-hand quantity in batches expiring within ``days`` days."""
        self.ensure_one()
        from datetime import timedelta
        horizon = fields.Datetime.now() + timedelta(days=days)
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('lot_id.expiration_date', '!=', False),
            ('lot_id.expiration_date', '<=', horizon),
        ])
        return sum(quants.mapped('quantity'))

    def action_pharmacy_substitutes(self):
        """Open the AI-ranked therapeutic alternatives for this medicine."""
        self.ensure_one()
        subs = self.env['pharmacy.ai.service'].suggest_substitutes(self)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Alternatives for %s' % self.display_name,
            'res_model': 'product.product',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', subs.ids)],
            'context': {'create': False},
            'help': '<p class="o_view_nocontent_smiling_face">'
                    'No therapeutic alternative found</p>'
                    '<p>AI looks for in-stock medicines sharing the same '
                    'active ingredients, ranked by availability and price.</p>',
        }
