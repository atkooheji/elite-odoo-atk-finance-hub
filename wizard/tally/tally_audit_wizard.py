import base64
import io
import pandas as pd
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TallyAuditWizard(models.TransientModel):
    _name = 'tally.audit.wizard'
    _description = 'Tally Audit Wizard'

    import_file = fields.Binary(string='Tally Trial Balance', required=True)
    file_name = fields.Char(string='File Name')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    comparison_date = fields.Date(string='Comparison Date', default=fields.Date.today)
    result_ids = fields.One2many('tally.audit.result', 'wizard_id', string='Audit Results', readonly=True)

    def action_compare(self):
        self.ensure_one()
        if not self.import_file: raise UserError(_("Please upload a file."))
        file_content = base64.b64decode(self.import_file)
        try:
            df = pd.read_excel(io.BytesIO(file_content), header=None)
        except Exception as e:
            raise UserError(_("Error reading Excel file: %s") % str(e))

        header_row = -1
        col_map = {}
        for i, row in df.iterrows():
            row_vals = [str(x).strip().lower() for x in row.tolist() if pd.notnull(x)]
            if any('particulars' in v for v in row_vals):
                header_row = i
                for look_ahead in range(3):
                    if (i + look_ahead) >= len(df): break
                    curr_row = df.iloc[i + look_ahead]
                    for col_idx, val in enumerate(curr_row):
                        if pd.isna(val): continue
                        val_str = str(val).strip().lower()
                        if 'particular' in val_str and 'particulars' not in col_map: col_map['particulars'] = col_idx
                        elif ('closing' in val_str or 'balance' in val_str) and 'closing' not in col_map:
                             if 'closing' in val_str: col_map['closing'] = col_idx
                break
        
        if header_row == -1 or 'particulars' not in col_map or 'closing' not in col_map:
             raise UserError(_("Could not find valid headers."))

        data_df = df.iloc[header_row+1:].copy()
        part_idx = col_map['particulars']
        close_idx = col_map['closing']

        mappings = self.env['tally.account.mapping'].search([('company_id', '=', self.company_id.id)])
        ledger_map = {m.tally_ledger_name: m.odoo_account_id for m in mappings}

        results = []
        for idx, row in data_df.iterrows():
            acct_name = str(row.iloc[part_idx]).strip()
            if not acct_name or acct_name.lower() in ['particulars', 'total']: continue
            val_str = str(row.iloc[close_idx]).lower().replace(',', '')
            is_cr = 'cr' in val_str
            try: tally_bal = float(val_str.replace('dr', '').replace('cr', ''))
            except: continue
            if is_cr: tally_bal = -tally_bal

            odoo_acc = ledger_map.get(acct_name)
            odoo_bal = 0.0
            if odoo_acc:
                query = "SELECT sum(debit - credit) FROM account_move_line WHERE account_id = %s AND date <= %s AND company_id = %s AND parent_state = 'posted'"
                self.env.cr.execute(query, (odoo_acc.id, self.comparison_date, self.company_id.id))
                odoo_bal = self.env.cr.fetchone()[0] or 0.0

            results.append((0, 0, {'account_name': acct_name, 'odoo_account_id': odoo_acc.id if odoo_acc else False, 'tally_balance': tally_bal, 'odoo_balance': odoo_bal}))

        self.write({'result_ids': results})
        return {'type': 'ir.actions.act_window', 'res_model': 'tally.audit.wizard', 'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
