# -*- coding: utf-8 -*-
from odoo import fields, models


class HrDepartmentQueue(models.Model):
    """Add a queue token prefix to hospital departments."""
    _inherit = 'hr.department'

    bista_queue_prefix = fields.Char(
        string='Queue Token Prefix',
        size=3,
        help=(
            "1–3 character prefix used to generate queue tokens for this department "
            "(e.g. 'OPD', 'A', 'GEN'). If left blank, the first letter of the "
            "department name is used. Tokens will look like: OPD-001, OPD-002 …"
        ),
    )
