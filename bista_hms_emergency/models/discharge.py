from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsDischarge(models.Model):
    _name = 'hms.discharge'
    _description = 'Discharge Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'discharge_datetime desc, id desc'

    name = fields.Char(string='Discharge Number', readonly=True, copy=False, default='New')

    # Source
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True, index=True
    )
    discharge_type = fields.Selection([
        ('ipd', 'IPD Discharge'),
        ('emergency', 'ER Discharge'),
    ], string='Discharge Type', required=True, tracking=True)
    admission_id = fields.Many2one(
        'hms.admission', string='Admission', ondelete='restrict',
        tracking=True, index=True
    )
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case', ondelete='restrict',
        tracking=True, index=True
    )

    # Discharge Details
    discharge_datetime = fields.Datetime(
        string='Discharge Date/Time', required=True,
        default=fields.Datetime.now, tracking=True
    )
    physician_id = fields.Many2one(
        'hms.physician', string='Discharging Physician',
        required=True, ondelete='restrict', tracking=True
    )
    discharge_condition = fields.Selection([
        ('improved', 'Improved'),
        ('cured', 'Cured'),
        ('unchanged', 'Unchanged'),
        ('worse', 'Worse'),
        ('deceased', 'Deceased'),
        ('lama', 'Left Against Medical Advice (LAMA)'),
        ('absconded', 'Absconded'),
    ], string='Discharge Condition', required=True, tracking=True)

    # Diagnoses
    diagnosis_ids = fields.Many2many(
        'hms.diseases', 'hms_discharge_diagnosis_rel', 'discharge_id', 'disease_id',
        string='Final Diagnoses'
    )
    admission_diagnosis = fields.Text(string='Diagnosis at Admission')
    discharge_diagnosis = fields.Text(string='Final Discharge Diagnosis')

    # Clinical Summary
    treatment_summary = fields.Html(string='Treatment Summary')
    procedures_summary = fields.Html(string='Procedures Summary')
    investigation_summary = fields.Html(string='Investigation Summary')
    discharge_medications = fields.Html(string='Discharge Medications', required=True)

    # Follow-up
    follow_up_instructions = fields.Html(string='Follow-up Instructions')
    follow_up_date = fields.Date(string='Follow-up Date')
    follow_up_physician_id = fields.Many2one(
        'hms.physician', string='Follow-up Physician', ondelete='restrict'
    )

    # Patient Instructions
    diet_instructions = fields.Text(string='Diet Instructions')
    activity_restrictions = fields.Text(string='Activity Restrictions')
    warning_signs = fields.Text(string='Warning Signs to Watch')

    # State Machine
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_payment', 'Pending Payment'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', required=True, tracking=True)

    # Billing
    billing_cleared = fields.Boolean(string='Bills Cleared', tracking=True)
    billing_remarks = fields.Text(string='Billing Remarks')

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)
    approval_datetime = fields.Datetime(string='Approved At', tracking=True)

    # Release
    released_by = fields.Many2one('res.users', string='Released By', tracking=True)
    release_datetime = fields.Datetime(string='Released At', tracking=True)

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
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.discharge') or 'New'
            # Auto-link source admission/emergency case to discharge
        records = super().create(vals_list)
        for rec in records:
            if rec.admission_id and not rec.admission_id.discharge_id:
                rec.admission_id.discharge_id = rec.id
            if rec.emergency_case_id and not rec.emergency_case_id.discharge_id:
                rec.emergency_case_id.discharge_id = rec.id
        return records

    # ---------------------------------------------------------------
    # Onchange
    # ---------------------------------------------------------------

    @api.onchange('admission_id')
    def _onchange_admission_id(self):
        if self.admission_id:
            self.patient_id = self.admission_id.patient_id
            self.physician_id = self.admission_id.attending_physician_id

    @api.onchange('emergency_case_id')
    def _onchange_emergency_case_id(self):
        if self.emergency_case_id:
            self.patient_id = self.emergency_case_id.patient_id
            self.physician_id = self.emergency_case_id.physician_id

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_submit(self):
        """Submit for billing clearance: Draft → Pending Payment."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft discharges can be submitted.'))
            if not rec.discharge_medications:
                raise UserError(_('Please fill in Discharge Medications before submitting.'))
            rec.state = 'pending_payment'

    def action_billing_cleared(self):
        """Mark billing as cleared: Pending Payment → Pending Approval."""
        for rec in self:
            if rec.state != 'pending_payment':
                raise UserError(_('Discharge must be Pending Payment to clear billing.'))
            rec.write({
                'state': 'pending_approval',
                'billing_cleared': True,
            })

    def action_approve(self):
        """Medical approval: Pending Approval → Approved."""
        for rec in self:
            if rec.state != 'pending_approval':
                raise UserError(_('Discharge must be Pending Approval.'))
            if not rec.billing_cleared:
                raise UserError(_('Billing must be cleared before approval.'))
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_datetime': fields.Datetime.now(),
            })

    def action_complete(self):
        """Final patient release: Approved → Completed.
        Releases bed and updates linked admission/ER case.
        """
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Discharge must be Approved before completing.'))
            now = fields.Datetime.now()
            rec.write({
                'state': 'completed',
                'released_by': self.env.user.id,
                'release_datetime': now,
            })
            rec._release_bed()
            rec._update_source_state(now)

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def _release_bed(self):
        """Release bed via the linked admission."""
        self.ensure_one()
        if self.discharge_type == 'ipd' and self.admission_id:
            self.admission_id._release_bed()

    def _update_source_state(self, release_dt=None):
        """Update linked admission / emergency case state on completion."""
        self.ensure_one()
        now = release_dt or fields.Datetime.now()
        if self.discharge_type == 'ipd' and self.admission_id:
            self.admission_id.write({
                'state': 'discharged',
                'actual_discharge_datetime': now,
            })
        elif self.discharge_type == 'emergency' and self.emergency_case_id:
            disposition = 'deceased' if self.discharge_condition == 'deceased' else 'discharged_home'
            self.emergency_case_id.write({
                'state': 'discharged',
                'disposition': disposition,
                'disposition_datetime': now,
            })
