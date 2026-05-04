# -*- coding: utf-8 -*-
from odoo import models


class PrescriptionOrder(models.Model):
    _name = 'prescription.order'
    _inherit = ['prescription.order', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/prescriptions/%s' % rec.id
