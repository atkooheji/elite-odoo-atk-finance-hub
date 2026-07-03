from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountCheckTemplate(models.Model):
    _name = 'account.check.template'
    _description = 'Check Layout Template'

    name = fields.Char(string='Template Name', required=True)
    
    # Date Coordinates
    date_top = fields.Float('Date Top (mm)', default=16.0)
    date_left = fields.Float('Date Left (mm)', default=121.0)
    date_letter_spacing = fields.Float('Date Letter Spacing (mm)', default=3.30)
    
    # Payee Coordinates
    payee_top = fields.Float('Payee Top (mm)', default=25.0)
    payee_left = fields.Float('Payee Left (mm)', default=45.0)
    payee_width = fields.Float('Payee Width (mm)', default=120.0)
    
    # Amount Words Coordinates
    amount_words_top = fields.Float('Amount Words Top (mm)', default=38.1)
    amount_words_left = fields.Float('Amount Words Left (mm)', default=20.0)
    amount_words_width = fields.Float('Amount Words Width (mm)', default=120.0)
    amount_words_line_height = fields.Float('Amount Words Line Height (mm)', default=8.0)
    amount_words_indent = fields.Float('Amount Words Indent (mm)', default=20.0)
    
    # Amount Figures Coordinates
    amount_top = fields.Float('Amount Figures Top (mm)', default=46.0)
    amount_left = fields.Float('Amount Figures Left (mm)', default=135.0)
    
    # Font Settings
    font_size = fields.Integer('Font Size (px)', default=14)
    font_family = fields.Char('Font Family', default='sans-serif')

    # A/C Payee
    ac_payee = fields.Boolean('A/C Payee Only', default=True)
    ac_payee_top = fields.Float('A/C Payee Top (mm)', default=5.0)
    ac_payee_left = fields.Float('A/C Payee Left (mm)', default=5.0)

class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    # Custom Check Printing Configuration
    check_layout_mode = fields.Selection([
        ('custom', 'Custom Layout')
    ], string="Check Layout Mode", default='custom')
    
    check_next_number = fields.Integer(string='Next Check Number', default=1, copy=False)

    # A/C Payee
    check_ac_payee = fields.Boolean('A/C Payee', default=True)
    check_ac_payee_top = fields.Float('A/C Payee Top (mm)', default=5.0)
    check_ac_payee_left = fields.Float('A/C Payee Left (mm)', default=5.0)

    # Date
    check_date_top = fields.Float('Date Top (mm)', default=16.0)
    check_date_left = fields.Float('Date Left (mm)', default=121.0)
    check_date_letter_spacing = fields.Float('Date Letter Spacing (mm)', default=3.30)
    
    # Payee
    check_payee_top = fields.Float('Payee Top (mm)', default=25.0)
    check_payee_left = fields.Float('Payee Left (mm)', default=45.0)
    check_payee_width = fields.Float('Payee Width (mm)', default=120.0)
    
    # Amount Words
    check_amount_words_top = fields.Float('Amount Words Top (mm)', default=38.1)
    check_amount_words_left = fields.Float('Amount Words Left (mm)', default=20.0)
    check_amount_words_width = fields.Float('Amount Words Width (mm)', default=120.0)
    check_amount_words_line_height = fields.Float('Amount Words Line Height (mm)', default=8.0)
    check_amount_words_indent = fields.Float('Amount Words Indent (mm)', default=20.0)
    
    # Amount Figures
    check_amount_top = fields.Float('Amount Figures Top (mm)', default=46.0)
    check_amount_left = fields.Float('Amount Figures Left (mm)', default=135.0)
    
    # Global
    check_font_size = fields.Integer('Font Size (px)', default=14)
    check_font_family = fields.Char('Font Family', default='sans-serif')
    
    check_template_id = fields.Many2one('account.check.template', string="Load Bank Template", help="Select a bank to auto-fill the coordinates below. You can also create your own.")

    @api.onchange('check_template_id')
    def _onchange_check_template_id(self):
        if not self.check_template_id:
            return
        
        t = self.check_template_id
        self.check_date_top = t.date_top
        self.check_date_left = t.date_left
        self.check_date_letter_spacing = t.date_letter_spacing
        
        self.check_payee_top = t.payee_top
        self.check_payee_left = t.payee_left
        self.check_payee_width = t.payee_width
        
        self.check_amount_words_top = t.amount_words_top
        self.check_amount_words_left = t.amount_words_left
        self.check_amount_words_width = t.amount_words_width
        self.check_amount_words_line_height = t.amount_words_line_height
        self.check_amount_words_indent = t.amount_words_indent
        
        self.check_amount_top = t.amount_top
        self.check_amount_left = t.amount_left
        self.check_font_size = t.font_size
        self.check_font_family = t.font_family
        self.check_ac_payee = t.ac_payee
        self.check_ac_payee_top = t.ac_payee_top
        self.check_ac_payee_left = t.ac_payee_left

    def action_save_as_template(self):
        """ Allows user to save current journal settings as a new template. """
        self.ensure_one()
        return {
            'name': 'Save as Check Template',
            'type': 'ir.actions.act_window',
            'res_model': 'account.check.template',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_date_top': self.check_date_top,
                'default_date_left': self.check_date_left,
                'default_date_letter_spacing': self.check_date_letter_spacing,
                'default_payee_top': self.check_payee_top,
                'default_payee_left': self.check_payee_left,
                'default_payee_width': self.check_payee_width,
                'default_amount_words_top': self.check_amount_words_top,
                'default_amount_words_left': self.check_amount_words_left,
                'default_amount_words_width': self.check_amount_words_width,
                'default_amount_words_line_height': self.check_amount_words_line_height,
                'default_amount_words_indent': self.check_amount_words_indent,
                'default_amount_top': self.check_amount_top,
                'default_amount_left': self.check_amount_left,
                'default_font_size': self.check_font_size,
                'default_font_family': self.check_font_family,
                'default_ac_payee': self.check_ac_payee,
                'default_ac_payee_top': self.check_ac_payee_top,
                'default_ac_payee_left': self.check_ac_payee_left,
            }
        }

    def action_print_test_check(self):
        """ Prints a test check with dummy data using current journal settings. """
        self.ensure_one()
        payment = self.env['account.payment'].search([('journal_id', '=', self.id)], limit=1)
        if not payment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Payment Found',
                    'message': 'Please ensure there is at least one payment in this journal to print a test check.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
            
        return self.env.ref('atk_finance_hub.action_print_check_custom').report_action(payment)

    def _get_check_layout_values(self):
        try:
            res = super()._get_check_layout_values()
        except:
            res = []
        res.append(('atk_finance_hub.action_print_check_custom', 'Bahraini Check Layout'))
        return res

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    check_amount_in_words = fields.Char(string="Amount in Words", compute='_compute_check_amount_in_words')
    check_number = fields.Char(string="Check Number", copy=False)
    is_check_payment = fields.Boolean(compute='_compute_is_check_payment')

    @api.depends('payment_method_line_id', 'journal_id')
    def _compute_is_check_payment(self):
        for payment in self:
            code = (payment.payment_method_line_id.code or '').lower()
            payment.is_check_payment = 'check' in code or (payment.journal_id and payment.journal_id.type == 'bank')

    def _compute_check_amount_in_words(self):
        for payment in self:
            amount_text = payment.currency_id.amount_to_text(payment.amount) if payment.currency_id else ''
            if amount_text:
                clean_text = amount_text.strip()
                if not clean_text.lower().endswith('only'):
                    amount_text = f"{clean_text} ONLY"
            payment.check_amount_in_words = amount_text

    def action_print_check_bh(self):
        """ Premium UX: Open wizard to confirm/set check number before printing. """
        self.ensure_one()
        if self.journal_id.type != 'bank':
            raise UserError(_('Checks can only be printed from a Bank journal.'))
            
        return self.env.ref('atk_finance_hub.action_print_check_bh_wizard').read()[0]
