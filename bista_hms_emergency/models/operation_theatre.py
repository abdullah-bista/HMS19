from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsOperationTheatre(models.Model):
    _name = 'hms.operation.theatre'
    _description = 'Operation Theatre Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'scheduled_datetime desc, id desc'

    name = fields.Char(
        string='OT Booking Number', readonly=True, copy=False, default='New'
    )

    # Patient
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True, index=True
    )
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', tracking=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='IPD Admission',
        ondelete='set null', tracking=True
    )

    # Operation Info
    operation_type = fields.Selection([
        ('emergency', 'Emergency'),
        ('elective', 'Elective'),
        ('semi_elective', 'Semi-Elective'),
    ], string='Operation Type', required=True, default='elective', tracking=True)
    ot_room = fields.Char(string='OT Room', required=True)

    # Surgical Team
    surgeon_id = fields.Many2one(
        'hms.physician', string='Surgeon', required=True,
        ondelete='restrict', tracking=True
    )
    anaesthetist_id = fields.Many2one(
        'hms.physician', string='Anaesthetist',
        ondelete='restrict', tracking=True
    )
    surgical_team_ids = fields.Many2many(
        'hms.physician', 'hms_ot_team_rel', 'ot_id', 'physician_id',
        string='Surgical Team'
    )

    # Anaesthesia
    anaesthesia_type = fields.Selection([
        ('general', 'General'),
        ('spinal', 'Spinal'),
        ('epidural', 'Epidural'),
        ('local', 'Local'),
        ('sedation', 'Sedation'),
        ('none', 'None'),
    ], string='Anaesthesia Type', tracking=True)

    # Scheduling
    scheduled_datetime = fields.Datetime(
        string='Scheduled Date/Time', required=True, tracking=True
    )
    estimated_duration = fields.Float(
        string='Estimated Duration (hrs)', digits=(4, 2)
    )

    # Actual Times
    actual_start = fields.Datetime(string='Actual Start', tracking=True)
    actual_end = fields.Datetime(string='Actual End', tracking=True)
    actual_duration = fields.Float(
        string='Actual Duration (hrs)', digits=(4, 2),
        compute='_compute_actual_duration', store=True
    )

    # Clinical
    diagnosis_ids = fields.Many2many(
        'hms.diseases', 'hms_ot_diagnosis_rel', 'ot_id', 'disease_id',
        string='Diagnoses'
    )
    pre_op_checklist = fields.Html(string='Pre-Op Checklist')
    operative_notes = fields.Html(string='Operative Notes')
    post_op_notes = fields.Html(string='Post-Op Instructions')
    complications = fields.Text(string='Complications')

    # State
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('pre_op', 'Pre-Op'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', required=True, tracking=True)
    cancelled_reason = fields.Text(string='Cancellation Reason')

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
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.operation.theatre') or 'New'
        return super().create(vals_list)

    # ---------------------------------------------------------------
    # Computed Fields
    # ---------------------------------------------------------------

    @api.depends('actual_start', 'actual_end')
    def _compute_actual_duration(self):
        for rec in self:
            if rec.actual_start and rec.actual_end:
                delta = rec.actual_end - rec.actual_start
                rec.actual_duration = delta.total_seconds() / 3600
            else:
                rec.actual_duration = 0.0

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_pre_op(self):
        """Move from Scheduled → Pre-Op."""
        for rec in self:
            if rec.state != 'scheduled':
                raise UserError(_('Only scheduled OT bookings can move to Pre-Op.'))
            rec.state = 'pre_op'

    def action_start(self):
        """Move from Pre-Op → In Progress and record actual start time."""
        for rec in self:
            if rec.state != 'pre_op':
                raise UserError(_('OT booking must be in Pre-Op state to start surgery.'))
            rec.write({
                'state': 'in_progress',
                'actual_start': fields.Datetime.now(),
            })

    def action_complete(self):
        """Move from In Progress → Completed and record actual end time."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('OT booking must be In Progress to complete.'))
            rec.write({
                'state': 'completed',
                'actual_end': fields.Datetime.now(),
            })

    def action_cancel(self):
        """Cancel OT booking."""
        for rec in self:
            if rec.state == 'completed':
                raise UserError(_('Completed OT bookings cannot be cancelled.'))
            rec.state = 'cancelled'
