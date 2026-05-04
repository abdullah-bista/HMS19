{
    'name': "Doctor's Desk",
    'version': '19.0.1.0.0',
    'category': 'Hospital Management',
    'summary': "Dedicated workspace for physicians — all doctor operations in one place",
    'depends': ['acs_hms', 'acs_laboratory', 'bista_hms_emergency'],
    'data': [
        'views/dashboard_action.xml',
        'views/appointment_views.xml',
        'views/admission_views.xml',
        'views/prescription_views.xml',
        'views/lab_request_views.xml',
        'views/patient_views.xml',
        'views/procedure_views.xml',
        'views/menu_item.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hms_doctor_cockpit/static/src/js/**/*',
            'hms_doctor_cockpit/static/src/xml/**/*',
            'hms_doctor_cockpit/static/src/scss/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
