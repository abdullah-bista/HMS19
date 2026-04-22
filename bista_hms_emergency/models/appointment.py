from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Appointment(models.Model):
    _inherit = 'hms.appointment'

    is_emergency = fields.Boolean(string='Emergency', default=False)
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        ondelete='set null', index=True
    )
    admission_id = fields.Many2one(
        'hms.admission', string='Admission',
        ondelete='set null', index=True
    )
    lab_request_ids = fields.One2many(
        'acs.laboratory.request', 'appointment_id', string='Lab Requests'
    )
    lab_request_count = fields.Integer(
        compute='_compute_lab_request_count', string='# Lab Requests'
    )
    admission_count = fields.Integer(
        compute='_compute_admission_count', string='# Admissions'
    )
    has_ongoing_admission = fields.Boolean(
        compute='_compute_admission_count',
        help="True when the linked admission is active (not discharged/cancelled)."
    )

    @api.depends('lab_request_ids')
    def _compute_lab_request_count(self):
        for rec in self:
            rec.lab_request_count = len(rec.lab_request_ids)

    @api.depends('admission_id', 'admission_id.state')
    def _compute_admission_count(self):
        for rec in self:
            rec.admission_count = 1 if rec.admission_id else 0
            rec.has_ongoing_admission = bool(
                rec.admission_id and rec.admission_id.state not in ('discharged', 'cancelled')
            )

    def action_view_lab_requests(self):
        """Open all lab requests linked to this appointment."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'acs_laboratory.hms_action_lab_test_request'
        )
        action['domain'] = [('appointment_id', '=', self.id)]
        action['context'] = {
            'default_appointment_id': self.id,
            'default_patient_id': self.patient_id.id,
            'default_physician_id': self.physician_id.id if self.physician_id else False,
        }
        return action

    def action_initiate_lab_request(self):
        """Open a new lab request form pre-filled with this appointment's data."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'acs_laboratory.hms_action_lab_test_request'
        )
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_appointment_id': self.id,
            'default_patient_id': self.patient_id.id,
            'default_physician_id': self.physician_id.id if self.physician_id else False,
        }
        return action

    def appointment_done(self):
        res = super().appointment_done()
        reception = self.env['hms.reception'].search([
            ('appointment_id', 'in', self.ids),
            ('state', 'not in', ('done', 'cancelled')),
        ])
        if reception:
            reception.state = 'done'
        return res

    def action_create_consultation_invoice(self):
        """Create a consultation invoice using the appointment's product at cost price."""
        self.ensure_one()
        if self.state != 'confirm':
            raise UserError(_('Invoice can only be created for confirmed appointments.'))
        if self.invoice_id:
            raise UserError(_('An invoice already exists for this appointment.'))
        if not self.product_id:
            raise UserError(_('Please set a consultation product on the appointment first.'))

        partner = self.patient_id.partner_id
        product_data = [{
            'product_id': self.product_id,
            'quantity': 1.0,
            'price_unit': self.product_id.standard_price,
        }]
        inv_data = {
            'physician_id': self.physician_id.id if self.physician_id else False,
            'hospital_invoice_type': 'appointment',
            'appointment_id': self.id,
        }
        invoice = self.acs_create_invoice(partner, self.patient_id, product_data, inv_data)
        self.invoice_id = invoice.id
        return self.view_invoice()

    def appointment_waiting(self):
        if not self.invoice_id:
            raise ValidationError('Please create invoice first before send the patient into Waiting.')
        return super(Appointment, self).appointment_waiting()

    def action_admit_to_ipd(self):
        """Open IPD Admission form pre-filled from this appointment (doctor consultation flow)."""
        self.ensure_one()
        if self.state != 'in_consultation':
            raise UserError(_('Admission can only be initiated during an active consultation.'))
        if self.admission_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('IPD Admission'),
                'res_model': 'hms.admission',
                'view_mode': 'form',
                'res_id': self.admission_id.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create IPD Admission'),
            'res_model': 'hms.admission',
            'view_mode': 'form',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_appointment_id': self.id,
                'default_admission_type': 'appointment',
                'default_attending_physician_id': self.physician_id.id if self.physician_id else False,
                'default_admission_reason': self.chief_complain or '',
            },
            'target': 'current',
        }

    def action_view_admission(self):
        """Open the linked IPD admission from the smart button."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('IPD Admission'),
            'res_model': 'hms.admission',
            'view_mode': 'form',
            'res_id': self.admission_id.id,
            'target': 'current',
        }
