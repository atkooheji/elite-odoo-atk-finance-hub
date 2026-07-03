from odoo import models, fields, api, _
from odoo.exceptions import UserError
from difflib import SequenceMatcher

class AccountAccount(models.Model):
    _inherit = 'account.account'

    tally_mapping_ids = fields.One2many('tally.account.mapping', 'odoo_account_id', string='Tally Mappings')

    def _get_company_domain(self):
        acc_fields = self.env['account.account']._fields
        company_id = self.env.company.id
        if 'company_ids' in acc_fields:
            if 'company_id' in acc_fields:
                return ['|', ('company_id', '=', company_id), ('company_ids', 'in', [company_id])]
            else:
                return [('company_ids', 'in', [company_id])]
        return [('company_id', '=', company_id)]

    def action_clear_all_accounts(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only Billing Managers can perform this action."))

        domain = self._get_company_domain()
        all_accounts = self.env['account.account'].search(domain)
        
        move_line_exists = self.env['account.move.line'].search([
            ('account_id', 'in', all_accounts.ids),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if move_line_exists:
            raise UserError(_("You cannot delete accounts because there are existing Journal Entries. \n"
                             "Please delete or reverse all transactions first."))

        try:
            journals = self.env['account.journal'].sudo().search([('company_id', '=', self.env.company.id)])
            if journals:
                journals.write({'suspense_account_id': False, 'default_account_id': False})
        except: pass

        try:
            prop_model = self.env.get('ir.property')
            if prop_model is not None:
                properties = prop_model.sudo().search([
                    ('company_id', '=', self.env.company.id),
                    ('value_reference', 'ilike', 'account.account,%')
                ])
                for prop in properties:
                    try:
                        res_id = int(prop.value_reference.split(',')[1])
                        if res_id in all_accounts.ids: prop.sudo().unlink()
                    except: continue
        except: pass

        count = 0
        for account in all_accounts:
            try:
                account.unlink()
                count += 1
            except: continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('COA Cleaned'),
                'message': _('Successfully deleted %s accounts.') % count,
                'type': 'success',
            }
        }

    def _get_or_create_group_recursive(self, group_path, company_id):
        if not group_path: return self.env['account.group']
        group_model = self.env['account.group'].sudo()
        parts = [p.strip() for p in str(group_path).split('>') if p.strip()]
        parent = self.env['account.group']
        for part in parts:
            idx = parts.index(part)
            domain = [('name', '=', part), ('company_id', '=', company_id), ('parent_id', '=', parent.id if parent else False)]
            current_group = group_model.search(domain, limit=1)
            if not current_group:
                current_group = group_model.create({'name': part, 'company_id': company_id, 'parent_id': parent.id if parent else False})
            parent = current_group
        return current_group

    def action_auto_grouping(self):
        records = self
        if not records:
             domain = self._get_company_domain()
             records = self.search(domain)

        groups = self.env['account.group'].sudo().search([('company_id', '=', self.env.company.id)], order='code_prefix_start desc')
        sorted_groups = sorted(groups, key=lambda g: len(g.code_prefix_start or ''), reverse=True)
        
        updated_count = 0
        mapping_model = self.env['tally.account.mapping']
        
        for account in records:
            match = False
            mapping = mapping_model.sudo().search([('odoo_account_id', '=', account.id)], limit=1)
            tally_group_name = mapping.tally_group if mapping else False
            
            if tally_group_name:
                group = self._get_or_create_group_recursive(tally_group_name, self.env.company.id)
                if group and account.group_id != group:
                    account.group_id = group
                    updated_count += 1
                match = True

            if not match and account.code:
                for group in sorted_groups:
                    if group.code_prefix_start and account.code.startswith(group.code_prefix_start):
                        if account.group_id != group.id:
                            account.group_id = group.id
                            updated_count += 1
                        match = True
                        break
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto Grouping Complete'),
                'message': _('Successfully updated %s accounts.') % updated_count,
                'type': 'success',
            }
        }

    def action_reorganize_coa(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only Billing Managers can perform this action."))

        company_id = self.env.company.id
        group_model = self.env['account.group'].sudo()
        acc_model = self.env['account.account'].sudo()
        
        # Tikco Structure Mapping (Simplified for brevity but maintaining logic)
        TIKCO_MAP = [
            ('1', '11', '111', ['cash'], 'asset_cash', ['Assets', 'Current Assets', 'Cash']),
            ('1', '11', '112', ['bank'], 'asset_cash', ['Assets', 'Current Assets', 'Bank']),
            ('1', '11', '113', ['receivable'], 'asset_receivable', ['Assets', 'Current Assets', 'Receivable']),
            ('2', '21', '211', ['payable'], 'liability_payable', ['Liabilities', 'Current Liabilities', 'Payable']),
            ('4', '41', '411', ['sales', 'revenue'], 'income', ['Revenue', 'Operating Income', 'Sales']),
            ('5', '51', '511', ['expense'], 'expense', ['Expenses', 'Operating Expenses', 'General']),
        ]

        def get_best_match(name):
            lname = str(name).lower()
            for l1, l2, l3, keywords, acc_type, g_names in TIKCO_MAP:
                if any(k in lname for k in keywords): return l1, l2, l3, acc_type, g_names
            return '9', '99', '999', 'asset_current', ['Other', 'Uncategorized', 'Review']

        def ensure_group(prefix, name, parent=None):
            group = group_model.search([('code_prefix_start', '=', prefix), ('company_id', '=', company_id)], limit=1)
            if not group:
                group = group_model.create({'name': name, 'code_prefix_start': prefix, 'code_prefix_end': prefix, 'parent_id': parent.id if parent else False, 'company_id': company_id})
            return group

        all_accounts = acc_model.with_context(active_test=False).search(self._get_company_domain())
        group_counts = {}

        for acc in all_accounts:
            l1, l2, l3, det_type, g_names = get_best_match(acc.name)
            g1 = ensure_group(l1, g_names[0])
            g2 = ensure_group(l2, g_names[1], parent=g1)
            g3 = ensure_group(l3, g_names[2], parent=g2)
            acc.account_type = det_type
            acc.group_id = g3.id
            if l3 not in group_counts: group_counts[l3] = 0
            group_counts[l3] += 1
            acc.code = f"{l3}{group_counts[l3]:02d}"

        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('COA Standarized'), 'message': _('COA restructured successfully.'), 'type': 'success'}}

    def action_learn_from_coa(self):
        mapping_model = self.env['tally.account.mapping'].sudo()
        group_mapping_model = self.env['tally.group.mapping'].sudo()
        company_id = self.env.company.id
        accounts = self.search(self._get_company_domain()).filtered(lambda a: a.group_id and a.tally_mapping_ids)
        learned_count = 0
        for acc in accounts:
            for mapping in acc.tally_mapping_ids:
                if mapping.tally_group:
                    if not group_mapping_model.search([('tally_group_name', '=', mapping.tally_group), ('company_id', '=', company_id)], limit=1):
                        group_mapping_model.create({'tally_group_name': mapping.tally_group, 'odoo_group_id': acc.group_id.id, 'company_id': company_id})
                        learned_count += 1
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('Learning Complete'), 'message': _('Created %s mapping rules.') % learned_count, 'type': 'success'}}
