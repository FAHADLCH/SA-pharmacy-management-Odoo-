# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PharmacyActiveIngredient(models.Model):
    _name = 'pharmacy.active.ingredient'
    _description = 'Pharmaceutical Active Ingredient (INN)'
    _order = 'name'

    name = fields.Char(
        string='Active Ingredient',
        required=True,
        index=True,
        help="International Non-proprietary Name (INN) of the active substance, "
             "e.g. Paracetamol, Amoxicillin, Metformin.")
    code = fields.Char(string='Reference Code', index=True)
    atc_code = fields.Char(
        string='ATC Code',
        help="WHO Anatomical Therapeutic Chemical classification code.")
    description = fields.Text(string='Description')
    therapeutic_class = fields.Char(string='Therapeutic Class')
    is_controlled = fields.Boolean(
        string='Controlled Substance',
        help="Ingredient is a scheduled / controlled substance subject to "
             "regulatory dispensing controls.")
    active = fields.Boolean(default=True)

    product_ids = fields.Many2many(
        'product.template',
        'pharmacy_product_ingredient_rel',
        'ingredient_id',
        'product_id',
        string='Medicines')
    product_count = fields.Integer(
        string='Medicines', compute='_compute_product_count')
    allergy_ids = fields.One2many(
        'pharmacy.allergy', 'ingredient_id', string='Linked Allergies')

    _sql_constraints = [
        ('name_uniq', 'unique(name)',
         'An active ingredient with this name already exists.'),
    ]

    @api.depends('product_ids')
    def _compute_product_count(self):
        for ingredient in self:
            ingredient.product_count = len(ingredient.product_ids)

    def action_view_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'domain': [('active_ingredient_ids', 'in', self.id)],
            'context': {'default_is_medicine': True},
        }

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.code:
                name = '[%s] %s' % (rec.code, rec.name)
            result.append((rec.id, name))
        return result
