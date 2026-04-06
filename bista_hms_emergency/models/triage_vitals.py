# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HmsTriageVitals(models.Model):
    _name = 'hms.triage.vitals'
    _description = 'Triage Vital Signs'
    _order = 'datetime desc'

    emergency_case_id = fields.Many2one(
        'hms.emergency.case', string='Emergency Case',
        required=True, ondelete='cascade', index=True
    )
    datetime = fields.Datetime(
        string='Recorded At', required=True, default=fields.Datetime.now
    )
    recorded_by = fields.Many2one(
        'res.users', string='Recorded By',
        required=True, default=lambda self: self.env.user
    )

    # ── Blood Pressure ─────────────────────────────────────────────
    systolic_bp = fields.Integer(string='Systolic (mmHg)')
    diastolic_bp = fields.Integer(string='Diastolic (mmHg)')

    # ── Cardiovascular / Respiratory ───────────────────────────────
    pulse = fields.Integer(string='Pulse (bpm)')
    respiratory_rate = fields.Integer(string='RR (/min)')
    spo2 = fields.Integer(string='SpO₂ (%)')

    # ── Temperature ─────────────────────────────────────────────────
    temperature = fields.Float(string='Temp (°C)', digits=(4, 1))

    # ── Metabolic ───────────────────────────────────────────────────
    blood_glucose = fields.Float(string='Blood Glucose (mg/dL)', digits=(6, 1))

    # ── Pain Score ──────────────────────────────────────────────────
    pain_score = fields.Selection(
        [(str(i), str(i)) for i in range(11)],
        string='Pain (0–10)'
    )

    # ── Glasgow Coma Scale ──────────────────────────────────────────
    gcs_eye = fields.Selection([
        ('1', '1 – No Response'),
        ('2', '2 – To Pain'),
        ('3', '3 – To Voice'),
        ('4', '4 – Spontaneous'),
    ], string='GCS Eye (E)')

    gcs_verbal = fields.Selection([
        ('1', '1 – No Response'),
        ('2', '2 – Incomprehensible'),
        ('3', '3 – Inappropriate'),
        ('4', '4 – Confused'),
        ('5', '5 – Oriented'),
    ], string='GCS Verbal (V)')

    gcs_motor = fields.Selection([
        ('1', '1 – No Response'),
        ('2', '2 – Extension'),
        ('3', '3 – Abnormal Flexion'),
        ('4', '4 – Withdrawal'),
        ('5', '5 – Localizes Pain'),
        ('6', '6 – Obeys Commands'),
    ], string='GCS Motor (M)')

    gcs_total = fields.Integer(
        string='GCS Total', compute='_compute_gcs_total', store=True
    )

    notes = fields.Text(string='Notes')

    # ── Computed ────────────────────────────────────────────────────

    @api.depends('gcs_eye', 'gcs_verbal', 'gcs_motor')
    def _compute_gcs_total(self):
        for rec in self:
            try:
                rec.gcs_total = (
                    int(rec.gcs_eye or 0)
                    + int(rec.gcs_verbal or 0)
                    + int(rec.gcs_motor or 0)
                )
            except (ValueError, TypeError):
                rec.gcs_total = 0
