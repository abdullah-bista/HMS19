# -*- coding: utf-8 -*-

from odoo import api, fields, models ,_
from odoo.exceptions import UserError
from datetime import date, datetime, timedelta

class ProcedureGroupLine(models.Model):
    _name = "procedure.group.line"
    _description = "Procedure Group Line"
    _order = 'sequence'
    _rec_name = 'product_id'

    sequence = fields.Integer("Sequence", default=10)
    group_id = fields.Many2one('procedure.group', ondelete='restrict', string='Procedure Group')
    product_id = fields.Many2one('product.product', string='Procedure', ondelete='restrict', required=True)
    days_to_add = fields.Integer('Days to add',help="Days to add for next date")
    procedure_time = fields.Float(related='product_id.procedure_time', string='Procedure Time', readonly=True)
    price_unit = fields.Float(related='product_id.list_price', string='Price', readonly=True)
    consumable_line_ids = fields.One2many('hms.consumable.line', 'procedure_group_id',
        string='Consumable Lines', copy=False)


class ProcedureGroup(models.Model):
    _name = "procedure.group"
    _description = "Procedure Group"

    name = fields.Char(string='Group Name', required=True)
    line_ids = fields.One2many('procedure.group.line', 'group_id', string='Group lines')


class AcsPatientProcedure(models.Model):
    _name="acs.patient.procedure"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin', 'acs.document.mixin', 'acs.calendar.mixin']
    _description = "Patient Procedure"
    _order = "id desc"

    @api.depends('date', 'date_stop')
    def acs_get_duration(self):
        for rec in self:
            duration = 0.0
            if rec.date and rec.date_stop:
                diff = rec.date_stop - rec.date
                duration = (diff.days * 24) + (diff.seconds/3600)
            rec.duration = duration

    def _acs_get_attachments(self):
        attachments = super(AcsPatientProcedure, self)._acs_get_attachments()
        attachments += self.appointment_ids.mapped('attachment_ids')
        return attachments

    name = fields.Char(string="Name", tracking=1,default='New')
    patient_id = fields.Many2one('hms.patient', string='Patient', required=True, tracking=1)
    product_id = fields.Many2one('product.product', string='Procedure', 
        change_default=True, ondelete='restrict', required=True)
    price_unit = fields.Float("Price")
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False)
    physician_id = fields.Many2one('hms.physician', ondelete='restrict', string='Physician', 
        index=True)
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
    ], string='Status', default='scheduled', tracking=1)
    company_id = fields.Many2one('res.company', ondelete='restrict',
        string='Hospital', default=lambda self: self.env.company)
    date = fields.Datetime("Date", tracking=1)
    date_stop = fields.Datetime("End Date", tracking=1)
    duration = fields.Float('Duration', compute="acs_get_duration", store=True)

    diseas_id = fields.Many2one('hms.diseases', 'Disease')
    description = fields.Text(string="Description")
    treatment_id = fields.Many2one('hms.treatment', 'Treatment')
    appointment_id = fields.Many2one('hms.appointment', 'Appointment')
    appointment_ids = fields.Many2many('hms.appointment', 'acs_appointment_procedure_rel', 'appointment_id', 'procedure_id', 'Appointments')
    department_id = fields.Many2one('hr.department', ondelete='restrict', 
        domain=[('patient_department', '=', True)], string='Department', tracking=1)
    department_type = fields.Selection(related='department_id.department_type', string="Appointment Department", store=True)

    consumable_line_ids = fields.One2many('hms.consumable.line', 'procedure_id',
        string='Consumable Line', copy=False)
    acs_kit_id = fields.Many2one('acs.product.kit', string='Kit')
    acs_kit_qty = fields.Integer("Kit Qty", default=1)
    invoice_exempt = fields.Boolean(string='Invoice Exempt')
    notes = fields.Char("Notes")
    nurse_id = fields.Many2one('res.users','Nurse')

    @api.model
    def default_get(self, fields):
        res = super(AcsPatientProcedure, self).default_get(fields)
        if self._context.get('acs_department_type'):
            department = self.env['hr.department'].search([('department_type','=',self._context.get('acs_department_type'))], limit=1)
            if department:
                res['department_id'] = department.id
        return res

    @api.onchange('product_id')
    def onchange_product(self):
        if self.product_id:
            self.price_unit = self.product_id.list_price

    @api.onchange('product_id','date')
    def onchange_date_and_product(self):
        if self.product_id and self.product_id.procedure_time and self.date:
            self.date_stop = self.date + timedelta(hours=self.product_id.procedure_time)

    def action_running(self):
        self.state = 'running'
        if not self.date:
            self.date = fields.Datetime.now()

    def action_schedule(self):
        self.state = 'scheduled'

    def action_done(self):
        if self.consumable_line_ids:
            self.acs_consume_material('procedure_id')
        self.state = 'done'
        if not self.date_stop:
            self.date_stop = fields.Datetime.now()
        if not self.nurse_id:
            self.nurse_id = self.env.user.id

    def action_cancel(self):
        self.state = 'cancel'

    def unlink(self):
        for rec in self:
            if rec.state not in ['scheduled','cancel']:
                raise UserError(_('Record can be deleted only in Canceled/Scheduled state.'))
        return super(AcsPatientProcedure, self).unlink()
    
    def acs_prepare_calendar_data(self):
        data = super().acs_prepare_calendar_data()
        user_id = self.physician_id.user_id
        partner_ids = [user_id.partner_id.id]        
        data.update({
            'user_id': user_id.id,
            'start': self.date,
            'stop': self.date_stop,
            'partner_ids': [(6, 0, partner_ids)],
        })
        return data

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                seq_date = None
                if vals.get('date'):
                    seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
                vals['name'] = self.env['ir.sequence'].with_company(vals.get('company_id')).next_by_code('acs.patient.procedure', sequence_date=seq_date) or _("New")
        res = super().create(vals_list)
        for record in res:
            record.acs_calendar_event('physician_id')
        return res

    def write(self, values):
        res = super().write(values)
        fields_to_check = ['date', 'date_stop' ,'physician_id', 'state']
        if any(f in values for f in fields_to_check):
            self.acs_calendar_event('physician_id')
        return res

    def get_procedure_invoice_data(self):
        product_data = [{
            'name': _("Patient Procedure Charges"),
        }]
        for rec in self:
            #Pass price if it is updated else pass 0
            #so if 0 is passed it will apply pricelist value properly.
            procedure_data = {'product_id': rec.product_id, 'line_type': 'procedure'}
            if rec.price_unit!=rec.product_id.list_price:
                procedure_data['price_unit'] = rec.price_unit
            product_data.append(procedure_data)

            #Line for procedure Consumables
            for consumable in rec.consumable_line_ids:
                product_data.append({
                    'product_id': consumable.product_id,
                    'quantity': consumable.qty,
                    'lot_id': consumable.lot_id and consumable.lot_id.id or False, 
                    'line_type': 'procedure'
                })
        return product_data

    def action_create_invoice(self):
        product_data = self.get_procedure_invoice_data()

        inv_data = {
            'physician_id': self.physician_id and self.physician_id.id or False,
            'hospital_invoice_type': 'procedure',
        }
        acs_context = {'commission_partner_ids':self.physician_id.partner_id.id}
        invoice = self.with_context(acs_context).acs_create_invoice(partner=self.patient_id.partner_id, patient=self.patient_id, product_data=product_data, inv_data=inv_data)
        self.invoice_id = invoice.id
        self.invoice_id.procedure_id = self.id        

    def acs_get_consume_locations(self):
        if not self.company_id.procedure_usage_location_id:
            raise UserError(_('Please define a procedure location where the consumables will be used.'))
        if not self.company_id.procedure_stock_location_id:
            raise UserError(_('Please define a procedure location from where the consumables will be taken.'))

        dest_location_id  = self.company_id.procedure_usage_location_id.id
        source_location_id  = self.company_id.procedure_stock_location_id.id
        return source_location_id, dest_location_id

    def view_invoice(self):
        invoices = self.mapped('invoice_id')
        action = self.acs_action_view_invoice(invoices)
        return action

    def action_show_details(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.action_acs_patient_procedure")
        action['context'] = {'default_patient_id': self.patient_id.id}
        action['res_id'] = self.id
        action['views'] = [(self.env.ref('acs_hms.view_acs_patient_procedure_form').id, 'form')]
        action['target'] = 'new'
        return action

    #method to create get invoice data and set passed invoice id.
    def acs_common_invoice_procedure_data(self, invoice_id=False):
        data = []
        if self.ids:
            data = self.get_procedure_invoice_data()
            if invoice_id:
                self.invoice_id = invoice_id.id
        return data


class StockMove(models.Model):
    _inherit = "stock.move"

    procedure_id = fields.Many2one('acs.patient.procedure', ondelete="cascade", string="Procedure")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: