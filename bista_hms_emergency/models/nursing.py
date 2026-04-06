from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsNursingSheet(models.Model):
    _name = 'hms.nursing.sheet'
    _description = 'Nursing Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'shift_date desc, shift desc'

    name = fields.Char(string='Sheet Number', readonly=True, copy=False, default='New')

    # Patient & Admission
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='restrict', tracking=True, index=True
    )
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='restrict', tracking=True, index=True
    )
    nurse_id = fields.Many2one(
        'res.users', string='Nurse', required=True,
        default=lambda self: self.env.user, tracking=True
    )

    # Shift
    shift = fields.Selection([
        ('morning', 'Morning  (6AM – 2PM)'),
        ('afternoon', 'Afternoon (2PM – 10PM)'),
        ('night', 'Night     (10PM – 6AM)'),
    ], string='Shift', required=True, tracking=True)
    shift_date = fields.Date(
        string='Shift Date', required=True,
        default=fields.Date.today, tracking=True
    )
    shift_start = fields.Datetime(string='Shift Start', tracking=True)
    shift_end = fields.Datetime(string='Shift End', tracking=True)

    # Vital Signs (child model)
    vitals_ids = fields.One2many(
        'hms.nursing.vitals', 'nursing_sheet_id', string='Vital Signs'
    )

    # Clinical Assessment
    general_condition = fields.Selection([
        ('stable', 'Stable'),
        ('improving', 'Improving'),
        ('deteriorating', 'Deteriorating'),
        ('critical', 'Critical'),
    ], string='General Condition', tracking=True)
    consciousness_level = fields.Selection([
        ('alert', 'Alert (A)'),
        ('verbal', 'Verbal (V)'),
        ('pain', 'Pain (P)'),
        ('unresponsive', 'Unresponsive (U)'),
    ], string='Consciousness (AVPU)', tracking=True)
    pain_level = fields.Selection([
        ('0', '0 – No Pain'),
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'),
        ('5', '5 – Moderate'),
        ('6', '6'), ('7', '7'), ('8', '8'), ('9', '9'),
        ('10', '10 – Worst Pain'),
    ], string='Pain Level (0–10)', tracking=True)
    mobility_status = fields.Selection([
        ('ambulatory', 'Ambulatory'),
        ('assisted', 'Assisted'),
        ('bedbound', 'Bedbound'),
        ('wheelchair', 'Wheelchair'),
    ], string='Mobility', tracking=True)

    # I/O Charting
    intake_oral = fields.Float(string='Oral (ml)')
    intake_iv = fields.Float(string='IV (ml)')
    intake_other = fields.Float(string='Other Intake (ml)')
    output_urine = fields.Float(string='Urine (ml)')
    output_stool = fields.Integer(string='Stool (count)')
    output_vomit = fields.Float(string='Vomit (ml)')
    output_drain = fields.Float(string='Drain (ml)')
    intake_output_balance = fields.Float(
        string='I/O Balance (ml)',
        compute='_compute_io_balance', store=True
    )

    # Clinical Notes
    patient_complaints = fields.Text(string='Patient Complaints')
    medications_given = fields.Html(string='Medications Given')
    procedures_done = fields.Html(string='Procedures Done')
    observations = fields.Html(string='Nursing Observations')
    care_plan_notes = fields.Html(string='Care Plan Updates')
    handover_notes = fields.Html(string='Handover Notes')

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('reviewed', 'Reviewed'),
    ], string='Status', default='draft', required=True, tracking=True)
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', tracking=True)
    review_datetime = fields.Datetime(string='Reviewed At', tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Hospital', compute='_compute_company_id', store=True
    )

    _sql_constraints = [
        (
            'admission_or_emergency_required',
            'CHECK(admission_id IS NOT NULL OR emergency_case_id IS NOT NULL)',
            'A nursing sheet must be linked to either an Admission or an Emergency Case.',
        ),
    ]

    # ---------------------------------------------------------------
    # ORM Overrides
    # ---------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.nursing.sheet') or 'New'
        return super().create(vals_list)

    # ---------------------------------------------------------------
    # Onchange
    # ---------------------------------------------------------------

    @api.onchange('admission_id')
    def _onchange_admission_id(self):
        if self.admission_id:
            self.patient_id = self.admission_id.patient_id

    @api.onchange('emergency_case_id')
    def _onchange_emergency_case_id(self):
        if self.emergency_case_id:
            self.patient_id = self.emergency_case_id.patient_id

    # ---------------------------------------------------------------
    # Computed Fields
    # ---------------------------------------------------------------

    @api.depends('admission_id', 'emergency_case_id')
    def _compute_company_id(self):
        for rec in self:
            if rec.admission_id:
                rec.company_id = rec.admission_id.company_id
            elif rec.emergency_case_id:
                rec.company_id = rec.emergency_case_id.company_id
            else:
                rec.company_id = self.env.company

    @api.depends('intake_oral', 'intake_iv', 'intake_other',
                 'output_urine', 'output_vomit', 'output_drain')
    def _compute_io_balance(self):
        for rec in self:
            total_intake = rec.intake_oral + rec.intake_iv + rec.intake_other
            total_output = rec.output_urine + rec.output_vomit + rec.output_drain
            rec.intake_output_balance = total_intake - total_output

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_start_shift(self):
        """Begin shift documentation: Draft → In Progress."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Shift has already been started.'))
            rec.write({
                'state': 'in_progress',
                'shift_start': fields.Datetime.now(),
            })

    def action_complete_shift(self):
        """Complete shift documentation: In Progress → Completed."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Shift must be In Progress to complete.'))
            rec.write({
                'state': 'completed',
                'shift_end': fields.Datetime.now(),
            })

    def action_review(self):
        """Review completed nursing sheet: Completed → Reviewed."""
        for rec in self:
            if rec.state != 'completed':
                raise UserError(_('Shift must be Completed before review.'))
            rec.write({
                'state': 'reviewed',
                'reviewed_by': self.env.user.id,
                'review_datetime': fields.Datetime.now(),
            })


class HmsNursingVitals(models.Model):
    _name = 'hms.nursing.vitals'
    _description = 'Vital Signs Record'
    _order = 'datetime desc'

    nursing_sheet_id = fields.Many2one(
        'hms.nursing.sheet', string='Nursing Sheet',
        required=True, ondelete='cascade', index=True
    )
    datetime = fields.Datetime(
        string='Recorded At', required=True, default=fields.Datetime.now
    )
    recorded_by = fields.Many2one(
        'res.users', string='Recorded By',
        required=True, default=lambda self: self.env.user
    )

    # Temperature
    temperature = fields.Float(string='Temp (°C)', digits=(4, 1))
    temperature_site = fields.Selection([
        ('oral', 'Oral'), ('axillary', 'Axillary'),
        ('rectal', 'Rectal'), ('tympanic', 'Tympanic'),
    ], string='Site')

    # Cardiovascular
    pulse = fields.Integer(string='Pulse (bpm)')
    pulse_rhythm = fields.Selection([
        ('regular', 'Regular'), ('irregular', 'Irregular'),
    ], string='Rhythm')
    systolic_bp = fields.Integer(string='Systolic (mmHg)')
    diastolic_bp = fields.Integer(string='Diastolic (mmHg)')

    # Respiratory
    respiratory_rate = fields.Integer(string='RR (/min)')
    spo2 = fields.Integer(string='SpO₂ (%)')
    oxygen_therapy = fields.Selection([
        ('none', 'None'), ('nasal_cannula', 'Nasal Cannula'),
        ('mask', 'Face Mask'), ('ventilator', 'Ventilator'),
    ], string='O₂ Therapy', default='none')
    oxygen_flow_rate = fields.Float(string='O₂ Flow (L/min)', digits=(4, 1))

    # Metabolic
    blood_sugar = fields.Float(string='Blood Sugar (mg/dL)', digits=(6, 1))
    blood_sugar_type = fields.Selection([
        ('fasting', 'Fasting'), ('random', 'Random'), ('pp', 'Post-Prandial'),
    ], string='BS Type')
    weight = fields.Float(string='Weight (kg)', digits=(5, 1))

    # Glasgow Coma Scale
    gcs_eye = fields.Selection([
        ('1', '1 – No Response'), ('2', '2 – To Pain'),
        ('3', '3 – To Voice'), ('4', '4 – Spontaneous'),
    ], string='GCS Eye (E)')
    gcs_verbal = fields.Selection([
        ('1', '1 – No Response'), ('2', '2 – Incomprehensible'),
        ('3', '3 – Inappropriate'), ('4', '4 – Confused'),
        ('5', '5 – Oriented'),
    ], string='GCS Verbal (V)')
    gcs_motor = fields.Selection([
        ('1', '1 – No Response'), ('2', '2 – Extension'),
        ('3', '3 – Abnormal Flexion'), ('4', '4 – Withdrawal'),
        ('5', '5 – Localizes Pain'), ('6', '6 – Obeys Commands'),
    ], string='GCS Motor (M)')
    gcs_total = fields.Integer(
        string='GCS Total', compute='_compute_gcs_total', store=True
    )

    notes = fields.Text(string='Notes')

    # ---------------------------------------------------------------
    # Computed Fields
    # ---------------------------------------------------------------

    @api.depends('gcs_eye', 'gcs_verbal', 'gcs_motor')
    def _compute_gcs_total(self):
        for rec in self:
            try:
                rec.gcs_total = (
                    int(rec.gcs_eye or 0)
                    + int(rec.gcs_verbal or 0)
                    + int(rec.gcs_motor or 0)
                )
            except (ValueError, TypeError):
                rec.gcs_total = 0

    def _check_critical_values(self):
        """Return warning string if critical vitals detected, else False."""
        self.ensure_one()
        alerts = []
        if self.systolic_bp:
            if self.systolic_bp > 180:
                alerts.append(_('High BP: %s/%s mmHg') % (self.systolic_bp, self.diastolic_bp))
            elif self.systolic_bp < 90:
                alerts.append(_('Low BP: %s/%s mmHg') % (self.systolic_bp, self.diastolic_bp))
        if self.spo2 and self.spo2 < 90:
            alerts.append(_('Low SpO₂: %s%%') % self.spo2)
        if self.pulse:
            if self.pulse > 120:
                alerts.append(_('Tachycardia: %s bpm') % self.pulse)
            elif self.pulse < 50:
                alerts.append(_('Bradycardia: %s bpm') % self.pulse)
        if self.temperature and self.temperature > 38.5:
            alerts.append(_('Fever: %.1f °C') % self.temperature)
        return '\n'.join(alerts) if alerts else False
