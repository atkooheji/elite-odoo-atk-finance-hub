import base64
import io
import logging
import pandas as pd
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BankStatementImportWizard(models.TransientModel):
    _name = 'bank.statement.import.wizard'
    _description = 'Bank Statement Import Wizard'

    import_file = fields.Binary(string='Statement File')
    file_name = fields.Char(string='File Name')
    journal_id = fields.Many2one('account.journal', string='Bank Journal', required=True, domain=[('type', 'in', ['bank', 'cash', 'credit', 'credit_card'])])
    attachment_ids = fields.Many2many('ir.attachment', string='Multiple Statements', help="Upload multiple bank statements (Excel/PDF)")
    auto_reconcile = fields.Boolean(string='Auto Reconcile', default=True, help="Automatically attempt matching transactions after import")
    import_local_folder = fields.Boolean(string='Import from Local Folder', help="Scan a directory on the server for statements")
    folder_path = fields.Char(string='Folder Path', default=r'D:\Nl3ab\Bank Statment')
    parser_type = fields.Selection([
        ('auto', 'Auto-Detect (Smart Scanning)'),
        ('aggressive', 'Forced Aggressive (Catch-All)'),
        ('nbb', 'National Bank of Bahrain (NBB)'),
        ('bbk', 'Bank of Bahrain and Kuwait (BBK)'),
        ('al_salam', 'Al Salam Bank'),
    ], string='Import Strategy', default='auto', required=True)

    def action_import(self):
        self.ensure_one()
        import os
        import hashlib
        # Updated Import Path for Consolidation
        # Robust Parser Loading
        from odoo.addons.atk_finance_hub.models.banking import parsers
        PARSERS = getattr(parsers, 'PARSERS', [])

        
        files_to_process = []
        
        # 1. Handle Local Folder
        if self.import_local_folder and self.folder_path:
            if not os.path.exists(self.folder_path):
                 raise UserError(_("Local folder path does not exist: %s") % self.folder_path)
            
            for fname in os.listdir(self.folder_path):
                if fname.lower().endswith(('.xlsx', '.xls', '.pdf', '.csv')):
                    fpath = os.path.join(self.folder_path, fname)
                    with open(fpath, 'rb') as f:
                        files_to_process.append({
                            'content': f.read(),
                            'name': fname
                        })
        
        # 2. Handle Uploaded Attachments
        if self.attachment_ids:
            for attach in self.attachment_ids:
                files_to_process.append({
                    'content': base64.b64decode(attach.datas),
                    'name': attach.name
                })
        
        # 3. Handle Single File Upload
        elif self.import_file:
            files_to_process.append({
                'content': base64.b64decode(self.import_file),
                'name': self.file_name
            })
            
        if not files_to_process:
            raise UserError(_("Please upload at least one file."))
        
        # Create Batch Record
        batch = self.env['bank.import.batch'].create({
            'journal_id': self.journal_id.id,
            'date': fields.Date.today(),
        })

        # Pre-load Partner Mappings
        mappings = self.env['bank.partner.mapping'].search_read([], ['name', 'partner_id'])
        
        statement_ids = []
        error_summary = []
        session_seen_hashes = set()
        
        for file_data in files_to_process:
            file_content = file_data['content']
            file_name = file_data['name']
            
            is_pdf = file_name and file_name.lower().endswith('.pdf')
            df = None
            
            try:
                if is_pdf:
                    df = self._parse_pdf(file_content)
                else:
                    try:
                        # Attempt deep workbook inspection
                        _logger.info("Scanning Excel workbook %s for transaction sheets...", file_name)
                        xlsx = pd.ExcelFile(io.BytesIO(file_content))
                        sheet_found = False
                        
                        for sheet_name in xlsx.sheet_names:
                            _logger.debug("Inspecting sheet: %s", sheet_name)
                            temp_df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
                            
                            # Use existing parsers to score this sheet
                            for ParserClass in PARSERS:
                                p_inst = ParserClass(self)
                                if p_inst.detect(temp_df):
                                    df = temp_df
                                    sheet_found = True
                                    _logger.info("VALID SHEET FOUND: '%s' in %s matched format '%s'", sheet_name, file_name, p_inst.name)
                                    break
                            if sheet_found: break
                        
                        if not sheet_found:
                            _logger.warning("No valid transaction sheet found in %s through deep scan. Falling back to primary sheet.", file_name)
                            df = pd.read_excel(io.BytesIO(file_content), header=None)
                    except Exception as e:
                        _logger.warning("Advanced deep scan failed for %s: %s. Reverting to standard read.", file_name, e)
                        try:
                            df = pd.read_excel(io.BytesIO(file_content), header=None)
                        except Exception as inner_e:
                            _logger.error("Total failure reading Excel %s: %s", file_name, inner_e)
                            try:
                                df = pd.read_csv(io.BytesIO(file_content), header=None)
                            except:
                                error_summary.append(f"{file_name}: Unreadable format.")
                                continue
            except Exception as e:
                _logger.error("Error reading file %s: %s", file_name, e)
                error_summary.append(f"{file_name}: {str(e)}")
                continue

            if df is None: continue

            # Try each parser
            active_parser = None
            header_info = False
            
            # Strategy Selection
            if self.parser_type == 'auto':
                for ParserClass in PARSERS:
                    parser_inst = ParserClass(self)
                    header_info = parser_inst.detect(df)
                    if header_info:
                        active_parser = parser_inst
                        break
            else:
                # Find specific parser
                for ParserClass in PARSERS:
                    parser_inst = ParserClass(self)
                    if parser_inst.code == self.parser_type:
                        active_parser = parser_inst
                        header_info = parser_inst.detect(df) or True # Force header 0 if choice is manual
                        break
                
                # Fallback to Aggressive if manual choice not found in code
                if not active_parser:
                    from .parsers.base_parser import BaseBankParser
                    active_parser = BaseBankParser(self)
                    active_parser.name = "Forced Manual Import"
                    header_info = active_parser.detect(df) or True
            
            if not active_parser:
                msg = _("Could not detect bank format for %s. Ensure it is a standard Bahraini bank statement.") % file_name
                _logger.warning(msg)
                error_summary.append(msg)
                continue
            
            # Create Bank Statement
            statement_vals = {
                'name': f"{active_parser.name}: {file_name}",
                'journal_id': self.journal_id.id,
                'date': fields.Date.today(),
                'bank_batch_id': batch.id,
            }
            statement = self.env['account.bank.statement'].create(statement_vals)
            statement_ids.append(statement.id)
            
            # Parse lines using the detection result, passing session hashes for Cross-File Deduplication
            line_vals, skipped_duplicates, total_found = active_parser.parse_rows(
                df, header_info, self.journal_id.id, mappings, seen_in_batch=session_seen_hashes
            )
            
            if line_vals:
                balance_start, balance_end_real = self._extract_balances(df)
                
                # Convert list of dicts to (0, 0, vals) format for Odoo
                line_ids = [(0, 0, v) for v in line_vals]
                for l in line_ids:
                    l[2]['statement_id'] = statement.id
                
                statement.write({
                    'line_ids': line_ids,
                    'balance_start': balance_start,
                    'balance_end_real': balance_end_real or (balance_start + sum(l[2]['amount'] for l in line_ids))
                })
                
                if self.auto_reconcile:
                    try:
                        statement.action_auto_reconcile()
                    except Exception as e:
                        _logger.warning("Auto-reconcile failed for %s: %s", file_name, e)
            else:
                statement.unlink()
                statement_ids.remove(statement.id)
                msg = f"{file_name}: No new transaction found."
                if total_found > 0:
                    msg += f" ( {total_found} transactions processed, all {skipped_duplicates} were duplicates)"
                else:
                    msg += " (No tabular transaction data detected in file)"
                error_summary.append(msg)

        if not statement_ids:
            batch.unlink()
            err_msg = _("No transactions could be imported.")
            if error_summary:
                err_msg += "\n\n" + "\n".join(error_summary)
            raise UserError(err_msg)
        
        batch.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Batch'),
            'res_model': 'bank.import.batch',
            'view_mode': 'form',
            'res_id': batch.id,
            'target': 'current',
        }


    def _extract_balances(self, df):
        """ Attemps to find Opening and Closing balances from the data """
        balance_start = 0.0
        balance_end_real = 0.0
        
        for idx, row in df.iterrows():
            row_vals = [str(x).lower().strip() for x in row.tolist() if pd.notnull(x)]
            row_str = " ".join(row_vals)
            
            if any(k in row_str for k in ['opening balance', 'balance b/f', 'brought forward', 'previous balance', 'initial balance']):
                for v in row.tolist():
                    val = self._parse_amount(v)
                    if val != 0.0:
                        balance_start = val
                        break
            
            if any(k in row_str for k in ['closing balance', 'carried forward', 'current balance', 'closing bal', 'final balance']):
                for v in row.tolist():
                    val = self._parse_amount(v)
                    if val != 0.0:
                        balance_end_real = val
        
        return balance_start, balance_end_real

    def _parse_amount(self, val):
        if pd.isna(val) or str(val).strip() == '':
            return 0.0
        try:
            val_str = str(val).lower().strip()
            # Shield: Ignore numbers longer than 12 digits (IBANs/Account Numbers)
            clean_digits = "".join(c for c in val_str if c.isdigit())
            if len(clean_digits) > 12:
                return 0.0
            
            # Amount Logic: Default to Credit (+), look for Debit (-) signals
            multiplier = 1.0
            
            # Look for negative indicators (DR, Withdraw, Debit, Out, parentheses)
            negative_indicators = ['-', 'dr', 'out', 'withdraw', 'debit', 'pay']
            positive_indicators = ['+', 'cr', 'in', 'deposit', 'receive']
            
            if any(ind in val_str for ind in negative_indicators):
                multiplier = -1.0
            elif '(' in val_str and ')' in val_str:
                multiplier = -1.0
            
            # Allow positive overrides (CR, etc.)
            if any(ind in val_str for ind in positive_indicators):
                multiplier = 1.0
            
            # Clean non-numeric except dot
            # We also handle comma as thousands separator or decimal
            clean_num = val_str.replace(',', '') # Bahraini usually uses , as thousands
            clean_num = "".join(c for c in clean_num if c.isdigit() or c == '.')
            
            if not clean_num: return 0.0
            
            return float(clean_num) * multiplier
        except:
            return 0.0



    def _parse_pdf(self, file_content):
        """ Parses PDF file content into a pandas DataFrame using pdfplumber with robust strategies """
        try:
            import pdfplumber
        except ImportError:
            raise UserError(_("The 'pdfplumber' library is not installed. Please install it to support PDF imports."))

        all_rows = []
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    # Attempt 1: Default/Lattice strategy (for grids)
                    tables = page.extract_tables()
                    
                    # Attempt 2: Text strategy (for whitespace-aligned data)
                    if not tables or len(tables[0]) < 2:
                        tables = page.extract_tables({
                            "vertical_strategy": "text", 
                            "horizontal_strategy": "text",
                            "snap_tolerance": 4,
                            "join_tolerance": 4,
                        })
                    
                    # Attempt 3: Stream strategy approximation
                    if not tables:
                         tables = page.extract_tables({
                            "vertical_strategy": "text", 
                            "horizontal_strategy": "text",
                             "intersection_tolerance": 5,
                        })

                    for table in tables:
                        if not table: continue
                        for row in table:
                            # Clean each cell
                            cleaned_row = [str(cell).replace('\n', ' ').strip() if cell else '' for cell in row]
                            # Only add if row has some content
                            if any(c and c.strip() for c in cleaned_row):
                                all_rows.append(cleaned_row)
                                 
        except Exception as e:
             _logger.error("Failed to parse PDF: %s", e)
             raise UserError(_("Failed to parse PDF: %s") % str(e))
        
        if not all_rows:
            raise UserError(_("No tabular data could be extracted from this PDF. Ensure it is a text-based PDF, not an image scan."))
            
        _logger.info("Extracted %s rows from PDF", len(all_rows))
        return pd.DataFrame(all_rows)
