# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import api, fields, models, SUPERUSER_ID
from odoo.tests import Form
from math import radians, cos, sin, asin, sqrt


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    note = fields.Text('Terms and conditions from SO')
    title = fields.Text('title from SO')
    commitment_date = fields.Datetime('Delivery Date from SO')
    require_materials = fields.Boolean('Require Materials from SO')
    address_street = fields.Text('Address Street from SO')
    address_floor = fields.Text('Address Floor from SO')
    address_portal = fields.Text('Address Portal from SO')
    address_number = fields.Text('Address Number from SO')
    address_door = fields.Text('Address door from SO')
    address_stairs = fields.Text('Address Stairs from SO')
    address_zip_code = fields.Text('Address ZIP Code from SO')
    address_latitude = fields.Text('Address Geo Latitude from SO')
    address_longitude = fields.Text('Address Geo Longitude from SO')
    new_created = fields.Boolean('New Created from SO')
    new_chat = fields.Boolean('New Chat from SO')
    new_chat_purchase = fields.Boolean(default=False)
    date_notification = fields.Boolean(default=False)
    new_budget = fields.Boolean(default=False)
    extra_budget = fields.Boolean(default=False)
    distance = fields.Float(default=0)
    # paidout = fields.Boolean(default=False)
    # For determing if promotion po is expired
    expired = fields.Boolean(default=False)
    # For determing if po is completly finish
    finish = fields.Boolean(default=False)
    cash = fields.Boolean(default=False)  # For payment in cash
    anonimus_author = fields.Text('Anonimus author')
    anonimus = fields.Boolean(default=False)  # For determing So anonymus

    @api.model
    def create(self, values):
        purchase_order = super(PurchaseOrder, self).create(values)

        partner = purchase_order.partner_id

        lon1, lat1, lon2, lat2 = map(radians, [float(purchase_order.address_longitude.replace(',', '.')), float(
            purchase_order.address_latitude.replace(',', '.')), float(partner.address_longitude.replace(',', '.')), float(partner.address_latitude.replace(',', '.'))])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers. Use 3956 for miles
        purchase_order.distance = round((c * r), 3)

        return purchase_order

    def write(self, values):
        if values.get('finish'):
            # purchase_orders = self.env['purchase.order'].search([('origin', 'ilike', self.name)])
            self.env['bus.bus'].sendone(
                self._cr.dbname + '_' + str(self.partner_id.id),
                {'type': 'purchase_order_notification', 'action': 'finish', "order_id": self.id})

        result = super(PurchaseOrder, self).write(values)
        return result

    def button_cancel(self):
        # notify to client when vendor cancel
        sale_order = self.env['sale.order'].search(
            [('name', 'ilike', self.origin)])
        self.env['bus.bus'].sendone(
            self._cr.dbname + '_' + str(sale_order.partner_id.id),
            {'type': 'purchase_order_notification', 'action': 'canceled', "order_id": self.id, "origin": self.origin})
        # notify to vendor when client cancel
        self.env['bus.bus'].sendone(
            self._cr.dbname + '_' + str(self.partner_id.id),
            {'type': 'purchase_order_notification', 'action': 'canceled', "order_id": self.id, "origin": self.origin})
        if self.state == 'purchase':
            sale_order.po_agreement = False
        result = super(PurchaseOrder, self).button_cancel()
        self.sudo().unlink()
        return result

    def check_expired(self):
        purchase_orders = self.env['purchase.order'].search(
            [('partner_id.id', '=', 7)])
        for po in purchase_orders:
            if po.commitment_date != False:
                if datetime.now() > po.commitment_date and po.expired == False:
                    po.expired = True
        return True

    def _activity_cancel_on_sale(self):
        """ If some PO are cancelled, we need to put an activity on their origin SO (only the open ones). Since a PO can have
            been modified by several SO, when cancelling one PO, many next activities can be schedulded on different SO.
        """
        sale_to_notify_map = False

    def button_confirm(self):
        result = super(PurchaseOrder, self).button_confirm()
        self.new_created = True
        # cancel other orders related to same SO
        self.env['bus.bus'].sendone(
            self._cr.dbname + '_' + str(self.partner_id.id),
            {'type': 'purchase_order_notification', 'action': 'confirmed', "order_id": self.id, "origin": self.origin})
        purchase_orders = self.env['purchase.order'].search(
            [('id', 'not in', self.ids), ('origin', 'ilike', self.origin)])
        for order in purchase_orders:
            order.sudo().button_cancel()
        self.update_sale_order_lines()
        sale_order = self.env['sale.order'].search(
            [('name', 'ilike', self.origin)])
        sale_order.new_created = True
        sale_order.po_agreement = True
        return result

    def update_sale_order_lines(self):
        # update SO with new PO lines
        sale_order_lines = self.env['sale.order.line'].search(
            [('order_id.name', 'ilike', self.origin)])
        sale_order_line_ids = []
        for sale_order_line in sale_order_lines:
            sale_order_line_ids.append(sale_order_line.id)
        for purchase_order_line in self.order_line:
            if purchase_order_line.sale_line_id.id not in sale_order_line_ids:
                purchase_order_line.sudo()._sale_service_create_line()
        return True

    def create_full_invoice(self):
        action = self.action_view_invoice()
        invoice_form = Form(self.env['account.move'].with_user(SUPERUSER_ID).with_context(
            action['context']
        ))
        invoice = invoice_form.save()
        invoice.post()
        return invoice.id

    def set_state_sent(self):
        self.write({'state': "sent"})
        # add origin SO client to followers
        for order in self.filtered(lambda order: order.partner_id not in order.message_partner_ids):
            sale_order = self.env['sale.order'].search(
                [('name', 'ilike', order.origin)])
            order.message_subscribe(
                [order.partner_id.id, sale_order.partner_id.id])
            self.env['bus.bus'].sendone(
                self._cr.dbname + '_' + str(sale_order.partner_id.id),
                {'type': 'purchase_order_notification', 'action': 'accepted', "order_id": order.id, "origin": order.origin})
        return True

    def search_messages(self, domain, fields):
        return self.env['mail.message'].sudo().search_read(domain, fields)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        message = super(PurchaseOrder, self.with_context(
            mail_post_autofollow=True)).message_post(**kwargs)
        purchase_order = self.env['purchase.order'].search(
            [('id', '=', message.res_id)])
        purchase_order.new_chat = True
        sale_order = self.env['sale.order'].search(
            [('name', 'ilike', purchase_order.origin)])
        sale_order.new_chat = True
        for partner_id in self.message_partner_ids:
            if partner_id.id != self.env.user.partner_id.id:
                self.env['bus.bus'].sendone(
                    self._cr.dbname + '_' + str(partner_id.id),
                    {'type': 'message_notification', 'action': 'new', "message_id": message.id, "puchase_id": purchase_order.id, "sale_id": sale_order.id, "state": purchase_order.state})
        return message


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _sale_service_create_line(self):
        """ Create sale.order.line from purchase.order.line.
            :param
            :rtype: dict
        """
        self.ensure_one()

        # compute quantity from PO line UoM
        product_quantity = self.product_qty
        purchase_qty_uom = self.product_uom._compute_quantity(
            product_quantity, self.product_id.uom_po_id)

        sale_order = self.env['sale.order'].sudo().search(
            [('name', 'ilike', self.order_id.origin)])

        fpos = sale_order.fiscal_position_id
        taxes = fpos.map_tax(
            self.product_id.supplier_taxes_id) if fpos else self.product_id.supplier_taxes_id
        if taxes:
            taxes = taxes.filtered(
                lambda t: t.company_id.id == self.company_id.id)

        # compute unit price
        price_unit = 0.0

        price_unit = self.env['account.tax'].sudo()._fix_tax_included_price_company(
            self.price_unit, self.product_id.supplier_taxes_id, taxes, self.company_id)
        if sale_order.currency_id and self.currency_id != sale_order.currency_id:
            price_unit = self.currency_id.compute(
                price_unit, sale_order.currency_id)

        values = {
            'name': '[%s] %s' % (self.product_id.default_code, self.name) if self.product_id.default_code else self.name,
            'product_uom_qty': purchase_qty_uom,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_po_id.id,
            'price_unit': price_unit,
            'tax_id': [(6, 0, taxes.ids)],
            'order_id': sale_order.id,
            'purchase_line_ids': [(6, 0, self.ids)],
        }

        return self.env['sale.order.line'].sudo().create(values)

    @api.model
    def create(self, values):
        line = super(PurchaseOrderLine, self).create(values)
        if values.get('price_unit') != 0.0:
            purchase_order = self.env['purchase.order'].search(
                [('id', '=', line.order_id.id)])
            purchase_order.new_budget = True

            if purchase_order.state == 'purchase':
                purchase_order.extra_budget = True

        for partner_id in line.order_id.message_partner_ids:
            if partner_id.id != self.env.user.partner_id.id:
                self.env['bus.bus'].sendone(
                    self._cr.dbname + '_' + str(partner_id.id),
                    {'type': 'purchase_order_line_notification', 'action': 'new', "price_unit": line.price_unit, "product_id": line.product_id.id, "order_id": line.order_id.id, "origin": line.order_id.origin, "state": purchase_order.state})
        return line

    def write(self, values):
        line = super(PurchaseOrderLine, self).write(values)
        if type(line) != bool:
            for partner_id in line.order_id.message_partner_ids:
                if partner_id.id != self.env.user.partner_id.id:
                    purchase_order = self.env['purchase.order'].search(
                        [('id', '=', line.order_id.id)])
                    self.env['bus.bus'].sendone(
                        self._cr.dbname + '_' + str(partner_id.id),
                        {'type': 'purchase_order_line_notification', 'action': 'update', "line_id": line.id, "order_id": line.order_id.id, "state": purchase_order.state})
        return line
