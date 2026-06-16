# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- Patient profile ---
    is_patient = fields.Boolean(string='Is a Patient')
    patient_code = fields.Char(string='Patient ID', copy=False, index=True)
    date_of_birth = fields.Date(string='Date of Birth')
    age = fields.Integer(string='Age', compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-'),
    ], string='Blood Group')
    allergy_ids = fields.Many2many(
        'pharmacy.allergy', string='Known Allergies')
    chronic_conditions = fields.Text(string='Chronic Conditions')
    is_pregnant = fields.Boolean(string='Pregnant / Breastfeeding')
    emergency_contact = fields.Char(string='Emergency Contact')
    insurance_provider_id = fields.Many2one(
        'res.partner', string='Insurance Provider',
        domain="[('is_company', '=', True)]")
    insurance_number = fields.Char(string='Insurance / Policy No.')

    # --- Prescriber profile ---
    is_prescriber = fields.Boolean(string='Is a Prescriber')
    prescriber_license = fields.Char(string='Medical License No.')
    prescriber_specialty = fields.Char(string='Specialty')

    prescription_ids = fields.One2many(
        'pharmacy.prescription', 'patient_id', string='Prescriptions')
    prescription_count = fields.Integer(
        compute='_compute_prescription_count')

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for partner in self:
            if partner.date_of_birth:
                dob = partner.date_of_birth
                partner.age = today.year - dob.year - (
                    (today.month, today.day) < (dob.month, dob.day))
            else:
                partner.age = 0

    def _compute_prescription_count(self):
        prescription = self.env['pharmacy.prescription']
        for partner in self:
            partner.prescription_count = prescription.search_count(
                [('patient_id', '=', partner.id)])

    def action_view_prescriptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Prescriptions',
            'res_model': 'pharmacy.prescription',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
