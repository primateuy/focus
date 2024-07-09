# -*- coding: utf-8 -*-
{
    'name': 'Fix Timesheet Lock',
    'version': '16.1.0.0',
    'author': 'PrimateUY',
    'website': 'https://www.primate.uy/',
    'category': 'Analytic',
    'description': """
        Bloquea la posibilidad de modificar horas facturables anteriores a la fecha 'Timesheet LockDate', establecida por configuración.
    """,
    'depends': ['sttl_lock_timesheets', 'timesheet_billable' ,'hr_timesheet', 'base'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
