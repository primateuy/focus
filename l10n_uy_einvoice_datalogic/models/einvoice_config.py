# -*- coding: utf-8 -*-


from odoo import models, fields, api
from odoo.osv import expression



class DgiPuntoEmision(models.Model):
    _inherit = 'dgi.punto.emision'

    emision_code = fields.Char(string='Codigo de terminal', size=100, help='Codigo de terminal')
