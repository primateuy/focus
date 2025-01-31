# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import xmltodict
import re
from zeep import Client
import logging
_logger = logging.getLogger("SERVICIOS DE FACTURACION ELECTRONICA")

class ResPartner(models.Model):
    _inherit = 'res.partner'

    obtener_acta = fields.Boolean()

    def get_param(self, param=None):
        self = self.sudo()
        # param_obj = self.env['res.company'].with_company(self.env.company).sudo()
        company = self.env.company
        result = getattr(company, param)
        if not result:
            raise ValidationError('No se ha configurado el parámetro ' + param)
        return result

    @api.onchange('obtener_acta')
    def onchange_my_button(self):
        for rec in self:
            if rec.obtener_acta:
                self.get_partner_dgi_data()


    def to_tree(self, cfe):
        return xmltodict.parse(cfe)


    
    def find_city(self, name=None):
        name = name.capitalize()
        city_obj = self.env['res.country.city']
        city_id = city_obj.search([('name', '=', name)], limit=1)
        if not city_id:
            city_id = self.env.company.partner_id.city_id
        return city_id

    def find_state(self, name=None):
        name = name.capitalize()
        city_obj = self.env['res.country.state']
        state_id = city_obj.search([('name', '=', name)], limit=1)
        if not state_id:
            state_id = self.env.company.partner_id.state_id
        return state_id

    def load_dgi_data(self, result=None):
        
        if result is None:
            result = {}
        partner = self.sudo()
        # Extraer datos relevantes con valores por defecto
        receptor = result.get('Respuesta', {}).get('Receptores', {}).get('Receptor')
        denominacion = receptor.get('RazonSocial', 'Nombre no disponible')
        nombre_fantasia = receptor.get('RazonSocial', 'Nombre no disponible')
        email = receptor.get('Mail', 'Mail no disponible')
        # tipo_entidad = datos_persona.get('TipoEntidad', 'Tipo de entidad no disponible')
        # estado_actividad = datos_persona.get('EstadoActividad', 'Estado de actividad no disponible')

        # Obtener datos de la dirección fiscal
        # datos_direccion = datos_persona.get('WS_DomFiscalLocPrincipal', {}).get('WS_PersonaActEmpresarial.WS_DomFiscalLocPrincipalItem', {})

        # Actualizar los campos del partner
        # city_id = self.find_city(name=datos_direccion.get('Dpto_Nom'))
        # if not city_id:
        #     state_id = self.find_state(name=datos_direccion.get('Dpto_Nom'))
        valores_a_actualizar = {
            'name': nombre_fantasia,
            'social_reason': denominacion,
            'is_company': True,
            'email': email,
            # 'street': datos_direccion.get('Calle_Nom', 'Calle no disponible'),
            # 'street2': datos_direccion.get('Dom_Pta_Nro', ''),
            # 'city_id': city_id.id,
            # 'state_id': city_id.state_id.id if city_id else state_id.id,
            # 'zip': datos_direccion.get('Dom_Pst_Cod', ''),
            # Añadir más campos según sea necesario
        }

        # Realizar la actualización
        # Manejar contactos (child_ids)
        # datos_direccion = datos_persona.get('WS_DomFiscalLocPrincipal', {}).get('WS_PersonaActEmpresarial.WS_DomFiscalLocPrincipalItem', {})

        # contactos = datos_direccion.get('Contactos', {}).get('WS_Domicilio.WS_DomicilioItem.Contacto', [])
        # if isinstance(contactos, dict):
        #     contactos = [contactos]
        # for contacto in contactos:
        #     tipo_contacto = contacto.get('TipoCtt_Id')
        #     valor_contacto = contacto.get('DomCtt_Val')
        #     if tipo_contacto == '6':  # Suponiendo que '6' es el tipo para teléfonos movil
        #         valores_a_actualizar['mobile'] = valor_contacto
        #     elif tipo_contacto == '1':  # Suponiendo que '1' es el tipo para correos electrónicos
        #         valores_a_actualizar['email'] = valor_contacto
        #     elif tipo_contacto == '5':  # Suponiendo que '5' es el tipo para teléfonos fijo
        #         valores_a_actualizar['phone'] = valor_contacto

        partner.write(valores_a_actualizar)


        return True



    def get_partner_dgi_data(self):
        docs = self
        docargs = {
            'doc_ids': [self.id],
            'doc_model': 'res.partner',
            'docs': docs,
            'company': self.env.company,
        }
        nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_xml_datos_partner'
        view = self.env.ref(nombre_vista)
        start_cdata_placeholder = '<startcdata></startcdata>'
        start_cdata = "<![CDATA["
        end_cdata = "]]>"
        end_cdata_placeholder = '<endcdata></endcdata>'
        try:
            cfe = str(view._render_template(nombre_vista, docargs))
        except Exception as error:
            raise ValidationError(error)
        docs = self
        cfe = cfe.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
        cfe = f"""
            {cfe}
        """
        cfe = cfe.encode('UTF-8')
        cfexml = re.sub(r'[\n\r|]|  ', '', cfe.decode('UTF-8'))
        url = self.env['account.move'].get_param(param='url_testing')
        soap_client = Client(url)

        _logger.info(cfe)
        try:
            
            response = soap_client.service.CONSULTARRECEPTORES(cfexml)
            response_dict = xmltodict.parse(response)
            resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)


            mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
            valor = xmltodict.parse(response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor', '<nothing/>'))
        except Exception as error:
            raise ValidationError(f'Eror al obtener datos {error}')
        _logger.info(response)
        if resultado == '1' and mensaje == 'Ok':
            _logger.info("""
            ****************************************************
            ****************************************************
            ****************************************************
            *****************OBTENCIÓN EXITOSA******************
            ****************************************************
            ****************************************************
            ****************************************************
            """)
            self.load_dgi_data(result=valor)
        else:
            raise ValidationError(mensaje)
        return True
