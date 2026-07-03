from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    tally_batch_id = fields.Many2one('tally.import.batch', string='Tally Import Batch', ondelete='set null', copy=False)
    tally_voucher_no = fields.Char(string='Tally Voucher No', readonly=True, copy=False)
    is_tally_import = fields.Boolean(string='Imported from Tally', default=False, readonly=True)
