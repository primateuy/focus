# -*- coding: utf-8 -*-
{
    'name': "l10n_uy_einvoice_document",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'web'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'data/report_paperformat_data.xml',
        'templates/invoice_document_custom.xml',
        'templates/copy_web_core.xml',
        'views/res_company_view.xml',
        'views/account_move_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
}

