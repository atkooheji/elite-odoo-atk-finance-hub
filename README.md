# ATK - Unified Finance Hub

## Overview

ATK Unified Finance Hub ======================== A premium, consolidated suite of financial tools for Bahrain. Refactored for modularity and scalability.

This repository contains the standalone Odoo addon `atk_finance_hub` extracted from the Elite Sport Odoo project. It is intended to be versioned, reviewed, and reused independently from the full Odoo deployment repository.

## Project Details

- **Technical module name:** `atk_finance_hub`
- **GitHub repository:** `https://github.com/atkooheji/elite-odoo-atk-finance-hub`
- **Odoo version target:** Odoo 19
- **Module version:** `19.0.1.3`
- **Author:** AntiGravity Technologies
- **License:** `LGPL-3`
- **Installable:** `True`
- **Application module:** `True`

## What This Module Does

Unified Bahraini Banking, Cheque Management, and Payment Gateway for Odoo 19.

Use this addon as part of the Elite Sport custom Odoo stack. It may depend on other ATK/Elite modules, so install dependencies first when deploying it outside the original monorepo.

## Dependencies

- `base`
- `account`
- `account_payment`
- `payment`
- `mail`
- `purchase`
- `atk_finance_dashboard`
- `atk_prop_mgmt`

## Included Data and Views

- `security/security.xml`
- `security/ir.model.access.csv`
- `views/payment_hub/payment_templates.xml`
- `views/cheques/report_check_template.xml`
- `wizard/banking/bank_statement_import_wizard_view.xml`
- `views/banking/bank_import_batch_views.xml`
- `views/banking/bank_partner_mapping_views.xml`
- `views/cheques/check_template_views.xml`
- `views/cheques/account_journal_views.xml`
- `views/cheques/account_payment_views.xml`
- `wizard/cheques/print_check_wizard_views.xml`
- `views/payment_hub/payment_provider_views.xml`
- `report/cheques/print_check_report.xml`
- `views/tally/account_views.xml`
- `views/tally/tally_batch_views.xml`
- `views/tally/tally_mapping_views.xml`
- `views/tally/tally_wizard_views.xml`
- `data/cheque_data.xml`
- `data/payment_data.xml`
- `data/tally_data.xml`
- `views/menu.xml`

## Demo Data

- None declared

## Repository Structure

- `__manifest__.py` - Odoo module manifest
- `__init__.py` - module initialization
- `models/` - 22 file(s)
- `views/` - 13 file(s)
- `security/` - 2 file(s)
- `data/` - 4 file(s)
- `static/` - 3 file(s)
- `wizard/` - 10 file(s)
- `report/` - 1 file(s)

## Installation

1. Copy this addon folder into an Odoo addons path, for example `/mnt/extra-addons/atk_finance_hub`.
2. Make sure all dependencies listed above are installed or available in the same Odoo database.
3. Restart the Odoo service so the addon path is rescanned.
4. Activate developer mode in Odoo.
5. Go to **Apps**, update the apps list, search for `atk_finance_hub`, and install it.

## Upgrade

After pulling changes into an existing Odoo environment, upgrade the module with:

```bash
odoo-bin -d <database_name> -u atk_finance_hub --stop-after-init
```

For Odoo.sh, push the branch and upgrade the module from the Odoo Apps interface or through the deployment upgrade flow.

## Development Workflow

1. Create a feature branch from `main`.
2. Make changes inside this addon only.
3. Test installation and upgrade on a local/staging database.
4. Check server logs for registry, XML, access-rights, and dependency errors.
5. Commit with a clear message and open a pull request before production use.

## Testing Checklist

- Module installs without registry errors.
- Module upgrades cleanly from the previous version.
- Menus, views, security groups, and access rights load correctly.
- Any scheduled actions, controllers, or integrations run as expected.
- No secrets, database dumps, or environment files are committed.

## Security Notes

This is a public repository. Do not commit `.env` files, credentials, customer data, database backups, private tokens, or production logs. Keep deployment-specific configuration outside the addon source.

## Source Context

Extracted from the Elite Sport Odoo project under:

```text
D:\001-AntiGravity\003-Odoo\elite_sport_project-main\elite_sport_project-main\addons\atk_finance_hub
```
