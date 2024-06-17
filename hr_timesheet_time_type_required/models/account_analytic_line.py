
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    is_time_type_required = fields.Boolean(
        string="Is Time Type Required", related="project_id.is_timesheet_time_type_required"
    )

    @api.constrains("project_id", "time_type_id")
    def _check_timesheet_time_type(self):
        for line in self:
            if line.is_time_type_required and not line.time_type_id:
                raise ValidationError(_("You must specify a time type for timesheet lines."))
