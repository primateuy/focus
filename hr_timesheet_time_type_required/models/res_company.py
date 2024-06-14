
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    is_timesheet_time_type_required = fields.Boolean(string="Require Time Type on Timesheets")
