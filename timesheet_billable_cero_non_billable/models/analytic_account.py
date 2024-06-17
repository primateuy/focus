# -*- coding: utf-8 -*-

from odoo import models, api


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.model
    def create(self, vals):
        billable_hours = vals.get('billable_hours', 0.0)
        res = super(AccountAnalyticLine, self).create(vals)

        allow_billable = self.project_id.allow_billable or False
        if not allow_billable:
            vals.update({'billable_hours': 0.0})

        return res

    def write(self, vals):
        allow_billable = self.project_id.allow_billable or False
        if not allow_billable:
            vals.update({'billable_hours': 0.0})

        print (f'non_cero_Before: {vals.get("billable_hours", 0.0)}')
        res = super(AccountAnalyticLine, self).write(vals)
        print(f'non_cero_After:')

        return res
