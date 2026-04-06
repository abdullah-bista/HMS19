# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, timedelta, date


class ACSAppointmentConsumable(models.Model):
    _name = "hms.consumable.line"
    _description = "List of Consumed Product and Services"

    @api.depends('price_unit','qty')
    def acs_get_total_price(self):
        for rec in self:
            rec.subtotal = rec.qty * rec.price_unit

    name = fields.Char(string='Name',default=lambda self: self.product_id.name)
    product_id = fields.Many2one('product.product', ondelete="restrict", string='Products/Services')
    # product_uom_category_id = fields.Many2one('uom.category', related='product_id.uom_id.category_id', depends=['product_id'])
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', help='Amount of medication (eg, 250 mg) per dose',)#  domain="[('category_id', '=', product_uom_category_id)]"
    qty = fields.Float(string='Quantity', default=1.0)
    tracking = fields.Selection(related='product_id.tracking', store=True, depends=['product_id'])
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number', 
        domain="[('product_id', '=', product_id),('product_qty','>',0),'|',('expiration_date','=',False),('expiration_date', '>', context_today().strftime('%Y-%m-%d'))]")
    price_unit = fields.Float(string='Unit Price', readonly=True)
    subtotal = fields.Float(compute=acs_get_total_price, string='Subtotal', readonly=True, store=True)
    move_id = fields.Many2one('stock.move', string='Stock Move')
    physician_id = fields.Many2one('hms.physician', string='Physician')
    department_id = fields.Many2one('hr.department', string='Department',domain=[('patient_department', '=', True)])
    patient_id = fields.Many2one('hms.patient', string='Patient')
    date = fields.Date("Date", default=fields.Date.context_today)
    note = fields.Char("Note")
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    ignore_stock_move = fields.Boolean(string='Ignore Stock Movement')
    acs_date_start = fields.Datetime('Start Time')
    acs_date_end = fields.Datetime('End Time')
    hospital_product_type = fields.Selection(related='product_id.hospital_product_type', store=True)
    display_type = fields.Selection([
        ('product', "Product"),
        ('line_section', "Section"),
        ('line_note', "Note")], help="Technical field for UX purpose.", default='product')

    @api.onchange('product_id', 'qty', 'product_uom_id')
    def onchange_product(self):
        if self.product_id:
            price = self.product_id.list_price
            if not self.product_uom_id:
                self.product_uom_id = self.product_id.uom_id.id
            if self.pricelist_id:
                price = self.pricelist_id._get_product_price(self.product_id, self.qty or 1, uom=self.product_uom_id)
            elif self.patient_id.property_product_pricelist:
                price = self.patient_id.property_product_pricelist._get_product_price(self.product_id, self.qty or 1, uom=self.product_uom_id)
            self.price_unit = price
            self.name = self.product_id.display_name

    def acs_set_unit_price(self):
        for rec in self:
            if rec.product_id.acs_fixed_price > 0.0 and rec.qty <= rec.product_id.acs_min_qty:
                rec.qty = rec.product_id.acs_min_qty
                rec.price_unit = rec.product_id.acs_fixed_price / (rec.product_id.acs_min_qty or 1)

    def action_start(self):
        self.acs_date_start = datetime.now()
        self.acs_date_end = False

    def action_stop(self):
        duration = 0.0
        if self.acs_date_start:
            datetime_diff = datetime.now() - self.acs_date_start
            time_obj= datetime.strptime(str(datetime_diff), "%H:%M:%S.%f") - datetime(1900, 1, 1)
            total_seconds = time_obj.total_seconds()
            total_hour = total_seconds / 60
            total_qty = self.product_id.uom_id._compute_quantity(total_hour, self.product_uom_id)
            duration = round(total_qty)
        self.write({
            'acs_date_end': datetime.now(),
            'qty' : duration
        })
        self.onchange_product()
        self.acs_set_unit_price()
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: