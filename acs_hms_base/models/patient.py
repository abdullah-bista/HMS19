# -*- coding: utf-8 -*-

from odoo import api, fields, models ,_
from odoo.exceptions import UserError,ValidationError
from datetime import datetime

class FormatGOVCodeLabelMixin(models.AbstractModel):
    _name = "format.gov.code.label.mixin"
    _description = "Country Specific Gov Code Label"
    
    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if gov_code_label := self.env.company.country_id.gov_code_label:
            for node in arch.iterfind(".//field[@name='gov_code']"):
                node.set("string", gov_code_label)
            # In some module gov_code field is replaced and so above string change is not working
            for node in arch.iterfind(".//label[@for='gov_code']"):
                node.set("string", gov_code_label)
        return arch, view

class ACSPatient(models.Model):
    _name = 'hms.patient'
    _description = 'Patient'
    _inherit = ['mail.thread', 'format.gov.code.label.mixin', 'mail.activity.mixin', 'acs.hms.mixin', 'acs.document.mixin']
    _inherits = {
        'res.partner': 'partner_id',
    }
    _rec_names_search = ['name', 'code', 'gov_code']

    def _rec_count(self):
        Invoice = self.env['account.move']
        for rec in self:
            rec.invoice_count = Invoice.sudo().search_count([('partner_id','=',rec.partner_id.id)])
    name = fields.Char("Name")

    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', auto_join=True,
        string='Related Partner', help='Partner-related data of the Patient')
    gov_code = fields.Char(string='Government Identity', copy=False, tracking=True)
    gov_code_label = fields.Char(compute="acs_get_gov_code_label", string="Government Identity Label")
    marital_status = fields.Selection([
        ('single', 'Single'), 
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widow', 'Widow')], string='Marital Status', default="single")
    spouse_name = fields.Char("Spouse's Name")
    spouse_edu = fields.Char("Spouse's Education")
    spouse_business = fields.Char("Spouse's Business")
    education = fields.Char("Patient Education")
    is_corpo_tieup = fields.Boolean(string='Corporate Tie-Up', 
        help="If not checked, these Corporate Tie-Up Group will not be visible at all.")
    corpo_company_id = fields.Many2one('res.partner', string='Corporate Company', 
        domain="[('is_company', '=', True),('customer_rank', '>', 0)]", ondelete='restrict')
    emp_code = fields.Char(string='Employee Code')
    user_id = fields.Many2one('res.users', string='Related User', ondelete='cascade', 
        help='User-related data of the patient')
    primary_physician_id = fields.Many2one('hms.physician', 'Primary Care Doctor')
    acs_tag_ids = fields.Many2many('hms.patient.tag', 'patient_tag_hms_rel', 'tag_id', 'patient_tag_id', string="HMS Tags")

    invoice_count = fields.Integer(compute='_rec_count', string='# Invoices')
    occupation = fields.Char("Occupation")
    acs_religion_id = fields.Many2one('acs.religion', string="Religion")
    caste = fields.Char("Tribe")
    nationality_id = fields.Many2one("res.country", string="Nationality")
    passport = fields.Char("Passport Number")
    active = fields.Boolean(string="Active", default=True)
    location_url = fields.Text()
    age = fields.Char("Age", store=True)
    mobile=fields.Integer(string="Mobile")
    title = fields.Char("Title")
    email = fields.Char("Email")
    birthday = fields.Date("Date of Birth")
    # state = fields.Selection([('draft', 'Draft'),('confirmed', 'Confirmed'),('dr_receipt', 'Dr Receipt'),
    #                           ('frist_consult', '1st Consult'),('lab_invoice', 'Lab Invoice'),('sample_collect', 'Sample Collect'),
    #                           ('lab_done', 'Lab Done'),('second_consult', '2nd Consult'),('nutritionist', 'Nutritionist'),
    #                           ('fitness', 'Fitness'),('completed', 'Completed')],default='draft',string="Status")
    is_registered = fields.Boolean(string="Is Registered", default=False)


    def acs_get_gov_code_label(self):
        for rec in self:
            rec.gov_code_label = self.env.company.country_id.gov_code_label

    def check_gov_code(self, gov_code):
        patient = self.search([('gov_code','=',gov_code)],limit=1)
        if patient and not self.env.context.get('acs_avoid_gov_code_check',False):
            raise ValidationError(_('Patient already exists with Government Identity: %s.') % (gov_code))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code','/')=='/':
                vals['code'] = self.env['ir.sequence'].next_by_code('hms.patient') or ''
            company_id = vals.get('company_id')
            if company_id:
                company_id = self.env['res.company'].sudo().search([('id','=',company_id)], limit=1)
            else:
                company_id = self.env.company
            if company_id.unique_gov_code and vals.get('gov_code'):
                self.check_gov_code(vals.get('gov_code'))
            if 'display_name' in vals:
                vals['name'] = vals['display_name']
            vals['customer_rank'] = True
            if not vals.get('partner_id'):
                partner = self.env['res.partner'].create({
                    'name': vals.get('name'),
                    'type': 'contact',
                })
                vals['partner_id'] = partner.id
        return super().create(vals_list)

    def write(self, values):
        company_id = self.sudo().company_id or self.env.user.sudo().company_id
        if company_id.unique_gov_code and values.get('gov_code'):
            self.check_gov_code(values.get('gov_code'))
        return super(ACSPatient, self).write(values)

    def view_invoices(self):
        invoices = self.env['account.move'].search([('partner_id','=',self.partner_id.id), ('move_type', 'in', ('out_invoice', 'out_refund'))])
        action = self.with_context(acs_open_blank_list=True).acs_action_view_invoice(invoices)
        action['context'].update({
            'default_partner_id': self.partner_id.id,
            'default_patient_id': self.id,
        })
        return action

    @api.model
    def send_birthday_email(self): 
        wish_template_id = self.env.ref('acs_hms_base.email_template_birthday_wish', raise_if_not_found=False)
        user_cmp_template = self.env.company.birthday_mail_template_id
        today = datetime.now()
        today_month_day = '%-' + today.strftime('%m') + '-' + today.strftime('%d')
        patient_ids = self.search([('birthday', 'like', today_month_day)])
        for patient_id in patient_ids:
            if patient_id.email:
                wish_temp = patient_id.company_id.birthday_mail_template_id or user_cmp_template or wish_template_id
                wish_temp.sudo().send_mail(patient_id.id, force_send=True)

    def _compute_display_name(self):
        for rec in self:
            name = rec.name
            if rec.title and rec.title.shortcut:
                name = (rec.title.shortcut or '') + ' ' + (rec.name or '')
            rec.display_name = name

    @api.onchange('mobile')
    def _onchange_mobile_warning(self):
        if not self.mobile:
            return
        message = ''
        domain = [('mobile','=',self.mobile)]
        if self._origin and self._origin.id:
            domain += [('id','!=',self._origin.id)]
        patients = self.sudo().search(domain)
        # for patient in patients:
        #     message += _('\nThe Mobile number is already registered with another Patient: %s, Government Identity:%s, DOB: %s.') %(patient.name, patient.gov_code, patient.birthday)
        # if message:
        #     message += _('\n\n Are you sure you want to create a new Patient?')
        #     return {
        #         'warning': {
        #             'title': _("Warning for Mobile Duplication"),
        #             'message': message,
        #         }
        #     }
    
    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        company = self.env.company
        if company.country_id.vat_label:
            for node in arch.xpath("//field[@name='gov_code']"):
                node.attrib["string"] = company.country_id.gov_code_label
        return arch, view
    
    # @api.onchange('phone', 'country_id', 'company_id')
    # def _onchange_phone_validation(self):
    #     if self.phone:
    #         self.phone = self._phone_format(fname='phone', force_format='INTERNATIONAL') or self.phone
    #
    # @api.onchange('mobile', 'country_id', 'company_id')
    # def _onchange_mobile_validation(self):
    #     if self.mobile:
    #         self.mobile = self._phone_format(fname='mobile', force_format='INTERNATIONAL') or self.mobile

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: