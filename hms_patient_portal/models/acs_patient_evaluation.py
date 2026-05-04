# -*- coding: utf-8 -*-
from odoo import models


class AcsPatientEvaluation(models.Model):
    _name = 'acs.patient.evaluation'
    _inherit = ['acs.patient.evaluation', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/my/evaluations/%s' % rec.id
