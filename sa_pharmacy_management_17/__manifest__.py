# -*- coding: utf-8 -*-
{
    'name': 'PharmaCore - Smart Pharmacy Management',
    'version': '17.0.2.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'AI-assisted pharmacy & drugstore management: prescriptions (Rx), '
               'FEFO batch/expiry control, drug-interaction & allergy alerts, '
               'AI risk scoring, smart reorder, multicurrency dispensing, '
               'analytics dashboards, region profiles, thermal receipts, '
               'controlled-substance register and dispensing.',
    'description': """
PharmaCore - Smart Pharmacy Management
======================================
A clinical-grade pharmacy management layer built natively on top of Odoo
Inventory, Sales, Accounting and Contacts. It closes the real-world gaps that
generic Odoo inventory leaves open for pharmacies:

* FEFO (First-Expiry-First-Out) removal strategy
* Prescription (Rx) lifecycle with refills, validity & prescriber registry
* Drug-Drug interaction screening + patient allergy alerts
* AI decision support: clinical risk scoring, substitution suggestions,
  demand forecasting / smart reorder and a clinical assistant
  (offline built-in engine, or any OpenAI-compatible endpoint)
* Region profiles (US/EU/UK/PK/AE/Global) for scheduling, language & receipts
* Multicurrency dispensing with automatic price conversion per company rates
* Analytics dashboard: revenue trend, top medicines, prescription status &
  clinical-risk distribution, near-expiry batches (pivot & graph reporting)
* Thermal-printer receipts (80 mm / 58 mm) and A4 receipts
* Controlled / scheduled substance register with full audit trail
* Near-expiry dashboard, automated alerts and write-off suggestions
* Pharmacist dispensing with batch traceability and printable labels

Compatible with Odoo 17, 18 and 19 (dedicated build per series).

By SA Systems - Where Business Grows Smarter.
""",
    'author': 'SA Systems',
    'company': 'SA Systems',
    'maintainer': 'SA Systems',
    'website': 'https://www.sasystems.solutions',
    'license': 'OPL-1',
    'price': 5.00,
    'currency': 'USD',
    'support': 'info@sasystems.solutions',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'product_expiry',
        'sale_management',
        'account',
        'contacts',
        'board',
        'barcodes',
    ],
    'data': [
        'security/pharmacy_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/product_removal_data.xml',
        'data/pharmacy_paperformat_data.xml',
        'data/pharmacy_region_data.xml',
        'data/pharmacy_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/pharmacy_menus.xml',
        'views/pharmacy_active_ingredient_views.xml',
        'views/pharmacy_drug_interaction_views.xml',
        'views/pharmacy_allergy_views.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/stock_lot_views.xml',
        'views/pharmacy_region_views.xml',
        'views/pharmacy_ai_views.xml',
        'views/pharmacy_prescription_views.xml',
        'views/pharmacy_dispense_views.xml',
        'views/pharmacy_dashboard_views.xml',
        'views/res_config_settings_views.xml',
        'report/pharmacy_report_actions.xml',
        'report/pharmacy_prescription_report.xml',
        'report/pharmacy_label_report.xml',
        'report/pharmacy_receipt_report.xml',
        'views/pharmacy_menus_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sa_pharmacy_management/static/src/scss/pharmacy.scss',
        ],
    },
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
