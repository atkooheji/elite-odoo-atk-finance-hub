from odoo import models, fields, api, _

class PrintCheckBhWizard(models.TransientModel):
    _name = 'print.check.bh.wizard'
    _description = 'Print Bahraini Check Wizard'

    payment_id = fields.Many2one('account.payment', string='Payment', required=True)
    journal_id = fields.Many2one('account.journal', related='payment_id.journal_id', string='Journal')
    check_number = fields.Char(string='Check Number', required=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        payment_id = self.env.context.get('active_id')
        if payment_id:
            payment = self.env['account.payment'].browse(payment_id)
            res['payment_id'] = payment.id
            res['check_number'] = payment.check_number or str(payment.journal_id.check_next_number or '1')
        return res

    def action_print(self):
        self.ensure_one()
        # Update check number on payment
        self.payment_id.write({'check_number': self.check_number})
        
        # Increment next number on journal if this matches the current next number
        try:
            current_next = int(self.journal_id.check_next_number or 0)
            if self.check_number.isdigit() and int(self.check_number) >= current_next:
                self.journal_id.check_next_number = int(self.check_number) + 1
        except:
            pass

        return self.env.ref('atk_finance_hub.action_print_check_custom').report_action(self.payment_id)
