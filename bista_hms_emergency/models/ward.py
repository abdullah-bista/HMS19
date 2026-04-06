from odoo import api, fields, models, _


class HmsWard(models.Model):
    _name = 'hms.ward'
    _description = 'Hospital Ward'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Ward Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    ward_type = fields.Selection([
        ('general', 'General'),
        ('icu', 'ICU'),
        ('emergency', 'Emergency'),
        ('maternity', 'Maternity'),
        ('pediatric', 'Pediatric'),
        ('surgical', 'Surgical'),
        ('psychiatric', 'Psychiatric'),
    ], string='Ward Type', required=True, tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', ondelete='set null')
    room_ids = fields.One2many('hms.room', 'ward_id', string='Rooms')
    bed_count = fields.Integer(string='Total Beds', compute='_compute_bed_counts', store=True)
    available_bed_count = fields.Integer(string='Available Beds', compute='_compute_bed_counts', store=True)
    occupied_bed_count = fields.Integer(string='Occupied Beds', compute='_compute_bed_counts', store=True)
    company_id = fields.Many2one(
        'res.company', string='Hospital', ondelete='restrict',
        default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.depends('room_ids.bed_ids.state')
    def _compute_bed_counts(self):
        for ward in self:
            beds = ward.room_ids.bed_ids
            ward.bed_count = len(beds)
            ward.available_bed_count = len(beds.filtered(lambda b: b.state == 'available'))
            ward.occupied_bed_count = len(beds.filtered(lambda b: b.state == 'occupied'))

    def action_view_beds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Beds'),
            'res_model': 'hms.bed',
            'view_mode': 'kanban,tree,form',
            'domain': [('ward_id', '=', self.id)],
            'context': {'default_ward_id': self.id},
        }


class HmsRoom(models.Model):
    _name = 'hms.room'
    _description = 'Hospital Room'
    _rec_name = 'name'

    name = fields.Char(string='Room Number/Name', required=True)
    ward_id = fields.Many2one('hms.ward', string='Ward', required=True, ondelete='cascade')
    room_type = fields.Selection([
        ('private', 'Private'),
        ('semi_private', 'Semi-Private'),
        ('general', 'General'),
        ('isolation', 'Isolation'),
    ], string='Room Type', required=True)
    bed_ids = fields.One2many('hms.bed', 'room_id', string='Beds')
    bed_count = fields.Integer(string='Bed Count', compute='_compute_bed_count', store=True)
    floor = fields.Char(string='Floor/Level')
    facilities = fields.Text(string='Facilities')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(related='ward_id.company_id', store=True)

    @api.depends('bed_ids')
    def _compute_bed_count(self):
        for room in self:
            room.bed_count = len(room.bed_ids)
