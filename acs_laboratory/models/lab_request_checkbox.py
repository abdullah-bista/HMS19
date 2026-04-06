# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.tools import partition

import itertools
from itertools import chain, repeat

from lxml import etree
from lxml.builder import E
from collections import defaultdict


def name_boolean_group(id):
    return 'in_group_' + str(id)

def is_boolean_group(name):
    return name.startswith('in_group_')

def is_reified_group(name):
    return is_boolean_group(name)

def get_boolean_group(name):
    return int(name[9:])

def parse_m2m(commands):
    "return a list of ids corresponding to a many2many value"
    ids = []
    for command in commands:
        if isinstance(command, (tuple, list)):
            if command[0] in (Command.UPDATE, Command.LINK):
                ids.append(command[1])
            elif command[0] == Command.CLEAR:
                ids = []
            elif command[0] == Command.SET:
                ids = list(command[2])
        else:
            ids.append(command)
    return ids


class LaboratoryRequestView(models.Model):
    _inherit = 'acs.laboratory.request'

    lab_test_ids = fields.Many2many('acs.lab.test', 'acs_lab_test_req_rel', 'test_id', 'requset_id', string="Tests")

    def acs_update_test_lines(self):
        RequestLine = self.env['laboratory.request.line']
        for rec in self:
            rec.line_ids.unlink()
            for test in rec.lab_test_ids:
                line = RequestLine.sudo().create({
                    'test_id': test.id,
                    'request_id': rec.id,
                })
                line.onchange_test()

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for values in vals_list:
            new_vals_list.append(self._remove_reified_groups(values))
        records = super(LaboratoryRequestView, self).create(new_vals_list)
        records.sudo().acs_update_test_lines()
        return records

    def write(self, values):
        values = self._remove_reified_groups(values)
        res = super(LaboratoryRequestView, self).write(values)
        if 'lab_test_ids' in values:
            self.acs_update_test_lines()
        return res

    @api.model
    def new(self, values={}, origin=None, ref=None):
        values = self._remove_reified_groups(values)
        user = super().new(values=values, origin=origin, ref=ref)
        return user

    def _remove_reified_groups(self, values):
        """ return `values` without reified group fields """
        add, rem = [], []
        values1 = {}

        for key, val in values.items():
            if is_boolean_group(key):
                (add if val else rem).append(get_boolean_group(key))
            else:
                values1[key] = val
        
        if 'lab_test_ids' not in values and (add or rem):
            # remove group ids in `rem` and add group ids in `add`
            values1['lab_test_ids'] = list(itertools.chain(
                zip(repeat(3), rem),
                zip(repeat(4), add)
            ))
        return values1

    @api.model
    def default_get(self, fields):
        group_fields, fields = partition(is_reified_group, fields)
        fields1 = (fields + ['lab_test_ids']) if group_fields else fields
        values = super(LaboratoryRequestView, self).default_get(fields1)
        self._add_reified_groups(group_fields, values)
        return values

    def onchange(self, values, field_names, fields_spec):
        reified_fnames = [fname for fname in fields_spec if is_reified_group(fname)]
        if reified_fnames:
            values = {key: val for key, val in values.items() if key != 'lab_test_ids'}
            values = self._remove_reified_groups(values)

            if any(is_reified_group(fname) for fname in field_names):
                field_names = [fname for fname in field_names if not is_reified_group(fname)]
                field_names.append('lab_test_ids')

            fields_spec = {
                field_name: field_spec
                for field_name, field_spec in fields_spec.items()
                if not is_reified_group(field_name)
            }
            fields_spec['lab_test_ids'] = {}

        result = super().onchange(values, field_names, fields_spec)

        if reified_fnames and 'lab_test_ids' in result.get('value', {}):
            self._add_reified_groups(reified_fnames, result['value'])
            result['value'].pop('lab_test_ids', None)

        return result

    def read(self, fields=None, load='_classic_read'):
        # determine whether reified groups fields are required, and which ones
        fields1 = fields or list(self.fields_get())
        group_fields, other_fields = partition(is_reified_group, fields1)

        # read regular fields (other_fields); add 'lab_test_ids' if necessary
        drop_groups_id = False
        if group_fields and fields:
            if 'lab_test_ids' not in other_fields:
                other_fields.append('lab_test_ids')
                drop_groups_id = True
        else:
            other_fields = fields

        res = super(LaboratoryRequestView, self).read(other_fields, load=load)

        # post-process result to add reified group fields
        if group_fields:
            for values in res:
                self._add_reified_groups(group_fields, values)
                if drop_groups_id:
                    values.pop('lab_test_ids', None)
        return res

    def _add_reified_groups(self, fields, values):
        """ add the given reified group fields into `values` """
        gids = set(parse_m2m(values.get('lab_test_ids') or []))
        for f in fields:
            if is_boolean_group(f):
                values[f] = get_boolean_group(f) in gids

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(LaboratoryRequestView, self).fields_get(allfields, attributes=attributes)
        # add reified groups fields
        Test = self.env['acs.lab.test'].sudo()
        for app, kind, gs, category_name in Test.get_groups_by_application():
            # boolean group fields
            for g in gs:
                field_name = name_boolean_group(g.id)
                if allfields and field_name not in allfields:
                    continue
                res[field_name] = {
                    'type': 'boolean',
                    'string': g.name,
                    #'help': g.comment,
                    'exportable': False,
                    'selectable': False,
                }
        return res


#Services VIEW WITH CHECKBOX Same as Users view
class AcsLabTestView(models.Model):
    _inherit = 'acs.lab.test'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self._update_lab_test_groups_view()
        # actions.get_bindings() depends on action records
        self.env.registry.clear_cache()
        self.env.invalidate_all()
        return res

    def write(self, values):
        # determine which values the "user groups view" depends on
        res = super(AcsLabTestView, self).write(values)
        # update the "user groups view" only if necessary
        if 'category_id' in values:
            self._update_lab_test_groups_view()
        # actions.get_bindings() depends on action records
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super(AcsLabTestView, self).unlink()
        self._update_lab_test_groups_view()
        # actions.get_bindings() depends on action records
        self.env.registry.clear_cache()
        return res

    @api.model
    def _update_lab_test_groups_view(self):
        """ Modify the view with xmlid ``acs_laboratory.patient_laboratory_test_request_form_checkbox``, which inherits
            the lab req form view, and introduces the reified checkbox fields.
        """
        # remove the language to avoid translations, it will be handled at the view level
        self = self.with_context(lang=None)

        # We have to try-catch this, because at first init the view does not
        # exist but we are already creating some basic groups.
        view = self.sudo().env.ref('acs_laboratory.patient_laboratory_test_request_form_checkbox', raise_if_not_found=False)
        if not (view and view._name == 'ir.ui.view'):
            return

        if self._context.get('install_filename') or self._context.get(MODULE_UNINSTALL_FLAG):
            # use a dummy view during install/upgrade/uninstall
            xml = E.field(name="line_ids", position="after")

        else:
            xml1, xml2, xml3 = [], [], []
            xml_by_category = {}

            user_type_field_name = ''
            user_readonly = "state!='draft'"
            sorted_tuples = sorted(self.get_groups_by_application())
            
            for app, kind, gs, category_name in sorted_tuples:  # we process the user type first
                attrs = {}
                invisible = "state!='draft'"
                acs_sub_group = []
                # application separator with boolean fields
                app_name = app.name or 'Other'
                acs_sub_group.append(E.separator(string=app_name, colspan="2", invisible=invisible))
                for g in gs:
                    #Update Attrs
                    user_readonly = "state!='draft'"
                    field_name = name_boolean_group(g.id)
                    acs_sub_group.append(E.field(name=field_name, readonly=user_readonly))
                
                xml3.append(E.group(*(acs_sub_group), col="2", invisible=invisible))

            xml = E.field(
                #E.group(*(xml1), col="2"),
                #E.group(*(xml2), col="2", attrs=str(user_type_attrs)),
                E.group(*(xml3), col="4"), name="lab_test_ids", position="replace")
            xml.addprevious(etree.Comment("GENERATED AUTOMATICALLY BY GROUPS"))

        # serialize and update the view
        xml_content = etree.tostring(xml, pretty_print=True, encoding="unicode")
        if xml_content != view.arch:  # avoid useless xml validation if no change
            new_context = dict(view._context)
            new_context.pop('install_filename', None)  # don't set arch_fs for this computed view
            new_context['lang'] = None
            view.with_context(new_context).write({'arch': xml_content})

    def get_application_groups(self, domain):
        """ Return the non-share groups that satisfy ``domain``. """
        return self.search(domain)

    @api.model
    def get_groups_by_application(self):
        """ Return all groups classified by application (module category), as a list::

                [(app, kind, groups), ...],

            where ``app`` and ``groups`` are recordsets, and ``kind`` is either
            ``'boolean'`` or ``'selection'``. Applications are given in sequence
            order.  If ``kind`` is ``'selection'``, ``groups`` are given in
            reverse implication order.
        """
        def linearize(app, gs, category_name):
            # determine sequence order: a group appears after its implied groups
            #order = {g: len(g.trans_implied_ids & gs) for g in gs}
            # check whether order is total, i.e., sequence orders are distinct
            return (app, 'boolean', gs, (100, 'Other'))

        # classify all groups by application
        by_app, others = defaultdict(self.browse), self.browse()
        for g in self.get_application_groups([]):
            if g.category_id:
                by_app[g.category_id] += g
            else:
                others += g
        # build the result
        res = []
        for app, gs in sorted(by_app.items(), key=lambda it: it[0].sequence or 0):    
            res.append(linearize(app, gs, (100, 'Other')))

        if others:
            res.append((self.env['acs.laboratory.test.category'], 'boolean', others, (100,'Other')))
        return res

    #ACS: Patch to avoid issue on updaintg module.
    @api.model
    def update_lab_test_groups_view(self):
        self._update_lab_test_groups_view()

 
class AcsLabTestCategoryView(models.Model):
    _inherit = "acs.laboratory.test.category"
    
    user_ids = fields.Many2many('res.users', 'lab_category_user_rel', 'lab_category_id', 'user_id', string="Users")

    def write(self, values):
        res = super().write(values)
        if "name" in values:
            self.env["acs.lab.test"]._update_lab_test_groups_view()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["acs.lab.test"]._update_lab_test_groups_view()
        return res
