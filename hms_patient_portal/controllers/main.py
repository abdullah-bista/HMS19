# -*- coding: utf-8 -*-
from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import datetime


class HMSPatientPortal(CustomerPortal):

    def _get_portal_patient(self):
        """Return the hms.patient linked to the current portal user, or empty recordset."""
        return request.env['hms.patient'].sudo().search(
            [('partner_id', '=', request.env.user.commercial_partner_id.id)], limit=1
        )

    def _patient_domain(self, patient):
        """Return a domain restricting records to the given patient.
        Returns an impossible domain when patient is not found, so no records leak."""
        if patient:
            return [('patient_id', '=', patient.id)]
        return [('id', '=', False)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        patient = self._get_portal_patient()
        domain = self._patient_domain(patient)

        # HMS counters — prefixed to avoid collision with Enterprise appointment module
        if 'hms_appointment_count' in counters:
            Appt = request.env['hms.appointment']
            values['hms_appointment_count'] = (
                Appt.sudo().search_count(domain) if Appt.has_access('read') else 0
            )
        if 'hms_prescription_count' in counters:
            Rx = request.env['prescription.order']
            values['hms_prescription_count'] = (
                Rx.sudo().search_count(domain) if Rx.has_access('read') else 0
            )
        if 'hms_treatment_count' in counters:
            Trt = request.env['hms.treatment']
            values['hms_treatment_count'] = (
                Trt.sudo().search_count(domain) if Trt.has_access('read') else 0
            )
        # Override lab counts produced by acs_laboratory (those use no patient filter)
        if 'lab_result_count' in counters:
            LabTest = request.env['patient.laboratory.test']
            values['lab_result_count'] = (
                LabTest.sudo().search_count(domain) if LabTest.has_access('read') else 0
            )
        if 'lab_request_count' in counters:
            LabReq = request.env['acs.laboratory.request']
            values['lab_request_count'] = (
                LabReq.sudo().search_count(domain) if LabReq.has_access('read') else 0
            )
        return values

    # -------------------------------------------------------------------------
    # Appointments
    # -------------------------------------------------------------------------

    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_appointments(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        patient = self._get_portal_patient()
        sortby = sortby or 'date'
        sortings = {
            'date':  {'label': _('Newest'), 'order': 'date desc'},
            'name':  {'label': _('Name'),   'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        domain = self._patient_domain(patient)
        order  = sortings.get(sortby, sortings['date'])['order']
        count  = request.env['hms.appointment'].sudo().search_count(domain)
        pager  = portal_pager(
            url='/my/appointments', url_args={},
            total=count, page=page, step=self._items_per_page,
        )
        appointments = request.env['hms.appointment'].sudo().search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset']
        )
        values.update({
            'appointments': appointments, 'pager': pager,
            'sortings': sortings, 'sortby': sortby,
            'page_name': 'appointment', 'default_url': '/my/appointments',
            'searchbar_sortings': sortings,
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
        physicians  = request.env['hms.physician'].sudo().search([('active', '=', True)])
        departments = request.env['hr.department'].sudo().search([])
        return request.render('hms_patient_portal.portal_appointment_request_form', {
            'physicians': physicians, 'departments': departments,
            'page_name': 'appointment_new',
        })

    @http.route(['/my/appointments/new'],
                type='http', auth='user', website=True, sitemap=False, methods=['POST'])
    def my_appointment_request_submit(self, **post):
        patient = self._get_portal_patient()
        if not patient:
            return request.redirect('/my')
        product = request.env.company.sudo().consultation_product_id
        vals = {
            'patient_id': patient.id,
            'physician_id':  int(post['physician_id'])  if post.get('physician_id')  else False,
            'department_id': int(post['department_id']) if post.get('department_id') else False,
            'date': datetime.datetime.fromisoformat(post.get('date')) if post.get('date', False) else fields.Datetime.now(),
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
        patient = self._get_portal_patient()
        sortby = sortby or 'date'
        sortings = {
            'date':  {'label': _('Newest'), 'order': 'prescription_date desc'},
            'name':  {'label': _('Name'),   'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        domain = self._patient_domain(patient)
        order  = sortings.get(sortby, sortings['date'])['order']
        count  = request.env['prescription.order'].sudo().search_count(domain)
        pager  = portal_pager(
            url='/my/prescriptions', url_args={},
            total=count, page=page, step=self._items_per_page,
        )
        prescriptions = request.env['prescription.order'].sudo().search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset']
        )
        values.update({
            'prescriptions': prescriptions, 'pager': pager,
            'sortings': sortings, 'sortby': sortby,
            'page_name': 'prescription', 'default_url': '/my/prescriptions',
            'searchbar_sortings': sortings,
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
        patient = self._get_portal_patient()
        sortby = sortby or 'date'
        sortings = {
            'date':  {'label': _('Newest'), 'order': 'date desc'},
            'name':  {'label': _('Name'),   'order': 'name'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        domain = self._patient_domain(patient)
        order  = sortings.get(sortby, sortings['date'])['order']
        count  = request.env['hms.treatment'].sudo().search_count(domain)
        pager  = portal_pager(
            url='/my/treatments', url_args={},
            total=count, page=page, step=self._items_per_page,
        )
        treatments = request.env['hms.treatment'].sudo().search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset']
        )
        values.update({
            'treatments': treatments, 'pager': pager,
            'sortings': sortings, 'sortby': sortby,
            'page_name': 'treatment', 'default_url': '/my/treatments',
            'searchbar_sortings': sortings,
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
        patient = self._get_portal_patient()
        latest_eval = False
        if patient:
            latest_eval = request.env['acs.patient.evaluation'].sudo().search(
                [('patient_id', '=', patient.id), ('state', '=', 'done')],
                order='date desc', limit=1,
            )
        return request.render('hms_patient_portal.portal_health_summary', {
            'patient': patient,
            'latest_eval': latest_eval,
            'page_name': 'health_summary',
        })

    # -------------------------------------------------------------------------
    # Lab Results — overrides acs_laboratory route to add patient filter
    # -------------------------------------------------------------------------

    @http.route(['/my/lab_results', '/my/lab_results/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_lab_results(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        patient = self._get_portal_patient()
        sortby = sortby or 'date'
        sortings = {
            'date': {'label': _('Newest'), 'order': 'date_analysis desc'},
            'name': {'label': _('Name'),   'order': 'name'},
        }
        domain = self._patient_domain(patient)
        order  = sortings.get(sortby, sortings['date'])['order']
        count  = request.env['patient.laboratory.test'].sudo().search_count(domain)
        pager  = portal_pager(
            url='/my/lab_results', url_args={},
            total=count, page=page, step=self._items_per_page,
        )
        lab_results = request.env['patient.laboratory.test'].sudo().search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset']
        )
        values.update({
            'lab_results': lab_results, 'pager': pager,
            'sortings': sortings, 'sortby': sortby,
            'page_name': 'lab_result', 'default_url': '/my/lab_results',
            'searchbar_sortings': sortings,
        })
        return request.render('acs_laboratory.lab_results', values)

    # -------------------------------------------------------------------------
    # Lab Requests — overrides acs_laboratory route to add patient filter
    # -------------------------------------------------------------------------

    @http.route(['/my/lab_requests', '/my/lab_requests/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def my_lab_requests(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        patient = self._get_portal_patient()
        sortby = sortby or 'date'
        sortings = {
            'date': {'label': _('Newest'), 'order': 'date desc'},
            'name': {'label': _('Name'),   'order': 'name'},
        }
        domain = self._patient_domain(patient)
        order  = sortings.get(sortby, sortings['date'])['order']
        count  = request.env['acs.laboratory.request'].sudo().search_count(domain)
        pager  = portal_pager(
            url='/my/lab_requests', url_args={},
            total=count, page=page, step=self._items_per_page,
        )
        lab_requests = request.env['acs.laboratory.request'].sudo().search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset']
        )
        values.update({
            'lab_requests': lab_requests, 'pager': pager,
            'sortings': sortings, 'sortby': sortby,
            'page_name': 'lab_request', 'default_url': '/my/lab_requests',
            'searchbar_sortings': sortings,
        })
        return request.render('acs_laboratory.lab_requests', values)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
