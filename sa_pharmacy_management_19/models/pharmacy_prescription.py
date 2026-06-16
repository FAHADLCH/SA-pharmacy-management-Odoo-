# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PharmacyPrescription(models.Model):
    _name = 'pharmacy.prescription'
    _description = 'Pharmacy Prescription (Rx)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'prescription_date desc, id desc'

    name = fields.Char(
        string='Rx Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: ('New'))
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, tracking=True,
        domain="[('is_patient', '=', True)]")
    prescriber_id = fields.Many2one(
        'res.partner', string='Prescriber', tracking=True,
        domain="[('is_prescriber', '=', True)]",
        help="Registered prescriber. Leave empty to enter an external "
             "prescriber manually below.")
    prescriber_name = fields.Char(string='External Prescriber')
    prescriber_license = fields.Char(string='Prescriber License No.')
    prescription_date = fields.Date(
        string='Prescription Date', required=True, tracking=True,
        default=fields.Date.context_today)
    validity_date = fields.Date(
        string='Valid Until', tracking=True,
        help="After this date the prescription can no longer be dispensed.")
    diagnosis = fields.Text(string='Diagnosis')
    note = fields.Text(string='Clinical Notes')

    refills_allowed = fields.Integer(string='Refills Allowed', default=0)
    refills_used = fields.Integer(
        string='Refills Used', readonly=True, copy=False, default=0)

    line_ids = fields.One2many(
        'pharmacy.prescription.line', 'prescription_id',
        string='Prescribed Items')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('partial', 'Partially Dispensed'),
        ('dispensed', 'Fully Dispensed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    dispense_ids = fields.One2many(
        'pharmacy.dispense', 'prescription_id', string='Dispensings')
    dispense_count = fields.Integer(compute='_compute_dispense_count')

    interaction_ids = fields.Many2many(
        'pharmacy.drug.interaction', string='Detected Interactions',
        compute='_compute_clinical_screening')
    has_interaction = fields.Boolean(
        compute='_compute_clinical_screening', store=True)
    interaction_warning = fields.Html(
        string='Interaction Warnings',
        compute='_compute_clinical_screening')
    allergy_warning = fields.Html(
        string='Allergy Warnings', compute='_compute_clinical_screening')
    has_allergy_alert = fields.Boolean(
        compute='_compute_clinical_screening', store=True)

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)

    # --- AI clinical decision support ---
    ai_risk_score = fields.Integer(
        string='AI Risk Score', readonly=True, copy=False)
    ai_risk_level = fields.Selection([
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='AI Risk Level', readonly=True, copy=False)
    ai_risk_summary = fields.Html(
        string='AI Clinical Insight', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pharmacy.prescription') or 'New'
        return super().create(vals_list)

    def _compute_dispense_count(self):
        for rx in self:
            rx.dispense_count = len(rx.dispense_ids)

    @api.depends('line_ids.product_id',
                 'line_ids.product_id.active_ingredient_ids',
                 'patient_id', 'patient_id.allergy_ids')
    def _compute_clinical_screening(self):
        interaction_model = self.env['pharmacy.drug.interaction']
        for rx in self:
            products = rx.line_ids.mapped('product_id')
            ingredients = products.mapped('active_ingredient_ids')
            interactions = interaction_model.find_interactions(
                ingredients.ids)
            rx.interaction_ids = interactions
            rx.has_interaction = bool(interactions)
            rx.interaction_warning = rx._render_interaction_html(interactions)
            allergy_html, has_allergy = rx._render_allergy_html(products)
            rx.allergy_warning = allergy_html
            rx.has_allergy_alert = has_allergy

    def _render_interaction_html(self, interactions):
        if not interactions:
            return False
        colors = {
            'minor': '#f0ad4e', 'moderate': '#ec971f',
            'major': '#d9534f', 'contraindicated': '#a02622',
        }
        labels = dict(
            self.env['pharmacy.drug.interaction']._fields['severity'].selection)
        rows = []
        for inter in interactions:
            rows.append(
                "<li style='margin-bottom:4px;'>"
                "<span style='display:inline-block;min-width:120px;"
                "font-weight:600;color:%s;'>%s</span> %s &amp; %s"
                "%s</li>" % (
                    colors.get(inter.severity, '#d9534f'),
                    labels.get(inter.severity, ''),
                    inter.ingredient_a_id.name,
                    inter.ingredient_b_id.name,
                    (" — %s" % inter.clinical_advice)
                    if inter.clinical_advice else ''))
        return "<ul style='padding-left:18px;margin:0;'>%s</ul>" % ''.join(rows)

    def _render_allergy_html(self, products):
        patient = self.patient_id
        if not patient or not patient.allergy_ids:
            return False, False
        allergy_ingredients = patient.allergy_ids.mapped('ingredient_id')
        rows = []
        for product in products:
            matched = product.active_ingredient_ids & allergy_ingredients
            for ingredient in matched:
                rows.append(
                    "<li style='color:#a02622;font-weight:600;'>%s contains "
                    "%s — patient is allergic.</li>" % (
                        product.name, ingredient.name))
        if not rows:
            return False, False
        return ("<ul style='padding-left:18px;margin:0;'>%s</ul>"
                % ''.join(rows)), True

    @api.constrains('validity_date', 'prescription_date')
    def _check_validity(self):
        for rx in self:
            if (rx.validity_date and rx.prescription_date
                    and rx.validity_date < rx.prescription_date):
                raise ValidationError(
                    "The validity date cannot be earlier than the "
                    "prescription date.")

    def action_validate(self):
        for rx in self:
            if not rx.line_ids:
                raise UserError(
                    "Add at least one prescribed item before validating.")
            if rx.has_interaction:
                contraindicated = rx.interaction_ids.filtered(
                    lambda i: i.severity == 'contraindicated')
                if contraindicated:
                    rx.message_post(
                        body="⚠️ Validated despite CONTRAINDICATED drug "
                             "interactions. Pharmacist override recorded.")
            rx.state = 'validated'
        self.action_ai_assess()
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_ai_assess(self):
        """Run the AI clinical-risk assessment and store the result."""
        service = self.env['pharmacy.ai.service']
        for rx in self:
            result = service.assess_prescription_risk(rx)
            rx.ai_risk_score = result['score']
            rx.ai_risk_level = result['level']
            rx.ai_risk_summary = result['summary']
        return True

    def action_open_dispense(self):
        self.ensure_one()
        if self.state not in ('validated', 'partial'):
            raise UserError(
                "Only validated prescriptions can be dispensed.")
        if self.validity_date and self.validity_date < fields.Date.context_today(
                self):
            self.state = 'expired'
            raise UserError("This prescription has expired.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dispense Prescription',
            'res_model': 'pharmacy.dispense',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_prescription_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
        }

    def action_view_dispensings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dispensings',
            'res_model': 'pharmacy.dispense',
            'view_mode': 'tree,form',
            'domain': [('prescription_id', '=', self.id)],
            'context': {'default_prescription_id': self.id},
        }

    def _update_dispense_state(self):
        for rx in self:
            if rx.state in ('cancelled', 'expired'):
                continue
            lines = rx.line_ids
            if lines and all(
                    line.dispensed_qty >= line.product_qty for line in lines):
                rx.state = 'dispensed'
            elif any(line.dispensed_qty > 0 for line in lines):
                rx.state = 'partial'

    @api.model
    def _cron_expire_prescriptions(self):
        today = fields.Date.context_today(self)
        expired = self.search([
            ('state', 'in', ('validated', 'partial')),
            ('validity_date', '!=', False),
            ('validity_date', '<', today),
        ])
        expired.write({'state': 'expired'})


class PharmacyPrescriptionLine(models.Model):
    _name = 'pharmacy.prescription.line'
    _description = 'Prescription Line'

    prescription_id = fields.Many2one(
        'pharmacy.prescription', string='Prescription',
        required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Medicine', required=True,
        domain="[('is_medicine', '=', True)]")
    product_qty = fields.Float(
        string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one(
        'uom.uom', string='Unit', related='product_id.uom_id', readonly=True)
    dosage = fields.Char(
        string='Dosage (SIG)',
        help="Dosing instructions, e.g. '1 tablet twice daily after meals'.")
    frequency = fields.Char(string='Frequency')
    duration_days = fields.Integer(string='Duration (days)')
    instructions = fields.Text(string='Patient Instructions')
    dispensed_qty = fields.Float(
        string='Dispensed', compute='_compute_dispensed_qty', store=True)
    remaining_qty = fields.Float(
        string='Remaining', compute='_compute_dispensed_qty', store=True)

    @api.depends('product_qty',
                 'prescription_id.dispense_ids.state',
                 'prescription_id.dispense_ids.line_ids.product_qty',
                 'prescription_id.dispense_ids.line_ids.product_id')
    def _compute_dispensed_qty(self):
        for line in self:
            dispensed = 0.0
            for dispense in line.prescription_id.dispense_ids.filtered(
                    lambda d: d.state == 'done'):
                for dline in dispense.line_ids.filtered(
                        lambda dl: dl.product_id == line.product_id):
                    dispensed += dline.product_qty
            line.dispensed_qty = dispensed
            line.remaining_qty = max(line.product_qty - dispensed, 0.0)

    @api.constrains('product_qty')
    def _check_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(
                    "Prescribed quantity must be greater than zero.")
