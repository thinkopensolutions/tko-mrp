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

{
    'name': 'MRP Enhancements',
    'version': '10.0.0.0.0',
    'category': 'Customizations',
    'description': ''' This module adds a few enhancements in the Manufacture and Inventory Workflow \n
''',
    'author': 'TKOBR',
    'website': 'http://www.tko.tko-br.com',
    'depends': [
        'mrp'
    ],
    'data': [
        'views/stock_location_view.xml',
    ],
    'qweb': [''],
    'init': [],
    'demo': [],
    'update': [],
    'test': [],  
    'installable': True,
    'application': False,
    'auto_install': False,
    'certificate': '',
}
