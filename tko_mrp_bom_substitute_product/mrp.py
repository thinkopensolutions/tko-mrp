# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    Thinkopen Brasil
#    Copyright (C) Thinkopen Solutions Brasil (<http://www.tkobr.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


import time
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.l10n_br_base.tools import fiscal
from odoo import tools, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class mrp_product_substitute(models.Model):
    _name = 'mrp.product.substitute'

    @api.multi
    def _get_available_qty(self):
        for substitute in self:
            product = substitute.product_id
            if substitute.substitute_product_id:
                product = substitute.substitute_product_id
            self.substitute = product.qty_available
            self.available_qty = product.qty_available

    # @api.v8
    # def get_substitute_lines(self, cr, uid, ids, line):
    #     substitute_lines = self.search(cr, uid, [('product_id', '=', line.product_id.id),
    #                                              ('production_id', '=', line.production_id.id), ('id', '!=', line.id)])
    #     return substitute_lines

    @api.multi
    def get_substitute_lines(self, line):
        substitute_lines = self.search([('product_id', '=', line.product_id.id),
                                                 ('production_id', '=', line.production_id.id), ('id', '!=', line.id)])
        return substitute_lines

    product_id = fields.Many2one('product.product', string='Product')
    substitute_product_id = fields.Many2one('product.product', string='Substitute')
    product_qty = fields.Float('Product Qty')
    available_qty = fields.Float('Available Qty',compute=_get_available_qty, store=True)
    # 'available_qty': fields.function(_get_available_qty, type='float', string='Available Qty', store=True),
    uom_id = fields.Many2one('product.uom', 'Unit of Measure')
    production_id = fields.Many2one('mrp.production', 'Production', required=True)
    produce = fields.Boolean('Produce')
    scheduled = fields.Boolean('Scheduled')  # set if line is scheduled
    state = fields.Selection([('d', 'Draft'), ('a', 'Available'), ('w', 'Waiting')], string='State',default="d")
    bom_line_id = fields.Many2one('mrp.bom.line', 'Bom Line')

class StockMove(models.Model):
    _inherit = 'stock.move'

    substitute_product_id = fields.Many2one('product.product', 'Substitute Product')


class mrp_production(models.Model):
    _inherit = 'mrp.production'

    substitute_lines = fields.One2many('mrp.product.substitute', 'production_id', string='Substitute Lines')
    computed_substitute = fields.Boolean('Computed', copy=False)

    @api.multi
    def bom_id_change(bom_id):
        res = super(mrp_production, self).bom_id_change(bom_id)
        res['value'].update({'computed_substitute': False})
        return res

    @api.multi
    def action_compute_substitute(self, properties=None):
        results = []
        bom_obj = self.env['mrp.bom']
        bom_line_obj = self.env['mrp.bom.line']
        uom_obj = self.env['product.uom']
        substitute_obj = self.env['mrp.product.substitute']
        for production in self:
            # unlink product_lines
            for line in production.substitute_lines:
                line.unlink()
            # substitute_obj.unlink([line.id for line in production.substitute_lines])

            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = bom_obj._bom_find(product=production.product_id,picking_type = self.picking_type_id, company_id=self.company_id.id)
                if bom_id:
                    bom_point = bom_obj.browse(bom_id)
                    routing_id = bom_point.routing_id.id or False
                    self.write([production.id], {'bom_id': bom_id, 'routing_id': routing_id})

            if not bom_id:
                raise ValidationError(_("Cannot find a bill of material for this product."))
            else:
                checked_products = []
                for bom_line in bom_obj.browse(bom_id).bom_line_ids:
                    if not bom_line.substitute_product_id and bom_line.product_id.id not in checked_products:
                        # if bomline with product already not checked then create line for this
                        substitute_obj.create({
                            'product_id': bom_line.product_id.id,
                            'substitute_product_id': bom_line.substitute_product_id and bom_line.substitute_product_id.id,
                            'uom_id': bom_line.product_uom_id.id,
                            'production_id': production.id,
                            'product_qty': production.product_qty * bom_line.product_qty,
                            'bom_line_id': bom_line.id,
                        })
                        # check substitute lines for current product
                        substitute_products = bom_line_obj.search([('bom_id', '=', bom_id), (
                        'substitute_product_id', '=', bom_line.product_id.id), ('id', '!=', bom_line.id)])
                        # create substitute lines for substitute pro
                        if len(substitute_products):
                            for bom_line in bom_line_obj.browse(substitute_products):
                                substitute_obj.create({
                                    'product_id': bom_line.substitute_product_id and bom_line.substitute_product_id.id,
                                    'substitute_product_id': bom_line.product_id.id,
                                    'uom_id': bom_line.product_uom_id.id,
                                    'production_id': production.id,
                                    'product_qty': production.product_qty * bom_line.product_qty,
                                    'bom_line_id': bom_line.id,
                                })

            self.check_availability_substitute()
            self.write({'computed_substitute': True})
        return True

    @api.multi
    def check_availability_substitute(self):
        substitute_obj = self.env['mrp.product.substitute']
        context = self._context
        for production in self:
            for line in production.substitute_lines:
                # recompute qty available of product in line
                qty = line.with_context(context)._get_available_qty()
                required_qty = line.product_qty
                available_qty = line.product_id.qty_available
                if not line.substitute_product_id:

                    # if available qty is negative set it to zero
                    if available_qty < 0:
                        available_qty = 0
                    # search qty of susbstitute lines
                    # substitute_lines = []

                    substitute_lines = [x.id for x in line.get_substitute_lines(line)]
                    # substitute_lines = substitute_obj.search(cr, uid, [('product_id','=', line.product_id.id) , ('production_id', '=', production.id), ('id' ,'!=', line.id)])
                    if len(substitute_lines):
                        # set available qty to 0 even if exists because it is not allowed to count
                        if not line.produce:
                            available_qty = 0

                        for substitute in substitute_obj.browse(substitute_lines):
                            if substitute.produce:  # it is allowed to count qty
                                available_qty = available_qty + substitute.substitute_product_id.qty_available

                    substitute_lines.append(line.id)
                    # change state of lines
                    if available_qty < required_qty:
                        for substitute in substitute_obj.browse(substitute_lines):
                            substitute.write({'state':'w'})
                        # substitute_obj.write(substitute_lines, {'state': 'w'})
                    else:
                        for substitute in substitute_obj.browse(substitute_lines):
                            substitute.write({'state':'a'})
                        # substitute_obj.write(cr, uid, substitute_lines, {'state': 'a'})

            # for line in production.substitute_lines:
            #     if line.state == 'w':
            #         for line in production.product_lines:
            #             line.unlink()
            #         return False
            properties = []
            self.action_compute(properties)
            # TODO call method here to fill scheduled products
        return True

    @api.model
    def action_produce(self, production_id, production_qty, production_mode,
                       wiz=False):
        production = self.browse(production_id)
        done_moves = production.move_finished_ids.filtered(
            lambda r: r.state == 'done')
        for move in production.move_finished_ids:
            prod_lots = move.lot_ids
            prod_lots.write({'bom_id': production.bom_id.id})
        return {}

    @api.multi
    def compute_substitute_lines(self, bom_id):
        result = []
        substitute_obj = self.env['mrp.product.substitute']
        if not bom_id:
            return False
            # raise warning
        for production in self:
            for line in production.substitute_lines:
                if not line.scheduled:
                    # search including current record because we might need it for compute qty of products
                    substitute_lines = substitute_obj.search([('product_id', '=', line.product_id.id),
                                                                       ('production_id', '=', production.id)])
                    if len(substitute_lines) > 1:  # there are other substitute check which one is asked to consume
                        available_qty = 0.0
                        substitute_dict = {}  # this dict will keep record of how many substitute lines are required for qty_available > qty_required

                        for line in substitute_obj.browse(substitute_lines):
                            if line.produce:
                                if not line.substitute_product_id and line.product_id.qty_available > 0:  # check qty of primary product
                                    available_qty = available_qty + line.product_id.qty_available
                                    substitute_dict[line] = line.product_id.qty_available
                                    if available_qty >= line.product_qty:
                                        # append line in result
                                        result.append({
                                            'name': line.bom_line_id.product_id.name,
                                            'product_id': line.bom_line_id.product_id.id,
                                            'product_qty': line.product_qty,
                                            'product_uom': line.bom_line_id.product_uom_id.id,
                                            'product_uos_qty': line.bom_line_id.product_uos and line.bom_line_id.product_uos_qty * factor,
                                                # line.bom_line_id.product_efficiency,line.bom_line_id.product_rounding) or False,
                                            'product_uos': line.bom_line_id.product_uos and line.bom_line_id.product_uos.id or False,
                                            'substitute_product_id': line.bom_line_id.substitute_product_id and line.bom_line_id.substitute_product_id.id,
                                        })
                                        substitute_obj.write(cr, uid, substitute_lines, {'scheduled': True})
                                        break

                                elif line.substitute_product_id.qty_available > 0:  # check qty of substitute product
                                    substitute_dict[line] = line.substitute_product_id.qty_available
                                    # if old available qty and avalable qty of current line is enough then get actual qty required from current line
                                    if available_qty + line.substitute_product_id.qty_available >= line.product_qty:
                                        substitute_dict[line] = line.product_qty - available_qty
                                        # append line in result
                                        for line, qty in substitute_dict.iteritems():
                                            result.append({
                                                'name': line.bom_line_id.product_id.name,
                                                'product_id': line.bom_line_id.product_id.id,
                                                'product_qty': qty,
                                                'product_uom': line.bom_line_id.product_uom_id.id,
                                                'product_uos_qty': line.bom_line_id.product_uos and line.bom_line_id.product_uos_qty * factor,
                                                    # line.bom_line_id.product_efficiency, line.bom_line_id.product_rounding) or False,
                                                'product_uos': line.bom_line_id.product_uos and line.bom_line_id.product_uos.id or False,
                                                'substitute_product_id': line.bom_line_id.substitute_product_id and line.bom_line_id.substitute_product_id.id,
                                            })
                                        # substitute_obj.write(cr, uid, substitute_lines, {'scheduled': True})
                                        substitute_lines.write({'scheduled': True})
                                        break
                                    else:
                                        available_qty = available_qty + line.substitute_product_id.qty_available


                                        # append line in result
                    else:  # doesn't have substitute must be created with full qty
                        if line.product_id.qty_available >= line.product_qty:
                            result.append({
                                'name': line.bom_line_id.product_id.name,
                                'product_id': line.bom_line_id.product_id.id,
                                'product_qty': line.product_qty,
                                'product_uom': line.bom_line_id.product_uom_id.id,
                                'product_uos_qty': line.bom_line_id.product_uos and line.bom_line_id.product_uos_qty * factor,
                                 #line.bom_line_id.product_efficiency, line.bom_line_id.product_rounding) or False,
                                'product_uos': line.bom_line_id.product_uos and line.bom_line_id.product_uos.id or False,
                            })
                            # substitute_obj.write(cr, uid, [line.id], {'scheduled': True})
                            line.write({'scheduled': True})
        return result

    @api.multi
    def _action_compute_lines(self, properties=None):
        """ Compute product_lines and workcenter_lines from BoM structure
        @return: product_lines
        """
        if properties is None:
            properties = []
        results = []
        bom_obj = self.env['mrp.bom']
        uom_obj = self.env['product.uom']
        # prod_line_obj = self.env['mrp.production.product.line']
        # workcenter_line_obj = self.env['mrp.production.workcenter.line']
        for production in self:
            # unlink product_lines
            # for line in production.product_lines:
            #     line.unlink()
            # unlink workcenter_lines
            # for wline in production.workcenter_lines:
            #     wline.unlink()
            # search BoM structure and route
            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = bom_obj._bom_find(product=production.product_id, picking_type = self.picking_type_id, company_id=self.company_id.id)
                if bom_id:
                    bom_point = bom_obj.browse(bom_id)
                    routing_id = bom_point.routing_id.id or False
                    production.write({'bom_id': bom_id, 'routing_id': routing_id})

            if not bom_id:
                raise UserError(_("Cannot find a bill of material for this product."))

            # get components and workcenter_lines from BoM structure
            factor = production.product_uom_id._compute_quantity(production.product_qty, bom_point.product_uom_id)
            # product_lines, workcenter_lines
            results, results2 = bom_obj._bom_explode(bom_point, production.product_id,
                                                     factor / bom_point.product_qty, properties,
                                                     routing_id=production.routing_id.id)

            # reset product_lines in production order
            if 'w' in [line.state for line in production.substitute_lines]:
                raise UserError(_("Can not confirm production some products are waiting"))
            # create scheduled products here
            substitute_obj = self.env['mrp.product.substitute']
            # set scheduled False before computing lines again.
            # substitute_obj.write(cr, uid, [line.id for line in production.substitute_lines], {'scheduled': False})
            for line in production.substitute_lines:
                line.write({'scheduled': False})
            results = self.compute_substitute_lines(bom_id)

            # for line in results:
            #     line['production_id'] = production.id
            #     substitute_obj.create(line)

            # reset workcenter_lines in production order
            # for line in results2:
            #     line['production_id'] = production.id
            #     workcenter_line_obj.create(line)
        return results

    @api.multi
    def action_compute(self, properties=None):
        """ Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        return len(self._action_compute_lines(properties=properties))

    @api.multi
    def action_confirm(self):
        for production in self:
            if not production.substitute_lines:
                raise UserError(_('No substitute lines probably you should compute substitute lines'))

        self.validate_scheduled_products()
        return super(mrp_production, self).action_confirm()
        # result  =super(mrp_production,self).action_confirm(cr, uid, ids, context= context)
        # call action assign to auto check availability
        self.action_assign()
        return result

    # confirm order and create moves of lines
    @api.multi
    def action_ready(self):

        """ Changes the production state to Ready and location id of stock move.
        @return: True
        """
        self.action_confirm()
        self.force_production()
        return super(mrp_production, self).action_ready()

    # validate if we have all scheduled lines and with correct qty
    @api.multi
    def validate_scheduled_products(self):
        for production in self:
            if not production.product_lines:
                raise UserError(_('Can not confirm production some products are waiting'))
            for bom_line in production.bom_id.bom_line_ids:
                # validate for each main product, scheduled lines must have equal qty between main product of BOM and main + substitute in scheduled products
                if not bom_line.substitute_product_id:
                    expected_qty = bom_line.product_qty * production.product_qty
                    actual_qty = 0.0
                    for product_line in production.product_lines:
                        if product_line.product_id.id == bom_line.product_id.id or product_line.substitute_product_id and bom_line.product_id.id == product_line.substitute_product_id.id:
                            actual_qty = actual_qty + product_line.product_qty
                    if expected_qty != actual_qty:
                        raise UserError(_(
                            'Please check scheduled products, qty mismatch for product %s between scheduled products and BOM') % (
                                      bom_line.product_id.name))
        return True
        # to bypass production wizard

    @api.multi
    def action_substitute_produce(self):
        if not isinstance(self._ids, list):
            ids = [self._ids]
        production = self.browse(self._ids)
        production.action_produce(production.id, production.product_qty, 'consume_produce', wiz=False)
        return True

    @api.multi
    def select_all_substitute(self):
        for production in self:
            for line in production.substitute_lines:
                line.write({'produce': True})
        return True

    @api.multi
    def clear_all_substitute(self):
        for production in self:
            for line in production.substitute_lines:
                line.write({'produce': False})
        return True


class mrp_bom(models.Model):
    _inherit = 'mrp.bom'

    @api.multi
    def _bom_explode(self, bom, product, factor, properties=None, level=0, routing_id=False,
                     previous_products=None, master_bom=None):
        """ Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product template.
        @param product: Select a particular variant of the BoM. If False use BoM without variants.
        @param factor: Factor represents the quantity, but in UoM of the BoM, taking into account the numbers produced by the BoM
        @param properties: A List of properties Ids.
        @param level: Depth level to find BoM lines starts from 10.
        @param previous_products: List of product previously use by bom explore to avoid recursion
        @param master_bom: When recursion, used to display the name of the master bom
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """
        uom_obj = self.env["product.uom"]
        routing_obj = self.env['mrp.routing']
        master_bom = master_bom or bom
        context = self._context

        # def _factor(factor, product_rounding):
        # # def _factor(factor, product_efficiency, product_rounding):
        #     # factor = factor / (product_efficiency or 1.0)
        #     factor = factor / 1.0
        #     if product_rounding:
        #         factor = tools.float_round(factor,
        #                                    precision_rounding=product_rounding,
        #                                    rounding_method='UP')
        #     if factor < product_rounding:
        #         factor = product_rounding
        #     return factor

        # factor = _factor(factor, bom.product_rounding)

        result = []
        result2 = []

        routing = (routing_id and routing_obj.browse(routing_id)) or bom.routing_id or False
        if routing:
            for wc_use in routing.operation_ids:
                wc = wc_use.workcenter_id
                d, m = divmod(factor, wc_use.workcenter_id.capacity)
                mult = (d + (m and 1.0 or 0.0))
                cycle = mult# * wc_use.cycle_nbr
                result2.append({
                    'name': tools.ustr(wc_use.name) + ' - ' + tools.ustr(bom.product_tmpl_id.name_get()[0][1]),
                    'workcenter_id': wc.id,
                    'sequence': level + (wc_use.sequence or 0),
                    'cycle': cycle,
                    'hour': float(mult + (
                    (wc.time_start or 0.0) + (wc.time_stop or 0.0) + cycle * (
                                  wc.time_efficiency or 1.0))),
                })

        for bom_line_id in bom.bom_line_ids:
            # if bom_line_id.date_start and bom_line_id.date_start > time.strftime(DEFAULT_SERVER_DATETIME_FORMAT) or \
            #                 bom_line_id.date_stop and bom_line_id.date_stop < time.strftime(
            #             DEFAULT_SERVER_DATETIME_FORMAT):
            #     continue
            # all bom_line_id variant values must be in the product
            if bom_line_id.attribute_value_ids:
                if not product or (
                    set(map(int, bom_line_id.attribute_value_ids or [])) - set(map(int, product.attribute_value_ids))):
                    continue

            if previous_products and bom_line_id.product_id.product_tmpl_id.id in previous_products:
                raise UserError(_('BoM "%s" contains a BoM line with a product recursion: "%s".') % (
                                     master_bom.name, bom_line_id.product_id.name_get()[0][1]))

            quantity = bom_line_id.product_qty * factor
            #bom_line_id.product_efficiency, bom_line_id.product_rounding)
            bom_id = self.with_context(context)._bom_find(product=bom_line_id.product_id, picking_type = self.picking_type_id, company_id=self.company_id.id)

            # If BoM should not behave like PhantoM, just add the product, otherwise explode further
            bom_line_obj = self.env['mrp.bom.line']
            # check only lines which doesn't have substitute product
            if bom_id.type != "phantom" and (
                not bom_id or self.browse(bom_id).type != "phantom"):
                if not bom_line_id.substitute_product_id:
                    result.append({
                        'name': bom_line_id.product_id.name,
                        'product_id': bom_line_id.product_id.id,
                        'product_qty': quantity,
                        'product_uom': bom_line_id.product_uom_id.id,
                        # 'product_uos_qty': bom_line_id.product_uos and bom_line_id.product_uos_qty * factor,
                        #                                                        #bom_line_id.product_efficiency, bom_line_id.product_rounding) or False,
                        # 'product_uos': bom_line_id.product_uos and bom_line_id.product_uos.id or False,
                    })
                    substitute_ids = bom_line_obj.search([('substitute_product_id', '=', bom_line_id.product_id.id),
                                                          ('bom_id', '=', bom_line_id.bom_id.id)])
                    if len(substitute_ids):
                        for substitute in bom_line_obj.browse(substitute_ids):
                            result.append({
                                'name': substitute.substitute_product_id.name,
                                'product_id': substitute.substitute_product_id.id,
                                'substitute_product_id': substitute.product_id.id,
                                'product_qty': substitute.product_qty,
                                'product_uom': substitute.product_uom_id.id,
                                # 'product_uos_qty': substitute.product_uos and substitute.product_uos_qty * factor or substitute.product_efficiency or False,
                                # 'product_uos': substitute.product_uos and substitute.product_uos.id or False,
                            })


            elif bom_id:
                all_prod = [bom.product_tmpl_id.id] + (previous_products or [])
                bom2 = self.browse(bom_id)
                # We need to convert to units/UoM of chosen BoM
                factor2 = bom_line_id.product_uom_id._compute_quantity(quantity, bom2.product_uom_id)
                # product_uom_factor = prod.product_uom_id._compute_quantity(prod.product_qty - prod.qty_produced, prod.bom_id.product_uom_id)
                quantity2 = factor2 / bom2.product_qty
                res = self._bom_explode(bom2, bom_line_id.product_id, quantity2,
                                        properties=properties, level=level + 10, previous_products=all_prod,
                                        master_bom=master_bom)
                result = result + res[0]
                result2 = result2 + res[1]
            else:
                raise UserError(_(
                    'BoM "%s" contains a phantom BoM line but the product "%s" does not have any BoM defined.') % (
                                     master_bom.name, bom_line_id.product_id.name_get()[0][1]))

        return result, result2

# write in V8 for get related fields working on on_change
class mrp_bom_line(models.Model):
    _inherit = 'mrp.bom.line'

    substitute_product_id = fields.Many2one('product.product', 'Substitute of Product')
    comment = fields.Char(u'Referência')
    fabricante = fields.Many2one('res.partner', related='product_id.manufacturer', string='FABRICANTE')
    ref_fabricante = fields.Char(related='product_id.manufacturer_pref', string='PARTNUMBER FABRICANTE')
    default_code = fields.Char(related='product_id.default_code', string='Código Trace')
    default_sequence = fields.Char(compute='_get_default_sequence', string='Sequence')

    @api.one
    def _get_default_sequence(self):
        res = {}
        i = 0
        for bomline in self:
            self.default_sequence = i
            for line in bomline.bom_id.bom_line_ids:
                i = i + 1
                if line.id == bomline.id:
                    self.default_sequence = i
                    break


