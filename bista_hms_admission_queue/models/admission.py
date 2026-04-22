# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsAdmissionQueue(models.Model):
    """Extend hms.admission with admission queue token and priority."""
    _inherit = 'hms.admission'

    admission_queue_token = fields.Char(
        string='Queue Token',
        copy=False,
        readonly=True,
        help="Daily admission queue token issued when the admission is confirmed (e.g. ICU-003).",
    )
    admission_queue_token_number = fields.Integer(
        string='Token Number',
        copy=False,
        readonly=True,
        help="Raw integer portion of the token for efficient ORDER BY.",
    )
    admission_queue_priority = fields.Integer(
        string='Queue Priority',
        compute='_compute_admission_queue_priority',
        store=True,
        help=(
            "Numeric priority derived from admission_type: "
            "0=emergency, 1=maternity, 2=transfer, 3=elective/appointment."
        ),
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('admission_type')
    def _compute_admission_queue_priority(self):
        _map = {
            'emergency': 0,
            'maternity': 1,
            'transfer': 2,
            'elective': 3,
            'appointment': 3,
        }
        for rec in self:
            rec.admission_queue_priority = _map.get(rec.admission_type, 3)

    # ------------------------------------------------------------------
    # Override: action_confirm — generate queue token after confirmation
    # ------------------------------------------------------------------

    def action_confirm(self):
        """After confirming (draft → confirmed), assign a daily queue token."""
        result = super().action_confirm()
        for rec in self:
            if not rec.admission_queue_token and rec.ward_id:
                token = self.env['bista.admission.queue.counter'].get_next_token(
                    ward_id=rec.ward_id.id,
                    company_id=rec.company_id.id,
                )
                try:
                    token_number = int(token.split('-')[-1])
                except (ValueError, IndexError):
                    token_number = 0
                rec.write({
                    'admission_queue_token': token,
                    'admission_queue_token_number': token_number,
                })
        return result

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_call_this_admission(self):
        """Admit this specific confirmed patient (confirmed → in_progress)."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed admissions can be admitted from the queue.'))
        self.action_admit()

    @api.model
    def action_call_next_admission(self, ward_id=None):
        """Admit the highest-priority confirmed admission.

        Ordering: admission_queue_priority ASC (0=emergency first),
                  then admission_datetime ASC (FIFO within same priority).

        Args:
            ward_id (int | None): Filter by ward, or None for all wards.

        Returns:
            dict: Info about the admitted record.

        Raises:
            UserError: If no confirmed admissions are in the queue.
        """
        domain = [('state', '=', 'confirmed')]
        if ward_id:
            domain.append(('ward_id', '=', ward_id))

        next_adm = self.search(
            domain,
            order='admission_queue_priority ASC, admission_datetime ASC',
            limit=1,
        )
        if not next_adm:
            raise UserError(_('No confirmed admissions are currently in the queue.'))

        next_adm.action_call_this_admission()
        return {
            'admission_id': next_adm.id,
            'patient_name': next_adm.patient_id.name,
            'token': next_adm.admission_queue_token or '',
        }
