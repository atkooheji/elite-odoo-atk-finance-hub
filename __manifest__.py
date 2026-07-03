{
    'name': 'ATK - Unified Finance Hub',
    'version': '19.0.1.3',
    'category': 'Accounting/Finance',
    'summary': 'Unified Bahraini Banking, Cheque Management, and Payment Gateway for Odoo 19.',
    'description': """
ATK Unified Finance Hub
========================
A premium, consolidated suite of financial tools for Bahrain.
Refactored for modularity and scalability.
    """,
    'author': 'AntiGravity Technologies',
    'website': 'https://antigravity.ai',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'account_payment',
        'payment',
        'mail',
        'purchase',
        'atk_finance_dashboard',
        'atk_prop_mgmt',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/payment_hub/payment_templates.xml',
        'views/cheques/report_check_template.xml',
        'wizard/banking/bank_statement_import_wizard_view.xml',
        'views/banking/bank_import_batch_views.xml',
        'views/banking/bank_partner_mapping_views.xml',
        'views/cheques/check_template_views.xml',
        'views/cheques/account_journal_views.xml',
        'views/cheques/account_payment_views.xml',
        'wizard/cheques/print_check_wizard_views.xml',
        'views/payment_hub/payment_provider_views.xml',
        'report/cheques/print_check_report.xml',
        'views/tally/account_views.xml',
        'views/tally/tally_batch_views.xml',
        'views/tally/tally_mapping_views.xml',
        'views/tally/tally_wizard_views.xml',
        'data/cheque_data.xml',
        'data/payment_data.xml',
        'data/tally_data.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # DISABLED LEGACY ASSETS CAUSING ODOO 19 WHITE SCREEN
            # 'atk_finance_hub/static/src/js/payment_hub.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
