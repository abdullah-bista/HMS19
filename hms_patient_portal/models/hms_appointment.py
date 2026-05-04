# -*- coding: utf-8 -*-
from odoo import models


class HmsAppointment(models.Model):
    _name = 'hms.appointment'
    _inherit = ['hms.appointment', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/appointments/%s' % rec.id
