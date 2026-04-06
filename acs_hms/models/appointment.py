# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class AppointmentPurpose(models.Model):
    _name = 'appointment.purpose'
    _description = "Appointment Purpose"

    name = fields.Char(string='Appointment Purpose', required=True, translate=True)


class AppointmentCabin(models.Model):
    _name = 'appointment.cabin'
    _description = "Appointment Cabin"

    name = fields.Char(string='Appointment Cabin', required=True, translate=True)


class AcsCancelReason(models.Model):
    _name = 'acs.cancel.reason'
    _description = "Cancel Reason"

    name = fields.Char('Reason')


class Appointment(models.Model):
    _name = 'hms.appointment'
    _description = "Appointment"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin', 'acs.document.mixin', 'acs.calendar.mixin']
    _order = "id desc"

    @api.model
    def _get_service_id(self):
        consultation = False
        if self.env.company.consultation_product_id:
            consultation = self.env.company.consultation_product_id.id
        return consultation
    
    @api.model
    def _get_default_physician(self):
        physician_id = False
        if self.env.user.sudo().physician_id:
            physician_id = self.env.user.physician_id.id
        return physician_id
    
    @api.model
    def get_default_end_date(self):
        duration = self.env.company.acs_appointment_planned_duration or 0.25
        return fields.Datetime.now() + timedelta(hours=duration)

    @api.depends('medical_alert_ids', 'allergy_ids')
    def acs_get_medical_data_count(self):
        for rec in self:
            rec.alert_count = len(rec.medical_alert_ids)
            rec.allergy_count = len(rec.allergy_ids)

    @api.depends('consumable_line_ids')
    def _get_consumable_line_count(self):
        for rec in self:
            rec.consumable_line_count = len(rec.consumable_line_ids.filtered(lambda l: l.display_type=='product'))

    @api.depends('patient_id', 'patient_id.birthday', 'date')
    def get_patient_age(self):
        for rec in self:
            age = ''
            if rec.patient_id.birthday:
                end_data = rec.date or fields.Datetime.now()
                delta = relativedelta(end_data, rec.patient_id.birthday)
                if delta.years <= 2:
                    age = str(delta.years) + _(" Year") + str(delta.months) + _(" Month ") + str(delta.days) + _(" Days")
                else:
                    age = str(delta.years) + _(" Year")
            rec.age = age

    @api.depends('evaluation_ids')
    def _get_evaluation(self):
        for rec in self:
            rec.evaluation_id = rec.evaluation_ids[0].id if rec.evaluation_ids else False

    def _acs_get_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    def _acs_invoice_policy(self):
        for rec in self:
            appointment_invoice_policy = rec.sudo().company_id.appointment_invoice_policy
            if rec.product_id.appointment_invoice_policy:
                appointment_invoice_policy = rec.product_id.appointment_invoice_policy
            rec.appointment_invoice_policy = appointment_invoice_policy
            if rec.appointment_invoice_policy=='foc':
                rec.invoice_exempt = True

    def get_procedures_to_invoice(self):
        Procedure = self.env['acs.patient.procedure']
        for rec in self:
            procedures = Procedure.search(['|',('appointment_ids', 'in', rec.id), ('appointment_id', '=', rec.id), ('invoice_id','=', False)])
            rec.procedure_to_invoice_ids = [(6, 0, procedures.ids)]

    def acs_get_department(self):
        for rec in self:
            acs_department_id = False
            if rec.department_id and rec.department_id.id:
                acs_department_id = self.env['hr.department'].sudo().search([('id','=',rec.department_id.id)]).id
            rec.acs_department_id = acs_department_id
    
    @api.depends('date')
    def get_appointment_date(self):
        for rec in self:
            rec.appointment_date = rec.date.date()
    
    def acs_patient_procedure_count(self):
        for rec in self:
            rec.patient_procedure_count = len(rec.patient_procedure_ids)

    name = fields.Char(string='Number', readonly=True, copy=False, tracking=1, default='New ')
    patient_id = fields.Many2one('hms.patient', ondelete='restrict',  string='Patient',
        required=True, index=True, help='Patient Name', tracking=1)
    image_128 = fields.Binary(related='patient_id.image_128',string='Image', readonly=True)
    physician_id = fields.Many2one('hms.physician', ondelete='restrict', string='Physician', 
        index=True, help='Physician\'s Name', tracking=1, default=_get_default_physician)
    department_id = fields.Many2one('hr.department', ondelete='restrict', 
        domain=[('patient_department', '=', True)], string='Department', tracking=1)

    #ACS: Added department field again here to avoid portal error. Instead of reading department_id used acs_department_id field so error can be avoided.
    acs_department_id = fields.Many2one('hr.department', compute="acs_get_department")
    invoice_exempt = fields.Boolean(string='Invoice Exempt')
    follow_date = fields.Datetime(string="Follow Up Date", copy=False)
    
    reminder_date = fields.Datetime(string="Reminder Date", copy=False)
    acs_reminder_sent = fields.Boolean("Reminder Sent", default=False)

    evaluation_ids = fields.One2many('acs.patient.evaluation', 'appointment_id', 'Evaluations')
    evaluation_id = fields.Many2one('acs.patient.evaluation', ondelete='restrict', compute=_get_evaluation,
        string='Evaluation', store=True)

    weight = fields.Float(related="evaluation_id.weight", string='Weight', help="Weight in KG")
    height = fields.Float(related="evaluation_id.height", string='Height', help="Height in cm")
    temp = fields.Float(related="evaluation_id.temp", string='Temp')
    hr = fields.Integer(related="evaluation_id.hr", string='HR', help="Heart Rate")
    rr = fields.Integer(related="evaluation_id.rr", string='RR', help='Respiratory Rate')
    systolic_bp = fields.Integer(related="evaluation_id.systolic_bp", string="Systolic BP")
    diastolic_bp = fields.Integer(related="evaluation_id.diastolic_bp", string="Diastolic BP")
    spo2 = fields.Integer(related="evaluation_id.spo2", string='SpO2', 
        help='Oxygen Saturation, percentage of oxygen bound to hemoglobin')
    rbs = fields.Integer(related="evaluation_id.rbs", string='RBS', 
        help="Random blood sugar measures blood glucose regardless of when you last ate.")
    bmi = fields.Float(related="evaluation_id.bmi", string='Body Mass Index', readonly=True)
    bmi_state = fields.Selection(related="evaluation_id.bmi_state", string='BMI State', readonly=True)
    acs_weight_name = fields.Char(related="evaluation_id.acs_weight_name", string='Patient Weight unit of measure label')
    acs_height_name = fields.Char(related="evaluation_id.acs_height_name", string='Patient Height unit of measure label')
    acs_temp_name = fields.Char(related="evaluation_id.acs_temp_name", string='Patient Temp unit of measure label')
    acs_spo2_name = fields.Char(related="evaluation_id.acs_spo2_name", string='Patient SpO2 unit of measure label')
    acs_rbs_name = fields.Char(related="evaluation_id.acs_rbs_name", string='Patient RBS unit of measure label')
    
    pain_level = fields.Selection(related="evaluation_id.pain_level", string="Pain Level")
    pain = fields.Selection(related="evaluation_id.pain", string="Pain")

    differential_diagnosis = fields.Text(string='Differential Diagnosis', help="The process of weighing the probability of one disease versus that of other diseases possibly accounting for a patient's illness.")
    medical_advice = fields.Text(string='Medical Advice', help="The provision of a formal professional opinion regarding what a specific individual should or should not do to restore or preserve health.")
    chief_complain = fields.Text(string='Chief Complaints', help="The concise statement describing the symptom, problem, condition, diagnosis, physician-recommended return, or other reason for a medical encounter.")
    present_illness = fields.Text(string='History of Present Illness')
    lab_report = fields.Text(string='Lab Report', help="Details of the lab report.")
    radiological_report = fields.Text(string='Radiological Report', help="Details of the Radiological Report")
    notes = fields.Text(string='Notes')
    past_history = fields.Text(string='Past History', help="Past history of any diseases.")
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False)
    payment_state = fields.Selection(related="invoice_id.payment_state", store=True, string="Payment Status")
    urgency = fields.Selection([
            ('normal', 'Normal'),
            ('urgent', 'Urgent'),
            ('medical_emergency', 'Medical Emergency'),
        ], string='Urgency Level', default='normal')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('waiting', 'Waiting'),
            ('in_consultation', 'In consultation'),
            ('pause', 'Pause'),
            ('to_invoice', 'To Invoice'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ], string='Status',default='draft', required=True, copy=False, tracking=1)
    product_id = fields.Many2one('product.product', ondelete='restrict', 
        string='Consultation Service', help="Consultation Services", 
        domain=[('hospital_product_type', '=', "consultation")], required=True, 
        default=_get_service_id)
    age = fields.Char(compute="get_patient_age", string='Age', store=True,
        help="Computed patient age at the moment of the evaluation")
    company_id = fields.Many2one('res.company', ondelete='restrict',
        string='Hospital', default=lambda self: self.env.company)
    appointment_invoice_policy = fields.Selection([('at_end','Invoice in the End'),
        ('anytime','Invoice Anytime'),
        ('advance','Invoice in Advance'),
        ('foc','No Invoice')],compute=_acs_invoice_policy, string="Appointment Invoicing Policy")
    invoice_exempt = fields.Boolean('Invoice Exempt')
    consultation_type = fields.Selection([
        ('consultation','Consultation'),
        ('followup','Follow Up')],'Consultation Type', copy=False)

    diseases_ids = fields.Many2many('hms.diseases', 'diseases_appointment_rel', 'diseas_id', 'appointment_id', 'Diseases')
    medical_history = fields.Text(related='patient_id.medical_history', 
        string="Past Medical History", readonly=True)
    patient_diseases_ids = fields.One2many('hms.patient.disease', readonly=True, 
        related='patient_id.patient_diseases_ids', string='Disease History')
    
    date = fields.Datetime(string='Date', default=fields.Datetime.now, tracking=1, copy=False)
    date_to = fields.Datetime(string='Date To', default=get_default_end_date, copy=False, tracking=1)
    appointment_date = fields.Date(string='Appointment Date', compute="get_appointment_date", copy=False, store=True)

    planned_duration = fields.Float('Duration', compute="_get_planned_duration", inverse='_inverse_planned_duration')
    manual_planned_duration = fields.Float('Manual Duration')

    waiting_date_start = fields.Datetime('Waiting Start Date', copy=False)
    waiting_date_end = fields.Datetime('Waiting end Date', copy=False)
    waiting_duration = fields.Float('Wait Time', readonly=True, copy=False)
    waiting_duration_timer = fields.Float(string='Wait Timer', compute="_compute_waiting_running_duration", readonly=True, default="0.1", copy=False)

    date_start = fields.Datetime(string='Start Date', copy=False)
    date_end = fields.Datetime(string='End Date', copy=False)
    appointment_duration = fields.Float('Consultation Time', readonly=True, copy=False)
    appointment_duration_timer = fields.Float(string='Consultation Timer', compute="_compute_consultation_running_duration", readonly=True, default="0.1", copy=False)

    purpose_id = fields.Many2one('appointment.purpose', ondelete='cascade', 
        string='Purpose', help="Appointment Purpose")
    cabin_id = fields.Many2one('appointment.cabin', ondelete='cascade', 
        string='Consultation Room (Cabin)', help="Appointment Cabin", copy=False)
    treatment_id = fields.Many2one('hms.treatment', ondelete='cascade', 
        string='Treatment', help="Treatment Id", tracking=1)

    ref_physician_id = fields.Many2one('res.partner', ondelete='restrict', string='Referring Physician', 
        index=True, help='Referring Physician', domain=[('is_referring_doctor','=',True)])
    responsible_id = fields.Many2one('hms.physician', "Responsible Jr. Doctor")
    medical_alert_ids = fields.Many2many('acs.medical.alert', 'appointment_medical_alert_rel','appointment_id', 'alert_id',
        string='Medical Alerts', related='patient_id.medical_alert_ids')
    alert_count = fields.Integer(compute='acs_get_medical_data_count', default=0)
    allergy_ids = fields.Many2many('acs.medical.allergy', 'appointment_allergies_rel','appointment_id', 'allergies_id',
        string='Allergies', related='patient_id.allergy_ids')
    allergy_count = fields.Integer(compute='acs_get_medical_data_count', default=0)
    consumable_line_ids = fields.One2many('hms.consumable.line', 'appointment_id',
        string='Consumable Line', copy=False)
    consumable_line_count = fields.Integer(compute="_get_consumable_line_count", store=True)
    #Only used in case of advance invoice
    consumable_invoice_id = fields.Many2one('account.move', string="Consumables Invoice", copy=False)

    pause_date_start = fields.Datetime('Pause Start Date', copy=False)
    pause_date_end = fields.Datetime('Pause end Date', copy=False)
    pause_duration = fields.Float('Paused Time', readonly=True, copy=False)
    prescription_ids = fields.One2many('prescription.order', 'appointment_id', 'Prescriptions', copy=False)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', check_company=True, 
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, related invoice will be affected.")
    location = fields.Char(string="Appointment Location")
    outside_appointment = fields.Boolean(string="Outside Appointment")
    is_video_call = fields.Boolean("Is Video Call")
    cancel_reason = fields.Text(string="Cancel Reason", copy=False)
    cancel_reason_id = fields.Many2one('acs.cancel.reason', string='Cancellation Reason')
    user_id = fields.Many2one('res.users',string='Responsible',
        ondelete='cascade', help='Responsible User for appointment validation And further Followup.')
    acs_kit_id = fields.Many2one('acs.product.kit', string='Kit')
    acs_kit_qty = fields.Integer("Kit Qty", default=1)
    invoice_ids = fields.One2many("account.move", "appointment_id", string="Invoices", groups="account.group_account_invoice")
    invoice_count = fields.Integer(compute="_acs_get_invoice_count", string="#Invoices", groups="account.group_account_invoice")
    procedure_to_invoice_ids = fields.Many2many('acs.patient.procedure', 'acs_appointment_procedure_rel', 'appointment_id', 'procedure_id', compute="get_procedures_to_invoice", string="Procedures to Invoice")
    refer_reason = fields.Text(string='Refer Reason')

    referred_from_appointment_id = fields.Many2one("hms.appointment", string="Referred From Appointment")
    referred_from_physician_id = fields.Many2one('hms.physician', related='referred_from_appointment_id.physician_id', string='Referred from Physician', tracking=1, store=True)
    referred_from_reason = fields.Text(related='referred_from_appointment_id.refer_reason', string='Referred From Reason', tracking=1, store=True)

    referred_to_appointment_id = fields.Many2one("hms.appointment", string="Referred Appointment")
    referred_to_physician_id = fields.Many2one('hms.physician', related='referred_to_appointment_id.physician_id', ondelete='restrict', string='Referred to Physician', tracking=1, store=True)
    
    #ACS NOTE: Because of error for portal appointment creation added _compute_field_value method.
    department_type = fields.Selection(related='department_id.department_type', string="Appointment Department", store=True)

    #Just to make object selectable in selection field this is required: Waiting Screen
    acs_show_in_wc = fields.Boolean(default=True)
    nurse_id = fields.Many2one('res.users','Assigned Nurse')
    acs_show_create_invoice = fields.Boolean(compute="get_acs_show_create_invoice", string="Show Create Invoice Button")
    acs_show_consumable_create_invoice = fields.Boolean(compute="get_acs_show_create_invoice", string="Show Consumable Create Invoice Button")

    #Links get added from portal module
    acs_access_url = fields.Char(compute="get_acs_access_url", string='Portal Access Link')

    procedure_group_id = fields.Many2one('procedure.group', ondelete="set null", string='Procedure Group')
    patient_procedure_ids = fields.One2many('acs.patient.procedure', 'appointment_id', 'Patient Procedures')
    patient_procedure_count = fields.Integer(compute='acs_patient_procedure_count', string='# Patient Procedures')

    acs_invoice_exempt_approval = fields.Boolean(string="Invoice Exempt Approval Requested", default=False)
    acs_show_invoice_exempt_request_button = fields.Boolean(compute="_compute_acs_show_invoice_exempt_request_button")

    def action_request_invoice_exempt(self):
        for rec in self:
            rec.acs_invoice_exempt_approval = True
            rec.message_post(body=_("Invoice Exempt request has been raised."))

    def _compute_acs_show_invoice_exempt_request_button(self):
        for rec in self:
            rec.acs_show_invoice_exempt_request_button = not self.env.user.has_group('acs_hms_base.group_acs_invoice_exemption')

    def action_approve_invoice_exempt(self):
        for rec in self:
            rec.acs_invoice_exempt_approval = False
            rec.invoice_exempt = True
            rec.message_post(body=_("Invoice Exempt request approved."))
    
    def action_reject_invoice_exempt(self):
        for rec in self:
            rec.acs_invoice_exempt_approval = False
            rec.message_post(body=_("Invoice Exempt request rejected."))

    def get_procedure_group_data(self):
        Consumable = self.env['hms.consumable.line']
        base_date = fields.datetime.now()
        for line in self.procedure_group_id.line_ids:
            procedure = self.patient_procedure_ids.create({
                'appointment_id': self.id,
                'product_id': line.product_id.id,
                'patient_id': self.patient_id.id,
                'date': base_date + timedelta(days=line.days_to_add),
                'date_stop': base_date + timedelta(days=line.days_to_add) + timedelta(hours=line.product_id.procedure_time),
                'price_unit': line.product_id.list_price,
            })
            for consumable_line in line.consumable_line_ids:
                Consumable.create({
                    'product_id': consumable_line.product_id.id,
                    'product_uom_id': consumable_line.product_uom_id.id,
                    'qty': consumable_line.qty,
                    'procedure_id': procedure.id,
                    'display_type': consumable_line.display_type
                })

    def get_acs_access_url(self):
        for rec in self:
            rec.acs_access_url = ''

    #ACS: Compute visibility of create invoice button.
    def get_acs_show_create_invoice(self):
        for rec in self:
            acs_show_create_invoice = False
            if not rec.invoice_id :
                if rec.state=='to_invoice':
                    acs_show_create_invoice = True
                elif rec.appointment_invoice_policy=='anytime' and not rec.invoice_exempt:
                    acs_show_create_invoice = True
                elif rec.appointment_invoice_policy=='advance' and not rec.invoice_exempt:
                    acs_show_create_invoice = True

            rec.acs_show_consumable_create_invoice = True if ((rec.invoice_id) and 
                                                   rec.state!='done' and 
                                                   (not rec.invoice_exempt) and
                                                   (rec.consumable_line_count) and
                                                   (not rec.consumable_invoice_id) and
                                                   rec.appointment_invoice_policy!='at_end'
                                                ) else False
            rec.acs_show_create_invoice = acs_show_create_invoice

    @api.depends('date', 'date_to')
    def _get_planned_duration(self):
        for rec in self:
            if rec.date and rec.date_to:
                diff = rec.date_to - rec.date
                planned_duration = (diff.days * 24) + (diff.seconds/3600)
                if rec.planned_duration != planned_duration:
                    rec.planned_duration = planned_duration
                else:
                    rec.planned_duration = rec.manual_planned_duration

    @api.onchange('planned_duration')
    def _inverse_planned_duration(self):
        for rec in self:
            rec.manual_planned_duration = rec.planned_duration
            if rec.date:
                rec.date_to = rec.date + timedelta(hours=rec.planned_duration)

    @api.depends('waiting_date_start', 'waiting_date_end') 
    def _compute_waiting_running_duration(self):
        for rec in self:
            if rec.waiting_date_start and rec.waiting_date_end:
                rec.waiting_duration_timer = round((rec.waiting_date_end - rec.waiting_date_start).total_seconds() / 60.0, 2)
            elif rec.waiting_date_start:
                rec.waiting_duration_timer = round((fields.Datetime.now() - rec.waiting_date_start).total_seconds() / 60.0, 2)
            else:
                rec.waiting_duration_timer = 0

    @api.depends('date_end', 'date_start') 
    def _compute_consultation_running_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                rec.appointment_duration_timer = round((rec.date_end - rec.date_start).total_seconds() / 60.0, 2)
            elif rec.date_start:
                rec.appointment_duration_timer = round((fields.Datetime.now() - rec.date_start).total_seconds() / 60.0, 2)
            else:
                rec.appointment_duration_timer = 0

    @api.model
    def default_get(self, fields):
        res = super(Appointment, self).default_get(fields)
        if (not res.get('date')) and (not res.get('date_to')):
            res['manual_planned_duration'] = self.env.company.acs_appointment_planned_duration
        if self._context.get('acs_department_type'):
            department = self.env['hr.department'].search([('department_type','=',self._context.get('acs_department_type'))], limit=1)
            if department:
                res['department_id'] = department.id
        return res

    def _compute_field_value(self, field):
        if field.name == 'department_type':
            for rec in self:
                if rec.department_id and rec.department_id.id:
                    department = self.env['hr.department'].sudo().search([('id','=',rec.department_id.id)])
                    rec.write({
                        'department_type': department.department_type
                    })
        else:
            super()._compute_field_value(field)

    def action_create_dental_invoice(self):
        pass

    def update_reminder_dates(self):
        for rec in self:
            if fields.Datetime.now() < rec.date:
                reminder_date = rec.date - timedelta(days=int(rec.company_id.acs_reminder_day)) - timedelta(hours=int(rec.company_id.acs_reminder_hours))
                if reminder_date >= fields.Datetime.now():
                    rec.reminder_date = reminder_date

    def update_appointment_referring(self):
        for rec in self:
            if rec.referred_from_appointment_id and rec.referred_from_appointment_id.referred_to_appointment_id!=rec:
                rec.referred_from_appointment_id.referred_to_appointment_id = rec.id

    @api.model
    def send_appointment_reminder(self):
        date_time_now = fields.Datetime.now()
        reminder_appointments = self.sudo().search([('acs_reminder_sent', '=', False),('state', 'in', ['draft','confirm']),('date','>',fields.Datetime.now()),('reminder_date','<=', date_time_now)])
        if reminder_appointments:
            for reminder_appointment in reminder_appointments:
                reminder_appointment.acs_reminder_sent = True
        return reminder_appointments

    @api.onchange('department_id')
    def onchange_department(self):
        res = {}
        if self.department_id:
            physicians = self.env['hms.physician'].search([('department_ids', 'in', self.department_id.id)])
            res['domain'] = {'physician_id':[('id','in',physicians.ids)]}
            self.department_type = self.department_id.department_type
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                seq_date = None
                if vals.get('date'):
                    seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date']))
                vals['name'] = self.env['ir.sequence'].with_company(vals.get('company_id')).next_by_code('hms.appointment', sequence_date=seq_date) or _("New")
        res = super().create(vals_list)
        for record in res:
            record.update_reminder_dates()
            record.update_appointment_referring()
        return res

    def write(self, values):
        res = super(Appointment, self).write(values)
        if 'follow_date' in values:
            self.sudo()._create_edit_followup_reminder()
        if 'date' in values:
            self.sudo().update_reminder_dates()
        if 'referred_from_appointment_id' in values:
            self.sudo().update_appointment_referring()
        fields_to_check = ['date','date_to','physician_id','state']
        if any(f in values for f in fields_to_check):
            self.acs_calendar_event('physician_id')
        return res
    
    def acs_prepare_calendar_data(self):
        data = super().acs_prepare_calendar_data()
        user_id = self.physician_id.user_id
        data.update({
            'user_id': user_id.id,
            'start': self.date,
            'stop': self.date_to,
            'partner_ids': [(6, 0, [user_id.partner_id.id])],
        })
        return data

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft_or_cancel(self):
        for record in self:
            if record.state not in ('draft', 'cancel'):
                raise UserError(_("You can delete a record in draft or cancelled state only."))

    def print_report(self):
        return self.env.ref('acs_hms.action_appointment_report').report_action(self)

    def action_appointment_send(self):
        '''
        This function opens a window to compose an email, with the template message loaded by default
        '''
        self.ensure_one()
        template_id = self.env['ir.model.data']._xmlid_to_res_id('acs_hms.acs_appointment_email', raise_if_not_found=False)

        ctx = {
            'default_model': 'hms.appointment',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def acs_appointment_inv_product_data(self, with_product=True):
        product_data = []
        if with_product:
            product_id = self.product_id
            if not product_id:
                raise UserError(_("Please Set Consultation Service first."))

            product_data = [{'product_id': product_id, 'line_type': 'appointment'}]

        if self.consumable_line_ids:
            product_data.append({
                'name': _("Consumed Product/services"),
            })
            for consumable in self.consumable_line_ids:
                product_data.append({
                    'product_id': consumable.product_id,
                    'quantity': consumable.qty,
                    'name': consumable.name,
                    'lot_id': consumable.lot_id and consumable.lot_id.id or False,
                    'product_uom_id': consumable.product_uom_id.id,
                    'line_type': 'appointment',
                    'display_type': consumable.display_type
                })

        #ACS: Check if we need it or not as it is getting created in combined 
        #invoice call by default. related method is also commented.
        if self._context.get('with_procedure'):
            if self.procedure_to_invoice_ids:
                product_data += self.procedure_to_invoice_ids.get_procedure_invoice_data()

        return product_data

    def acs_appointment_inv_data(self):
        return {
            'ref_physician_id': self.ref_physician_id and self.ref_physician_id.id or False,
            'physician_id': self.physician_id and self.physician_id.id or False,
            'appointment_id': self.id,
            'hospital_invoice_type': 'appointment',
        }

    #Method to collect other related records data
    def acs_appointment_common_data(self, invoice_id):
        """
            Currently we are managing  following related records invoicing:
            1> Procedures: that are already covered in acs_appointment_inv_product_data and dene here also
            2> Pharmacy: done in pharmacy module
            3> Surgery: done in surgery module
            4> Laboratory: done in hms Laboratory module
            5> Radiology: done in hms Radiology module
        """
        #Procedure Invoicing
        data = self.procedure_to_invoice_ids.acs_common_invoice_procedure_data(invoice_id)
        return data

    #method to create invoice on related records like done in hospitalization
    def acs_appointment_common_invoicing(self, invoice_id):
        data = self.acs_appointment_common_data(invoice_id)
        #create Invoice lines only if invoice is passed
        if invoice_id:
            for line in data:
                inv_line = self.with_context(acs_pricelist_id=self.pricelist_id.id).acs_create_invoice_line(line, invoice_id)
        return data

    def create_invoice(self):
        inv_data = self.acs_appointment_inv_data()
        product_data = self.acs_appointment_inv_product_data()
        acs_context = {'commission_partner_id':self.physician_id.partner_id.id}
        if self.pricelist_id:
            acs_context.update({'acs_pricelist_id': self.pricelist_id.id})
        invoice = self.with_context(acs_context).acs_create_invoice(partner=self.patient_id.partner_id, patient=self.patient_id, product_data=product_data, inv_data=inv_data)
        self.invoice_id = invoice.id
        self.acs_appointment_common_invoicing(invoice)
        if self.state == 'to_invoice':
            self.appointment_done()

        if self.state == 'draft' and not self._context.get('avoid_confirmation'):
            if self.invoice_id and not self.company_id.acs_check_appo_payment:
                self.appointment_confirm()

    def create_consumed_prod_invoice(self):
        if not self.consumable_line_ids.filtered(lambda l: l.display_type=='product'):
            raise UserError(_("There is no consumed product to invoice."))

        inv_data = self.acs_appointment_inv_data()
        product_data = self.acs_appointment_inv_product_data(with_product=False)

        pricelist_context = {}
        if self.pricelist_id:
            pricelist_context = {'acs_pricelist_id': self.pricelist_id.id}
        invoice = self.with_context(pricelist_context).acs_create_invoice(partner=self.patient_id.partner_id, patient=self.patient_id, product_data=product_data, inv_data=inv_data)
        self.consumable_invoice_id = invoice.id
        self.acs_appointment_common_invoicing(invoice)
        if self.state == 'to_invoice':
            self.appointment_done()

    def action_create_invoice_with_procedure(self):
        return self.with_context(with_procedure=True).create_invoice()

    def view_invoice(self):
        appointment_invoices = self.invoice_ids
        action = self.acs_action_view_invoice(appointment_invoices)
        action['context'].update({
            'default_partner_id': self.patient_id.partner_id.id,
            'default_patient_id': self.patient_id.id,
            'default_appointment_id': self.id,
            'default_ref_physician_id': self.ref_physician_id and self.ref_physician_id.id or False,
            'default_physician_id': self.physician_id and self.physician_id.id or False,
            'default_hospital_invoice_type': 'appointment',
            'default_ref': self.name,
        })
        return action

    def action_refer_doctor(self):
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.action_appointment")
        action['domain'] = [('patient_id','=',self.id)]
        action['context'] = {
            'default_patient_id': self.patient_id.id, 
            'default_physician_id': self.physician_id.id,
            'default_referred_from_appointment_id': self.id
        }
        action['views'] = [(self.env.ref('acs_hms.view_hms_appointment_form').id, 'form')]
        return action

    def action_create_evaluation(self):
        if not self.nurse_id:
            self.nurse_id = self.env.user.id
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.action_acs_patient_evaluation_popup")
        action['domain'] = [('patient_id','=',self.id)]
        action['context'] = {'default_patient_id': self.patient_id.id, 'default_physician_id': self.physician_id.id, 'default_appointment_id': self.id}
        return action

    @api.onchange('patient_id', 'date')
    def onchange_patient_id(self):
        if self.patient_id:
            self.age = self.patient_id.age
            followup_days = self.env.company.followup_days
            followup_day_limit = (datetime.now() - timedelta(days=followup_days)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            appointment_id = self.search([('patient_id', '=', self.patient_id.id),('date','>=',followup_day_limit), ('state','not in',['cancel','draft']), ('invoice_exempt','=',False)])
            
            #Avoid setting physician if already there from treatment or manually selected.
            if not self.physician_id:
                self.physician_id = self.patient_id.primary_physician_id and self.patient_id.primary_physician_id.id
            if appointment_id and followup_days:
                self.consultation_type = 'followup'
                if self.env.company.followup_product_id:
                    self.product_id = self.env.company.followup_product_id.id
            else:
                self.consultation_type = 'consultation'

    @api.onchange('date', 'planned_duration')
    def onchange_date_duration(self):
        if self.date:
            if self.manual_planned_duration:
                self.date_to = self.date + timedelta(hours=self.manual_planned_duration)
            if not self.date_to:
                self.date_to = self.date

    @api.onchange('physician_id', 'department_id', 'consultation_type')
    def onchange_physician(self):
        product_id = False
        #ACS: First check configuration on department.
        if self.acs_department_id:
            #ACS: To avoid portal access error research department here.
            if self.consultation_type=='followup':
                if self.acs_department_id.followup_service_id:
                    product_id = self.acs_department_id.followup_service_id.id

            elif self.acs_department_id.consultation_service_id:
                product_id = self.acs_department_id.consultation_service_id.id

        if self.physician_id:
            if self.consultation_type=='followup':
                if self.physician_id.followup_service_id:
                    product_id = self.physician_id.followup_service_id.id

            elif self.physician_id.consultation_service_id:
                product_id = self.physician_id.consultation_service_id.id

            if self.physician_id.appointment_duration and not self._context.get('acs_online_transaction'):
                self.planned_duration = self.physician_id.appointment_duration
            
        if product_id:
            self.product_id = product_id

    def appointment_confirm(self):
        if (not self._context.get('acs_online_transaction')) and (not self.invoice_exempt):
            if self.appointment_invoice_policy=='advance' and not self.invoice_id:
                raise UserError(_('Invoice is not created yet'))

            elif self.invoice_id and self.company_id.acs_check_appo_payment and self.payment_state not in ['in_payment','paid']:
                raise UserError(_('Invoice is not Paid yet.')) 

        if not self.user_id:
            self.user_id = self.env.user.id

        if self.patient_id.email and (self.company_id.acs_auto_appo_confirmation_mail or self._context.get('acs_online_transaction')):
            template = self.env.ref('acs_hms.acs_appointment_email')
            template.sudo().send_mail(self.id, raise_exception=False)
        self.state = 'confirm'

    def appointment_waiting(self):
        self.state = 'waiting'
        self.waiting_date_start = datetime.now()
        self.waiting_duration = 0.1

    def appointment_consultation(self):
        if not self.waiting_date_start:
            raise UserError(('No waiting start time defined.'))
        datetime_diff = datetime.now() - self.waiting_date_start
        m, s = divmod(datetime_diff.total_seconds(), 60)
        h, m = divmod(m, 60)
        self.waiting_duration = float(('%0*d')%(2,h) + '.' + ('%0*d')%(2,m*1.677966102))
        self.state = 'in_consultation'
        self.waiting_date_end = datetime.now()
        self.date_start = datetime.now()

    def action_pause(self):
        self.state = 'pause'
        self.pause_date_start = datetime.now()

        if self.date_start:
            datetime_diff = datetime.now() - self.date_start
            m, s = divmod(datetime_diff.total_seconds(), 60)
            h, m = divmod(m, 60)
            self.appointment_duration = float(('%0*d')%(2,h) + '.' + ('%0*d')%(2,m*1.677966102)) - self.pause_duration
        self.date_end = datetime.now()

    def action_start_paused(self):
        self.state = 'in_consultation'
        self.pause_date_end = datetime.now()
        self.date_end = False
        datetime_diff = datetime.now() - self.pause_date_start
        m, s = divmod(datetime_diff.total_seconds(), 60)
        h, m = divmod(m, 60)
        self.pause_duration += float(('%0*d')%(2,h) + '.' + ('%0*d')%(2,m*1.677966102))

    def consultation_done(self):
        if not self.date_end:
            if self.date_start:
                datetime_diff = datetime.now() - self.date_start
                m, s = divmod(datetime_diff.total_seconds(), 60)
                h, m = divmod(m, 60)
                self.appointment_duration = float(('%0*d')%(2,h) + '.' + ('%0*d')%(2,m*1.677966102)) - self.pause_duration
        self.date_end = datetime.now()
        if (self.invoice_exempt or self.invoice_id) and not (self.consumable_line_ids.filtered(lambda l: l.display_type=='product') and self.appointment_invoice_policy=='advance' and not self.invoice_exempt and not self.consumable_invoice_id):
            self.appointment_done()
        else:
            self.state = 'to_invoice'
        if self.consumable_line_ids.filtered(lambda l: l.display_type=='product'):
            self.acs_consume_material('appointment_id')
        
        #Only create disease history if treatment is not linked.
        if not self.treatment_id:
            for disease in self.diseases_ids:
                self.env['hms.patient.disease'].create({
                    'patient_id': self.patient_id.id,
                    'physician_id': self.physician_id.id,
                    'disease_id': disease.id,
                    'age': self.age,
                    'diagnosed_date': self.date,
                })

    def appointment_done(self):
        self.state = 'done'
        if self.company_id.sudo().auto_followup_days:
            self.follow_date = self.date + timedelta(days=self.company_id.sudo().auto_followup_days)

    def appointment_cancel(self):
        self.state = 'cancel'
        self.waiting_date_start = False
        self.waiting_date_end = False

        if self.sudo().invoice_id and self.sudo().invoice_id.state=='draft':
            self.sudo().invoice_id.unlink()

    def appointment_draft(self):
        self.state = 'draft'
    
    def action_reopen(self):
        self.state = 'in_consultation'

    def action_prescription(self):
        action = self.env["ir.actions.actions"].sudo()._for_xml_id("acs_hms.act_open_hms_prescription_order_view")
        action['domain'] = [('appointment_id', '=', self.id)]
        action['context'] = {
                'default_patient_id': self.patient_id.id,
                'default_physician_id': self.physician_id.id,
                'default_diseases_ids': [(6,0,self.diseases_ids.ids)],
                'default_treatment_id': self.treatment_id and self.treatment_id.id or False,
                'default_appointment_id': self.id}
        return action

    def button_pres_req(self):
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.act_open_hms_prescription_order_view")        
        action['domain'] = [('appointment_id', '=', self.id)]
        action['views'] = [(self.env.ref('acs_hms.view_hms_prescription_order_form').id, 'form')]
        action['context'] = {
                'default_patient_id': self.patient_id.id,
                'default_physician_id':self.physician_id.id,
                'default_diseases_ids': [(6,0,self.diseases_ids.ids)],
                'default_treatment_id': self.treatment_id and self.treatment_id.id or False,
                'default_appointment_id': self.id}
        return action
    
    def action_view_treatment(self):
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.acs_action_form_hospital_treatment")
        action['context'] = {
            'default_appointment_ids': [(6,0,self.ids)],
            'default_patient_id': self.patient_id.id,
            'default_physician_id': self.physician_id.id,
            'default_diseases_ids': self.diseases_ids and self.diseases_ids[0].id or False,
            'acs_current_appointment': self.id,
        }
        action['views'] = [(self.env.ref('acs_hms.view_hospital_hms_treatment_form').id, 'form')]
        if self.treatment_id:
            action['domain'] = [('id','=',self.treatment_id.id)]
            action['res_id'] = self.treatment_id.id
        elif self.patient_id.treatment_ids.filtered(lambda trt: trt.state in ['draft','running']):
            running_treatment_ids = self.patient_id.treatment_ids.filtered(lambda trt: trt.state in ['draft','runnig'])
            action['domain'] = [('id','in',running_treatment_ids.ids)]            
            action['views'] = [(self.env.ref('acs_hms.view_acs_hms_treatment_appointment_list').id, 'list')]
        return action

    def acs_get_consume_locations(self):
        if not self.company_id.appointment_usage_location_id:
            raise UserError(_('Please define a appointment location where the consumables will be used.'))
        if not self.company_id.appointment_stock_location_id:
            raise UserError(_('Please define a appointment location from where the consumables will be taken.'))

        dest_location_id  = self.company_id.appointment_usage_location_id.id
        source_location_id  = self.company_id.appointment_stock_location_id.id
        return source_location_id, dest_location_id

    def action_view_patient_procedures(self):
        action = self.env["ir.actions.actions"]._for_xml_id("acs_hms.action_acs_patient_procedure")
        domain = ['|',('appointment_ids', 'in', self.id),('appointment_id', '=', self.id)]
        if self.treatment_id:
            domain = ['|',('treatment_id', '=', self.treatment_id.id)] + domain
        action['domain'] = domain
        action['context'] = {
            'default_treatment_id': self.treatment_id and self.treatment_id.id or False,
            'default_appointment_ids': [(6,0,[self.id])],
            'default_patient_id': self.patient_id.id,
            'default_physician_id': self.physician_id.id,
            'default_department_id': self.department_id.id
        }
        return action

    # Create/Edit Followup activity if needed
    def _create_edit_followup_reminder(self):
        Activity = self.env['mail.activity']
        default_activity_type = self.env['mail.activity.type'].search([],limit=1)
        res_model = self.env['ir.model'].sudo().search([('model', '=', self._name)])
        for rec in self:
            if rec.follow_date:
                company = rec.company_id.sudo() or self.env.company.sudo()
                activity_type = company.acs_followup_activity_type_id or default_activity_type
                if not activity_type:
                    raise UserError(_("Please Set Followup activity Type on Configuration."))
                
                followup_date = rec.follow_date - timedelta(days=1)
                if not rec.user_id:
                    rec.user_id = self.env.user.id
                user_id = rec.user_id

                existing_activity = Activity.search([('res_id', '=', rec.id),('res_model_id','=',self._name),
                    ('activity_type_id','=',activity_type.id),('user_id','=',user_id.id)])
                if existing_activity:
                    existing_activity.date_deadline = followup_date
                else:
                    activity_vals = {
                        'res_id': rec.id,
                        'res_model_id': res_model.id,
                        'activity_type_id': activity_type.id,
                        'summary': _('Appointment Follow up'),
                        'date_deadline': followup_date,
                        'automated': True,
                        'user_id': user_id.id
                    }
                    self.env['mail.activity'].with_context(mail_activity_quick_update=True).create(activity_vals)

    def cancel_old_appointments(self):
        yesterday = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        if self.env.user.sudo().company_id.acs_cancel_old_appointment:
            previous_appointments = self.env['hms.appointment'].search([('date','<=',yesterday),('state','in',['draft','confirm'])])
            for appointment in previous_appointments:
                appointment.with_context(cancel_from_cron=True).appointment_cancel()
        return

    def acs_reschedule_appointments(self, reschedule_time):
        for rec in self:
            rec.date =  rec.date + timedelta(hours=reschedule_time)
            rec.date_to =  rec.date_to + timedelta(hours=reschedule_time)


class StockMove(models.Model):
    _inherit = "stock.move"

    appointment_id = fields.Many2one('hms.appointment', string="Appointment", ondelete="restrict")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
