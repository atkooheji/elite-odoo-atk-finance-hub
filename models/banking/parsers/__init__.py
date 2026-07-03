from .base_parser import BaseBankParser, GenericBankParser
from .al_salam import AlSalamParser
from .bisb import BisBParser
from .ithmaar import IthmaarParser

# Global list of available bank parsers
PARSERS = [
    AlSalamParser,
    BisBParser,
    IthmaarParser,
    GenericBankParser, # Final catch-all
]
