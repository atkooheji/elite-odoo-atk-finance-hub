from . import models
from . import wizard

def post_init_hook(env):
    """ Re-map XML IDs from old modules to ensure zero data loss with surgical SQL """
    old_modules = ('atk_bank_bh', 'atk_check_bh', 'atk_payment', 'atk_tally')
    
    # 1. Delete old metadata records IF they already exist in the new hub (to avoid unique constraint errors)
    # This happens for shared security rules or standard data redefined in the hub.
    env.cr.execute("""
        DELETE FROM ir_model_data old
        WHERE old.module IN %s
          AND EXISTS (
              SELECT 1 FROM ir_model_data new 
              WHERE new.module = 'atk_finance_hub' 
                AND new.name = old.name
          )
    """, (old_modules,))
    
    # 2. Safely update the module ownership for all other records
    # This preserves all your transaction history, bank statements, and mappings.
    env.cr.execute("""
        UPDATE ir_model_data 
        SET module = 'atk_finance_hub' 
        WHERE module IN %s
    """, (old_modules,))
