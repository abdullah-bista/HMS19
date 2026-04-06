from odoo import api, fields, models, _


class Patient(models.Model):
    _inherit = 'hms.patient'

    # Status flags
    is_emergency = fields.Boolean(
        string='In Emergency', compute='_compute_admission_status', store=True
    )
    is_admitted = fields.Boolean(
        string='Currently Admitted', compute='_compute_admission_status', store=True
    )

    # Current records
    current_admission_id = fields.Many2one(
        'hms.admission', string='Current Admission',
        compute='_compute_admission_status', store=True
    )
    current_bed_id = fields.Many2one(
        'hms.bed', string='Current Bed',
        related='current_admission_id.bed_id', store=True
    )
    current_ward_id = fields.Many2one(
        'hms.ward', string='Current Ward',
        related='current_admission_id.ward_id', store=True
    )

    # History
    emergency_case_ids = fields.One2many(
        'hms.emergency.case', 'patient_id', string='Emergency Cases'
    )
    admission_ids = fields.One2many(
        'hms.admission', 'patient_id', string='Admissions'
    )

    # Counts
    emergency_count = fields.Integer(compute='_compute_counts', store=True)
    admission_count = fields.Integer(compute='_compute_counts', store=True)

    @api.depends('admission_ids.state', 'emergency_case_ids.state')
    def _compute_admission_status(self):
        for patient in self:
            active_admissions = patient.admission_ids.filtered(
                lambda a: a.state == 'in_progress'
            )
            patient.is_admitted = bool(active_admissions)
            patient.current_admission_id = active_admissions[:1].id

            active_er = patient.emergency_case_ids.filtered(
                lambda e: e.state in ('arrived', 'triage', 'treatment', 'observation')
            )
            patient.is_emergency = bool(active_er)

    @api.depends('emergency_case_ids', 'admission_ids')
    def _compute_counts(self):
        for patient in self:
            patient.emergency_count = len(patient.emergency_case_ids)
            patient.admission_count = len(patient.admission_ids)

    def action_view_emergency_cases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Emergency Cases'),
            'res_model': 'hms.emergency.case',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
        }

    def action_view_admissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admissions'),
            'res_model': 'hms.admission',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
        }
