# -*- coding: utf-8 -*-
{
    'name': 'Fix Timesheet Lock',
    'version': '16.0.1.0',
    'author': 'PrimateUY',
    'website': 'https://www.silvertouch.com',
    'category': 'Analytic',
    'license': 'OPL-1',
    'description': """
        This addon is to prevent the update of Timesheet by user after it is sumbmitted to the client.
    """,
    'price': 00,
    'currency': 'EUR',
    'depends': ['sttl_lock_timesheets', 'timesheet_billable' ,'hr_timesheet', 'base'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
