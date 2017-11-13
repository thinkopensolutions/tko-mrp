# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    ThinkOpen Solutions Brasil
#    Copyright (C) Thinkopen Solutions <http://www.tkobr.com>.
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
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
from odoo.addons import decimal_precision as dp



class Location(models.Model):
    _inherit = "stock.location"
    _description = "Inventory Locations"

    pos_cabinet = fields.Integer(string='Cabinet')
    pos_box = fields.Integer(string='Box')


class product_template(models.Model):
    _inherit = 'product.template'

    attachments = fields.Binary(string="Attach Files")
    attachments_ids = fields.One2many('product.attachment', 'product_id')
    volume = fields.Float('Volume', digits=dp.get_precision('Stock Volume'), help="The volume in m3.")


    @api.constrains('default_code')
    def constrain_default_code(self):
        if self.default_code:
            if len(self.search([('default_code', '=', self.default_code)])) > 1:
                raise Warning(_('The internal reference must be unique!'))

    @api.multi
    def open_attachment(self):
        view_id = self.env.ref('tko_mrp.view_attachment')
        return{
               'view_type':'form',
               'view_mode':'form',
               'res_model':'select.attachment',
               'view_id':view_id.id,
               'type':'ir.actions.act_window',
               'name':'Attachment',
               'target':'new',
               }

class stock_change_product_qty(models.TransientModel):
    _inherit = 'stock.change.product.qty'

    notes = fields.Char(string="Notes")

    @api.multi
    def change_product_qty(self):
        date = datetime.strftime(datetime.today().date(), "%d-%m-%Y")
        message = _("<ul class=o_timeline_tracking_value_list><li>Date<span> : </span><span class=o_timeline_tracking_value>%s</span></li>"
                    "<li>User Name<span> : </span><span class=o_timeline_tracking_value>%s</span></li>"
                    "<li>Old Qty<span> : </span><span class=o_timeline_tracking_value>%s</span></li>"
                    "<li>New Qty<span> : </span><span class=o_timeline_tracking_value>%s</span></li>"
                    "<li>Notes<span> : </span><span class=o_timeline_tracking_value>%s</span></li></ul>"
                    ) % (date, self.env.user.name , self.product_tmpl_id.qty_available, self.new_quantity, self.notes if self.notes else '')
        self.product_tmpl_id.message_post(body=message)
        """ Changes the Product Quantity by making a Physical Inventory. """
        Inventory = self.env['stock.inventory']
        for wizard in self:
            product = wizard.product_id.with_context(location=wizard.location_id.id, lot_id=wizard.lot_id.id)
            line_data = wizard._prepare_inventory_line()
            if wizard.product_id.id and wizard.lot_id.id:
                inventory_filter = 'none'
            elif wizard.product_id.id:
                inventory_filter = 'product'
            else:
                inventory_filter = 'none'
            inventory = Inventory.create({
                'name': _('INV: %s') % tools.ustr(wizard.product_id.name),
                'filter': inventory_filter,
                'product_id': wizard.product_id.id,
                'location_id': wizard.location_id.id,
                'lot_id': wizard.lot_id.id,
                'line_ids': [(0, 0, line_data)],
            })
            inventory.action_done()
        return {'type': 'ir.actions.act_window_close'}



class select_attachment(models.TransientModel):
    _name = 'select.attachment'

    file_name = fields.Char(string="")
    file_data = fields.Binary(string="Name")

    @api.one
    def create_attachment(self):
        self.env['product.attachment'].create({'file_data':self.file_data,
                                               'product_id':self._context.get('active_id'),
                                               'file_name':self.file_name
                                               })


class product_attachment(models.Model):
    _name = 'product.attachment'

    product_id = fields.Many2one('product.template', string="Product")
    file_name = fields.Char(string="File Name")
    file_data = fields.Binary(string="File Name")
