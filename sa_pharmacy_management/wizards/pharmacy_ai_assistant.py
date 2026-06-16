# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PharmacyAiAssistant(models.TransientModel):
    """Conversational clinical assistant.

    Routes the pharmacist's question to the configured AI provider with a
    safety-first system prompt. When no external provider is configured it
    returns deterministic, safe guidance so the feature is always usable.
    """

    _name = 'pharmacy.ai.assistant'
    _description = 'Pharmacy AI Assistant'

    prescription_id = fields.Many2one(
        'pharmacy.prescription', string='Related Prescription')
    patient_id = fields.Many2one('res.partner', string='Patient')
    question = fields.Text(
        string='Ask the assistant', required=True,
        help="e.g. 'Safe paracetamol dose for a 6-year-old?' or "
             "'Counselling points for warfarin'.")
    answer = fields.Html(string='Assistant Response', readonly=True)
    provider_label = fields.Char(string='Engine', readonly=True)

    @api.onchange('prescription_id')
    def _onchange_prescription_id(self):
        if self.prescription_id:
            self.patient_id = self.prescription_id.patient_id

    def action_ask(self):
        self.ensure_one()
        service = self.env['pharmacy.ai.service']
        cfg = service._config()
        context_bits = []
        if self.patient_id:
            context_bits.append(
                "Patient age %s, %s." % (
                    self.patient_id.age or 'n/a',
                    'pregnant' if self.patient_id.is_pregnant
                    else 'not pregnant'))
            if self.patient_id.allergy_ids:
                context_bits.append(
                    "Known allergies: %s." % ', '.join(
                        self.patient_id.allergy_ids.mapped('name')))
        if self.prescription_id:
            context_bits.append(
                "Current medicines: %s." % ', '.join(
                    self.prescription_id.line_ids.mapped('product_id.name')))
        prompt = '%s\n\nQuestion: %s' % (' '.join(context_bits), self.question)

        answer = service.complete(prompt, max_tokens=500)
        if answer:
            self.provider_label = 'AI (%s)' % cfg['model']
            body = answer.replace('\n', '<br/>')
        else:
            self.provider_label = 'Built-in guidance'
            body = self._builtin_answer()

        self.answer = (
            "<div style='padding:8px 12px;background:#fbfcfd;"
            "border-left:4px solid #E8242A;'>%s"
            "<div style='font-size:10px;color:#9aa5b1;margin-top:8px;'>"
            "Decision-support only — verify against current references and "
            "use your professional judgement.</div></div>" % body)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pharmacy.ai.assistant',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _builtin_answer(self):
        """Safe offline fallback when no LLM provider is configured."""
        return (
            "AI provider not configured, so here is general guidance:<br/>"
            "1. Confirm the patient's allergies and current medicines.<br/>"
            "2. Check the prescription for interactions on the Rx form "
            "(the clinical screening banner).<br/>"
            "3. For dosing, consult your local formulary / BNF.<br/>"
            "4. Counsel the patient on administration, timing and red-flag "
            "symptoms.<br/><br/>"
            "Tip: enable an AI provider under Pharmacy → Configuration → "
            "Settings → Artificial Intelligence to get tailored answers.")
