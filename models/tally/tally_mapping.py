from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TallyAccountMapping(models.Model):
    _name = 'tally.account.mapping'
    _description = 'Tally Account Mapping'
    _rec_name = 'tally_ledger_name'

    tally_ledger_name = fields.Char(string='Tally Ledger Name', required=True, index=True)
    tally_group = fields.Char(string='Tally Group')
    is_summary = fields.Boolean(string='Is Summary Ledger', default=False)
    odoo_account_id = fields.Many2one('account.account', string='Odoo GL Account')
    confidence_score = fields.Float(string='Match Confidence', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _tally_ledger_name_company_uniq = models.Constraint(
        'unique(tally_ledger_name, company_id)',
        'Tally Ledger Name must be unique per company!'
    )

    def action_bulk_auto_map(self):
        """ Restoration: Automatically map Tally ledgers to Odoo accounts with advanced heuristics and auto-creation. """
        acc_model = self.env['account.account']
        acc_fields = acc_model._fields
        for record in self:
            if not record.odoo_account_id:
                ledger_name = record.tally_ledger_name.strip()
                lname = ledger_name.lower()
                
                # Base Company Domain
                comp_dom = []
                if 'company_id' in acc_fields:
                    comp_dom.append(('company_id', '=', record.company_id.id))
                elif 'company_ids' in acc_fields:
                    comp_dom.append(('company_ids', 'in', [record.company_id.id]))
                
                # 1. Try Exact/Partial Match
                match = acc_model.search(comp_dom + [('name', '=ilike', ledger_name)], limit=1)
                if not match:
                    match = acc_model.search(comp_dom + [('name', 'ilike', ledger_name)], limit=1)
                
                # 2. Keyword Fallback for Payables/Receivables
                if not match:
                    if 'payable' in lname or 'creditor' in lname:
                        match = acc_model.search(comp_dom + [('account_type', '=', 'liability_payable')], limit=1)
                    elif 'receivable' in lname or 'debtor' in lname:
                        match = acc_model.search(comp_dom + [('account_type', '=', 'asset_receivable')], limit=1)

                # 3. Utility / EWA Mapping
                if not match and any(k in lname for k in ['ewa', 'electricity', 'water', 'utility']):
                    match = acc_model.search(comp_dom + ['|', ('name', 'ilike', 'utilit'), ('name', 'ilike', 'electric')], limit=1)

                # 4. Maintenance Mapping
                if not match and any(k in lname for k in ['maintenance', 'repair', 'renovation']):
                    match = acc_model.search(comp_dom + ['|', ('name', 'ilike', 'mainten'), ('name', 'ilike', 'repair')], limit=1)

                # 5. Capital / Equity Mapping
                if not match and 'capital' in lname:
                    match = acc_model.search(comp_dom + [('account_type', '=', 'equity')], limit=1)

                # 6. Partner/Individual Detection (Heuristic for names like "First Last")
                if not match:
                    words = ledger_name.split()
                    if len(words) >= 2 and all(w[0].isupper() for w in words if len(w) > 1):
                        # Map to general Payable if it looks like a person
                        match = acc_model.search(comp_dom + [('account_type', '=', 'liability_payable')], limit=1)

                if match:
                    record.odoo_account_id = match.id

        # Automatically trigger creation for anything still missing
        self.action_create_missing_accounts()
        return True

    def action_create_missing_accounts(self):
        """ Restoration: Create missing GL accounts in Odoo based on Tally ledger names. """
        acc_model = self.env['account.account'].sudo()
        acc_fields = acc_model._fields
        created_count = 0
        for record in self:
            if not record.odoo_account_id:
                ledger_name = record.tally_ledger_name.strip()
                lname = ledger_name.lower()
                
                # Determine Account Type
                acc_type = 'expense'
                if any(k in lname for k in ['payable', 'creditor', 'liability']): acc_type = 'liability_payable'
                elif any(k in lname for k in ['receivable', 'debtor', 'customer']): acc_type = 'asset_receivable'
                elif any(k in lname for k in ['income', 'revenue', 'sales', 'dividend']): acc_type = 'income'
                elif any(k in lname for k in ['bank', 'cash']): acc_type = 'asset_cash'
                elif 'capital' in lname or 'equity' in lname: acc_type = 'equity'
                
                # Determine Code Prefix
                prefix = {'expense': '51', 'income': '41', 'liability_payable': '21', 'asset_receivable': '12', 'asset_cash': '10', 'equity': '31'}.get(acc_type, '99')
                
                # Base Company Domain
                comp_dom = []
                if 'company_id' in acc_fields:
                    comp_dom.append(('company_id', '=', record.company_id.id))
                elif 'company_ids' in acc_fields:
                    comp_dom.append(('company_ids', 'in', [record.company_id.id]))
                
                # Find the next available code
                last_acc = acc_model.search(comp_dom + [('code', '=like', f'{prefix}%')], order='code desc', limit=1)
                next_code = str(int(last_acc.code) + 1) if last_acc and last_acc.code.isdigit() else f"{prefix}0001"
                
                # Create the account
                vals = {
                    'name': ledger_name,
                    'code': next_code,
                    'account_type': acc_type,
                }
                if 'company_id' in acc_fields: vals['company_id'] = record.company_id.id
                elif 'company_ids' in acc_fields: vals['company_ids'] = [(4, record.company_id.id)]
                
                new_acc = acc_model.create(vals)
                record.odoo_account_id = new_acc.id
                created_count += 1
        return True

class TallyGroupMapping(models.Model):
    _name = 'tally.group.mapping'
    _description = 'Tally Group Mapping'
    _rec_name = 'tally_group_name'

    tally_group_name = fields.Char(string='Tally Group Name', required=True, index=True)
    odoo_group_id = fields.Many2one('account.group', string='Odoo Account Group', required=True)
    account_type = fields.Selection(selection=[
        ('asset_receivable', 'Receivable'),
        ('asset_cash', 'Bank and Cash'),
        ('asset_current', 'Current Assets'),
        ('asset_non_current', 'Non-current Assets'),
        ('asset_prepayments', 'Prepayments'),
        ('asset_fixed', 'Fixed Assets'),
        ('liability_payable', 'Payable'),
        ('liability_credit_card', 'Credit Card'),
        ('liability_current', 'Current Liabilities'),
        ('liability_non_current', 'Non-current Liabilities'),
        ('equity', 'Equity'),
        ('equity_unaffected', 'Current Year Earnings'),
        ('income', 'Income'),
        ('income_other', 'Other Income'),
        ('expense', 'Expenses'),
        ('expense_depreciation', 'Depreciation'),
        ('expense_direct_cost', 'Cost of Revenue'),
        ('off_balance', 'Off-Balance Sheet'),
    ], string='Odoo Account Type')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _tally_group_name_company_uniq = models.Constraint(
        'unique(tally_group_name, company_id)',
        'Tally Group Name must be unique per company!'
    )

    def action_bulk_auto_map(self):
        """ Automatically map Tally groups to Odoo groups by name. """
        for record in self:
            if not record.odoo_group_id:
                match = self.env['account.group'].search([
                    ('name', '=ilike', record.tally_group_name),
                    ('company_id', '=', record.company_id.id)
                ], limit=1)
                if match:
                    record.odoo_group_id = match.id
        return True

    def action_create_missing_groups(self):
        """ Create missing account groups in Odoo. """
        pass
        return True

class TallyVoucherMapping(models.Model):
    _name = 'tally.voucher.mapping'
    _description = 'Tally Voucher Mapping'
    _rec_name = 'tally_voucher_type'

    tally_voucher_type = fields.Char(string='Tally Voucher Type', required=True, index=True)
    odoo_journal_id = fields.Many2one('account.journal', string='Odoo Journal', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _tally_voucher_type_company_unique = models.Constraint(
        'unique(tally_voucher_type, company_id)',
        'Tally Voucher Type must be unique per company!'
    )

    def action_auto_map_journals(self):
        """ Automatically map Tally voucher types to Odoo journals. """
        for record in self:
            if not record.odoo_journal_id:
                match = self.env['account.journal'].search([
                    ('name', '=ilike', record.tally_voucher_type),
                    ('company_id', '=', record.company_id.id)
                ], limit=1)
                if match:
                    record.odoo_journal_id = match.id
        return True

class TallyVoucherTypeMapping(models.Model):
    """ Legacy Alias: To satisfy registry lookups for the older model name until the DB is fully migrated. """
    _name = 'tally.voucher.type.mapping'
    _description = 'Tally Voucher Type Mapping (Alias)'
    _inherit = 'tally.voucher.mapping'
