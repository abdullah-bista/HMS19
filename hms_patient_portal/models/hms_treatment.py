# -*- coding: utf-8 -*-
from odoo import models


class HmsTreatment(models.Model):
    _name = 'hms.treatment'
    _inherit = ['hms.treatment', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/treatments/%s' % rec.id
