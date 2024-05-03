# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import pytz

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    timesheet_lock = fields.Date("Timesheet LockDate", related="company_id.timesheet_lock", store=True, readonly=False)


class ResCompany(models.Model):
    _inherit = "res.company"

    timesheet_lock = fields.Date("Timesheet LockDate", store=True, readonly=False)


class ProjectTask(models.Model):
    _inherit = "project.project"

    project_timeSheet_lockDate = fields.Date("Timesheet LockDate")


class AccountAnalyticLineTimesheet(models.Model):
    _inherit = 'account.analytic.line'

    is_timesheet_expire = fields.Boolean("Is Timesheet Expire", compute="_compute_timesheet_lock")

    @api.depends('company_id.timesheet_lock')
    def _compute_timesheet_lock(self):
        for rec in self:    
            rec.is_timesheet_expire = False
            if rec.project_id.project_timeSheet_lockDate and rec.date < rec.project_id.project_timeSheet_lockDate:
                rec.is_timesheet_expire = True
            elif rec.company_id.timesheet_lock and rec.date < rec.company_id.timesheet_lock:
                rec.is_timesheet_expire = True

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(AccountAnalyticLineTimesheet, self).create(vals_list)
        for res in lines:
            if res.company_id.timesheet_lock and res.date < res.company_id.timesheet_lock:
                raise UserError(_("You can not create/update timesheet before the date %s.") % res.company_id.timesheet_lock)
        return lines

    def write(self, vals):
        user_tz = self.env.context.get('tz')
        for rec in self:
            if vals.get('date'):
                date = datetime.strptime(vals.get('date'), '%Y-%m-%d').date()
            else:
                date = rec.date

            if rec.project_id.project_timeSheet_lockDate and date < rec.project_id.project_timeSheet_lockDate:
                raise UserError(_("You can not create/update timesheet before the date %s.") % rec.project_id.project_timeSheet_lockDate)
            elif rec.company_id.timesheet_lock and date < rec.company_id.timesheet_lock:
                raise UserError(_("You can not create/update timesheet before the date %s.") % rec.company_id.timesheet_lock)

        
        return super(AccountAnalyticLineTimesheet, self).write(vals)
         