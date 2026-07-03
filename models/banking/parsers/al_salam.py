from .base_parser import BaseBankParser

class AlSalamParser(BaseBankParser):
    name = "Ithmaar Bank / Al Salam (New)"
    
    # Specific keywords for Al Salam Bank statements
    kw_date = ['date', 'val date', 'value date', 'transaction date']
    kw_tran_date = ['tran date', 'transaction date']
    kw_desc = ['description', 'particulars', 'narration', 'transaction narrative', 'narrative', 'details', 'remarks']
    kw_amount = ['amount', 'net amount', 'tran amount', 'amt', 'value amount']
    kw_debit = ['withdrawals', 'withdrawal', 'out', 'debit', 'dr']
    kw_credit = ['deposits', 'deposit', 'in', 'credit', 'cr']
    kw_ref = ['reference', 'cheque', 'ref no', 'ref.', 'chq', 'ref code', 'doc no', 'ft reference']
    kw_balance = ['balance', 'closing balance', 'cur bal', 'final balance', 'bal']
