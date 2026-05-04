# -*- coding: utf-8 -*-
{
    'name': 'Patient Portal - HMS',
    'summary': 'Secure patient portal: appointments, prescriptions, treatments, health summary.',
    'description': """
        Provides a secure portal for patients to access their health records including:
        - Appointment history and new appointment requests
        - Prescription viewer with QR code
        - Treatment history
        - Health summary with latest vitals
        - Secure messaging with healthcare providers via appointment chatter
    """,
    'version': '19.0.1.0.0',
    'category': 'Medical',
    'author': 'HMS Demo',
    'website': '',
    'license': 'OPL-1',
    'depends': ['acs_hms', 'acs_laboratory', 'portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/grant_portal_access_view.xml',
        'views/portal_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
