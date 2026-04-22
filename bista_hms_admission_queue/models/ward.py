# -*- coding: utf-8 -*-
from odoo import fields, models


class HmsWardAdmissionQueue(models.Model):
    """Add an admission queue token prefix to hospital wards."""
    _inherit = 'hms.ward'

    admission_queue_prefix = fields.Char(
        string='Admission Queue Prefix',
        size=3,
        help=(
            "1–3 character prefix used to generate admission queue tokens for this ward "
            "(e.g. 'ICU', 'MAT', 'SUR'). If left blank, the first 3 letters of the "
            "ward name are used. Tokens will look like: ICU-001, ICU-002 …"
        ),
    )
