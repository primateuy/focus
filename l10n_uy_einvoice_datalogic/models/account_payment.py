# -*- coding: utf-8 -*-

import qrcode
from io import StringIO, BytesIO
from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
import requests
import base64
import datetime
import uuid as guid_generator
import json
import xmltodict
import logging
import re
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def numero_cfe(self):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay número de cfe')
        cfe = eval(self.cfe)
        return int(cfe['numero'])

    def serie(self):
        if not self.cfe:
            raise ValidationError(u'No se ha emitido el cfe, por lo tanto no hay serie')
        cfe = eval(self.cfe)
        return str(cfe['serie'])

    def obtener_pdf(self, raw_return=False):
        if not self.move_id.cfe_type:
            self.move_id.cfe_type = str(self.cfe_type)
        return self.move_id.with_context(payment_id=self.id).obtener_pdf(raw_return=raw_return)

    def estado_cfe(self):
        return self.move_id.with_context(payment_id=self.id).estado_cfe()

    def carga_datos_firma_payment(self, sign_result):
        res = super(AccountPayment, self).carga_datos_firma_payment()
        def get_serie(cfe, cfe_type):
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

    def facturar(self):
        move = self.move_id
        if not move.l10n_latam_document_type_id:
            move.l10n_latam_document_type_id = self.l10n_latam_document_type_id
            move.cfe_type = self.cfe_type
        move.genera_xml_y_firma_factura()

    def emitir_recibo(self):
        self.ensure_one()
