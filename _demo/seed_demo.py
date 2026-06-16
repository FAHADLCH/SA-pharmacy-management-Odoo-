# -*- coding: utf-8 -*-
# Demo seed for PharmaCore. Run via:  odoo shell -d pharmacy_demo < seed_demo.py
from datetime import date, timedelta

env = env  # provided by odoo shell
Ingredient = env['pharmacy.active.ingredient']
Interaction = env['pharmacy.drug.interaction']
Allergy = env['pharmacy.allergy']
Product = env['product.template']
Partner = env['res.partner']
Rx = env['pharmacy.prescription']
Lot = env['stock.lot']
Quant = env['stock.quant']

company = env.company
warehouse = env['stock.warehouse'].search(
    [('company_id', '=', company.id)], limit=1)
stock_loc = warehouse.lot_stock_id


def ing(name, **kw):
    rec = Ingredient.search([('name', '=', name)], limit=1)
    return rec or Ingredient.create(dict(name=name, **kw))


# --- Active ingredients (INN) ---
warfarin = ing('Warfarin', therapeutic_class='Anticoagulant', atc_code='B01AA03')
aspirin = ing('Acetylsalicylic Acid', therapeutic_class='Antiplatelet/NSAID',
              atc_code='B01AC06')
amoxicillin = ing('Amoxicillin', therapeutic_class='Penicillin Antibiotic',
                  atc_code='J01CA04')
penicillin = ing('Penicillin V', therapeutic_class='Penicillin Antibiotic',
                 atc_code='J01CE02')
metformin = ing('Metformin', therapeutic_class='Antidiabetic (Biguanide)',
                atc_code='A10BA02')
paracetamol = ing('Paracetamol', therapeutic_class='Analgesic/Antipyretic',
                  atc_code='N02BE01')
ibuprofen = ing('Ibuprofen', therapeutic_class='NSAID', atc_code='M01AE01')
codeine = ing('Codeine Phosphate', therapeutic_class='Opioid Analgesic',
              atc_code='R05DA04', is_controlled=True)

# --- Drug-drug interactions ---
def interaction(a, b, severity, desc, advice):
    rec = Interaction.search([
        ('ingredient_a_id', '=', a.id), ('ingredient_b_id', '=', b.id)], limit=1)
    if rec:
        return rec
    return Interaction.create({
        'ingredient_a_id': a.id, 'ingredient_b_id': b.id,
        'severity': severity, 'description': desc, 'clinical_advice': advice,
        'reference': 'Stockley\'s Drug Interactions',
    })

interaction(warfarin, aspirin, 'contraindicated',
            'Markedly increased risk of major bleeding (additive '
            'anticoagulant + antiplatelet effect).',
            'Avoid combination. If unavoidable, monitor INR closely and watch '
            'for signs of bleeding.')
interaction(ibuprofen, aspirin, 'moderate',
            'NSAID may blunt the cardioprotective antiplatelet effect of '
            'low-dose aspirin.',
            'Separate dosing by at least 2 hours; prefer paracetamol for pain.')
interaction(warfarin, ibuprofen, 'major',
            'Increased bleeding risk and possible potentiation of warfarin.',
            'Avoid; use paracetamol for analgesia and monitor INR.')

# --- Allergens linked to ingredients ---
pen_allergy = Allergy.search([('name', '=', 'Penicillin Allergy')], limit=1) or \
    Allergy.create({
        'name': 'Penicillin Allergy', 'ingredient_id': penicillin.id,
        'description': 'Documented IgE-mediated hypersensitivity to '
                       'penicillins (rash / anaphylaxis risk).'})
# Cross-reactivity: also flag amoxicillin (same beta-lactam class)
amox_allergy = Allergy.search([('name', '=', 'Amoxicillin Allergy')], limit=1) or \
    Allergy.create({
        'name': 'Amoxicillin Allergy', 'ingredient_id': amoxicillin.id,
        'description': 'Beta-lactam hypersensitivity (cross-reactive with '
                       'penicillins).'})


# --- Medicines (products) ---
def medicine(name, ingredients, kind='generic', form='tablet', strength='',
             rx=False, price=0.0, controlled=False):
    p = Product.search([('name', '=', name)], limit=1)
    if not p:
        p = Product.create({
            'name': name,
            'is_medicine': True,
            'medicine_kind': kind,
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
            'use_expiration_date': True,
            'dosage_form': form,
            'strength': strength,
            'prescription_required': rx,
            'list_price': price,
            'active_ingredient_ids': [(6, 0, [i.id for i in ingredients])],
        })
    return p

m_warfarin = medicine('Warfarin 5 mg Tablets', [warfarin], 'generic',
                      'tablet', '5 mg', rx=True, price=8.50)
m_aspirin = medicine('Aspirin 75 mg Tablets', [aspirin], 'otc', 'tablet',
                     '75 mg', price=2.20)
m_amox = medicine('Amoxicillin 500 mg Capsules', [amoxicillin], 'generic',
                  'capsule', '500 mg', rx=True, price=6.40)
m_metformin = medicine('Metformin 850 mg Tablets', [metformin], 'generic',
                       'tablet', '850 mg', rx=True, price=4.10)
m_para = medicine('Paracetamol 500 mg Tablets', [paracetamol], 'otc',
                  'tablet', '500 mg', price=1.80)
m_codeine = medicine('Codeine 30 mg Tablets', [codeine], 'generic', 'tablet',
                     '30 mg', rx=True, price=9.90, controlled=True)


# --- Stock with staggered expiry (demonstrates FEFO) ---
def add_batch(product, lot_name, qty, expiry):
    variant = product.product_variant_id
    lot = Lot.search([('name', '=', lot_name),
                      ('product_id', '=', variant.id)], limit=1)
    if not lot:
        lot = Lot.create({
            'name': lot_name, 'product_id': variant.id,
            'company_id': company.id, 'expiration_date': expiry})
    q = Quant.with_context(inventory_mode=True).create({
        'product_id': variant.id, 'location_id': stock_loc.id,
        'lot_id': lot.id, 'inventory_quantity': qty})
    q.action_apply_inventory()
    return lot

today = date.today()
# Amoxicillin: two batches — the SECOND created one expires SOONER (FEFO should pick it first)
add_batch(m_amox, 'AMX-2027A', 200, today + timedelta(days=540))
add_batch(m_amox, 'AMX-NEAR',  120, today + timedelta(days=45))   # near expiry
add_batch(m_warfarin, 'WARF-A', 150, today + timedelta(days=400))
add_batch(m_warfarin, 'WARF-SOON', 60, today + timedelta(days=20))  # near expiry
add_batch(m_aspirin, 'ASP-LOT1', 500, today + timedelta(days=720))
add_batch(m_metformin, 'MET-LOT1', 300, today + timedelta(days=300))
add_batch(m_para, 'PARA-LOT1', 400, today + timedelta(days=600))
add_batch(m_codeine, 'COD-LOT1', 80, today + timedelta(days=365))


# --- Prescriber ---
prescriber = Partner.search([('name', '=', 'Dr. Sarah Khan')], limit=1)
if not prescriber:
    prescriber = Partner.create({
        'name': 'Dr. Sarah Khan', 'is_prescriber': True,
        'prescriber_license': 'PMDC-44219',
        'prescriber_specialty': 'Internal Medicine',
        'phone': '+92 300 1234567'})

# --- Patients ---
def patient(name, code, dob, gender, blood, allergies=None, **kw):
    p = Partner.search([('patient_code', '=', code)], limit=1)
    if p:
        return p
    return Partner.create(dict({
        'name': name, 'is_patient': True, 'patient_code': code,
        'date_of_birth': dob, 'gender': gender, 'blood_group': blood,
        'allergy_ids': [(6, 0, [a.id for a in (allergies or [])])],
    }, **kw))

p_ahmed = patient('Ahmed Raza', 'PT-0001', date(1958, 4, 12), 'male', 'o+',
                  chronic_conditions='Atrial fibrillation, Hypertension')
p_fatima = patient('Fatima Noor', 'PT-0002', date(1990, 9, 3), 'female', 'a+',
                   allergies=[pen_allergy, amox_allergy],
                   chronic_conditions='Type 2 Diabetes')
p_bilal = patient('Bilal Hassan', 'PT-0003', date(1975, 1, 25), 'male', 'b+')


# --- Prescription 1: triggers a CONTRAINDICATED interaction (Warfarin + Aspirin) ---
def make_rx(patient_rec, lines, diagnosis):
    rx = Rx.create({
        'patient_id': patient_rec.id,
        'prescriber_id': prescriber.id,
        'prescription_date': today,
        'validity_date': today + timedelta(days=30),
        'diagnosis': diagnosis,
        'line_ids': [(0, 0, {
            'product_id': l[0].product_variant_id.id,
            'product_qty': l[1], 'dosage': l[2],
            'frequency': l[3], 'duration_days': l[4],
        }) for l in lines],
    })
    return rx

rx1 = make_rx(p_ahmed, [
    (m_warfarin, 30, '5 mg', 'Once daily', 30),
    (m_aspirin, 30, '75 mg', 'Once daily', 30),
], 'AF anticoagulation review')

# --- Prescription 2: allergic patient prescribed Amoxicillin (allergy stop on dispense) ---
rx2 = make_rx(p_fatima, [
    (m_amox, 21, '500 mg', 'Three times daily', 7),
    (m_metformin, 60, '850 mg', 'Twice daily', 30),
], 'Chest infection + diabetes maintenance')

# --- Prescription 3: clean, controlled substance present ---
rx3 = make_rx(p_bilal, [
    (m_codeine, 20, '30 mg', 'As needed', 10),
    (m_para, 20, '500 mg', 'Up to 4x daily', 10),
], 'Post-operative pain')

env.cr.commit()

print('SEED_DONE')
print('Ingredients:', Ingredient.search_count([]))
print('Interactions:', Interaction.search_count([]))
print('Medicines:', Product.search_count([('is_medicine', '=', True)]))
print('Patients:', Partner.search_count([('is_patient', '=', True)]))
print('Prescriptions:', Rx.search_count([]))
print('Rx1 has_interaction:', rx1.has_interaction,
      '| interactions:', rx1.interaction_ids.mapped('severity'))
print('Rx2 has_allergy_alert:', rx2.has_allergy_alert)
