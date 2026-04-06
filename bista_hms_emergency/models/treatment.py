from odoo import fields, models


class Treatment(models.Model):
    _inherit = 'hms.treatment'

    is_emergency = fields.Boolean(string='Emergency', default=False)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', index=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='set null', index=True
    )
