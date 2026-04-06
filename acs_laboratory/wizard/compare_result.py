# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class LabComparisonResult(models.TransientModel):
    _name = "lab.comparison.result"
    _description = "Lab Comparison Result"
    _rec_name = 'patient_id'

    patient_id = fields.Many2one('hms.patient', string="Patient", required=True)
    test_id = fields.Many2one('acs.lab.test', string="Test", required=True)
    comparison_results = fields.Html(string="Comparison Results",compute="_compute_result_table", readonly=True)
    test_result_ids = fields.Many2many('patient.laboratory.test', 'test_result_comparison_rel', 'comparison_id', 'test_result_id', string='Test Results',required=True)

    @api.onchange('patient_id','test_id')
    def _onchange_patient_test(self):
        lab_tests = self.env['patient.laboratory.test'].search([
            ('patient_id', '=', self.patient_id.id),
            ('test_id', '=', self.test_id.id)
        ])
        self.test_result_ids = lab_tests[:5] if len(lab_tests) > 5 else lab_tests

    @api.depends('test_result_ids','test_id')   
    def _compute_result_table(self):        
        lab_tests = self.test_result_ids
        if len(lab_tests) < 2:
            self.comparison_results = False

        lab_test_critearea = self.test_id.critearea_ids
        if len(lab_tests) == 2:
            first_report = lab_tests[0]
            last_report = lab_tests[-1]

            comparison_html = f"""
                <table style='width: 100%; border-collapse: collapse; font-family: Arial, sans-serif;'>
                    <tr style='background-color: #d0eaf3; color: #333;'>
                        <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'><b>Parameter</b></th>
                        <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'><b>{first_report.date_analysis.strftime('%d-%m-%Y')} ({first_report.name})</b></th>
                        <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'><b>{last_report.date_analysis.strftime('%d-%m-%Y')} ({last_report.name})</b></th>
                        <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'><b>Difference (%)</b></th>
                    </tr> 
            """

            for param in lab_test_critearea:
                if param.display_type == 'line_section':
                    comparison_html += f"""
                        <tr style='background-color: #e9f5f9;'>
                            <td colspan="4" style='border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold; background-color: #edf7fa;'>{param.name}</td>
                        </tr>"""
                else:
                    first_crit = first_report.critearea_ids.filtered(lambda c: c.name == param.name)
                    last_crit = last_report.critearea_ids.filtered(lambda c: c.name == param.name)

                    if first_crit and last_crit:
                        first_value = float(first_crit.result or 0)
                        last_value = float(last_crit.result or 0)
                        if first_value != 0:
                            difference = ((last_value - first_value) / first_value) * 100
                        else:
                            difference = 0.0

                        comparison_html += f"""
                            <tr style='background-color: #fcfefe;'>
                                <td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>{param.name}</td>
                                <td style='border: 1px solid #ddd; padding: 8px; text-align: end;'>{first_value}</td>
                                <td style='border: 1px solid #ddd; padding: 8px; text-align: end;'>{last_value}</td>
                                <td style='border: 1px solid #ddd; padding: 8px; text-align: end; color: {"#eb2632" if difference < 0.0 else "#006a60"}; font-weight: bold;'>{difference:.2f}%</td>
                            </tr>"""

            comparison_html += "</table>"
            self.comparison_results = comparison_html

        else:
            comparison_html = f"""
                <table style='width: 100%; border-collapse: collapse; font-family: Arial, sans-serif;'>
                    <tr style='background-color: #d0eaf3; color: #333;'>
                        <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'><b>Parameter</b></th>
            """

            for test in lab_tests:
                comparison_html += f"""
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: center;'>
                        <b>{test.date_analysis.strftime('%d-%m-%Y')} ({test.name})</b>
                    </th>
                """

            comparison_html += "</tr>"

            for param in lab_test_critearea:
                if param.display_type == 'line_section':
                    comparison_html += f"""
                        <tr style='background-color: #e9f5f9;'>
                            <td colspan="{len(lab_tests) + 1}" style='border: 1px solid #ddd; padding: 8px; text-align: start; font-weight: bold;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{param.name}</td>
                        </tr>
                    """
                else:
                    comparison_html += f"""
                        <tr style='background-color: #fcfefe;'>
                            <td style='border: 1px solid #ddd; padding: 8px; text-align: center;'>{param.name}</td>
                    """
                    for test in lab_tests:
                        crit = test.critearea_ids.filtered(lambda c: c.name == param.name)
                        value = float(crit.result or 0)
                        comparison_html += f"<td style='border: 1px solid #ddd; padding: 8px; text-align: end;'>{value}</td>"

                    comparison_html += "</tr>"

            comparison_html += "</table>"
            self.comparison_results = comparison_html       
