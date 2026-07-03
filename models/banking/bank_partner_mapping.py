from odoo import models, fields, api

class BankPartnerMapping(models.Model):
    _name = 'bank.partner.mapping'
    _description = 'Bank Partner Keyword Mapping'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Keyword', required=True, help="Keyword found in bank statement description")
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)


    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Keyword must be unique per company!'
    )
