# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PharmacyDispense(models.Model):
    _name = 'pharmacy.dispense'
    _description = 'Pharmacy Dispensing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'dispense_date desc, id desc'

    name = fields.Char(
        string='Dispense Ref', required=True, copy=False, readonly=True,
        index=True, default=lambda self: 'New')
    prescription_id = fields.Many2one(
        'pharmacy.prescription', string='Prescription', tracking=True,
        ondelete='set null')
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, tracking=True,
        domain="[('is_patient', '=', True)]")
    pharmacist_id = fields.Many2one(
        'res.users', string='Pharmacist', required=True,
        default=lambda self: self.env.user, tracking=True)
    dispense_date = fields.Datetime(
        string='Dispensed On', default=fields.Datetime.now, required=True)
    line_ids = fields.One2many(
        'pharmacy.dispense.line', 'dispense_id', string='Dispensed Items')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Dispensed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)
    counseling_done = fields.Boolean(string='Patient Counseled')
    note = fields.Text(string='Notes')
    picking_id = fields.Many2one(
        'stock.picking', string='Delivery', readonly=True, copy=False)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1))
    amount_total = fields.Monetary(
        string='Total', compute='_compute_amount_total', store=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True, tracking=True,
        default=lambda self: self._default_currency_id())
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    has_controlled = fields.Boolean(compute='_compute_has_controlled')

    @api.model
    def _default_currency_id(self):
        """Prefer the active region currency, else the company currency."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.preferred_currency_id')
        if param:
            currency = self.env['res.currency'].browse(int(param)).exists()
            if currency and currency.active:
                return currency.id
        return self.env.company.currency_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pharmacy.dispense') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('subtotal'))

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        """Re-price every line when the transaction currency changes."""
        if not self.currency_id:
            return
        company = self.company_id or self.env.company
        for line in self.line_ids:
            if line.product_id:
                line.price_unit = company.currency_id._convert(
                    line.product_id.lst_price, self.currency_id,
                    company, fields.Date.context_today(self))

    @api.depends('line_ids.product_id.is_controlled')
    def _compute_has_controlled(self):
        for rec in self:
            rec.has_controlled = any(
                rec.line_ids.mapped('product_id.is_controlled'))

    @api.onchange('prescription_id')
    def _onchange_prescription_id(self):
        if not self.prescription_id:
            return
        self.patient_id = self.prescription_id.patient_id
        lines = []
        for rx_line in self.prescription_id.line_ids:
            if rx_line.remaining_qty <= 0:
                continue
            lines.append((0, 0, {
                'product_id': rx_line.product_id.id,
                'product_qty': rx_line.remaining_qty,
                'dosage': rx_line.dosage,
            }))
        self.line_ids = [(5, 0, 0)] + lines

    def action_dispense(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Only draft dispensings can be confirmed.")
        if not self.line_ids:
            raise UserError("Add at least one item to dispense.")
        self._check_clinical_safety()
        self._check_quantities()
        self._create_and_validate_picking()
        self.state = 'done'
        if self.prescription_id:
            self.prescription_id._update_dispense_state()
        if self.has_controlled:
            self.message_post(
                body="Controlled substance dispensed and logged in the "
                     "register by %s." % self.pharmacist_id.name)
        return True

    def _check_clinical_safety(self):
        patient = self.patient_id
        allergy_ingredients = patient.allergy_ids.mapped('ingredient_id')
        blocked = []
        for line in self.line_ids:
            matched = line.product_id.active_ingredient_ids & allergy_ingredients
            if matched:
                blocked.append("%s (allergy: %s)" % (
                    line.product_id.display_name,
                    ', '.join(matched.mapped('name'))))
        if blocked:
            raise UserError(
                "Allergy safety stop. The following items conflict with the "
                "patient's recorded allergies:\n- %s\n\nRemove them or update "
                "the patient profile to proceed." % '\n- '.join(blocked))

    def _check_quantities(self):
        for line in self.line_ids:
            if line.product_qty <= 0:
                raise ValidationError(
                    "Quantity must be positive for %s."
                    % line.product_id.display_name)
            cap = line.product_id.max_dispense_qty
            if cap and line.product_qty > cap:
                raise UserError(
                    "%s exceeds the maximum dispense quantity of %s."
                    % (line.product_id.display_name, cap))
            if (line.product_id.prescription_required
                    and not self.prescription_id):
                raise UserError(
                    "%s requires a prescription. Link an Rx to dispense it."
                    % line.product_id.display_name)

    def _create_and_validate_picking(self):
        warehouse = self.warehouse_id or self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(
                "No warehouse configured for this company.")
        picking_type = warehouse.out_type_id
        customer_loc = self.env.ref('stock.stock_location_customers')
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': customer_loc.id,
            'partner_id': self.patient_id.id,
            'origin': self.name,
            'move_type': 'direct',
        })
        moves_by_line = {}
        for line in self.line_ids:
            move = self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_qty,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            })
            moves_by_line[line.id] = move
        picking.action_confirm()
        for line in self.line_ids:
            move = moves_by_line[line.id]
            # Drop any auto-generated reservation lines so we control the lot.
            move.move_line_ids.unlink()
            lot = line.lot_id
            if not lot and line.product_id.tracking != 'none':
                lot = line._suggest_fefo_lot()
                if not lot:
                    raise UserError(
                        "No batch available for %s. Receive stock with a "
                        "lot/expiry before dispensing."
                        % line.product_id.display_name)
                line.lot_id = lot
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'lot_id': lot.id if lot else False,
                'quantity': line.product_qty,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            })
            move.picked = True
        picking.with_context(
            skip_backorder=True,
            picking_ids_not_to_backorder=picking.ids,
        ).button_validate()
        self.picking_id = picking.id

    def action_cancel(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state == 'done':
                raise UserError(
                    "Stock has already moved. Reverse the delivery in "
                    "Inventory before cancelling this dispensing.")
            if rec.picking_id:
                rec.picking_id.action_cancel()
            rec.state = 'cancelled'

    def action_view_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Delivery',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
        }

    def action_print_label(self):
        return self.env.ref(
            'sa_pharmacy_management.action_report_pharmacy_label'
        ).report_action(self)

    def action_print_receipt(self):
        """Print the customer receipt on the region's default paper."""
        paper = self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.receipt_paper', 'thermal_80')
        if paper == 'a4':
            report = 'sa_pharmacy_management.action_report_dispense_receipt'
        else:
            report = ('sa_pharmacy_management.'
                      'action_report_dispense_receipt_thermal')
        return self.env.ref(report).report_action(self)

    def _pharmacy_region_footer(self):
        """Regulatory footer text for patient-facing print-outs."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'sa_pharmacy.regulatory_footer', '') or ''


class PharmacyDispenseLine(models.Model):
    _name = 'pharmacy.dispense.line'
    _description = 'Pharmacy Dispense Line'

    dispense_id = fields.Many2one(
        'pharmacy.dispense', string='Dispense', required=True,
        ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Medicine', required=True,
        domain="[('is_medicine', '=', True)]")
    lot_id = fields.Many2one(
        'stock.lot', string='Batch / Lot',
        domain="[('product_id', '=', product_id)]")
    expiration_date = fields.Datetime(
        related='lot_id.expiration_date', string='Expiry', readonly=True)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one(
        related='product_id.uom_id', string='Unit', readonly=True)
    price_unit = fields.Float(string='Unit Price')
    dosage = fields.Char(string='Dosage (SIG)')
    subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_subtotal', store=True)
    currency_id = fields.Many2one(
        related='dispense_id.currency_id', readonly=True)
    dispense_date = fields.Datetime(
        related='dispense_id.dispense_date', store=True, index=True,
        string='Dispensed On')
    state = fields.Selection(
        related='dispense_id.state', store=True, index=True, string='Status')
    pharmacist_id = fields.Many2one(
        related='dispense_id.pharmacist_id', store=True, string='Pharmacist')
    company_id = fields.Many2one(
        related='dispense_id.company_id', store=True, string='Company')
    is_controlled = fields.Boolean(
        related='product_id.is_controlled', store=True,
        string='Controlled Substance')

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        company = self.dispense_id.company_id or self.env.company
        currency = self.dispense_id.currency_id or company.currency_id
        self.price_unit = company.currency_id._convert(
            self.product_id.lst_price, currency, company,
            fields.Date.context_today(self))
        self.lot_id = self._suggest_fefo_lot()

    def _suggest_fefo_lot(self):
        """Return the in-stock lot with the earliest expiry (FEFO)."""
        self.ensure_one()
        if not self.product_id:
            return False
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product_id.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
        ])
        lots = quants.mapped('lot_id').filtered('expiration_date')
        if not lots:
            return quants.mapped('lot_id')[:1]
        return lots.sorted(key=lambda l: l.expiration_date)[:1]
