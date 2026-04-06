from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsBed(models.Model):
    _name = 'hms.bed'
    _description = 'Hospital Bed'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Bed Identifier', required=True, tracking=True)
    room_id = fields.Many2one('hms.room', string='Room', required=True, ondelete='restrict', tracking=True)
    ward_id = fields.Many2one('hms.ward', string='Ward', related='room_id.ward_id', store=True)
    bed_type = fields.Selection([
        ('standard', 'Standard'),
        ('electric', 'Electric'),
        ('icu', 'ICU'),
        ('bariatric', 'Bariatric'),
        ('pediatric', 'Pediatric'),
        ('stretcher', 'Stretcher'),
    ], string='Bed Type', required=True, default='standard', tracking=True)
    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
    ], string='Status', default='available', required=True, tracking=True)

    # Current occupancy (populated by hms.admission)
    current_admission_id = fields.Many2one(
        'hms.admission', string='Current Admission', tracking=True
    )
    current_patient_id = fields.Many2one(
        'hms.patient', string='Current Patient',
        related='current_admission_id.patient_id', store=True
    )

    daily_rate = fields.Float(string='Daily Rate', tracking=True)
    product_id = fields.Many2one('product.product', string='Billing Product')
    company_id = fields.Many2one(related='room_id.ward_id.company_id', store=True)
    active = fields.Boolean(default=True)

    def action_mark_available(self):
        """Release bed back to available (from reserved or maintenance)."""
        for bed in self:
            if bed.state in ('reserved', 'maintenance'):
                bed.state = 'available'

    def action_mark_maintenance(self):
        """Set bed to under maintenance."""
        for bed in self:
            if bed.state == 'occupied':
                raise UserError(_('Cannot set occupied bed "%s" to maintenance.') % bed.name)
            bed.state = 'maintenance'

    def action_reserve(self):
        """Reserve an available bed for incoming patient."""
        for bed in self:
            if bed.state != 'available':
                raise UserError(_('Bed "%s" is not available for reservation.') % bed.name)
            bed.state = 'reserved'

    def _check_availability(self):
        """Raise if bed is not available or reserved. Used by admission logic."""
        self.ensure_one()
        if self.state not in ('available', 'reserved'):
            raise UserError(
                _('Bed "%s" is not available. Current status: %s') % (
                    self.name,
                    dict(self._fields['state'].selection).get(self.state, self.state)
                )
            )
