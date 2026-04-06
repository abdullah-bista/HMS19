# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    acs_medical_event = fields.Text("Medical Event")

    def write(self, values):
        if not self._context.get('acs_avoid_check'):
            for rec in self:
                if rec.acs_medical_event and not ('videocall_channel_id' in values):
                    raise UserError(_("Medical operation is linked with this event. Please update data on respective medical record not here."))
        return super().write(values)
    
    def unlink(self):
        if not self._context.get('acs_avoid_check'):
            for rec in self:
                if rec.acs_medical_event:
                    raise UserError(('There is already linked medical operation with this record.'))
        return super().unlink()
