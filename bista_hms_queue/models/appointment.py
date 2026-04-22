# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsAppointmentQueue(models.Model):
    """Extend hms.appointment with queue token and priority ordering."""
    _inherit = 'hms.appointment'

    bista_queue_token = fields.Char(
        string='Queue Token',
        copy=False,
        readonly=True,
        help="Daily queue token issued when the patient enters the waiting room (e.g. OPD-007).",
    )
    bista_queue_token_number = fields.Integer(
        string='Token Number',
        copy=False,
        readonly=True,
        help="Raw integer portion of the token, used for efficient ORDER BY in queue views.",
    )
    bista_queue_priority = fields.Integer(
        string='Queue Priority',
        compute='_compute_bista_queue_priority',
        store=True,
        help="Numeric priority derived from urgency: 0=Medical Emergency, 1=Urgent, 2=Normal.",
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('urgency')
    def _compute_bista_queue_priority(self):
        _map = {'medical_emergency': 0, 'urgent': 1, 'normal': 2}
        for rec in self:
            rec.bista_queue_priority = _map.get(rec.urgency, 2)

    # ------------------------------------------------------------------
    # Override: appointment_waiting — generate token after state change
    # ------------------------------------------------------------------

    def appointment_waiting(self):
        """Chain: bista_hms_queue → bista_hms_emergency → acs_hms (base).

        bista_hms_emergency validates that an invoice exists.
        acs_hms sets state='waiting' and waiting_date_start.
        This override then assigns a daily queue token.
        """
        result = super().appointment_waiting()
        for rec in self:
            if not rec.bista_queue_token:
                token = self.env['bista.queue.counter'].get_next_token(
                    department_id=rec.department_id.id if rec.department_id else False,
                    company_id=rec.company_id.id,
                )
                try:
                    token_number = int(token.split('-')[-1])
                except (ValueError, IndexError):
                    token_number = 0
                rec.write({
                    'bista_queue_token': token,
                    'bista_queue_token_number': token_number,
                })
        return result

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @api.model
    def action_call_next_patient(self, department_id=None, physician_id=None):
        """Call the highest-priority waiting patient.

        Ordering: bista_queue_priority ASC (0=emergency first),
                  then waiting_date_start ASC (FIFO within same priority).

        Args:
            department_id (int | None): Filter by department, or None for all.
            physician_id (int | None): Filter by physician, or None for all.

        Returns:
            dict: Info about the called appointment.

        Raises:
            UserError: If no patients are currently waiting.
        """
        domain = [('state', '=', 'waiting')]
        if department_id:
            domain.append(('department_id', '=', department_id))
        if physician_id:
            domain.append(('physician_id', '=', physician_id))

        next_appt = self.search(
            domain,
            order='bista_queue_priority ASC, waiting_date_start ASC',
            limit=1,
        )
        if not next_appt:
            raise UserError(_('No patients are currently waiting in the queue.'))

        next_appt.appointment_consultation()
        return {
            'appointment_id': next_appt.id,
            'patient_name': next_appt.patient_id.name,
            'token': next_appt.bista_queue_token or '',
        }

    def action_call_this_patient(self):
        """Call this specific waiting patient to consultation."""
        self.ensure_one()
        if self.state != 'waiting':
            raise UserError(_('Only patients currently in waiting state can be called.'))
        self.appointment_consultation()
