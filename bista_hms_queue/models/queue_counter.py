# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BistaqueueCounter(models.Model):
    """Daily queue token counter per department.

    One row is created per (department, date, company) combination.
    The last_token_number is incremented atomically within the PostgreSQL
    transaction each time a new token is issued, making it safe under
    concurrent receptionist sessions.
    """
    _name = 'bista.queue.counter'
    _description = 'Queue Token Counter'
    _order = 'counter_date desc, department_id'
    _rec_name = 'counter_date'

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
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
            'unique_dept_date_company',
            'UNIQUE(department_id, counter_date, company_id)',
            'A queue counter record must be unique per department, date and company.',
        ),
    ]

    @api.model
    def get_next_token(self, department_id, company_id):
        """Atomically increment and return the next token for today.

        Args:
            department_id (int | False): ID of hr.department, or False for general queue.
            company_id (int): ID of res.company.

        Returns:
            str: Formatted token string, e.g. ``"OPD-007"`` or ``"G-001"``.
        """
        today = fields.Date.today()

        # Determine token prefix from department
        prefix = 'G'
        if department_id:
            dept = self.env['hr.department'].browse(department_id)
            if dept.bista_queue_prefix:
                prefix = dept.bista_queue_prefix.strip().upper()
            elif dept.name:
                prefix = dept.name[:1].upper()

        counter = self.search([
            ('department_id', '=', department_id or False),
            ('counter_date', '=', today),
            ('company_id', '=', company_id),
        ], limit=1)

        if not counter:
            counter = self.create({
                'department_id': department_id or False,
                'counter_date': today,
                'last_token_number': 0,
                'company_id': company_id,
            })

        next_number = counter.last_token_number + 1
        counter.last_token_number = next_number

        return '{}-{}'.format(prefix, str(next_number).zfill(3))
