from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BankImportBatch(models.Model):
    _name = 'bank.import.batch'
    _description = 'Bank Statement Import Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    journal_id = fields.Many2one('account.journal', string='Bank Journal', required=True, domain=[('type', 'in', ['bank', 'cash', 'credit', 'credit_card'])])
    date = fields.Date(string='Import Date', default=fields.Date.context_today, required=True)
    user_id = fields.Many2one('res.users', string='Imported By', default=lambda self: self.env.user)
    import_file = fields.Binary(string='Statement File', attachment=True)
    import_filename = fields.Char(string='Filename')
    
    statement_ids = fields.One2many('account.bank.statement', 'bank_batch_id', string='Imported Statements')
    line_ids = fields.One2many('account.bank.statement.line', 'bank_batch_id', string='Statement Lines')
    
    line_count = fields.Integer(string='Total Lines', compute='_compute_stats')
    reconciled_count = fields.Integer(string='Auto-Matched', compute='_compute_stats')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_stats', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='journal_id.company_id.currency_id')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bank.import.batch') or _('New')
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.is_reconciled')
    def _compute_stats(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.reconciled_count = len(batch.line_ids.filtered(lambda l: l.is_reconciled))
            batch.total_amount = sum(batch.line_ids.mapped('amount'))

    def action_undo(self):
        self.ensure_one()
        if self.state == 'done':
            # Check if any lines are already reconciled
            if self.line_ids.filtered(lambda l: l.is_reconciled):
                raise UserError(_("Cannot undo import: Some lines are already reconciled. Please unreconcile them first."))
        
        # 1. Capture lines and statements
        lines = self.line_ids
        statements = self.statement_ids
        
        # 2. Unlink Statement Lines (Journal Transactions)
        # This will remove them from the Odoo Bank Journal views
        if lines:
            _logger.info("Batch Undo: Deleting %s statement lines for batch %s", len(lines), self.name)
            lines.unlink()
            
        # 3. Unlink Grouping Statements
        if statements:
            _logger.info("Batch Undo: Deleting %s bank statements for batch %s", len(statements), self.name)
            statements.unlink()
            
        # 4. Finalize Batch Status
        self.state = 'cancel'
        return True

    def action_auto_reconcile(self):
        self.ensure_one()
        for statement in self.statement_ids:
            statement.action_auto_reconcile()
        return True

    def action_auto_create_all(self):
        self.ensure_one()
        for line in self.line_ids.filtered(lambda l: not l.is_reconciled):
            try:
                line.action_auto_create_record()
            except Exception:
                continue
        return True

    def action_import_from_file(self):
        """
        Processes the attached file using the wizard's logic but within the current batch context.
        """
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please attach a file before executing the import."))
            
        # We instantiate a transient wizard to reuse its parsing logic without duplication
        wizard = self.env['bank.statement.import.wizard'].create({
            'journal_id': self.journal_id.id,
            'import_file': self.import_file,
            'file_name': self.import_filename,
            'auto_reconcile': True,
        })
        
        # Override action_import logic slightly to target THIS batch
        import base64
        import io
        import pandas as pd
        from odoo.addons.atk_finance_hub.models.banking import parsers
        PARSERS = getattr(parsers, 'PARSERS', [])
        
        file_content = base64.b64decode(self.import_file)
        file_name = self.import_filename
        
        is_pdf = file_name and file_name.lower().endswith('.pdf')
        df = None
        
        if is_pdf:
            df = wizard._parse_pdf(file_content)
        else:
            try:
                df = pd.read_excel(io.BytesIO(file_content), header=None)
            except:
                try:
                    df = pd.read_csv(io.BytesIO(file_content), header=None)
                except:
                    raise UserError(_("Could not read file %s. Please ensure it is a valid Excel or CSV file.") % file_name)

        if df is None:
            raise UserError(_("The file appears to be empty or corrupted."))

        # Detect Parser
        active_parser = None
        header_info = False
        for ParserClass in PARSERS:
            parser_inst = ParserClass(self)
            header_info = parser_inst.detect(df)
            if header_info:
                active_parser = parser_inst
                break
        
        if not active_parser:
             raise UserError(_("Could not detect bank format for %s. Ensure it is a standard Bahraini bank statement.") % file_name)

        # Pre-load Partner Mappings
        mappings = self.env['bank.partner.mapping'].search_read([], ['name', 'partner_id'])
        
        # Create Bank Statement linked to THIS batch
        statement = self.env['account.bank.statement'].create({
            'name': f"{active_parser.name}: {file_name}",
            'journal_id': self.journal_id.id,
            'date': fields.Date.today(),
            'bank_batch_id': self.id,
        })
        
        line_vals, skipped_duplicates = active_parser.parse_rows(
            df, header_info, self.journal_id.id, mappings, seen_in_batch=set()
        )
        
        if line_vals:
            balance_start, balance_end_real = wizard._extract_balances(df)
            line_ids = [(0, 0, v) for v in line_vals]
            for l in line_ids:
                l[2]['statement_id'] = statement.id
            
            statement.write({
                'line_ids': line_ids,
                'balance_start': balance_start,
                'balance_end_real': balance_end_real or (balance_start + sum(l[2]['amount'] for l in line_ids))
            })
            statement.action_auto_reconcile()
        else:
            statement.unlink()
            raise UserError(_("No new transactions found in the file. %s duplicates were skipped.") % skipped_duplicates if skipped_duplicates else "")
            
        self.state = 'done'
        return True

    def action_open_statements(self):
        self.ensure_one()
        return {
            'name': _('Statements'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement',
            'view_mode': 'list,form',
            'domain': [('bank_batch_id', '=', self.id)],
            'context': {**self.env.context, 'default_journal_id': self.journal_id.id},
        }

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import Bank Statement (Bahrain)'),
            'type': 'ir.actions.act_window',
            'res_model': 'bank.statement.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_journal_id': self.journal_id.id,
                'default_bank_batch_id': self.id,
            }
        }
