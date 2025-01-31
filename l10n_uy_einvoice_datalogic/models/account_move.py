# -*- coding: utf-8 -*-
import qrcode
import uuid as guid_generator
from io import StringIO, BytesIO
from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import requests
import base64
import datetime
import json
import xmltodict
import logging
import re
import xml.etree.ElementTree as ET
from zeep import Client
import xml.etree.ElementTree as ET
from xml.dom import minidom
from odoo.tools import float_round
_logger = logging.getLogger(__name__)

successful_cod_rta_dict = {
    '00': 'Petición aceptada y procesada.',
    '11': 'CFE aceptado por UCFE, en espera de respuesta de DGI.',
    '?': 'Cualquier otro código no especificado debe entenderse como requerimiento denegado.'
}
error_cod_rta_dict = {
    '01': 'Petición denegada.',
    '03': 'Comercio inválido.',
    '05': 'CFE rechazado por DGI.',
    '06': 'CFE observado por DGI.',
    '12': 'Requerimiento inválido.',
    '30': 'Error en formato.',
    '31': 'Error en formato de CFE.',
    '89': 'Terminal inválida.',
    '96': 'Error en sistema.',
    '99': 'Sesión no iniciada.',
    '500': 'Error en el cuerpo del mensaje',
    '?': 'Cualquier otro código no especificado debe entenderse como requerimiento denegado.'
}
codigos_cfe = {
    'ticket': 101,
    'nc-ticket': 102,
    'nd-ticket': 103,
    'factura': 111,
    'nc-factura': 112,
    'nd-factura': 113,
    'factura-exp': 121,
    'nc-factura-exp': 122,
    'nd-factura-exp': 123,
    'remito-exp': 124,
    'remito': 181,
    'eresguardo': 182
}


class AccountMove(models.Model):
    _inherit = 'account.move'


    def strip_html(self, html_content):
        if not html_content:
            return ''
        if not html_content.removeprefix('<p><br></p>'):
            return ''
        clean_text = re.sub('<br>', 'çç', html_content)
        clean_text = re.sub('\n', 'çç', clean_text)
        clean_text = re.sub('</p>', 'çç', clean_text)
        clean_text = re.sub('</li>', 'çç', clean_text)
        clean_text = re.sub('</ul>', 'çç', clean_text)
        clean_text = re.sub('<.*?>', '', clean_text)
        return clean_text


    def obtener_pdf(self, raw_return=False):
        supplier_moves = ['in_invoice', 'in_refund']
        if self.move_type in supplier_moves and self.cfe_emitido:
            return self.obtener_pdf_recibido(raw_return=raw_return, cfe_type=self.cfe_type_received)
        self = self.sudo()
        has_payment = self.payment_id
        company = self.env.user.company_id
        cfe_base_url_parm = self.get_cfe_base_url_parm()
        cfe_base_url = self.get_param(param=cfe_base_url_parm)
        full_url = cfe_base_url
        docs = self
        if has_payment:
            cfe_type = has_payment.l10n_latam_document_type_id.dgi_cfe_type
        else:
            cfe_type = self.l10n_latam_document_type_id.dgi_cfe_type

        # cfe_type = self.l10n_latam_document_type_id.dgi_cfe_type
        docargs = {
            'doc_ids': [self.id],
            'doc_model': 'account.move',
            'docs': docs,
            'cfe_type': cfe_type,
            'company': company,
            'amount_total': self.amount_total,
        }
        if has_payment.anulacion_resguardo:
            docargs['amount_total'] = -docargs['amount_total']
        nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_obtener_pdf'
        view = self.env.ref(nombre_vista)
        start_cdata_placeholder = '<startcdata></startcdata>'
        start_cdata = "<![CDATA["
        end_cdata = "]]>"
        end_cdata_placeholder = '<endcdata></endcdata>'
        try:
            cfe_pdf = str(view._render_template(nombre_vista, docargs))
        except Exception as error:
            raise ValidationError(error)
        cfe_pdf = cfe_pdf.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
        cfe_pdf = f"""
            {cfe_pdf}
        """

        cfe_pdf = cfe_pdf.encode('UTF-8')
        cfe_pdf_xml = re.sub(r'[\n\r|]|  ', '', cfe_pdf.decode('UTF-8'))
        soap_client = Client(full_url)
        try:
            response = soap_client.service.CFE_GENERARPDF(cfe_pdf_xml)
            response_dict = xmltodict.parse(response)
            resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
            mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
            valor = response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor')
        except Exception as error:
            raise ValidationError(f'Error al obtener PDF {error}')
        _logger.info(response)
        if resultado == '1':
            _logger.info("""
            ****************************************************
            ****************************************************
            ****************************************************
            *****************RESPUESTA EXITOSA**********************
            ****************************************************
            ****************************************************
            ****************************************************
            """)
        else:
            raise ValidationError(mensaje)

        if raw_return:
            return valor
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        attachment_obj = self.env['ir.attachment'].sudo()
        attach_values = {
            'name': self.name,
            'type': 'binary',
            'datas': valor,
            'store_fname': valor,
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        }
        if has_payment:
            attach_values['res_model'] = 'account.payment'
            attach_values['res_id'] = has_payment.id
        attachment_id = attachment_obj.create(attach_values)
        download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }

    def obtener_pdf_recibido(self, cfe_type=None, raw_return=False):
        self = self.sudo()
        has_payment = self.payment_id
        company = self.env.user.company_id
        cfe_base_url_parm = self.get_cfe_base_url_parm()
        cfe_base_url = self.get_param(param=cfe_base_url_parm)
        full_url = cfe_base_url
        docs = self
        docargs = {
            'doc_ids': [self.id],
            'doc_model': 'account.move',
            'docs': docs,
            'cfe_type': cfe_type,
            'company': company,
        }
        nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_obtener_pdf_recibido'
        view = self.env.ref(nombre_vista)
        start_cdata_placeholder = '<startcdata></startcdata>'
        start_cdata = "<![CDATA["
        end_cdata = "]]>"
        end_cdata_placeholder = '<endcdata></endcdata>'
        try:
            cfe_pdf = str(view._render_template(nombre_vista, docargs))
        except Exception as error:
            raise ValidationError(error)
        cfe_pdf = cfe_pdf.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
        cfe_pdf = f"""
            {cfe_pdf}
        """

        cfe_pdf = cfe_pdf.encode('UTF-8')
        cfe_pdf_xml = re.sub(r'[\n\r|]|  ', '', cfe_pdf.decode('UTF-8'))
        soap_client = Client(full_url)
        try:
            response = soap_client.service.CFE_OBTENERPDFRECIBIDO(cfe_pdf_xml)
            response_dict = xmltodict.parse(response)
            resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
            mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
            valor = response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor')
        except Exception as error:
            raise ValidationError(f'Error al obtener PDF {error}')
        _logger.info(response)
        if resultado == '1':
            _logger.info("""
            ****************************************************
            ****************************************************
            ****************************************************
            *****************RESPUESTA EXITOSA**********************
            ****************************************************
            ****************************************************
            ****************************************************
            """)
        else:
            raise ValidationError(mensaje)

        if raw_return:
            return valor
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        attachment_obj = self.env['ir.attachment'].sudo()
        attach_values = {
            'name': self.name,
            'type': 'binary',
            'datas': valor,
            'store_fname': valor,
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        }
        if has_payment:
            attach_values['res_model'] = 'account.payment'
            attach_values['res_id'] = has_payment.id
        attachment_id = attachment_obj.create(attach_values)
        download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }


    def estado_cfe(self):
        result = super(AccountMove, self).estado_cfe()
        has_payment = self.payment_id
        cfe_base_url_parm = self.get_cfe_base_url_parm()
        cfe_base_url = self.get_param(param=cfe_base_url_parm)
        full_url = cfe_base_url
        # self.check_connection(url=full_url)
        nombre_vista = 'l10n_uy_einvoice_datalogic.estado_cfe_emitido'
        docs = self
        docargs = {
            'doc_ids': [self.id],
            'doc_model': 'account.move',
            'docs': docs,
        }
        view = self.env.ref(nombre_vista)
        start_cdata_placeholder = '<startcdata></startcdata>'
        start_cdata = "<![CDATA["
        end_cdata = "]]>"
        end_cdata_placeholder = '<endcdata></endcdata>'
        try:
            cfe = str(view._render_template(nombre_vista, docargs))
        except Exception as error:
            raise ValidationError(error)
        cfe = cfe.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
        cfe = f"""
            {cfe}
        """
        cfe = cfe.encode('UTF-8')
        cfexml = re.sub(r'[\n\r|]|  ', '', cfe.decode('UTF-8'))
        soap_client = Client(full_url)
        _logger.info(cfe)
        try:
            response = soap_client.service.CONSULTARCFE(cfexml)
            response_dict = xmltodict.parse(response)
            resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
            mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)

        except Exception as error:
            raise ValidationError(f'Erro al firmar {error}')
        if resultado == '1' and mensaje == 'Ok':
            _logger.info("""
            ****************************************************
            *****************FIRMA EXITOSA**********************
            ****************************************************
            ****************************************************
            """)
            valor = xmltodict.parse(response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor'))


            if not valor.get('XMLResultado', {}).get('Enviados', {}):
                return result

            cfe_result = valor.get('XMLResultado', {}).get('Enviados', {}).get('Enviado', {})
            if isinstance(cfe_result, list):
                cfe_result = cfe_result[0]
            cfe_estado_dgi = cfe_result.get('Estado', '')
            cfe_estado_receptor = cfe_result.get('EstadoReceptor', '')
            self.cfe_state = cfe_estado_dgi
            self.cfe_state_receptor = cfe_estado_receptor
            if has_payment:
                has_payment.cfe_state = cfe_estado_dgi
                has_payment.cfe_state_receptor = cfe_estado_receptor
        else:
            raise ValidationError(mensaje)
        return result

    def recibidos(self):
        ctx = self.env.context.copy()
        user = self.get_param(param='cfe_user')
        password = self.get_param(param='cfe_password')
        token = base64.b64encode((user + ':' + password).encode('UTF-8')).decode('UTF-8')
        url = "https://test.ucfe.com.uy/Query116/WebServicesFE.svc/rest/ObtenerCfeRecibido"

        # Parámetros de la solicitud
        data = {
            "rut": self.env.company.vat[2:len(self.env.company.vat)],  # RUT de la empresa que recibió el CFE
            "rutRecibido": self.env.company.vat[2:len(self.env.company.vat)],  # RUT de la empresa que emitió el CFE
            "tipoCfe": self.cfe_type,  # Tipo de CFE
            "serieCfe": self.serie(),  # Serie del CFE
            "numeroCfe": str(self.numero_cfe()),  # Número del CFE
        }

        # Encabezados de la solicitud
        headers = {
            'Authorization': 'Basic ' + token,
            'Content-Type': 'application/json',
        }

        # Realizar la solicitud POST
        response = requests.post(url, data=json.dumps(data), headers=headers)

        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            # Procesar la respuesta
            respuesta = response.json()  # o response.text si la respuesta es en texto plano/XML
            print(respuesta)
        else:
            print(f"Error en la solicitud: {response.status_code} - {response.text}")



    def serie(self):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay serie')
        cfe = eval(self.cfe)
        if self.cfe_type in ['111', '112']:
            tag = 'eFact'
        elif self.cfe_type in ['101', '102']:
            tag = 'eTck'
        elif self.cfe_type in ['182']:
            tag = 'eResg'
        else:
            tag = 'eTck'
        serie = cfe['CFE'][tag]['Encabezado']['IdDoc']['Serie']
        return serie

    def numero_cfe(self):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay serie')
        cfe = eval(self.cfe)
        if self.cfe_type in ['111', '112']:
            tag = 'eFact'
        elif self.cfe_type in ['101', '102']:
            tag = 'eTck'
        elif self.cfe_type in ['182']:
            tag = 'eResg'
        else:
            tag = 'eTck'
        numero_cfe = cfe['CFE'][tag]['Encabezado']['IdDoc']['Nro']
        return numero_cfe

    def serie_recibido(self, cfe_type):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay serie')
        cfe = eval(self.cfe)
        if cfe_type in ['111', '112']:
            tag = 'eFact'
        elif cfe_type in ['101', '102']:
            tag = 'eTck'
        elif cfe_type in ['182']:
            tag = 'eResg'
        else:
            tag = 'eTck'
        serie = cfe['CFE'][tag]['Encabezado']['IdDoc']['Serie']
        return serie

    def numero_cfe_recibido(self, cfe_type):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay número de cfe')
        cfe = eval(self.cfe)
        if cfe_type in ['111', '112']:
            tag = 'eFact'
        elif cfe_type in ['101', '102']:
            tag = 'eTck'
        elif cfe_type in ['182']:
            tag = 'eResg'
        else:
            tag = 'eTck'
        numero_cfe = int(cfe['CFE'][tag]['Encabezado']['IdDoc']['Nro'])
        return numero_cfe

    # def get_line_type(self, line):
    #     if line.filtered(lambda x: x.display_type == 'product' and x.price_unit and x.quantity > 0):
    #         return 'line_product'
    #
    #     if line.filtered(lambda x: x.display_type == 'line_section'):
    #         return 'line_section'
    #
    #     if line.filtered(lambda x: x.display_type == 'line_note'):
    #         return 'line_note'
    #
    #     if line.filtered(lambda x: x.display_type == 'product' and not x.price_unit and not x.quantity > 0):
    #         return 'line_other'

    def get_line_type(self, line):
        if line.filtered(lambda x: x.display_type == 'product' and x.price_unit and x.quantity > 0):
            return 'line_product'

        if line.filtered(lambda x: x.display_type == 'line_section'):
            return 'line_section'

        if line.filtered(lambda x: x.display_type == 'line_note'):
            return 'line_note'

        if line.filtered(lambda x: x.display_type == 'product' and not x.price_unit and not x.quantity > 0):
            return 'line_other'




    def carga_datos_firma(self, sign_result):
        res = super(AccountMove, self).carga_datos_firma()

        def get_serie(cfe, cfe_type):
            if not cfe_type:
                    raise ValidationError(f'No se pudo extraer cfe_type {cfe_type}')
            if cfe_type in ['111', '112']:
                tag = 'eFact'
            elif cfe_type in ['101', '102']:
                tag = 'eTck'
            elif cfe_type in ['182']:
                tag = 'eResg'
            else:
                tag = 'eTck'

            return cfe['CFE'][tag]['Encabezado']['IdDoc']['Serie']

        def get_numero_cfe(cfe, cfe_type):
            if cfe_type in ['111', '112']:
                tag = 'eFact'
            elif cfe_type in ['101', '102']:
                tag = 'eTck'
            elif cfe_type in ['182']:
                tag = 'eResg'
            else:
                tag = 'eTck'
            return int(cfe['CFE'][tag]['Encabezado']['IdDoc']['Nro'])

        if self.payment_id:
            cfe_type = self.payment_id.l10n_latam_document_type_id.dgi_cfe_type
        else:
            cfe_type = self.l10n_latam_document_type_id.dgi_cfe_type

        cfe_serie = get_serie(cfe=sign_result.get('xmlcfe', {}), cfe_type=cfe_type)
        cfe_numero = get_numero_cfe(cfe=sign_result.get('xmlcfe', {}), cfe_type=cfe_type)
        cfe_hash = sign_result.get('hashcfe')
        self.cfe_type = cfe_type
        self.cfe_hash = cfe_hash
        self.cfe_serie_num = f"{cfe_type}-{cfe_serie}-{cfe_numero}"
        self.cfe_fecha_hora_firma = sign_result.get('fechafirma')
        self.cfe_cae_from = sign_result.get('nrocaeini')
        self.cfe_cae_to = sign_result.get('nrocaefin')
        self.cfe_cae_exp_date = sign_result.get('caefchven')
        self.cfe_cae_auth_date = sign_result.get('fechacfe')

        try:
            self.name = self.cfe_serie_num
        except Exception as error:
            self._cr.commit()
            print(error)
        """""
        self.cfe_url_qr = sign_result.get('a:DatosQr', False)
        if self.cfe_url_qr:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=20, border=4)
            qr.add_data(self.cfe_url_qr)
            qr.make(fit=True)
            img = qr.make_image()
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue())
            self.qr_img = img_str
        """""
        return res

    def genera_xml_y_firma_factura(self):
        print('entramos a la funcion genera_xml_y_firma_factura')
        payment = self.payment_id
        if not payment:
            if not self.cfe_emitido:
                self.cfe_emitido = self._facturar()
        if payment:
            if not payment.cfe_emitido:
                payment.cfe_emitido = self._facturar()
                if payment.cfe_emitido and payment.es_resguardo and not payment.anulacion_resguardo:
                    if payment.dgi_retention_code_id:
                        payment.dgi_retention_code_id.retention_rate = payment.dgi_retention_rate




    def _facturar(self):
        self.validar_datos()
        has_payment = self.payment_id
        company = self.env.user.company_id
        cfe_base_url_parm = self.get_cfe_base_url_parm()
        cfe_base_url = self.get_param(param=cfe_base_url_parm)
        full_url = cfe_base_url
        self.check_connection(url=full_url)
        docs = self
        if has_payment:
            cfe_type = int(docs.payment_id.l10n_latam_document_type_id.dgi_cfe_type)
        else:
            cfe_type = int(docs.l10n_latam_document_type_id.dgi_cfe_type)

        if not self.dgi_sucursal_id and has_payment:
            self.dgi_sucursal_id = has_payment.dgi_sucursal_id
        dgi_sucursal_id = self.dgi_sucursal_id.sucursal_code

        if not dgi_sucursal_id:
            raise ValidationError('No se ha configurado la sucursal para la compañía ' + company.name)

        if not self.punto_emision_id and has_payment:
            self.punto_emision_id = has_payment.punto_emision_id
        dgi_punto_emision = self.punto_emision_id.emision_code

        if not dgi_punto_emision:
            raise ValidationError('No se ha configurado el punto de emisión para la compañía ' + company.name)


        docargs = {
            'doc_ids': [self.id],
            'doc_model': 'account.move',
            'docs': docs,
            'cfe_type': cfe_type,
            'float_round': float_round,
        }


        nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_xml_entrada'
        view = self.env.ref(nombre_vista)
        start_cdata_placeholder = '<startcdata></startcdata>'
        start_cdata = "<![CDATA["
        end_cdata = "]]>"
        end_cdata_placeholder = '<endcdata></endcdata>'
        now = datetime.datetime.now()
        if self.payment_id.es_resguardo and self.invoice_date != self.payment_id.date:
            self.invoice_date = self.payment_id.date
        elif not self.invoice_date:
            self.invoice_date = now
        try:
            cfe = str(view._render_template(nombre_vista, docargs))
        except Exception as error:
            raise ValidationError(error)
        cfe = cfe.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
        cfe = f"""
            {cfe}
        """
        cfe = cfe.encode('UTF-8')
        cfexml = re.sub(r'[\n\r|]|  ', '', cfe.decode('UTF-8'))
        soap_client = Client(full_url)

        _logger.info(cfe)
        self.data_sent = cfexml
        self._cr.commit()
        try:
            response = soap_client.service.GRABAR(cfexml)
            response_dict = xmltodict.parse(response)
            resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
            mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
            valor = xmltodict.parse(response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor'))
            result = valor.get('XML_ResultadoWSGrabarCFE')
            cfe = result.get('xmlcfe')
        except Exception as error:
            raise ValidationError(f'Erro al firmar {error}')
        _logger.info(response)
        self.cfe = cfe
        if resultado == '1':
            _logger.info("""
            ****************************************************
            ****************************************************
            ****************************************************
            *****************FIRMA EXITOSA**********************
            ****************************************************
            ****************************************************
            ****************************************************
            """)
            self.carga_datos_firma(sign_result=result)
            if cfe_type in [182]:
                self.payment_id.cfe = cfe
                self.payment_id.carga_datos_firma_payment(sign_result=result)
            try:
                self.estado_cfe()
            except Exception as error:
                _logger.info(error)
                self._cr.commit()
            try:
                if has_payment:
                    has_payment.obtener_pdf()
                else:
                    self.obtener_pdf()
            except Exception as error:
                _logger.info(error)
                self._cr.commit()
            return True
        else:
            raise ValidationError(mensaje)
