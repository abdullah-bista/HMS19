# -*- coding: utf-8 -*-
{
    'name': 'Bista HMS Upcoming Patient Queue',
    'version': '19.0.1.0.0',
    'category': 'Medical / Healthcare',
    'summary': 'Pre-registration waitlist for patients awaiting OPD consultation or IPD admission',
    'author': 'Bista Solutions',
    'website': 'https://www.bistasolutions.com',
    'license': 'OPL-1',
    'depends': ['bista_hms_queue', 'bista_hms_admission_queue'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/upcoming_queue_views.xml',
        'views/menu_item.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
