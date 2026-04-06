from odoo import fields, models


class LaboratoryRequest(models.Model):
    _inherit = 'acs.laboratory.request'

    appointment_id = fields.Many2one(
        'hms.appointment', string='Appointment',
        ondelete='set null', index=True
    )
