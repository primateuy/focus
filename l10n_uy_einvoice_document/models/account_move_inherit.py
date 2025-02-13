from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    def action_print_invoice(self):
        return {'type': 'ir.actions.report','report_name': 'l10n_uy_einvoice_document.report_custom_template_prueba','report_type':"qweb-pdf"}
