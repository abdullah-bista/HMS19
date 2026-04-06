from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsAdmission(models.Model):
    _name = 'hms.admission'
    _description = 'Patient Admission (IPD)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin']
    _rec_name = 'name'
    _order = 'admission_datetime desc, id desc'

    name = fields.Char(string='Admission Number', readonly=True, copy=False, default='New')

    # Patient
    patient_id = fields.Many2one(
        'hms.patient', string='Patient', required=True,
        ondelete='restrict', tracking=True, index=True
    )
    admission_datetime = fields.Datetime(
        string='Admission Date/Time', required=True,
        default=fields.Datetime.now, tracking=True
    )
    admission_type = fields.Selection([
        ('emergency', 'Emergency'),
        ('elective', 'Elective'),
        ('transfer', 'Transfer'),
        ('maternity', 'Maternity'),
    ], string='Admission Type', required=True, default='elective', tracking=True)
    admission_reason = fields.Text(string='Reason for Admission', required=True)

    # Source
    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case', ondelete='set null', tracking=True
    )

    # Physicians
    referring_physician_id = fields.Many2one(
        'hms.physician', string='Referring Physician', ondelete='restrict'
    )
    attending_physician_id = fields.Many2one(
        'hms.physician', string='Attending Physician',
        required=True, ondelete='restrict', tracking=True
    )
    secondary_physician_ids = fields.Many2many(
        'hms.physician', 'hms_admission_physician_rel', 'admission_id', 'physician_id',
        string='Consulting Physicians'
    )

    # Bed Assignment
    ward_id = fields.Many2one('hms.ward', string='Ward', required=True, ondelete='restrict', tracking=True)
    room_id = fields.Many2one('hms.room', string='Room', ondelete='restrict', tracking=True)
    bed_id = fields.Many2one('hms.bed', string='Bed', required=True, ondelete='restrict', tracking=True)

    # Diagnoses
    diagnosis_ids = fields.Many2many(
        'hms.diseases', 'hms_admission_diagnosis_rel', 'admission_id', 'disease_id',
        string='Diagnoses'
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'Admitted'),
        ('treatment_done', 'Treatment Done'),
        ('discharged', 'Discharged'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)
    treatment_done_datetime = fields.Datetime(string='Treatment Done At', tracking=True)

    # Clinical Records (One2many via extension fields on target models)
    treatment_ids = fields.One2many('hms.treatment', 'admission_id', string='Treatments')
    nursing_sheet_ids = fields.One2many('hms.nursing.sheet', 'admission_id', string='Nursing Sheets')
    lab_request_ids = fields.One2many('acs.laboratory.request', 'admission_id', string='Lab Requests')
    prescription_ids = fields.One2many('prescription.order', 'admission_id', string='Prescriptions')
    procedure_ids = fields.One2many('acs.patient.procedure', 'admission_id', string='Procedures')
    nursing_sheet_count = fields.Integer(compute='_compute_nursing_sheet_count')

    # Discharge Info
    expected_discharge_date = fields.Date(string='Expected Discharge Date', tracking=True)
    actual_discharge_datetime = fields.Datetime(string='Actual Discharge Date/Time', tracking=True)
    length_of_stay = fields.Integer(
        string='Length of Stay (Days)', compute='_compute_length_of_stay', store=True
    )

    # Financial
    invoice_ids = fields.Many2many(
        'account.move', 'hms_admission_invoice_rel', 'admission_id', 'invoice_id',
        string='Invoices', copy=False
    )
    invoice_count = fields.Integer(compute='_compute_financials')
    total_invoiced = fields.Float(
        string='Total Invoiced', compute='_compute_financials', digits='Account'
    )
    total_paid = fields.Float(
        string='Total Paid', compute='_compute_financials', digits='Account'
    )
    balance_due = fields.Float(
        string='Balance Due', compute='_compute_financials', digits='Account'
    )

    # OT Bookings
    ot_booking_ids = fields.One2many('hms.operation.theatre', 'admission_id', string='OT Bookings')
    ot_booking_count = fields.Integer(compute='_compute_ot_count')

    # Discharge link (Phase 5)
    discharge_id = fields.Many2one(
        'hms.discharge', string='Discharge Record', ondelete='set null', tracking=True, copy=False
    )

    company_id = fields.Many2one(
        'res.company', string='Hospital', ondelete='restrict',
        default=lambda self: self.env.company
    )

    # ---------------------------------------------------------------
    # ORM Overrides
    # ---------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hms.admission') or 'New'
        return super().create(vals_list)

    # ---------------------------------------------------------------
    # Onchange — bed cascade
    # ---------------------------------------------------------------

    @api.onchange('ward_id')
    def _onchange_ward_id(self):
        self.room_id = False
        self.bed_id = False

    @api.onchange('room_id')
    def _onchange_room_id(self):
        self.bed_id = False

    # ---------------------------------------------------------------
    # Computed Fields
    # ---------------------------------------------------------------

    @api.depends('admission_datetime', 'actual_discharge_datetime')
    def _compute_length_of_stay(self):
        for rec in self:
            if rec.admission_datetime:
                end = rec.actual_discharge_datetime or fields.Datetime.now()
                delta = end - rec.admission_datetime
                rec.length_of_stay = delta.days
            else:
                rec.length_of_stay = 0

    @api.depends('invoice_ids', 'invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_financials(self):
        for rec in self:
            active_invoices = rec.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
            rec.invoice_count = len(rec.invoice_ids)
            rec.total_invoiced = sum(active_invoices.mapped('amount_total'))
            rec.balance_due = sum(active_invoices.mapped('amount_residual'))
            rec.total_paid = rec.total_invoiced - rec.balance_due

    # ---------------------------------------------------------------
    # State Machine Actions
    # ---------------------------------------------------------------

    def action_confirm(self):
        """Confirm admission and reserve the bed."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft admissions can be confirmed.'))
            if rec.bed_id.state not in ('available', 'reserved'):
                raise UserError(
                    _('Bed "%s" is not available for reservation.') % rec.bed_id.name
                )
            rec.bed_id.write({'state': 'reserved'})
            rec.state = 'confirmed'

    def action_admit(self):
        """Admit patient: occupy bed and update linked records."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_('Admission must be confirmed before admitting the patient.'))
            if rec.bed_id.state not in ('available', 'reserved'):
                raise UserError(
                    _('Bed "%s" is no longer available.') % rec.bed_id.name
                )
            rec.bed_id.write({
                'state': 'occupied',
                'current_admission_id': rec.id,
            })
            rec.state = 'in_progress'
            # If originating from an ER case, update ER case disposition
            if rec.emergency_case_id and rec.emergency_case_id.state not in ('admitted',):
                rec.emergency_case_id.write({
                    'state': 'admitted',
                    'disposition': 'admitted',
                    'disposition_datetime': fields.Datetime.now(),
                    'admission_id': rec.id,
                })

    def action_mark_treatment_done(self):
        """Mark treatment as done: in_progress → treatment_done."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only admitted patients can be marked as treatment done.'))
            rec.write({
                'state': 'treatment_done',
                'treatment_done_datetime': fields.Datetime.now(),
            })

    def action_initiate_discharge(self):
        """Open the Discharge form pre-filled for this admission."""
        self.ensure_one()
        if self.state not in ('in_progress', 'treatment_done'):
            raise UserError(_('Only admitted patients can be discharged.'))
        if self.discharge_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Discharge Record'),
                'res_model': 'hms.discharge',
                'view_mode': 'form',
                'res_id': self.discharge_id.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Discharge'),
            'res_model': 'hms.discharge',
            'view_mode': 'form',
            'context': {
                'default_discharge_type': 'ipd',
                'default_patient_id': self.patient_id.id,
                'default_admission_id': self.id,
                'default_physician_id': self.attending_physician_id.id,
            },
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel admission and release the bed if reserved/occupied."""
        for rec in self:
            if rec.state in ('discharged', 'cancelled'):
                raise UserError(_('Discharged admissions cannot be cancelled.'))
            rec._release_bed()
            rec.state = 'cancelled'

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    @api.depends('nursing_sheet_ids')
    def _compute_nursing_sheet_count(self):
        for rec in self:
            rec.nursing_sheet_count = len(rec.nursing_sheet_ids)

    @api.depends('ot_booking_ids')
    def _compute_ot_count(self):
        for rec in self:
            rec.ot_booking_count = len(rec.ot_booking_ids)

    def action_view_nursing_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nursing Sheets'),
            'res_model': 'hms.nursing.sheet',
            'view_mode': 'list,form',
            'domain': [('admission_id', '=', self.id)],
            'context': {
                'default_admission_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
        }

    def action_view_ot_bookings(self):
        """Open OT bookings for this admission."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OT Bookings'),
            'res_model': 'hms.operation.theatre',
            'view_mode': 'list,form',
            'domain': [('admission_id', '=', self.id)],
            'context': {
                'default_admission_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
        }

    def _release_bed(self):
        """Release the assigned bed back to available."""
        self.ensure_one()
        if self.bed_id and self.bed_id.state in ('reserved', 'occupied') \
                and self.bed_id.current_admission_id == self:
            self.bed_id.write({
                'state': 'available',
                'current_admission_id': False,
            })

    # ---------------------------------------------------------------
    # Smart Button Actions
    # ---------------------------------------------------------------

    def action_view_discharge(self):
        """Open the linked discharge record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discharge Record'),
            'res_model': 'hms.discharge',
            'view_mode': 'form',
            'res_id': self.discharge_id.id,
            'target': 'current',
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }

    def action_create_invoice(self):
        """Create bed charge invoice for this admission."""
        self.ensure_one()
        if not self.bed_id.product_id:
            raise UserError(
                _('Please configure a Billing Product on bed "%s" before creating an invoice.')
                % self.bed_id.name
            )
        days = self.length_of_stay or 1
        product_data = [{
            'product_id': self.bed_id.product_id,
            'quantity': days,
            'price_unit': self.bed_id.daily_rate,
        }]
        invoice = self.acs_create_invoice(
            partner=self.patient_id.partner_id,
            patient=self.patient_id,
            product_data=product_data,
        )
        self.invoice_ids = [(4, invoice.id)]
        return self.action_view_invoices()
