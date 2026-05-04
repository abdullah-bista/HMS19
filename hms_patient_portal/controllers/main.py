# -*- coding: utf-8 -*-
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class HMSPatientPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        if 'appointment_count' in counters:
            Appointment = request.env['hms.appointment'].sudo()
            values['appointment_count'] = (
                Appointment.search_count([]) if Appointment.has_access('read') else 0
            )

        if 'prescription_count' in counters:
            Prescription = request.env['prescription.order'].sudo()
            values['prescription_count'] = (
                Prescription.search_count([]) if Prescription.has_access('read') else 0
            )

        if 'treatment_count' in counters:
            Treatment = request.env['hms.treatment'].sudo()
            values['treatment_count'] = (
                Treatment.search_count([]) if Treatment.has_access('read') else 0
            )

        return values

    # -------------------------------------------------------------------------
    # Appointments
    # -------------------------------------------------------------------------

    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_appointments(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Appointment = request.env['hms.appointment'].sudo()

        if not sortby:
            sortby = 'date'

        sortings = {
            'date': {'label': _('Newest'), 'order': 'date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }

        order = sortings.get(sortby, sortings['date'])['order']
        count = Appointment.search_count([])

        pager = portal_pager(
            url='/my/appointments',
            url_args={},
            total=count,
            page=page,
            step=self._items_per_page,
        )

        appointments = Appointment.search(
            [], order=order, limit=self._items_per_page, offset=pager['offset']
        )

        values.update({
            'sortings': sortings,
            'sortby': sortby,
            'appointments': appointments,
            'page_name': 'appointment',
            'default_url': '/my/appointments',
            'searchbar_sortings': sortings,
            'pager': pager,
        })
        return request.render('hms_patient_portal.portal_my_appointments', values)

    @http.route(['/my/appointments/<int:appointment_id>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_appointment_detail(self, appointment_id, access_token=None, **kw):
        try:
            appt_sudo = self._document_check_access(
                'hms.appointment', appointment_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        return request.render('hms_patient_portal.portal_appointment_detail', {
            'appointment': appt_sudo,
            'page_name': 'appointment',
        })

    @http.route(['/my/appointments/new'],
                type='http', auth='user', website=True, sitemap=False, methods=['GET'])
    def my_appointment_request_form(self, **kw):
        physicians = request.env['hms.physician'].sudo().search([('active', '=', True)])
        departments = request.env['hr.department'].sudo().search([])
        return request.render('hms_patient_portal.portal_appointment_request_form', {
            'physicians': physicians,
            'departments': departments,
            'page_name': 'appointment_new',
        })

    @http.route(['/my/appointments/new'],
                type='http', auth='user', website=True, sitemap=False, methods=['POST'])
    def my_appointment_request_submit(self, **post):
        patient = request.env['hms.patient'].sudo().search(
            [('partner_id', '=', request.env.user.commercial_partner_id.id)], limit=1
        )
        if not patient:
            return request.redirect('/my')

        product = request.env.company.sudo().consultation_product_id
        vals = {
            'patient_id': patient.id,
            'physician_id': int(post['physician_id']) if post.get('physician_id') else False,
            'department_id': int(post['department_id']) if post.get('department_id') else False,
            'date': post.get('date') or fields.Datetime.now(),
            'chief_complain': post.get('notes', ''),
            'state': 'draft',
        }
        if product:
            vals['product_id'] = product.id

        new_appt = request.env['hms.appointment'].sudo().create(vals)
        return request.redirect('/my/appointments/%s' % new_appt.id)

    # -------------------------------------------------------------------------
    # Prescriptions
    # -------------------------------------------------------------------------

    @http.route(['/my/prescriptions', '/my/prescriptions/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_prescriptions(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Prescription = request.env['prescription.order'].sudo()

        if not sortby:
            sortby = 'date'

        sortings = {
            'date': {'label': _('Newest'), 'order': 'prescription_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }

        order = sortings.get(sortby, sortings['date'])['order']
        count = Prescription.search_count([])

        pager = portal_pager(
            url='/my/prescriptions',
            url_args={},
            total=count,
            page=page,
            step=self._items_per_page,
        )

        prescriptions = Prescription.search(
            [], order=order, limit=self._items_per_page, offset=pager['offset']
        )

        values.update({
            'sortings': sortings,
            'sortby': sortby,
            'prescriptions': prescriptions,
            'page_name': 'prescription',
            'default_url': '/my/prescriptions',
            'searchbar_sortings': sortings,
            'pager': pager,
        })
        return request.render('hms_patient_portal.portal_my_prescriptions', values)

    @http.route(['/my/prescriptions/<int:prescription_id>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_prescription_detail(self, prescription_id, access_token=None, **kw):
        try:
            rx_sudo = self._document_check_access(
                'prescription.order', prescription_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        return request.render('hms_patient_portal.portal_my_prescription_detail', {
            'prescription': rx_sudo,
            'page_name': 'prescription',
        })

    # -------------------------------------------------------------------------
    # Treatments
    # -------------------------------------------------------------------------

    @http.route(['/my/treatments', '/my/treatments/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_treatments(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Treatment = request.env['hms.treatment'].sudo()

        if not sortby:
            sortby = 'date'

        sortings = {
            'date': {'label': _('Newest'), 'order': 'date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }

        order = sortings.get(sortby, sortings['date'])['order']
        count = Treatment.search_count([])

        pager = portal_pager(
            url='/my/treatments',
            url_args={},
            total=count,
            page=page,
            step=self._items_per_page,
        )

        treatments = Treatment.search(
            [], order=order, limit=self._items_per_page, offset=pager['offset']
        )

        values.update({
            'sortings': sortings,
            'sortby': sortby,
            'treatments': treatments,
            'page_name': 'treatment',
            'default_url': '/my/treatments',
            'searchbar_sortings': sortings,
            'pager': pager,
        })
        return request.render('hms_patient_portal.portal_my_treatments', values)

    @http.route(['/my/treatments/<int:treatment_id>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_treatment_detail(self, treatment_id, access_token=None, **kw):
        try:
            trt_sudo = self._document_check_access(
                'hms.treatment', treatment_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        return request.render('hms_patient_portal.portal_my_treatment_detail', {
            'treatment': trt_sudo,
            'page_name': 'treatment',
        })

    # -------------------------------------------------------------------------
    # Health Summary
    # -------------------------------------------------------------------------

    @http.route(['/my/health_summary'],
                type='http', auth='user', website=True, sitemap=False)
    def my_health_summary(self, **kw):
        patient = request.env['hms.patient'].sudo().search(
            [('partner_id', '=', request.env.user.commercial_partner_id.id)], limit=1
        )
        latest_eval = False
        if patient:
            latest_eval = request.env['acs.patient.evaluation'].sudo().search(
                [('patient_id', '=', patient.id), ('state', '=', 'done')],
                order='date desc',
                limit=1,
            )

        return request.render('hms_patient_portal.portal_health_summary', {
            'patient': patient,
            'latest_eval': latest_eval,
            'page_name': 'health_summary',
        })

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
