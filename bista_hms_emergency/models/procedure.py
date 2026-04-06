from odoo import fields, models


class PatientProcedure(models.Model):
    _inherit = 'acs.patient.procedure'

    is_emergency = fields.Boolean(string='Emergency Procedure', default=False)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', index=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='set null', index=True
    )
