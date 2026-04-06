from odoo import fields, models


class LaboratoryRequest(models.Model):
    _inherit = 'acs.laboratory.request'

    is_emergency = fields.Boolean(string='Emergency Request', default=False)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', index=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='set null', index=True
    )
