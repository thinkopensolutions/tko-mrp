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

{
    'name': 'tko_mrp_bom_substitute_product',
    'version': '0.030',
    'category': 'mrp',
    'sequence': 120,
    'complexity': 'medium',
    'description': '''tko_mrp_bom_substitute_product  ''',
    'author': 'ThinkOpen Solutions',
    'website': 'http://www.thinkopensolution.com',
    'images': ['images/oerp61.jpeg', ],
    'depends': [
        'base',
        'mrp',
        'tko_product_manufacture',
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'mrp_view.xml',
        'mrp_workflow.xml',
    ],
    'demo_xml': [],
    'installable': True,
    'application': False,
    'certificate': '',
}
