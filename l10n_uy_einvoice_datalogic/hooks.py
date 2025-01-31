# Copyright 2016 Antonio Espinosa <antonio.espinosa@tecnativa.com>
# Copyright 2017-2018 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import logging
_logger = logging.getLogger("SERVICIOS DE FACTURACION ELECTRONICA DATALOGIC")

def last_thing(env):
    ruc = env.ref('l10n_uy_einvoice_base.dgi_document_type_ruc')
    document_type = 'l10n_uy.it_rut'
    try:
        document_type_rut = env.ref(document_type)
    except Exception as error:
        print(error)
        _logger.error(f'No se pudo encontrar el tipo de documento {document_type}')
        document_type_rut = False
    if document_type_rut:
        partner_document_type = env['res.partner'].search([('l10n_latam_identification_type_id', '=', document_type_rut.id)])
        if partner_document_type:
            partner_document_type.l10n_latam_identification_type_id = ruc.id

        document_type_rut.unlink()

def post_init_hook_datalogic(env):
    print('START OPERATION')
    last_thing(env)
    return True