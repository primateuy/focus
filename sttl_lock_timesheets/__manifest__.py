# -*- coding: utf-8 -*-
{
    'name': 'Timesheet Lock',
    'version': '16.0.1.0',
    'author': 'Silver Touch Technologies Limited',
    'website': 'https://www.silvertouch.com',
    'category': 'Analytic',
    'license': 'OPL-1',
    'description': """
        This addon is to prevent the update of Timesheet by user after it is sumbmitted to the client.
    """,
    'price': 00,
    'currency': 'EUR',
    'depends': ['hr_timesheet', 'base'],
    'data': [
        'views/account_analytic_line_view.xml',
        'views/timesheet_res_config_view.xml',
        'views/project_project_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
