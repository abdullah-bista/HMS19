# -*- coding: utf-8 -*-
{
    'name': 'Bista HMS Patient Queue',
    'version': '19.0.1.0.0',
    'category': 'Medical / Healthcare',
    'summary': 'Patient Waiting Queue with token numbers, priority ordering, and Call Next',
    'author': 'Bista Solutions',
    'website': 'https://www.bistasolutions.com',
    'license': 'OPL-1',
    'depends': ['bista_hms_emergency'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/queue_counter_views.xml',
        'views/queue_views.xml',
        'views/appointment_inherit.xml',
        'views/menu_item.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
