
{
    "name": "Hr Timesheet Time Type Required",
    "summary": """
        Set time type on timesheet as a mandatory field""",
    "version": "16.0.0",
    "license": "AGPL-3",
    "author": "Primate UY",
    "website": "https://www.primate.uy/",
    "depends": ["hr_timesheet", "hr_timesheet_time_type"],
    "data": [
        "views/account_analytic_line.xml",
        "views/project_project.xml",
        "views/res_config_settings.xml",
    ],
}
