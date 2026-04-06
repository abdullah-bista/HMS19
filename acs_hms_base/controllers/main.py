# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request

class AcsHms(http.Controller):

    @http.route(['/acs/data'], type='jsonrpc', auth="public", methods=['POST'], website=True)
    def acs_system_data(self, **kw):
        return request.env['res.company'].acs_get_blocking_data()
