from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HmsEmergencyCase(models.Model):
    _name = 'hms.emergency.case'
    _description = 'Emergency Case'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin']
    _rec_name = 'name'
    _order = 'arrival_datetime desc, id desc'

    name = fields.Char(string='Case Number', readonly=True, copy=False, default='New')

    # Patient & Arrival
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True, index=True
    )
    arrival_datetime = fields.Datetime(
        string='Arrival Date/Time', required=True,
        default=fields.Datetime.now, tracking=True
    )
    arrival_mode = fields.Selection([
        ('walk_in', 'Walk-In'),
        ('ambulance', 'Ambulance'),
        ('transfer', 'Transfer'),
        ('police', 'Police'),
        ('other', 'Other'),
    ], string='Arrival Mode', required=True, default='walk_in', tracking=True)
    brought_by = fields.Char(string='Brought By')
    brought_by_phone = fields.Char(string='Contact Number')
    chief_complaint = fields.Text(string='Chief Complaint', required=True)

    # Triage — 4-Level Bangladesh SATS (G9)
    triage_level = fields.Selection([
        ('red',    '🔴 RED — Immediate (< 0 min)'),
        ('orange', '🟠 ORANGE — Very Urgent (≤ 10 min)'),
        ('yellow', '🟡 YELLOW — Urgent (≤ 60 min)'),
        ('green',  '🟢 GREEN — Non-Urgent (≤ 120 min)'),
    ], string='Triage Category', tracking=True)
    triage_datetime = fields.Datetime(string='Triage Time', tracking=True)
    triage_nurse_id = fields.Many2one('res.users', string='Triage Nurse', tracking=True)
    triage_notes = fields.Text(string='Triage Notes')

    # Inline triage vitals (G10)
    triage_vitals_ids = fields.One2many(
        'hms.triage.vitals', 'emergency_case_id', string='Triage Vitals'
    )

    # Special Condition Flags (G11)
    flag_pregnancy   = fields.Boolean(string='Pregnancy')
    flag_pediatric   = fields.Boolean(string='Pediatric (< 12 yrs)')
    flag_geriatric   = fields.Boolean(string='Geriatric (> 65 yrs)')
    flag_known_allergy = fields.Boolean(string='Known Allergies')
    flag_mlc         = fields.Boolean(string='Medico-Legal Case (MLC)', tracking=True)
    flag_infectious  = fields.Boolean(string='Infectious Disease Suspect')
    flag_vip         = fields.Boolean(string='VIP / Government Official')
    flag_mental      = fields.Boolean(string='Mentally Unstable')

    # Medical Team
    physician_id = fields.Many2one(
        'hms.physician', string='Attending Physician',
        ondelete='restrict', tracking=True
    )
    department_id = fields.Many2one('hr.department', string='Department')

    # State Machine
    state = fields.Selection([
        ('arrived', 'Arrived'),
        ('triage', 'Triage'),
        ('treatment', 'Treatment'),
        ('observation', 'Observation'),
        ('admitted', 'Admitted'),
        ('discharged', 'Discharged'),
        ('transferred', 'Transferred'),
        ('deceased', 'Deceased'),
    ], string='Status', default='arrived', required=True, tracking=True)

    # Disposition
    disposition = fields.Selection([
        ('admitted', 'Admitted to IPD'),
        ('discharged_home', 'Discharged to Home'),
        ('transferred', 'Transferred to Another Facility'),
        ('left_ama', 'Left Against Medical Advice'),
        ('deceased', 'Death in ER'),
    ], string='Disposition', tracking=True)
    disposition_datetime = fields.Datetime(string='Disposition Time', tracking=True)

    # Clinical Notes
    notes = fields.Html(string='Clinical Notes')

    # Linked Clinical Records
    treatment_ids = fields.One2many('hms.treatment', 'emergency_case_id', string='Treatments')
    appointment_ids = fields.One2many('hms.appointment', 'emergency_case_id', string='Appointments')
    lab_request_ids = fields.One2many('acs.laboratory.request', 'emergency_case_id', string='Lab Requests')
    prescription_ids = fields.One2many('prescription.order', 'emergency_case_id', string='Prescriptions')
    procedure_ids = fields.One2many('acs.patient.procedure', 'emergency_case_id', string='Procedures')

    # OT Bookings
    ot_booking_ids = fields.One2many('hms.operation.theatre', 'emergency_case_id', string='OT Bookings')

    # Nursing Sheets
    nursing_sheet_ids = fields.One2many('hms.nursing.sheet', 'emergency_case_id', string='Nursing Sheets')

    # Counts for smart buttons
    treatment_count = fields.Integer(compute='_compute_counts')
    lab_request_count = fields.Integer(compute='_compute_counts')
    prescription_count = fields.Integer(compute='_compute_counts')
    procedure_count = fields.Integer(compute='_compute_counts')
    ot_booking_count = fields.Integer(compute='_compute_counts')
    nursing_sheet_count = fields.Integer(compute='_compute_counts')

    # Admission link (Phase 3)
    admission_id = fields.Many2one(
        'hms.admission', string='IPD Admission', ondelete='set null', tracking=True
    )

    # Discharge link (Phase 5)
    discharge_id = fields.Many2one(
        'hms.discharge', string='Discharge Record', ondelete='set null', tracking=True, copy=False
    )

    # Registration Invoice
    invoice_id = fields.Many2one('account.move', string='Registration Invoice', copy=False, readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Hospital', ondelete='restrict',
        default=lambda self: self.env.company
    )

    # ---------------------------------------------------------------
    # ORM Overrides
    # ---------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.emergency.case') or 'New'
        return super().create(vals_list)

    # ---------------------------------------------------------------
    # Computed Fields
    # ---------------------------------------------------------------

    @api.depends('treatment_ids', 'lab_request_ids', 'prescription_ids', 'procedure_ids',
                 'ot_booking_ids', 'nursing_sheet_ids')
    def _compute_counts(self):
        for rec in self:
            rec.treatment_count = len(rec.treatment_ids)
            rec.lab_request_count = len(rec.lab_request_ids)
            rec.prescription_count = len(rec.prescription_ids)
            rec.procedure_count = len(rec.procedure_ids)
            rec.ot_booking_count = len(rec.ot_booking_ids)
            rec.nursing_sheet_count = len(rec.nursing_sheet_ids)

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_triage(self):
        """Move case from Arrived → Triage."""
        for rec in self:
            if rec.state != 'arrived':
                raise UserError(_('Only arrived cases can be moved to triage.'))
            if not rec.invoice_id:
                raise ValidationError('Please create invoice first.')
            rec.write({
                'state': 'triage',
                'triage_datetime': fields.Datetime.now(),
                'triage_nurse_id': self.env.user.id,
            })

    def action_start_treatment(self):
        """Move case from Triage → Treatment."""
        for rec in self:
            if rec.state != 'triage':
                raise UserError(_('Case must be in Triage state to start treatment.'))
            if not rec.triage_level:
                raise UserError(_('Please set the Triage Category before starting treatment.'))
            rec.state = 'treatment'

    def action_observe(self):
        """Move case from Treatment → Observation."""
        for rec in self:
            if rec.state != 'treatment':
                raise UserError(_('Case must be in Treatment state to move to Observation.'))
            rec.state = 'observation'

    def action_admit(self):
        """Open IPD Admission form pre-filled from this ER case."""
        self.ensure_one()
        if self.state not in ('treatment', 'observation'):
            raise UserError(_('Case must be in Treatment or Observation state to admit.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create IPD Admission'),
            'res_model': 'hms.admission',
            'view_mode': 'form',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_emergency_case_id': self.id,
                'default_admission_type': 'emergency',
                'default_attending_physician_id': self.physician_id.id,
            },
            'target': 'current',
        }

    def action_discharge(self):
        """Open the Discharge form pre-filled for this ER case."""
        self.ensure_one()
        if self.state not in ('treatment', 'observation'):
            raise UserError(_('Case must be in Treatment or Observation state to discharge.'))
        if self.discharge_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Discharge Record'),
                'res_model': 'hms.discharge',
                'view_mode': 'form',
                'res_id': self.discharge_id.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create ER Discharge'),
            'res_model': 'hms.discharge',
            'view_mode': 'form',
            'context': {
                'default_discharge_type': 'emergency',
                'default_patient_id': self.patient_id.id,
                'default_emergency_case_id': self.id,
                'default_physician_id': self.physician_id.id,
            },
            'target': 'current',
        }

    def action_transfer(self):
        """Mark patient as Transferred to another facility."""
        for rec in self:
            if rec.state not in ('treatment', 'observation'):
                raise UserError(_('Case must be in Treatment or Observation state to transfer.'))
            rec.write({
                'state': 'transferred',
                'disposition': 'transferred',
                'disposition_datetime': fields.Datetime.now(),
            })

    def action_deceased(self):
        """Mark patient as Deceased in ER."""
        for rec in self:
            if rec.state not in ('treatment', 'observation'):
                raise UserError(_('Case must be in Treatment or Observation state.'))
            rec.write({
                'state': 'deceased',
                'disposition': 'deceased',
                'disposition_datetime': fields.Datetime.now(),
            })

    def action_view_invoice(self):
        """Open the registration invoice for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registration Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }

    def action_create_invoice(self):
        """Create a registration invoice for this emergency case."""
        self.ensure_one()
        if self.state != 'arrived':
            raise UserError(_('Registration invoice can only be created for cases in Arrived state.'))
        product_id = self.env.company.patient_registration_product_id
        if not product_id:
            raise UserError(_('Please configure the Patient Registration Product in General Settings first.'))
        invoice = self.acs_create_invoice(
            partner=self.patient_id.partner_id,
            patient=self.patient_id,
            product_data=[{'product_id': product_id}],
            inv_data={'hospital_invoice_type': 'patient'},
        )
        self.invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registration Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    # ---------------------------------------------------------------
    # Smart Button Actions
    # ---------------------------------------------------------------

    def action_view_lab_requests(self):
        """Open lab requests list for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lab Requests'),
            'res_model': 'acs.laboratory.request',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_physician_id': self.physician_id.id,
                'default_emergency_case_id': self.id,
                'default_is_emergency': True,
            },
        }

    def action_view_prescriptions(self):
        """Open prescriptions list for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Prescriptions'),
            'res_model': 'prescription.order',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_physician_id': self.physician_id.id,
                'default_emergency_case_id': self.id,
                'default_is_emergency': True,
            },
        }

    def action_view_procedures(self):
        """Open procedures list for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Procedures'),
            'res_model': 'acs.patient.procedure',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_physician_id': self.physician_id.id,
                'default_emergency_case_id': self.id,
                'default_is_emergency': True,
            },
        }

    def action_view_treatments(self):
        """Open treatments list for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Treatments'),
            'res_model': 'hms.treatment',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_physician_id': self.physician_id.id,
                'default_emergency_case_id': self.id,
                'default_is_emergency': True,
            },
        }

    def action_view_ot_bookings(self):
        """Open OT bookings for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OT Bookings'),
            'res_model': 'hms.operation.theatre',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_emergency_case_id': self.id,
                'default_operation_type': 'emergency',
            },
        }

    def action_view_nursing_sheets(self):
        """Open nursing sheets for this emergency case."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nursing Sheets'),
            'res_model': 'hms.nursing.sheet',
            'view_mode': 'list,form',
            'domain': [('emergency_case_id', '=', self.id)],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_emergency_case_id': self.id,
            },
        }
