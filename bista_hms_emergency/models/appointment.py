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

    @api.depends('lab_request_ids')
    def _compute_lab_request_count(self):
        for rec in self:
            rec.lab_request_count = len(rec.lab_request_ids)

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
