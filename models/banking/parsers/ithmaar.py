from .base_parser import BaseBankParser

class IthmaarParser(BaseBankParser):
    name = "Ithmaar Bank (Legacy)"
    kw_date = ['date', 'val date', 'value date', 'transaction date']
    kw_desc = ['description', 'particulars', 'narration', 'transaction narrative', 'narrative', 'details', 'remarks']
    kw_debit = ['withdrawals', 'withdrawal', 'out', 'debit', 'dr']
    kw_credit = ['deposits', 'deposit', 'in', 'credit', 'cr']
