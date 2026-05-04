def post_init_hook(env):
    """Re-add group_hms_doctor to the doctor test user after install.

    hms.physician.create() calls acs_make_dr_portal_user() which uses the
    (6, 0, [...]) replace-all command on group_ids, leaving the user with only
    base.group_user. This hook restores the intended role after all data is loaded.
    """
    doctor_user = env['res.users'].search([('login', '=', 'doctor@hms.demo')], limit=1)
    if doctor_user:
        group = env.ref('acs_hms.group_hms_doctor')
        doctor_user.write({'group_ids': [(4, group.id)]})
