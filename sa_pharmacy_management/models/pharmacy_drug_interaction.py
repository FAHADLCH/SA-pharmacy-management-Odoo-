# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PharmacyDrugInteraction(models.Model):
    _name = 'pharmacy.drug.interaction'
    _description = 'Drug-Drug Interaction'
    _order = 'severity desc, id desc'
    _rec_name = 'display_name'

    ingredient_a_id = fields.Many2one(
        'pharmacy.active.ingredient',
        string='Ingredient A', required=True, ondelete='cascade', index=True)
    ingredient_b_id = fields.Many2one(
        'pharmacy.active.ingredient',
        string='Ingredient B', required=True, ondelete='cascade', index=True)
    severity = fields.Selection([
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('contraindicated', 'Contraindicated'),
    ], string='Severity', required=True, default='moderate', index=True)
    description = fields.Text(string='Interaction Effect')
    clinical_advice = fields.Text(string='Clinical Management Advice')
    reference = fields.Char(string='Evidence / Source')
    active = fields.Boolean(default=True)
    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('pair_uniq',
         'unique(ingredient_a_id, ingredient_b_id)',
         'This interaction pair already exists.'),
    ]

    @api.depends('ingredient_a_id', 'ingredient_b_id', 'severity')
    def _compute_display_name(self):
        labels = dict(self._fields['severity'].selection)
        for rec in self:
            if rec.ingredient_a_id and rec.ingredient_b_id:
                rec.display_name = '%s ⇄ %s (%s)' % (
                    rec.ingredient_a_id.name,
                    rec.ingredient_b_id.name,
                    labels.get(rec.severity, ''))
            else:
                rec.display_name = labels.get(rec.severity, 'Interaction')

    @api.constrains('ingredient_a_id', 'ingredient_b_id')
    def _check_distinct_ingredients(self):
        for rec in self:
            if rec.ingredient_a_id == rec.ingredient_b_id:
                raise ValidationError(
                    "An interaction must reference two different active "
                    "ingredients.")

    @api.model
    def find_interactions(self, ingredient_ids):
        """Return interaction records affecting any pair within ingredient_ids."""
        if not ingredient_ids or len(ingredient_ids) < 2:
            return self.browse()
        ids = list(ingredient_ids)
        return self.search([
            ('ingredient_a_id', 'in', ids),
            ('ingredient_b_id', 'in', ids),
        ])
