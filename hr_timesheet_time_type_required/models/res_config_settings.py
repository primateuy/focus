
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_timesheet_time_type_required = fields.Boolean(
        string="Require Time Type on Timesheets",
        related="company_id.is_timesheet_time_type_required",
        readonly=False,
    )
