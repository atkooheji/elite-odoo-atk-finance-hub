# -*- coding: utf-8 -*-
import base64
import hashlib
from urllib.parse import urlencode
from odoo import models, fields, api, _

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'atk_pay':
            return res

        # BenefitPay logic (Direct hashing)
        amount_str = "{:.3f}".format(self.amount)
        reference = self.reference
        
        raw_string = "{}{}{}{}{}{}".format(
            self.provider_id.benefit_merchant_id,
            self.provider_id.benefit_app_id,
            amount_str,
            "BHD",
            reference,
            self.provider_id.benefit_secret_key
        )
        secure_hash = base64.b64encode(hashlib.sha256(raw_string.encode('utf-8')).digest()).decode('utf-8')

        return {
            'api_url': "https://benefit-checkout.benefitpay.bh/#/home",
            'merchantId': self.provider_id.benefit_merchant_id,
            'appId': self.provider_id.benefit_app_id,
            'transactionAmount': amount_str,
            'transactionCurrency': "BHD",
            'referenceNumber': reference,
            'secure_hash': secure_hash,
            'google_merchant_id': self.provider_id.google_merchant_id,
            'google_merchant_name': self.provider_id.google_merchant_name,
            'apple_merchant_id': self.provider_id.apple_merchant_id,
            'apple_domain_verification': self.provider_id.apple_domain_verification,
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction when coming back from BenefitPay"""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'atk_pay' or len(tx) == 1:
            return tx
            
        reference = notification_data.get('referenceNumber')
        if not reference:
            return tx

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'atk_pay')])
        return tx

    def _process_notification_data(self, notification_data):
        """Update transaction status after payment"""
        if hasattr(super(), '_process_notification_data'):
            super()._process_notification_data(notification_data)
        if self.provider_code != 'atk_pay':
            return

        # BenefitPay status handling
        status = notification_data.get('status')
        if status == 'SUCCESS':
            self._set_done()
        elif status in ['CANCELLED', 'FAILED']:
            self._set_canceled()
        else:
            self._set_pending()
