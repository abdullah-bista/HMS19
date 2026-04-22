# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BistaUpcomingPatientQueue(models.Model):
    _name = 'bista.upcoming.patient.queue'
    _description = 'Upcoming Patient Queue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'queue_priority asc, registration_datetime asc'

    # ── Identity ──────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )

    # ── Patient ───────────────────────────────────────────────────────
    patient_id = fields.Many2one(
        'hms.patient',
        string='Patient',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    # ── Contact Channel ───────────────────────────────────────────────
    contact_channel = fields.Selection([
        ('walk_in',            'Walk-In'),
        ('phone',              'Phone'),
        ('online',             'Online'),
        ('referral',           'Referral'),
        ('insurance',          'Insurance'),
        ('emergency_referral', 'Emergency Referral'),
    ], string='Contact Channel', required=True, tracking=True)

    referral_source_id = fields.Many2one(
        'res.partner',
        string='Referral Source',
        domain=[('is_referring_doctor', '=', True)],
        ondelete='set null',
        help="Referring physician or partner. Visible only when channel is Referral.",
    )

    # ── Queue Type ────────────────────────────────────────────────────
    queue_type = fields.Selection([
        ('consultation', 'OPD Consultation'),
        ('admission',    'IPD Admission'),
    ], string='Queue Type', required=True, tracking=True)

    # ── Routing Fields ────────────────────────────────────────────────
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain=[('patient_department', '=', True)],
        ondelete='restrict',
    )
    ward_id = fields.Many2one(
        'hms.ward',
        string='Ward',
        ondelete='restrict',
    )
    preferred_physician_id = fields.Many2one(
        'hms.physician',
        string='Preferred Physician',
        ondelete='restrict',
    )

    # ── Clinical ──────────────────────────────────────────────────────
    urgency = fields.Selection([
        ('normal',            'Normal'),
        ('urgent',            'Urgent'),
        ('medical_emergency', 'Medical Emergency'),
    ], string='Urgency', default='normal', required=True, tracking=True)

    chief_complaint = fields.Text(string='Chief Complaint')

    # ── Timestamps ────────────────────────────────────────────────────
    registration_datetime = fields.Datetime(
        string='Registered At',
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('pending',   'Pending'),
        ('contacted', 'Contacted'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='pending', required=True, copy=False, tracking=True)

    # ── Output Links ──────────────────────────────────────────────────
    appointment_id = fields.Many2one(
        'hms.appointment',
        string='Appointment',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    admission_id = fields.Many2one(
        'hms.admission',
        string='Admission',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    # ── Staff Notes ───────────────────────────────────────────────────
    notes = fields.Text(string='Staff Notes')

    # ── Multi-company ─────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Hospital',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # ── Computed Priority (for ORDER BY) ──────────────────────────────
    queue_priority = fields.Integer(
        string='Queue Priority',
        compute='_compute_queue_priority',
        store=True,
        help="0=Medical Emergency, 1=Urgent, 2=Normal. Used for ordering.",
    )

    # ── Compute ───────────────────────────────────────────────────────

    @api.depends('urgency')
    def _compute_queue_priority(self):
        _map = {'medical_emergency': 0, 'urgent': 1, 'normal': 2}
        for rec in self:
            rec.queue_priority = _map.get(rec.urgency, 2)

    # ── ORM overrides ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('bista.upcoming.patient.queue') or 'New'
                )
        return super().create(vals_list)

    # ── State Transitions ─────────────────────────────────────────────

    def action_contact(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(
                    _('Only records in Pending state can be moved to Contacted. '
                      'Current state: %s') % rec.state
                )
            rec.state = 'contacted'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'processed':
                raise UserError(_('Processed queue records cannot be cancelled.'))
            if rec.state == 'cancelled':
                continue
            rec.state = 'cancelled'

    def action_reset_to_pending(self):
        for rec in self:
            if rec.state != 'contacted':
                raise UserError(_('Only Contacted records can be reset to Pending.'))
            rec.state = 'pending'

    # ── Process Actions ───────────────────────────────────────────────

    def action_create_appointment(self):
        self.ensure_one()
        if self.state != 'contacted':
            raise UserError(
                _('Please mark the patient as Contacted before creating an appointment.')
            )
        if self.queue_type != 'consultation':
            raise UserError(_('This queue entry is for admission, not consultation.'))

        product_id = self.env.company.consultation_product_id
        if not product_id:
            raise UserError(
                _('Please configure the Consultation Service product in Hospital Settings '
                  'before creating appointments from the queue.')
            )

        appointment = self.env['hms.appointment'].create({
            'patient_id':    self.patient_id.id,
            'department_id': self.department_id.id if self.department_id else False,
            'physician_id':  self.preferred_physician_id.id if self.preferred_physician_id else False,
            'urgency':       self.urgency,
            'chief_complain': self.chief_complaint or '',
            'product_id':    product_id.id,
            'company_id':    self.company_id.id,
        })

        self.write({
            'appointment_id': appointment.id,
            'state': 'processed',
        })

        return {
            'type':      'ir.actions.act_window',
            'res_model': 'hms.appointment',
            'res_id':    appointment.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_create_admission(self):
        self.ensure_one()
        if self.state != 'contacted':
            raise UserError(
                _('Please mark the patient as Contacted before creating an admission.')
            )
        if self.queue_type != 'admission':
            raise UserError(_('This queue entry is for consultation, not admission.'))

        return {
            'type':      'ir.actions.act_window',
            'res_model': 'hms.admission',
            'view_mode': 'form',
            'target':    'current',
            'context': {
                'default_patient_id':             self.patient_id.id,
                'default_ward_id':                self.ward_id.id if self.ward_id else False,
                'default_attending_physician_id':  self.preferred_physician_id.id if self.preferred_physician_id else False,
                'default_admission_type':         'elective',
                'default_admission_reason':       self.chief_complaint or '',
                'default_company_id':             self.company_id.id,
                'default_upcoming_queue_id':      self.id,
            },
        }

    # ── Call Next ─────────────────────────────────────────────────────

    @api.model
    def action_call_next(self, queue_type=None, department_id=None, ward_id=None):
        domain = [
            ('state', '=', 'pending'),
            ('company_id', 'in', self.env.companies.ids),
        ]
        if queue_type:
            domain.append(('queue_type', '=', queue_type))
        if department_id:
            domain.append(('department_id', '=', department_id))
        if ward_id:
            domain.append(('ward_id', '=', ward_id))

        next_rec = self.search(
            domain,
            order='queue_priority ASC, registration_datetime ASC',
            limit=1,
        )
        if not next_rec:
            raise UserError(_('No pending patients are currently in the upcoming queue.'))

        next_rec.action_contact()
        return {
            'queue_id':     next_rec.id,
            'name':         next_rec.name,
            'patient_name': next_rec.patient_id.name,
        }


class HmsAdmissionUpcomingQueue(models.Model):
    """Extend hms.admission with a back-pointer to the upcoming queue record.
    When an admission is created from the upcoming queue (via action_create_admission),
    the create override writes back to the queue record to mark it as processed.
    """
    _inherit = 'hms.admission'

    upcoming_queue_id = fields.Many2one(
        'bista.upcoming.patient.queue',
        string='Upcoming Queue Entry',
        ondelete='set null',
        copy=False,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.upcoming_queue_id:
                rec.upcoming_queue_id.write({
                    'admission_id': rec.id,
                    'state': 'processed',
                })
        return records
