# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    company_code = fields.Char(string='Código de la compañía', required=True)
