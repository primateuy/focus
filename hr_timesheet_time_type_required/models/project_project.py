
from odoo import api, fields, models

class ProjectProject(models.Model):
    _inherit = "project.project"

    is_timesheet_time_type_required = fields.Boolean(
        string="Require Time Type on Timesheets",
        default=lambda self: self._default_is_timesheet_time_type_required(),
    )

    @api.model
    def _default_is_timesheet_time_type_required(self):
        company = self.env["res.company"].browse(
            self._context.get("company_id", self.env.user.company_id.id)
        )
        return company.is_timesheet_time_type_required
