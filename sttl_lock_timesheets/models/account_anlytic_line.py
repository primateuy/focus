
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    
    from_time = fields.Float('From Time')
    to_time = fields.Float('To Time')
