# -*- coding: utf-8 -*-
{
    'name': 'Integración de Facturación Electrónica DataLogic',
    'version': '1.0',
    'author': 'Primate',
    'category': 'Contabilidad',
    'summary': 'Integración de Odoo con Facturación Electrónica DataLogic',
    'website': 'primate.uy',
    'depends': ['base', 'account', 'l10n_uy_einvoice_base'],
    'external_dependencies': {
        'python': ['xmltodict', 'qrcode', 'io']
    },
    'data': [
        'report/cfe_bandeja.xml',
        'report/estado_cfe.xml',
        'views/invoice_view.xml',
        'views/account_payment_view.xml',
        'views/dgi_punto_emision_view.xml',
        'views/res_company_view.xml',
        'views/cfe_received_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
