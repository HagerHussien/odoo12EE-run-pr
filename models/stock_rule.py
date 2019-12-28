# -*- coding: utf-8 -*-

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round

from odoo.exceptions import UserError

from odoo import api, fields, models, registry, _, tools
from datetime import datetime
from dateutil.relativedelta import relativedelta

import logging

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_purchase_schedule_date(self, values):
        procurement_date_planned = fields.Datetime.from_string(values['date_planned'])
        schedule_date = (procurement_date_planned - relativedelta(days=values['company_id'].po_lead))
        return schedule_date

    def _prepare_purchase_order(self, values):
        schedule_date = self._get_purchase_schedule_date(values)

        return {
            'company_id': values['company_id'].id,
            'end_start': schedule_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'date_start': datetime.now(),
        }

    @api.multi
    def _run_buy(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        cache = {}
        domain = (
            ('state', '=', 'draft'),
        )
        pr = self.env['sprogroup.purchase.request'].sudo().search([dom for dom in domain])
        pr = pr[0] if pr else False
        cache[domain] = pr
        if not pr:
            vals = self._prepare_purchase_order(values)
            vals['name'] = origin
            vals['assigned_to'] = self._uid
            company_id = values.get('company_id') and values['company_id'].id or self.env.user.company_id.id
            pr = self.env['sprogroup.purchase.request'].with_context(force_company=company_id).sudo().create(vals)
            cache[domain] = pr
        elif not pr.name:
            if pr.name:
                if origin:
                    pr.write({'name': pr.name + ', ' + origin})
                else:
                    pr.write({'name': pr.name})
            else:
                pr.write({'name': origin})

        # Create Line
        pr_line = False
        for line in pr.line_ids:
            if line.product_id == product_id and line.product_uom_id == product_id.uom_pr_id:
                if line._merge_in_existing_line(product_id, product_qty, product_uom, location_id, name, origin,
                                                values):
                    vals = self._update_purchase_request_line(product_id, product_qty, product_uom, values, line,
                                                            self._uid.partner_id)
                    pr_line = line.write(vals)
                    break
        if not pr_line:
            vals = {}
            vals['product_qty'] = product_qty
            vals['product_id'] = product_id.id
            vals['name'] = product_id.name
            vals['request_id'] = pr.id
            vals['date_required'] = datetime.now()
            self.env['sprogroup.purchase.request.line'].sudo().create(vals)

