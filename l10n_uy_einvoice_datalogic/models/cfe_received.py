# -*- coding: utf-8 -*-
import qrcode
from io import StringIO, BytesIO
from odoo import models, fields, api, exceptions, SUPERUSER_ID
from odoo.exceptions import ValidationError
import requests
import base64
import datetime
import json
import xmltodict
import logging
from zeep import Client

_logger = logging.getLogger("SERVICIOS DE FACTURACION ELECTRONICA")
import re
import xml.etree.ElementTree as ET
import requests
from datetime import datetime, timedelta
from ...tools import production_check

class CFEReceivedInvoiceValues(models.Model):
    _inherit = 'cfe.received.invoice.values'

    procesado_message = fields.Char(string='Resultado procesamiento', readonly=True)


    def action_retry_create_invoice(self):
        res = super(CFEReceivedInvoiceValues, self).action_retry_create_invoice()
        try:
            invoice_id = self.cfe_received_id.cfe_create_invoice(xmlcfefirmado=eval(self.invoice_value), line=self)
            if invoice_id:
                self.cfe_received_id.invoice_ids += invoice_id
                self.cfe_received_id.partner_ids += invoice_id.partner_id
                self.invoice_id = invoice_id.id
                _logger.info(f' CFE Recibido creado {invoice_id}')
                print(f' CFE Recibido creado {invoice_id.name}')
                self.state = 'done'
                self.message = f'Comprobante creado correctamente'
        except Exception as error:
            _logger.info(f'Error al crear el comprobante {error}')
            self.state = 'fail'

        return res

class CFEReceived(models.Model):
    _inherit = 'cfe.received'

    last_numero_cfe = fields.Integer(string='Ultimo número CFE', default=0)
    last_serie_cfe = fields.Char(string='Ultima serie CFE')
    max_records = fields.Integer(string='Número máximo de comprobantes', default=10000)
    explanation_text = fields.Html(string='Explicación', store=False, compute='_compute_explanation_text')

    @api.depends('state', 'company_id')
    def _compute_explanation_text(self):
        for rec in self:
            cfe_base_url_parm = self.env["account.move"].get_cfe_base_url_parm()
            url = self.get_param(param=cfe_base_url_parm)
            # marcado_place_holder = 'PROCESADO POR ERP' if cfe_base_url_parm == 'url_produccion' else 'NO PROCESADO POR ERP'
            marcado_place_holder = 'PROCESADO POR ERP'
            rec.explanation_text = f'<div class="o_editor_banner o_not_editable lh-1 d-flex align-items-center alert alert-info pb-0 pt-3" data-oe-protected="true"><i class="fs-4 fa fa-info-circle mb-3"></i><div class="w-100 px-3" data-oe-protected="false"><p>Se descargarán los comprobantes que se encuentren en estado&nbsp;2-No procesado, 3-Procesado con errores, 4-Procesado sin modelo. Desde la URL {url}</p><p>Luego serán marcados como {marcado_place_holder}</p></div></div><p><br></p>'

    def action_download_documents(self):
        res = super(CFEReceived, self).action_download_documents()
        try:
            self.obtener_comprobantes()
            if self.state == 'draft':
                self.state = 'data_downloaded'
        except Exception as error:
            _logger.error(f'Error al descargar los comprobantes {error}')
        return res

    def get_param(self, param=None):
        self = self.sudo()
        company = self.env.company
        result = getattr(company, param)
        if not result:
            raise ValidationError('No se ha configurado el parámetro ' + param)
        return result

    def remove_prefix(self, original_dict, prefix=None):
        if isinstance(original_dict, dict):
            return {key.replace(prefix, ''): self.remove_prefix(value, prefix) for key, value in original_dict.items()}
        elif isinstance(original_dict, list):
            return [self.remove_prefix(item, prefix) for item in original_dict]
        else:
            return original_dict

    def normalize_keys(self, dictionary):
        for key, value in dictionary.items():
            prefix = key.split('CFE')[0]
            break
        normalized_dictionary = self.remove_prefix(dictionary, prefix=prefix)
        return normalized_dictionary


    def remove_ns_prefix(self, original_dict):
        if isinstance(original_dict, dict):
            return {key.replace('ns0:', ''): self.remove_ns_prefix(value) for key, value in original_dict.items()}
        elif isinstance(original_dict, list):
            return [self.remove_ns_prefix(item) for item in original_dict]
        else:
            return original_dict



    def prepare_cfe_received_values(self, values=None):
        invoice_obj = self.env['account.move']
        cfe_received_values_obj = self.env['cfe.received.invoice.values']
        xml_resultado = values.get('XMLResultado', {})
        recibidos_values = xml_resultado.get('Recibidos', {}) if not isinstance(xml_resultado.get('Recibidos', {}), type(None)) else {}
        recibidos = recibidos_values.get('Recibido', [])
        if not recibidos:
            return self.write({'state': 'fail'})
        for recibido in recibidos:
            if not isinstance(recibido, dict):
                continue
            uuid = recibido['Empresa'] + recibido['TipoDocumentoCFE'] + recibido['SerieDocumentoCFE'] + recibido['ComprobanteCFE'] + recibido['FechaCFE']
            invoice_id = invoice_obj.search([('uuid', '=', uuid)], limit=1)
            if invoice_id:
                _logger.info(f'Factura ya creada {invoice_id}')
                print(f'Factura ya creada {invoice_id}')
                values = {
                    'cfe_received_id': self.id,
                    'invoice_value': xmlcfefirmado,
                    'uuid': uuid,

                }
                new_cfe_received_values = cfe_received_values_obj.create(values)

                new_cfe_received_values.state = 'done'
                new_cfe_received_values.invoice_id = invoice_id
                self.action_marcar_cfe_procesado(documents=[invoice_id])
                continue
            cfe = recibido['XMLCFE']
            xmlcfefirmado = self.normalize_keys(xmltodict.parse(cfe))
            xmlcfefirmado['uuid'] = uuid
            values = {
                'cfe_received_id': self.id,
                'invoice_value': xmlcfefirmado,
                'uuid': uuid,

            }
            if not cfe_received_values_obj.search([('uuid', '=', uuid), ('cfe_received_id', '=', self.id)], limit=1):
                new_cfe_received_values = cfe_received_values_obj.create(values)
                print(f'creamos valores de cfe recibido {new_cfe_received_values.id}')
            else:
                print(f'omitimos valores de cfe recibido {uuid}, ya existe')
        return True

    def has_cobranza_invoice(self, xml_cfe):
        """
        Nos fijamos en el cabezal del documento si tiene
        IndCobPropia  == '1' para indicar que la factura es de cobranza
        """
        return xml_cfe.get('eFact', {}).get('Encabezado', {}).get('IdDoc', {}).get('IndCobPropia', False) == '1'



    def cfe_create_invoice(self, xmlcfefirmado=None, line=None, is_production=None):
        self = self.sudo().with_company(self.company_id).with_user(SUPERUSER_ID)
        invoice_obj = self.env['account.move']
        supplier_pricelist_id = self.env['product.supplierinfo']
        uuid = xmlcfefirmado.get('uuid', False)
        sign = 1
        cfe_base_url_parm = self.env["account.move"].get_cfe_base_url_parm()
        url = self.get_param(param=cfe_base_url_parm)
        # marcar_procesado = True if cfe_base_url_parm == 'url_produccion' else False
        product_id = self.env['product.product'].sudo()
        partner_obj = self.env['res.partner'].sudo()
        tax_obj = self.env['account.tax'].sudo()
        invoice_id = invoice_obj.search_count([('uuid', '=', uuid)], limit=1)
        if invoice_id:
            invoice_id = invoice_obj.search([('uuid', '=', uuid)], limit=1)
            _logger.info(f'Factura ya creada {invoice_id}')
            print(f'Factura ya creada {invoice_id}')
            # if marcar_procesado:
            #     self.action_marcar_cfe_procesado(documents=[invoice_id])
            self.action_marcar_cfe_procesado(documents=[invoice_id])
            #self.action_marcar_cfe_procesado(documents=[invoice_id])
            #if not isinstance(is_production, bool):
                #is_production = production_check.es_produccion(self)

            #if is_production:
                #print("Marco como procesado")
                # self.action_marcar_cfe_procesado(documents=[invoice_id])

            return invoice_id
        # Extraer información relevante del XML
        try:
            xml_cfe = xmlcfefirmado['CFE']
            if not xml_cfe.get('eFact', False):
                print(f'Ignoramos los comprobantes que no son factura de proveedor {uuid}')
                _logger.info(f'Ignoramos los comprobantes que no son factura de proveedor {uuid}')
                line.message_post(body=f'Ignoramos los comprobantes que no son factura de proveedor {uuid}')
                line.message = f'Ignoramos los comprobantes que no son factura de proveedor {uuid}'
                line.state = 'omitted'
                return False
            factura_cobranza = self.has_cobranza_invoice(xml_cfe)
            if factura_cobranza:
                print(f'Ignoramos las facturas de cobranza {uuid}')
                _logger.info(f'Ignoramos las facturas de cobranza {uuid}')
                line.message_post(body=f'Ignoramos las facturas de cobranza {uuid}')
                line.message = f'Ignoramos las facturas de cobranza {uuid}'
                line.state = 'omitted'
                return False
            encabezado = xmlcfefirmado['CFE']['eFact']['Encabezado']
            purchase_order = encabezado.get('CompraID', '')
        except Exception as error:
            line.message_post(body=f'Error al extraer información relevante del XML: {error} \n {xmlcfefirmado}')
            print(f'Error al extraer información relevante del XML: {error} \n {xmlcfefirmado}')
            _logger.info(f'Error al extraer información relevante del XML: {error} \n {xmlcfefirmado}')
            line.message = f'Error al extraer información relevante del XML: {error} \n {xmlcfefirmado}'
            line.state = 'fail'
            return False
        tipo_documento = encabezado['IdDoc']['TipoCFE']
        if tipo_documento == '111':
            move_type = 'in_invoice'
        elif tipo_documento == '112':
            move_type = 'in_refund'
        else:
            move_type = 'in_invoice'

        emisor = encabezado['Emisor']
        id_doc = encabezado['IdDoc']
        serie = id_doc['Serie']
        numero = encabezado['IdDoc']['Nro']
        ref = serie + '-' + numero
        precio_con_iva = id_doc.get('MntBruto', False) == '1'
        #name
        #[secuencia] - [referencia del documento] (refrencia del documento es serie-numero)
        sequence = self.env['ir.sequence'].next_by_code('move.received.sequence')
        name = ref + '-' + sequence
        #move.received.sequence
        journal_id = self.company_id.cfe_received_journal_id.id
        # si la forma de pago es 1 (contado) colocamos el payment_term y la fecha, si no colocamos solo la fecha
        immediate_payment = encabezado['IdDoc']['FmaPago'] == '1'
        immediate_payment_term_id = self.env.ref('account.account_payment_term_immediate') if immediate_payment else False
        ruc_emisor = emisor['RUCEmisor']
        fecha_factura = encabezado['IdDoc'].get('FchEmis', False)
        fecha_vencimiento = encabezado['IdDoc'].get('FchVenc', False)
        totales = encabezado['Totales']
        moneda = totales['TpoMoneda']
        currency_id = self.env['res.currency'].search([('name', '=', moneda)], limit=1)
        items = xmlcfefirmado['CFE']['eFact']['Detalle']['Item']
        # Buscar el partner (proveedor) en Odoo
        partner_id = partner_obj.search([('vat', '=', ruc_emisor), ('parent_id', '=', False)])
        if len(partner_id) > 1:
            message = f"Se han encontrado múltiples proveedores con el mismo RUC ({ruc_emisor}): {', '.join([x.name for x in partner_id])}."
            line.partner_ids += partner_id
            self.message_post(body=message)
            line.message_post(body=message)
            line.message = message
            print(message)
            _logger.info(f'Error al buscar el partner: {message}')
            line.state = 'fail'
            return False
        if not partner_id:
            try:
                city_id = self.env['res.country.city'].search([('name', 'like', emisor.get('Ciudad', '').title())], limit=1)
            except Exception as error:
                city_id = self.env.ref('l10n_uy_einvoice_base.montevideo_ciudad')
            partner_id = self.env['res.partner'].create({
                'name': emisor['RznSoc'],
                'social_reason': emisor['RznSoc'],
                'vat': emisor['RUCEmisor'],
                'company_type': 'company',
                'street': emisor.get('DomFiscal', ''),
                'city_id': city_id.id,
                'country_id': self.env.ref('base.uy').id,
                'l10n_latam_identification_type_id': self.env.ref('l10n_uy_einvoice_base.dgi_document_type_ruc').id,
                'created_from_cfe': True
            })
            try:
                self.env.cr.commit()
                _logger.info(f'COMMITEAMOS')
                partner_id._consultar_partner_ruc()
                _logger.info(f'Proveedor creado {partner_id.name}')
                print(f'Proveedor creado {partner_id.name}')
            except Exception as error:
                _logger.info(f'Error al consultar el RUC {error}')
                print(f'Error al consultar el RUC {error}')

        if partner_id.company_id:
            partner_id.company_id = False
            self.env.cr.commit()
        # Crear líneas de factura
        invoice_lines = []
        if not isinstance(items, list):
            items = [items]
        total_items = len(items)
        for item_count, item in enumerate(items, start=1):
            ##manejo de descuentos##
            discount = 0.0
            if item.get('DescuentoPct', False):
                discount = eval(item.get('DescuentoPct'))

            print(f'vamos en el item {item_count}/{total_items}')
            _logger.info(f'vamos en el item {item_count}/{total_items}')
            ind_fact = item['IndFact']
            # Determinar el impuesto basado en IndFact
            indicador = self.env['invoicing.indicator'].search([('code','=', ind_fact)])
            sign = eval(indicador.sign)

            tax_ids = indicador._get_supplier_tax()
            try:
                product_item = item.get('CodItem', {})
                if isinstance(product_item, list):
                    code_type = product_item[0].get('TpoCod', False)
                    product_code = product_item[0].get('Cod', {})

                else:
                    code_type = product_item.get('TpoCod', False)
                    product_code = product_item.get('Cod', {})


                if code_type and code_type == 'GTIN13':
                    product_id = self.env['product.product'].search([('barcode', '=', product_code)], limit=1)
                    if not product_id:
                        partner_cfe_received = partner_id.cfe_received_ids.filtered(lambda x: x.invoicing_indicator_id == indicador)
                        if partner_cfe_received:
                            product_id = partner_cfe_received.product_id
                            tax_ids = partner_cfe_received.invoicing_indicator_id._get_supplier_tax()

                        else:
                            product_id = indicador.product_id
                            tax_ids = indicador._get_supplier_tax()
                elif code_type and code_type == 'INT1':
                    supplier_pricelist_id = supplier_pricelist_id.search([('product_code', '=', product_code), ('partner_id', '=', partner_id.id)], limit=1)
                    product_id = supplier_pricelist_id.product_id or supplier_pricelist_id.product_tmpl_id.product_variant_id
                    if not product_id:
                        partner_cfe_received = partner_id.cfe_received_ids.filtered(lambda x: x.invoicing_indicator_id == indicador)
                        if partner_cfe_received:
                            product_id = partner_cfe_received.product_id
                            tax_ids = partner_cfe_received.invoicing_indicator_id._get_supplier_tax()

                        else:
                            product_id = indicador.product_id
                            tax_ids = indicador._get_supplier_tax()
                elif code_type and code_type != 'INT1' and code_type != 'GTIN13' or not code_type:
                    partner_cfe_received = partner_id.cfe_received_ids.filtered(lambda x: x.invoicing_indicator_id == indicador)
                    if partner_cfe_received:
                        product_id = partner_cfe_received.product_id
                        tax_ids = partner_cfe_received.invoicing_indicator_id._get_supplier_tax()

                    else:
                        product_id = indicador.product_id
                        tax_ids = indicador._get_supplier_tax()
            except Exception as error:
                self.message_post(body=f'Error al obtener el código del producto: {error}')
                line.message_post(body=f'Error al obtener el código del producto: {error}')
                line.message = f'Error al obtener el código del producto: {error}'
                line.state = 'fail'
                return False
            cantidad = float(item['Cantidad'])
            precio_unitario = float(item['PrecioUnitario'])
            if precio_con_iva and indicador._get_supplier_tax().amount:
                tax_amount = indicador._get_supplier_tax().amount
                domain = [('price_include', '=', True), ('amount', '=', tax_amount), ('type_tax_use', '=', 'purchase')]
                tax_ids = tax_obj.search(domain, limit=1)
                if not tax_ids:
                    msg = f'No se encontró un impuesto de compras de tasa {tax_amount} cuya configuración sea con impuesto incluido.'
                    print(msg)
                    _logger.info(msg)
                    line.message_post(body=msg)
                    line.message = msg
                    line.state = 'fail'
                    return False
            descripcion = item['NomItem']
            if not product_id:
                product_id = indicador.product_id

            invoice_line = (0, 0, {
                'product_id': product_id.id,
                'quantity': cantidad,
                'discount': discount,
                'price_unit': precio_unitario * sign,
                'name': descripcion,
                'company_id': self.company_id.id,
                'tax_ids': [(6, 0, tax_ids.ids)],
            })
            invoice_lines.append(invoice_line)

        # Crear la factura
        invoice_vals = {
            'name': name,
            'ref': ref,
            'partner_id': partner_id.id,
            'uuid': uuid,
            'move_type': move_type,
            'invoice_date': fecha_factura,
            'invoice_date_due': fecha_vencimiento,
            'invoice_payment_term_id': immediate_payment_term_id.id if immediate_payment else False,
            'currency_id': currency_id.id,
            'invoice_line_ids': invoice_lines,
            'cfe': xmlcfefirmado,
            'invoice_origin': purchase_order,
            'cfe_type_received': tipo_documento,
            'company_id': self.company_id.id,
            'cfe_emitido': True,
        }
        if journal_id:
            invoice_vals['journal_id'] = journal_id
        invoice_id = invoice_obj.with_context(dont_check_dates_sequence=True).create(invoice_vals)
        try:
            invoice_id.obtener_pdf_recibido(cfe_type=tipo_documento)
        except Exception as error:
            print(f'Error al obtener el pdf {error}')
            _logger.info(f'Error al obtener el pdf {error}')
        try:
            print(f'Comprobante creado {invoice_id}')
            # if marcar_procesado:
            #     self.action_marcar_cfe_procesado(documents=[invoice_id])
            self.action_marcar_cfe_procesado(documents=[invoice_id])
            """""
            if not isinstance(is_production, bool):
                is_production = production_check.es_produccion(self)
            if is_production:
                print("Marco como procesado")
                # self.action_marcar_cfe_procesado(documents=[invoice_id])
            """
        except Exception as error:
            print(f'Error al marcar el cfe como procesado {error}')
            _logger.info(f'Error al marcar el cfe como procesado {error}')
        return invoice_id



    def obtener_comprobantes(self, cfe_id_ids=None, last_numero_cfe=None, last_serie_cfe=None, max_records=None):
        last_numero_cfe = False
        last_serie_cfe = False
        max_records = self.max_records if self.max_records else 1000  # Puedes ajustar este valor según sea necesario
        total_comprobantes = 0
        all_values = []
        count = 0
        while True:
            count+=1
            docargs = {
                'doc_ids': [self.id],
                'doc_model': 'cfe.received',
                'docs': self,
                'company': self.company_id,
                'last_numero_cfe': False,
                'last_serie_cfe': False,
            }
            nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_recibidos'
            view = self.env.ref(nombre_vista)
            start_cdata_placeholder = '<startcdata></startcdata>'
            start_cdata = "<![CDATA["
            end_cdata = "]]>"
            end_cdata_placeholder = '<endcdata></endcdata>'

            cfe_request_template = str(view._render_template(nombre_vista, docargs))
            cfe_request = cfe_request_template.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
            cfe_request = f"{cfe_request}".encode('UTF-8')
            cfexml = re.sub(r'[\n\r|]|  ', '', cfe_request.decode('UTF-8'))
            cfe_base_url_parm = self.env["account.move"].get_cfe_base_url_parm()
            url = self.get_param(param=cfe_base_url_parm)
            soap_client = Client(url)
            _logger.info(cfe_request)
            try:
                response = soap_client.service.CONSULTARCFE(cfexml)
                response_dict = xmltodict.parse(response)
                resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
                mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
                values = xmltodict.parse(response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor'))

                if resultado != '1' or mensaje != 'Ok':
                    raise ValidationError(f'Error en la obtención de datos: {mensaje}')

                recibidos_values = values.get('XMLResultado', {}).get('Recibidos', {}) if not isinstance(values.get('XMLResultado', {}).get('Recibidos', {}), type(None)) else {}
                recibidos = recibidos_values.get('Recibido', [])

                if not recibidos or count == max_records:
                    break

                all_values.extend(recibidos)

                # Verifica si es necesario paginar
                total_comprobantes += len(recibidos)
                if len(recibidos) < max_records:
                    break  # No hay más comprobantes por descargar
                else:
                    last_comprobante = recibidos[-1]  # Rastrear el último comprobante para la próxima solicitud
                    last_numero_cfe = last_comprobante.get('ComprobanteCFE')
                    last_serie_cfe = last_comprobante.get('SerieDocumentoCFE')
                    self.write({'last_numero_cfe': last_numero_cfe, 'last_serie_cfe': last_serie_cfe})
                    self.env.cr.commit()  # Commit para evitar sobrecarga de la base
                    _logger.info(f"Página siguiente: descargados {total_comprobantes} comprobantes")

            except Exception as error:
                raise ValidationError(f'Error al obtener datos: {error}')

        if all_values:
            self.prepare_cfe_received_values(values={'XMLResultado': {'Recibidos': {'Recibido': all_values}}})
            _logger.info(f"Total de comprobantes descargados: {total_comprobantes}")
        else:
            self.write({'state': 'fail'})
            _logger.warning("No se descargaron comprobantes.")

        return True



    def action_marcar_cfe_procesado(self, documents=None):
        estado = '1'
        """
         1 – Procesado
         2 – No Procesado
         3 – Procesado Con Errores
         4 – Procesado Sin Modelo
        """
        for document in documents:
            line = self.invoice_values_ids.filtered(lambda x: x.invoice_id == document)
            if line:
                line = line[0]
            docargs = {
                'doc_ids': [self.id],
                'doc_model': 'cfe.received',
                'docs': self,
                'company': self.company_id,
                'documento': document,
                'estado': estado,
            }
            nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_recibido_marcar_cfe'
            view = self.env.ref(nombre_vista)
            start_cdata_placeholder = '<startcdata></startcdata>'
            start_cdata = "<![CDATA["
            end_cdata = "]]>"
            end_cdata_placeholder = '<endcdata></endcdata>'

            cfe_request_template = str(view._render_template(nombre_vista, docargs))

            cfe_request = cfe_request_template.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
            cfe_request = f"{cfe_request}".encode('UTF-8')
            cfexml = re.sub(r'[\n\r|]|  ', '', cfe_request.decode('UTF-8'))

            cfe_base_url_parm = self.env['account.move'].get_cfe_base_url_parm()
            url = self.get_param(param=cfe_base_url_parm)

            soap_client = Client(url)
            _logger.info(cfe_request)
            try:
                response = soap_client.service.MARCARCFE(cfexml)
                response_dict = xmltodict.parse(response)
                resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
                mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)

                if resultado == '1' and mensaje == 'Ok':
                    print(f'Comprobante marcado correctamente {document.name}')
                    _logger.info(f'Comprobante marcado correctamente {document.name}')
                    if line:
                        line.procesado_message = f'Comprobante marcado correctamente'

            except Exception as error:
                raise ValidationError(f'Error al obtener datos: {error}')

    def marcar_cfe_procesado(self):
        documents = self.invoice_values_ids.mapped('invoice_id')
        self.action_marcar_cfe_procesado(documents=documents)
        return True

    def action_create_invoices(self):
        ctx = self.env.context.copy()
        lines_state = ctx.get('lines_state', 'draft')
        commit_after = 30
        side_count = 0
        count = 0
        lines = self.invoice_values_ids.filtered(lambda x: x.state == lines_state)[:50]
        total = len(lines)
        self.invoice_ids += self.invoice_values_ids.mapped('invoice_id')

        # is_production = production_check.es_produccion(self)
        for cfe_received_values in lines:
            side_count += 1
            count += 1
            if side_count > commit_after:
                self.env.cr.commit()
                print('commit')
                side_count = 0
            print(f'vamos {count}/{total}')
            _logger.info(f'vamos {count}/{total}')
            try:
                # invoice_id = self.cfe_create_invoice(xmlcfefirmado=eval(cfe_received_values.invoice_value), line=cfe_received_values, is_production=is_production)
                invoice_id = self.cfe_create_invoice(xmlcfefirmado=eval(cfe_received_values.invoice_value), line=cfe_received_values)
                if invoice_id:
                    self.invoice_ids += invoice_id
                    self.partner_ids += invoice_id.partner_id
                    cfe_received_values.invoice_id = invoice_id.id
                    _logger.info(f' CFE Recibido creado {invoice_id}')
                    print(f' CFE Recibido creado {invoice_id.name}')
                    cfe_received_values.state = 'done'
                    cfe_received_values.message = f'Comprobante creado correctamente'
                # else:
                #     cfe_received_values.state = 'fail'
            except Exception as error:
                _logger.info(f'Error al crear el comprobante {error}')
                cfe_received_values.state = 'fail'
                continue
        if not self.invoice_values_ids.filtered(lambda x: x.state == 'draft'):
            self.state = 'done'
        return True

    def cfe_received_by_list(self):
        res = super(CFEReceived, self).action_download_documents()
        total_comprobantes = 0
        all_values = []
        lines = self.cfe_received_multi_ids.filtered(lambda x: x.state == 'draft')

        for contador, line in enumerate(lines):
            print(f'vamos  {line} de {len(lines)}')
            _logger.info(f'vamos  {contador} de {len(lines)}')
            docargs = {
                'doc_ids': [self.id],
                'doc_model': 'cfe.received',
                'docs': self,
                'company': self.company_id,
                'tipoCfe': line.tipoCfe,
                'serie': line.serieCfe,
                'numero': line.numeroCfe,
            }
            nombre_vista = 'l10n_uy_einvoice_datalogic.cfe_recibidos_by_list'
            view = self.env.ref(nombre_vista)
            start_cdata_placeholder = '<startcdata></startcdata>'
            start_cdata = "<![CDATA["
            end_cdata = "]]>"
            end_cdata_placeholder = '<endcdata></endcdata>'

            cfe_request_template = str(view._render_template(nombre_vista, docargs))
            cfe_request = cfe_request_template.replace(start_cdata_placeholder, start_cdata).replace(end_cdata_placeholder, end_cdata)
            cfe_request = f"{cfe_request}".encode('UTF-8')
            cfexml = re.sub(r'[\n\r|]|  ', '', cfe_request.decode('UTF-8'))

            url = self.get_param(param='url_produccion')
            soap_client = Client(url)
            _logger.info(cfe_request)
            try:
                response = soap_client.service.CONSULTARCFE(cfexml)
                response_dict = xmltodict.parse(response)
                resultado = response_dict.get('XMLRetorno', {}).get('Resultado', 0)
                mensaje = response_dict.get('XMLRetorno', {}).get('Descripcion', 0)
                values = xmltodict.parse(response_dict.get('XMLRetorno', {}).get('Datos', {}).get('Dato', {}).get('Valor'))

                if resultado != '1' or mensaje != 'Ok':
                    raise ValidationError(f'Error en la obtención de datos: {mensaje}')

                recibidos_values = values.get('XMLResultado', {}).get('Recibidos', {}) if not isinstance(values.get('XMLResultado', {}).get('Recibidos', {}), type(None)) else {}
                recibidos = recibidos_values.get('Recibido', [])

                if not recibidos or count == max_records:
                    break

                all_values.extend(recibidos)

                # Verifica si es necesario paginar
                total_comprobantes += len(recibidos)
                if len(recibidos) < max_records:
                    break  # No hay más comprobantes por descargar
                else:
                    last_comprobante = recibidos[-1]  # Rastrear el último comprobante para la próxima solicitud
                    last_numero_cfe = last_comprobante.get('ComprobanteCFE')
                    last_serie_cfe = last_comprobante.get('SerieDocumentoCFE')
                    self.write({'last_numero_cfe': last_numero_cfe, 'last_serie_cfe': last_serie_cfe})
                    self.env.cr.commit()  # Commit para evitar sobrecarga de la base
                    _logger.info(f"Página siguiente: descargados {total_comprobantes} comprobantes")

            except Exception as error:
                raise ValidationError(f'Error al obtener datos: {error}')

        if all_values:
            self.prepare_cfe_received_values(values={'XMLResultado': {'Recibidos': {'Recibido': all_values}}})
            _logger.info(f"Total de comprobantes descargados: {total_comprobantes}")
        else:
            self.write({'state': 'fail'})
            _logger.warning("No se descargaron comprobantes.")

        return True