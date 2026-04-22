# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BistaAdmissionQueueCounter(models.Model):
    """Daily admission queue token counter per ward.

    One row per (ward_id, counter_date, company_id). The last_token_number
    is incremented atomically within the PostgreSQL transaction each time a
    new admission token is issued.
    """
    _name = 'bista.admission.queue.counter'
    _description = 'Admission Queue Token Counter'
    _order = 'counter_date desc, ward_id'
    _rec_name = 'counter_date'

    ward_id = fields.Many2one(
        'hms.ward',
        string='Ward',
        ondelete='restrict',
        index=True,
    )
    counter_date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        index=True,
    )
    last_token_number = fields.Integer(
        string='Last Token Issued',
        default=0,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    _sql_constraints = [
        (
            'unique_ward_date_company',
            'UNIQUE(ward_id, counter_date, company_id)',
            'An admission queue counter must be unique per ward, date and company.',
        ),
    ]

    @api.model
    def get_next_token(self, ward_id, company_id):
        """Atomically increment and return the next admission queue token.

        Args:
            ward_id (int | False): ID of hms.ward, or False for general queue.
            company_id (int): ID of res.company.

        Returns:
            str: e.g. 'ICU-007', 'MAT-001', 'ADM-003'
        """
        today = fields.Date.today()

        prefix = 'ADM'
        if ward_id:
            ward = self.env['hms.ward'].browse(ward_id)
            if ward.admission_queue_prefix:
                prefix = ward.admission_queue_prefix.strip().upper()
            elif ward.name:
                prefix = ward.name[:3].upper()

        counter = self.search([
            ('ward_id', '=', ward_id or False),
            ('counter_date', '=', today),
            ('company_id', '=', company_id),
        ], limit=1)

        if not counter:
            counter = self.create({
                'ward_id': ward_id or False,
                'counter_date': today,
                'last_token_number': 0,
                'company_id': company_id,
            })

        next_number = counter.last_token_number + 1
        counter.last_token_number = next_number

        return '{}-{}'.format(prefix, str(next_number).zfill(3))
