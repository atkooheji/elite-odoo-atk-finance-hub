from odoo import models, fields, api, _

class TallyAuditResult(models.TransientModel):
    _name = 'tally.audit.result'
    _description = 'Tally Audit Comparison Result'

    account_name = fields.Char(string='Account Name')
    odoo_account_id = fields.Many2one('account.account', string='Odoo Account')
    tally_balance = fields.Float(string='Tally Balance')
    odoo_balance = fields.Float(string='Odoo Balance')
    difference = fields.Float(string='Difference', compute='_compute_difference', store=True)
    status = fields.Selection([
        ('match', 'Match'),
        ('mismatch', 'Mismatch'),
        ('unmapped', 'Unmapped')
    ], string='Status', compute='_compute_status', store=True)
    
    wizard_id = fields.Many2one('tally.audit.wizard', string='Wizard')

    @api.depends('tally_balance', 'odoo_balance')
    def _compute_difference(self):
        for record in self:
            record.difference = record.tally_balance - record.odoo_balance

    @api.depends('difference', 'odoo_account_id')
    def _compute_status(self):
        for record in self:
            if not record.odoo_account_id: record.status = 'unmapped'
            elif abs(record.difference) < 0.01: record.status = 'match'
            else: record.status = 'mismatch'
