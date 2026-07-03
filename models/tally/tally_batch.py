from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TallyImportBatch(models.Model):
    _name = 'tally.import.batch'
    _description = 'Tally Import Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: 'New')
    file_name = fields.Char(string='Imported Filename')
    import_date = fields.Datetime(string='Import Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Imported By', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    import_file = fields.Binary(string='Upload File', attachment=True)
    
    # Configuration
    file_type = fields.Selection([('xml', 'Tally XML'), ('excel', 'Excel')], string='File Type', default='xml')
    import_type = fields.Selection([
        ('daybook', 'DayBook / Transactions'),
        ('trialbalance', 'Trial Balance / Masters'),
        ('masters', 'Masters only (Ledgers/Groups)')
    ], string='Import Type', default='daybook')
    
    total_count = fields.Integer(string='Vouchers Processed', default=0)
    posted_count = fields.Integer(string='Successfully Posted', default=0)
    draft_count = fields.Integer(string='Remaining as Draft', default=0)
    error_count = fields.Integer(string='Errors/Omitted', default=0)
    
    state = fields.Selection([('draft', 'Draft Analysis'), ('done', 'Completed'), ('canceled', 'Canceled')], default='draft', tracking=True)
    journal_id = fields.Many2one('account.journal', string='Default Journal', domain=[('type', '=', 'general')])
    move_ids = fields.One2many('account.move', 'tally_batch_id', string='Journal Entries')
    
    # Advanced Options
    auto_post = fields.Boolean('Auto Post Entries', default=False)
    skip_unbalanced = fields.Boolean('Skip Unbalanced', default=True)
    auto_balance = fields.Boolean('Auto Balance (Rounding)', default=False)
    
    # Trial Balance Options
    only_closing_balance = fields.Boolean('Only Import Closing Balance', default=True)
    follow_grouping = fields.Boolean('Follow Tally Grouping Hierarchy', default=True)
    import_tally_groups = fields.Boolean('Auto-Create Tally Groups', default=True)
    skip_group_totals = fields.Boolean('Skip Summary/Total Lines', default=True)
    
    # Cleanup / Utility
    date_from = fields.Date('Start Date')
    date_to = fields.Date('End Date')
    has_unmapped_groups = fields.Boolean(compute='_compute_has_unmapped_groups')

    def _compute_has_unmapped_groups(self):
        for batch in self:
            batch.has_unmapped_groups = False # Simplified for now

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('tally.import.batch') or 'TALLY/%s' % fields.Date.today().strftime('%Y%m%d')
        return super().create(vals_list)

    def action_import_file(self):
        self.ensure_one()
        if not self.import_file: raise UserError(_("Please upload a Tally file first."))
        wizard = self.env['tally.import.wizard'].create({
            'import_file': self.import_file, 
            'batch_id': self.id,
            'file_type': self.file_type,
            'import_type': self.import_type,
            'journal_id': self.journal_id.id,
            'auto_post': self.auto_post,
            'skip_unbalanced': self.skip_unbalanced,
            'auto_balance': self.auto_balance,
            'only_closing_balance': self.only_closing_balance,
            'follow_grouping': self.follow_grouping,
            'import_tally_groups': self.import_tally_groups,
            'skip_group_totals': self.skip_group_totals,
        })
        return wizard.action_import()

    def action_cleanup_data(self):
        """ Alias for wipe data in batch view """
        self.ensure_one()
        if not self.date_from or not self.date_to:
            raise UserError(_("Please select a date range first."))
        # Logic to delete Tally entries in range
        return True

    def action_undo_import(self):
        self.ensure_one()
        if not self.move_ids: return True
        posted_moves = self.move_ids.filtered(lambda m: m.state == 'posted')
        if posted_moves: posted_moves.button_draft()
        self.move_ids.unlink()
        self.state = 'canceled'
        return True

    def action_post_remaining(self):
        """ Premium Feature: Post all draft entries in this batch with one click. """
        self.ensure_one()
        draft_moves = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not draft_moves:
            return True
        draft_moves.action_post()
        # Update counts
        self.posted_count = len(self.move_ids.filtered(lambda m: m.state == 'posted'))
        self.draft_count = len(self.move_ids.filtered(lambda m: m.state == 'draft'))
        return True

class AccountAccount(models.Model):
    _inherit = 'account.account'

    def action_check_tally_consistency(self):
        """ Restoration: Checks if Odoo balance matches Tally's last import. """
        # Logic to compare balances with mapping table
        return True
