# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('atk_pay', 'ATK Payment Hub')], ondelete={'atk_pay': 'set default'})
    
    # --- BENEFITPAY CONFIG ---
    benefit_merchant_id = fields.Char(string="Benefit Merchant ID")
    benefit_app_id = fields.Char(string="Benefit App ID")
    benefit_secret_key = fields.Char(string="Benefit Secret Key")
    benefit_guide_url = fields.Char(string="Benefit Guide", default="https://www.benefit.bh/Business/OnlinePaymentGateway/")

    # --- APPLE PAY CONFIG ---
    apple_merchant_id = fields.Char(string="Apple Merchant ID")
    apple_merchant_cert = fields.Binary(string="Merchant Certificate (.pem)")
    apple_domain_verification = fields.Char(string="Domain Verification Code")
    apple_guide_url = fields.Char(string="Apple Guide", default="https://developer.apple.com/apple-pay/")

    # --- GOOGLE PAY CONFIG ---
    google_merchant_id = fields.Char(string="Google Merchant ID")
    google_merchant_name = fields.Char(string="Business Name")
    google_guide_url = fields.Char(string="Google Guide", default="https://pay.google.com/business/console/")

    def _get_supported_currencies(self):
        res = super()._get_supported_currencies()
        if self.code == 'atk_pay':
            return self.env['res.currency'].search([('name', 'in', ['BHD', 'SAR', 'USD'])])
        return res
