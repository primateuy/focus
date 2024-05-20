# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    billable_hours = fields.Float(string='Horas Facturables', default=0.0)

    @api.model
    def create(self, vals):
        if vals.get('billable_hours', 0.0):
            if self.env.user.has_group('timesheet_billable.edit_billable_hours'):
                billable_hours = vals.get('billable_hours', 0.0)
                vals['billable_hours'] = billable_hours
        if vals.get('unit_amount', False) and not vals.get('billable_hours', False):
            unit_amount = vals.get('unit_amount', 0.0)
            vals['billable_hours'] = unit_amount
        elif vals.get('unit_amount', False) and vals.get('billable_hours', False) and not self.env.user.has_group(
                'timesheet_billable.edit_billable_hours'):
            unit_amount = vals.get('unit_amount', 0.0)
            vals['billable_hours'] = unit_amount

        return super(AccountAnalyticLine, self).create(vals)

    def write(self, vals):
        if vals.get('billable_hours', 0.0):
            if self.env.user.has_group('timesheet_billable.edit_billable_hours'):
                billable_hours = vals.get('billable_hours', 0.0)
                vals['billable_hours'] = billable_hours
            else:
                vals['billable_hours'] = self.billable_hours

        if vals.get('unit_amount', False):
            unit_amount = vals.get('unit_amount', 0.0)
            vals['billable_hours'] = unit_amount

        return super(AccountAnalyticLine, self).write(vals)
