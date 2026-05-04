{
    'name': 'HMS Access Rights',
    'version': '19.0.1.0.0',
    'category': 'Hospital Management',
    'summary': 'Centralized access rights and test users for all HMS staff roles',
    'depends': ['acs_hms', 'acs_laboratory', 'hms_doctor_cockpit', 'hms_patient_portal', 'bista_hms_emergency'],
    'data': [
        'security/ir.model.access.csv',
        'data/test_users.xml',
        'views/menu_item_perm.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
