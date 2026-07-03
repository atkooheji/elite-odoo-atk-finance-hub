from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    bank_batch_id = fields.Many2one('bank.import.batch', string='Import Batch', ondelete='cascade')

    def action_auto_reconcile(self):
        """ Delegate to lines """
        self.ensure_one()
        return self.line_ids.action_auto_reconcile()


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    bank_batch_id = fields.Many2one('bank.import.batch', string='Import Batch', compute='_compute_bank_batch_id', store=True)
    unique_import_id = fields.Char(string='Unique Import ID', index=True, help="Hash for duplicate detection")
    transaction_date = fields.Date(string='Transaction Date', help="The actual date the transaction occurred at the bank.")

    @api.depends('statement_id.bank_batch_id')
    def _compute_bank_batch_id(self):
        for line in self:
            line.bank_batch_id = line.statement_id.bank_batch_id if line.statement_id else False

    def action_auto_reconcile(self):
        """ 
        Automatically reconciles statement lines with existing journal items (payments/invoices).
        Matches by amount and date (within a 3-day window).
        """
        reconciled_count = 0
        unreconciled_lines = self.filtered(lambda l: not l.is_reconciled)
        
        for line in unreconciled_lines:
            domain = [
                ('parent_state', '=', 'posted'),
                ('reconciled', '=', False),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable', 'asset_cash']),
                ('balance', '=', -line.amount), # Opposite sign
            ]
            
            # Date proximity (3 days)
            date_from = fields.Date.subtract(line.date, days=3)
            date_to = fields.Date.add(line.date, days=3)
            domain += [('date', '>=', date_from), ('date', '<=', date_to)]
            
            potential_matches = self.env['account.move.line'].search(domain)
            
            if len(potential_matches) == 1:
                try:
                    line.reconcile(lines_vals_list=[{'id': potential_matches.id}])
                    reconciled_count += 1
                except Exception as e:
                    _logger.warning("Failed to auto-reconcile line %s: %s", line.id, e)
        
        if reconciled_count > 0:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': _("Auto-reconciled %s lines.") % reconciled_count,
                    'type': 'rainbow_man',
                }
            }
        return True

    def action_auto_create_record(self):
        """
        Extracts phone/ref from description, finds partner, 
        and automatically creates an Invoice (if amount > 0) or Bill (if amount < 0).
        """
        self.ensure_one()
        if self.is_reconciled:
            raise UserError(_("This line is already reconciled."))

        desc = self.payment_ref or ""
        partner = False
        
        # 1. Look for phone pattern /PHONE/XXXXXXXX
        phone_match = re.search(r'PHONE/(\d+)', desc)
        if not phone_match:
            # Fallback: any 8-12 digit number
            phone_match = re.search(r'(\d{8,12})', desc)
            
        if phone_match:
            phone_num = phone_match.group(1)
            # Find partner by phone or mobile
            partner = self.env['res.partner'].search([
                '|', ('phone', 'ilike', phone_num), ('mobile', 'ilike', phone_num)
            ], limit=1)
        
        if not partner:
            # If still not found, search by name keywords in description (from main branch)
            words = [w for w in desc.split() if len(w) > 3 and w.isalpha()]
            for word in words:
                partner = self.env['res.partner'].search([('name', 'ilike', word)], limit=1)
                if partner: break

        if not partner:
            raise UserError(_("No partner found matching phone/keywords in description: %s") % desc)

        # Determine move type and sign
        if self.amount > 0:
            move_type = 'out_invoice'
            amount = self.amount
        else:
            move_type = 'in_invoice'
            amount = -self.amount

        journal = self.env['account.journal'].search([('type', '=', 'sale' if move_type == 'out_invoice' else 'purchase')], limit=1)
        if not journal:
             raise UserError(_("No sale/purchase journal found to create the record."))

        invoice_vals = {
            'move_type': move_type,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': self.date,
            'date': self.date,
            'ref': self.payment_ref,
            'invoice_line_ids': [(0, 0, {
                'name': self.payment_ref or _('Bank Transaction'),
                'quantity': 1,
                'price_unit': amount,
            })],
        }

        invoice = self.env['account.move'].create(invoice_vals)
        
        return {
            'name': _('Auto Created Record'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_link_iban(self):
        """ Extracts IBAN from description and links it to the partner. (Merged from main) """
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please set a Partner on this line first."))
            
        desc = self.payment_ref or ""
        # Bahrain IBAN pattern
        iban_match = re.search(r'(BH\d{2}[A-Z]{4}[A-Z0-9]{14})', desc.upper())
        
        if not iban_match:
            # Look for any string starting with BH and many numbers
            iban_match = re.search(r'(BH\d{18,22})', desc.upper())
            
        if not iban_match:
            raise UserError(_("No IBAN found in the description."))
            
        iban = iban_match.group(1)
        
        # Check if already exists
        existing = self.env['res.partner.bank'].search([('acc_number', '=', iban), ('partner_id', '=', self.partner_id.id)])
        if not existing:
            self.env['res.partner.bank'].create({
                'acc_number': iban,
                'partner_id': self.partner_id.id,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('IBAN Linked'),
                    'message': _('Successfully added IBAN %s to %s') % (iban, self.partner_id.name),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_("This IBAN is already linked to this partner."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        # Override if needed to prevent deletion of important lines
        pass
