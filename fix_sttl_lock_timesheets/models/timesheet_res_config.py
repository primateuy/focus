# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class AccountAnalyticLineTimesheet(models.Model):
    _inherit = 'account.analytic.line'

    def update_billable_hours(self, billable_hours):
        for rec in self:
            rec.env.cr.execute('''
                UPDATE account_analytic_line
                SET billable_hours = %s
                WHERE id = %s
            ''', (billable_hours, rec.id))

    def write(self, vals):
        if 'billable_hours' in vals and len(vals) == 1:
            self.update_billable_hours(vals['billable_hours'])
            return True

        return super(AccountAnalyticLineTimesheet, self).write(vals)
         