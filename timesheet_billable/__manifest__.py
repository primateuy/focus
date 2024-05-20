# -*- coding: utf-8 -*-
{
    'name': "Horas Facturables",

    'summary': """
        TimeSheet – Horas Facturables""",

    'description': """
        En términos generales se desea adecuar la funcionalidad de timesheet para
poder agregar dos nuevos valores al registro de horas: coeficiente de
facturación (porcentaje positivo) y horas facturables. 
    """,

    'author': "Proyecta",
    'website': "https://odoo.proyectasoft.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'hr',
    'version': '26.09.2022.15.30',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr_timesheet'],

    # always loaded
    'data': [
        'security/security.xml',
        'views/hr_timesheet_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
