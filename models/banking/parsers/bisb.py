from .base_parser import BaseBankParser

class BisBParser(BaseBankParser):
    name = "BisB (Bahrain Islamic Bank)"
    kw_date = ['value date', 'date', 'val date', 'transaction date']
    kw_desc = ['narration', 'transaction details', 'description', 'particulars', 'remarks']
    kw_debit = ['withdrawal', 'debit', 'out', 'dr']
    kw_credit = ['deposit', 'credit', 'in', 'cr']
