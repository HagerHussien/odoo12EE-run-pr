# -*- coding: utf-8 -*-
from odoo import api, fields, models, registry, _, tools
from datetime import datetime
from dateutil.relativedelta import relativedelta

import logging

_logger = logging.getLogger(__name__)


class SprogroupPurchaseRequestLine(models.Model):
    _inherit = "sprogroup.purchase.request.line"

    def _merge_in_existing_line(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        if values.get('route_ids') and values['route_ids'] == self.env.ref('stock_dropshipping.route_drop_shipping'):
            return False
        return super(SprogroupPurchaseRequestLine, self)._merge_in_existing_line(
            product_id=product_id, product_qty=product_qty, product_uom=product_uom,
            location_id=location_id, name=name, origin=origin, values=values)

    @api.model
    def _get_date_planned(self, seller, pr=False):
        date_order = pr.date_start if pr else self.request_id.date_start
        if date_order:
            return date_order + relativedelta(days=seller.delay if seller else 0)
        else:
            return datetime.today() + relativedelta(days=seller.delay if seller else 0)

    def _update_purchase_request_line(self, product_id, product_qty, product_uom, values, line, partner):
        procurement_uom_po_qty = product_uom._compute_quantity(product_qty, product_id.uom_po_id)
        seller = product_id.with_context(force_company=values['company_id'].id)._select_seller(
            partner_id=partner,
            quantity=line.product_qty + procurement_uom_po_qty,
            date=line.request_id.date_order and line.request_id.date_order.date(),
            uom_id=product_id.uom_po_id)

        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, line.product_id.supplier_taxes_id, line.taxes_id, values['company_id']) if seller else 0.0
        if price_unit and seller and line.request_id.currency_id and seller.currency_id != line.request_id.currency_id:
            price_unit = seller.currency_id._convert(
                price_unit, line.request_id.currency_id, line.request_id.company_id, fields.Date.today())

        return {
            'product_qty': line.product_qty + procurement_uom_po_qty,
            'price_unit': price_unit,
        }