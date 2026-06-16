# -*- coding: utf-8 -*-
from odoo import fields, models


class PharmacyAllergy(models.Model):
    _name = 'pharmacy.allergy'
    _description = 'Pharmacy Allergen'
    _order = 'name'

    name = fields.Char(string='Allergen', required=True, index=True)
    ingredient_id = fields.Many2one(
        'pharmacy.active.ingredient',
        string='Related Active Ingredient',
        ondelete='set null',
        help="When set, dispensing any medicine containing this ingredient to "
             "a patient flagged with this allergy raises a safety alert.")
    description = fields.Text(string='Clinical Notes')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This allergen already exists.'),
    ]
