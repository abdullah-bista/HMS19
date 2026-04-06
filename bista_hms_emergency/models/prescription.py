from odoo import fields, models


class PrescriptionOrder(models.Model):
    _inherit = 'prescription.order'

    is_emergency = fields.Boolean(string='Emergency Prescription', default=False)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', index=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='set null', index=True
    )
