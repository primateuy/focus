# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    background_color = fields.Char('Color')
    layout_background_image = fields.Binary(string='Background Image', readonly=False)
    invoice_address = fields.Boolean(string='Mostrar direccion en factura', default=True)    
    product_tag = fields.Boolean(string='Mostrar las etiquetas de los productos', default=True)
    translations = fields.Boolean(string='Mostrar las traducciones en el idioma del cliente', default=False)
