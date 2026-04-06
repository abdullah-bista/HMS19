from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsReception(models.Model):
    _name = 'hms.reception'
    _description = 'Patient Reception / Check-In'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'checkin_datetime desc, id desc'

    name = fields.Char(
        string='Reception Number', readonly=True, copy=False, default='New'
    )
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True, index=True
    )
    checkin_datetime = fields.Datetime(
        string='Check-In Date/Time', default=fields.Datetime.now, tracking=True
    )
    receptionist_id = fields.Many2one(
        'res.users', string='Receptionist',
        default=lambda self: self.env.user, tracking=True
    )
    chief_complaint = fields.Text(string='Chief Complaint', required=True)
    is_emergency = fields.Boolean(string='Emergency', default=False, tracking=True)
    state = fields.Selection([
        ('registered', 'Registered'),
        ('routed', 'Routed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='registered', required=True, tracking=True)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case', readonly=True,
        ondelete='set null', tracking=True
    )
    appointment_id = fields.Many2one(
        'hms.appointment', string='Appointment', readonly=True,
        ondelete='set null', tracking=True
    )
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
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.reception') or 'New'
        return super().create(vals_list)

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_route_to_emergency(self):
        """Route patient to Emergency: create ER case and link it."""
        self.ensure_one()
        if self.state != 'registered':
            raise UserError(_('Only registered check-ins can be routed.'))
        er_case = self.env['hms.emergency.case'].create({
            'patient_id': self.patient_id.id,
            'arrival_datetime': self.checkin_datetime or fields.Datetime.now(),
            'chief_complaint': self.chief_complaint,
            'company_id': self.company_id.id,
        })
        self.write({
            'emergency_case_id': er_case.id,
            'is_emergency': True,
            'state': 'routed',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Emergency Case'),
            'res_model': 'hms.emergency.case',
            'view_mode': 'form',
            'res_id': er_case.id,
            'target': 'current',
        }

    def action_route_to_appointment(self):
        """Create a new appointment from this check-in and open it."""
        self.ensure_one()
        if self.state != 'registered':
            raise UserError(_('Only registered check-ins can be routed.'))
        appointment = self.env['hms.appointment'].create({
            'patient_id': self.patient_id.id,
            'date': self.checkin_datetime or fields.Datetime.now(),
            'chief_complain': self.chief_complaint,
        })
        self.write({
            'appointment_id': appointment.id,
            'state': 'routed',
        })
        return self.action_view_appointment()

    def action_view_appointment(self):
        """Open the linked appointment form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Appointment'),
            'res_model': 'hms.appointment',
            'view_mode': 'form',
            'res_id': self.appointment_id.id,
            'target': 'current',
        }

    def action_view_emergency_case(self):
        """Open the linked emergency case form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Emergency Case'),
            'res_model': 'hms.emergency.case',
            'view_mode': 'form',
            'res_id': self.emergency_case_id.id,
            'target': 'current',
        }

    def action_done(self):
        """Mark check-in as done."""
        for rec in self:
            if rec.state not in ('registered', 'routed'):
                raise UserError(_('Only registered or routed check-ins can be marked done.'))
            rec.state = 'done'

    def action_cancel(self):
        """Cancel check-in."""
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Done check-ins cannot be cancelled.'))
            rec.state = 'cancelled'
