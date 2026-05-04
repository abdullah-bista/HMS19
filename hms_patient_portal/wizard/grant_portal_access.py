# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsGrantPortalAccess(models.TransientModel):
    _name = 'hms.grant.portal.access'
    _description = 'Grant Portal Access to Patient'

    patient_id = fields.Many2one('hms.patient', string='Patient', required=True)
    partner_id = fields.Many2one('res.partner', related='patient_id.partner_id', readonly=True)
    email = fields.Char(string='Email', related='patient_id.email', readonly=False)

    def action_grant_access(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError(_('The selected patient has no linked partner record.'))

        # Sync email back to partner if it was edited in the wizard
        if self.email and partner.email != self.email:
            partner.email = self.email

        if not partner.email:
            raise UserError(_('Please provide an email address to grant portal access.'))

        portal_group = self.env.ref('base.group_portal')
        user = self.env['res.users'].sudo().search(
            [('partner_id', '=', partner.id), ('active', 'in', [True, False])], limit=1
        )

        if user:
            # Ensure the user is in the portal group (may already be internal user)
            if portal_group not in user.groups_id:
                user.sudo().write({'groups_id': [(4, portal_group.id)]})
        else:
            # Use Odoo's portal wizard logic to invite a new portal user
            wizard = self.env['portal.wizard'].sudo().create({'user_ids': []})
            wizard_user = self.env['portal.wizard.user'].sudo().create({
                'wizard_id': wizard.id,
                'partner_id': partner.id,
                'email': partner.email,
                'is_portal': True,
            })
            wizard_user.action_grant_access()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Portal access has been granted to %s.') % partner.name,
                'type': 'success',
                'sticky': False,
            }
        }
