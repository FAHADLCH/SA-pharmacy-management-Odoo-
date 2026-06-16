# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

# Severity ordering used to compute a numeric clinical-risk score.
_SEVERITY_WEIGHT = {
    'minor': 1,
    'moderate': 2,
    'major': 3,
    'contraindicated': 4,
}


class PharmacyAiService(models.AbstractModel):
    """Pluggable AI/clinical-intelligence layer.

    The service is provider-agnostic:

    * ``builtin``  - a fully offline, deterministic clinical engine. It never
      calls the network, so the module works out-of-the-box with real value
      (risk scoring, substitution, demand forecasting).
    * ``openai``   - an OpenAI-compatible chat-completions endpoint (OpenAI,
      Azure OpenAI, Together, Ollama, vLLM, ...). Configured entirely from
      Settings. Any failure transparently falls back to ``builtin`` so AI is
      always additive and never blocks pharmacy operations.
    """

    _name = 'pharmacy.ai.service'
    _description = 'Pharmacy AI Service'

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @api.model
    def _config(self):
        params = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': params.get_param('sa_pharmacy.ai_enabled', '1') == '1',
            'provider': params.get_param('sa_pharmacy.ai_provider', 'builtin'),
            'endpoint': params.get_param(
                'sa_pharmacy.ai_endpoint',
                'https://api.openai.com/v1/chat/completions'),
            'api_key': params.get_param('sa_pharmacy.ai_api_key', ''),
            'model': params.get_param('sa_pharmacy.ai_model', 'gpt-4o-mini'),
            'timeout': int(params.get_param('sa_pharmacy.ai_timeout', '20')),
        }

    @api.model
    def is_enabled(self):
        return self._config()['enabled']

    # ------------------------------------------------------------------
    # Generic LLM completion (safe, optional)
    # ------------------------------------------------------------------
    @api.model
    def complete(self, prompt, system=None, max_tokens=600):
        """Return an AI completion string, or '' when unavailable.

        Always safe to call: never raises, never blocks. Falls back to an
        empty string so callers can use their deterministic engine instead.
        """
        cfg = self._config()
        if not cfg['enabled'] or cfg['provider'] != 'openai':
            return ''
        if not requests or not cfg['api_key']:
            return ''
        system = system or (
            "You are a clinical pharmacy assistant. Be concise, evidence "
            "based and safety-first. Always remind the user that final "
            "clinical judgement rests with the licensed pharmacist.")
        try:
            response = requests.post(
                cfg['endpoint'],
                headers={
                    'Authorization': 'Bearer %s' % cfg['api_key'],
                    'Content-Type': 'application/json',
                },
                data=json.dumps({
                    'model': cfg['model'],
                    'messages': [
                        {'role': 'system', 'content': system},
                        {'role': 'user', 'content': prompt},
                    ],
                    'temperature': 0.2,
                    'max_tokens': max_tokens,
                }),
                timeout=cfg['timeout'],
            )
            response.raise_for_status()
            data = response.json()
            return (data['choices'][0]['message']['content'] or '').strip()
        except Exception as exc:  # noqa: BLE001 - AI must never break ops
            _logger.warning('PharmaCore AI completion failed: %s', exc)
            return ''

    # ------------------------------------------------------------------
    # Feature 1 - Smart substitution
    # ------------------------------------------------------------------
    @api.model
    def suggest_substitutes(self, product, limit=5):
        """Therapeutic alternatives sharing the same active ingredient(s).

        Ranked by: in-stock first, then lowest price. Deterministic and
        offline. Returns a ``product.product`` recordset.
        """
        if not product or not product.active_ingredient_ids:
            return self.env['product.product']
        ingredient_ids = product.active_ingredient_ids.ids
        candidates = self.env['product.product'].search([
            ('is_medicine', '=', True),
            ('id', '!=', product.id),
            ('active_ingredient_ids', 'in', ingredient_ids),
        ])
        # Keep only candidates covering ALL ingredients of the source drug.
        source = set(ingredient_ids)
        candidates = candidates.filtered(
            lambda p: source.issubset(set(p.active_ingredient_ids.ids)))

        def _qty(prod):
            return prod.with_context(
                location=False).qty_available or 0.0

        ranked = candidates.sorted(
            key=lambda p: (-(1 if _qty(p) > 0 else 0), p.lst_price))
        return ranked[:limit]

    # ------------------------------------------------------------------
    # Feature 2 - Prescription risk assessment
    # ------------------------------------------------------------------
    @api.model
    def assess_prescription_risk(self, prescription):
        """Return a structured clinical-risk assessment dict.

        Keys: ``score`` (0-100), ``level``, ``summary`` (HTML),
        ``factors`` (list of str).
        """
        rx = prescription
        factors = []
        raw = 0

        # Drug-drug interactions
        for inter in rx.interaction_ids:
            weight = _SEVERITY_WEIGHT.get(inter.severity, 1)
            raw += weight * 12
            factors.append(
                '%s interaction: %s + %s' % (
                    inter.severity.capitalize(),
                    inter.ingredient_a_id.name,
                    inter.ingredient_b_id.name))

        # Allergy conflicts
        if rx.has_allergy_alert:
            raw += 45
            factors.append('Allergy conflict with a prescribed item')

        # Patient-specific modifiers
        patient = rx.patient_id
        if patient:
            if patient.is_pregnant:
                raw += 10
                factors.append('Patient pregnant / breastfeeding')
            if patient.age and patient.age >= 65:
                raw += 8
                factors.append('Geriatric patient (age %s)' % patient.age)
            if patient.age and 0 < patient.age <= 12:
                raw += 8
                factors.append('Paediatric patient (age %s)' % patient.age)

        # Controlled substances on the script
        controlled = rx.line_ids.filtered(
            lambda line: line.product_id.is_controlled)
        if controlled:
            raw += 10
            factors.append(
                '%s controlled substance(s) prescribed' % len(controlled))

        # Polypharmacy
        if len(rx.line_ids) >= 5:
            raw += 6
            factors.append('Polypharmacy (%s items)' % len(rx.line_ids))

        score = min(raw, 100)
        if score >= 70:
            level = 'critical'
        elif score >= 40:
            level = 'high'
        elif score >= 15:
            level = 'moderate'
        else:
            level = 'low'

        summary = self._risk_summary_html(rx, score, level, factors)
        return {
            'score': score,
            'level': level,
            'summary': summary,
            'factors': factors,
        }

    def _risk_summary_html(self, rx, score, level, factors):
        colors = {
            'low': '#2e7d32', 'moderate': '#ef6c00',
            'high': '#d9534f', 'critical': '#a02622',
        }
        color = colors.get(level, '#627d98')

        # Try an LLM-authored narrative; gracefully fall back to a template.
        narrative = ''
        if factors:
            prompt = (
                "Patient: age %s, %s. Prescription items: %s. "
                "Detected risk factors: %s. In 2-3 short sentences, give the "
                "pharmacist a prioritised counselling and monitoring plan."
                % (
                    rx.patient_id.age or 'n/a',
                    'pregnant' if rx.patient_id.is_pregnant else 'not pregnant',
                    ', '.join(rx.line_ids.mapped('product_id.name')) or 'none',
                    '; '.join(factors)))
            narrative = self.complete(prompt, max_tokens=220)
        if not narrative:
            narrative = self._builtin_narrative(level, factors)

        items = ''.join('<li>%s</li>' % f for f in factors) or \
            '<li>No significant risk factors detected.</li>'
        return (
            "<div style='border-left:4px solid %s;padding:8px 12px;"
            "background:#fbfcfd;'>"
            "<div style='font-weight:700;color:%s;font-size:14px;'>"
            "Clinical risk: %s &nbsp;·&nbsp; score %s/100</div>"
            "<ul style='margin:6px 0;padding-left:18px;'>%s</ul>"
            "<div style='font-size:12px;color:#334e68;'>%s</div>"
            "<div style='font-size:10px;color:#9aa5b1;margin-top:6px;'>"
            "AI-assisted decision support · final judgement rests with the "
            "licensed pharmacist.</div></div>"
            % (color, color, level.capitalize(), score, items, narrative))

    @api.model
    def _builtin_narrative(self, level, factors):
        if level in ('critical', 'high'):
            return ("Escalate before dispensing: verify the prescriber's "
                    "intent, document an override rationale, counsel the "
                    "patient on warning signs and arrange follow-up "
                    "monitoring.")
        if level == 'moderate':
            return ("Proceed with caution: counsel the patient on the flagged "
                    "items and advise on what symptoms warrant contact.")
        return ("Routine dispensing. Provide standard counselling on usage, "
                "timing and storage.")

    # ------------------------------------------------------------------
    # Feature 3 - Demand forecast / smart reorder
    # ------------------------------------------------------------------
    @api.model
    def forecast_reorder(self, product, horizon_days=30, history_days=90):
        """Estimate a suggested reorder quantity for a medicine.

        Uses dispensing velocity over ``history_days`` projected across
        ``horizon_days``, adjusted for current on-hand and near-expiry stock.
        Returns a dict with the working numbers so the UI can explain itself.
        """
        from datetime import timedelta
        from odoo import fields as odoo_fields

        since = odoo_fields.Datetime.now() - timedelta(days=history_days)
        lines = self.env['pharmacy.dispense.line'].search([
            ('product_id', '=', product.id),
            ('dispense_id.state', '=', 'done'),
            ('dispense_id.dispense_date', '>=', since),
        ])
        dispensed = sum(lines.mapped('product_qty'))
        daily_velocity = dispensed / max(history_days, 1)
        projected_demand = daily_velocity * horizon_days

        on_hand = product.qty_available or 0.0
        # Stock expiring before the horizon ends cannot satisfy demand.
        near_expiry_qty = product._pharmacy_qty_expiring_within(horizon_days) \
            if hasattr(product, '_pharmacy_qty_expiring_within') else 0.0
        usable = max(on_hand - near_expiry_qty, 0.0)

        suggested = max(projected_demand - usable, 0.0)
        return {
            'daily_velocity': round(daily_velocity, 2),
            'projected_demand': round(projected_demand, 1),
            'on_hand': round(on_hand, 1),
            'near_expiry': round(near_expiry_qty, 1),
            'suggested_qty': round(suggested, 0),
            'history_days': history_days,
            'horizon_days': horizon_days,
        }
