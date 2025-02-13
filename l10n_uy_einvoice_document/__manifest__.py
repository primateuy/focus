# -*- coding: utf-8 -*-
{
    'name': "l10n_uy_einvoice_document",
    'author': 'Primate',
    'category': 'Contabilidad',
    'summary': 'Customización de Factura Electrónica para Uruguay',
    'website': 'primate.uy',
    'version': '1.0',
    'depends': ['base', 'account', 'web'],
    'data': [
        'data/report_paperformat_data.xml',
        'templates/invoice_document_custom.xml',
        'templates/copy_web_core.xml',
        'views/res_company_view.xml',
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

