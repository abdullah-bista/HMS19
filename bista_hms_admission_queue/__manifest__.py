# -*- coding: utf-8 -*-
{
    'name': 'Bista HMS Admission Queue',
    'version': '19.0.1.0.0',
    'category': 'Medical / Healthcare',
    'summary': 'IPD Admission Waiting Queue with token numbers, priority, and Admit Next',
    'author': 'Bista Solutions',
    'website': 'https://www.bistasolutions.com',
    'license': 'OPL-1',
    'depends': ['bista_hms_queue', 'bista_hms_emergency'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/admission_queue_counter_views.xml',
        'views/ward_form_inherit.xml',
        'views/admission_queue_views.xml',
        'views/admission_form_inherit.xml',
        'views/menu_item.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
