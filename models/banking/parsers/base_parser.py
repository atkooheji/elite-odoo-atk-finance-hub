import pandas as pd
import hashlib
import logging
import re
import datetime
from odoo import _

_logger = logging.getLogger(__name__)

class BaseBankParser:
    name = "Aggressive Pattern Parser"
    code = "aggressive"
    
    # Generic keywords - prioritized
    kw_date = ['date', 'value date', 'val date', 'v-date', 'booking date', 'posting date']
    kw_tran_date = ['tran date', 'transaction date', 'txn date', 't-date', 'transaction day']
    kw_desc = ['description', 'particulars', 'narration', 'transaction details', 'details', 'trans particulars', 'remarks', 'particular', 'transaction narrative', 'narrative']
    kw_amount = ['amount', 'net amount', 'tran amount', 'amt', 'value amount', 'transaction value', 'transaction amount', 'total amount']
    kw_debit = ['debit', 'withdrawal', 'out', 'paid out', 'dr amt', 'dr. amount', 'withdrawals', 'dr', 'debits']
    kw_credit = ['credit', 'deposit', 'in', 'paid in', 'cr amt', 'cr. amount', 'deposits', 'cr', 'credits']
    kw_ref = ['reference', 'cheque', 'ref no', 'ref.', 'chq', 'ref code', 'doc no', 'refnum', 'code', 'transaction ref']
    kw_balance = ['balance', 'closing balance', 'cur bal', 'final balance', 'bal', 'stmt balance', 'running balance']

    def __init__(self, wizard):
        self.wizard = wizard

    def detect(self, df):
        """ Scans the dataframe with a weighted scoring system to find the header row """
        # Scan first 300 rows (increased from 100 for deep headers)
        max_scan = min(len(df), 300)
        
        best_row = -1
        best_mapping = {}
        best_score = 0

        for i in range(max_scan):
            row = df.iloc[i]
            row_vals = [str(x).replace('\n', ' ').strip().lower() if pd.notnull(x) else "" for x in row.tolist()]
            
            # Skip mostly empty rows
            if len([v for v in row_vals if v]) < 2:
                continue

            mapping = {}
            score = 0
            
            def find_idx(keywords):
                for idx, val in enumerate(row_vals):
                    if val in keywords: return idx
                    if any(k in val for k in keywords): return idx
                    if any(val == k for k in keywords if len(val) > 2): return idx
                return -1

            d_idx = find_idx(self.kw_date)
            t_idx = find_idx(self.kw_tran_date)
            desc_idx = find_idx(self.kw_desc)
            amt_idx = find_idx(self.kw_amount)
            deb_idx = find_idx(self.kw_debit)
            cre_idx = find_idx(self.kw_credit)
            ref_idx = find_idx(self.kw_ref)
            bal_idx = find_idx(self.kw_balance)

            # Weighting System (Min requirement often Date + Desc + Amount)
            if d_idx != -1: score += 10
            if desc_idx != -1: score += 10
            if amt_idx != -1: score += 10
            elif deb_idx != -1 and cre_idx != -1: score += 10
            
            # Bonus identifiers
            if bal_idx != -1: score += 5
            if ref_idx != -1: score += 3
            if t_idx != -1: score += 2

            # Greedy Fallback: If score is low, check if row looks like a transaction (Date + Number)
            if score < 20:
                has_date, _ = self._extract_date(row_vals[d_idx] if d_idx != -1 else "")
                if not has_date:
                    # Try scanning the whole row for a date
                    for v in row_vals:
                        has_date, _ = self._extract_date(v)
                        if has_date: break
                
                if has_date:
                    # Check for at least one numeric-looking column
                    has_num = False
                    for v in row_vals:
                        if re.search(r'\d+[.,]\d{2,3}', str(v)):
                            has_num = True
                            break
                    if has_num:
                        score += 15  # Massive bonus for data pattern match

            # Threshold: Must have at least Date + Description + (Amount or Balance)
            if score >= 20:
                if score > best_score:
                    mapping['date'] = d_idx if d_idx != -1 else t_idx
                    if mapping['date'] == -1:
                        # Find the first date-looking column
                        for j, v in enumerate(row_vals):
                            if self._extract_date(v)[0]:
                                mapping['date'] = j
                                break
                    
                    if t_idx != -1: mapping['tran_date'] = t_idx
                    mapping['desc'] = desc_idx
                    if amt_idx != -1: mapping['amount'] = amt_idx
                    if deb_idx != -1: mapping['debit'] = deb_idx
                    if cre_idx != -1: mapping['credit'] = cre_idx
                    if ref_idx != -1: mapping['ref'] = ref_idx
                    
                    best_score = score
                    best_row = i
                    best_mapping = mapping
                    
                    # If we have a very high score, stop early
                    if score >= 35: break

        if best_row != -1:
            _logger.info("Detected %s header at row %s with score %s and mapping %s", self.name, best_row, best_score, best_mapping)
            return {'row': best_row, 'mapping': best_mapping}
            
        return False

    def parse_rows(self, df, header_info, journal_id, mappings, seen_in_batch=None):
        """ Parses rows from the detected header downwards """
        data_df = df.iloc[header_info['row'] + 1:]
        col_map = header_info['mapping']
        
        parsed_lines = []
        skipped_duplicates = 0
        current_line = None
        last_date = False

        for idx, row in data_df.iterrows():
            try:
                date_col = row.iloc[col_map['date']] if isinstance(col_map['date'], int) else row[col_map['date']]
                tran_date_col = None
                if 'tran_date' in col_map:
                    tran_date_col = row.iloc[col_map['tran_date']] if isinstance(col_map['tran_date'], int) else row[col_map['tran_date']]
                
                desc_col = row.iloc[col_map['desc']] if isinstance(col_map['desc'], int) else row[col_map['desc']]
                
                # Check for a real date (Value Date)
                is_real_date, date_val = self._extract_date(date_col)
                if is_real_date:
                    last_date = date_val

                # Check for Transaction Date
                is_real_tran_date, tran_date_val = self._extract_date(tran_date_col)
                
                if not is_real_date:
                    date_val = last_date
                
                # Description cleaning
                desc = str(desc_col).strip() if pd.notnull(desc_col) else ""
                
                # Amount parsing
                amount = 0.0
                if 'amount' in col_map:
                    amount_val = row.iloc[col_map['amount']] if isinstance(col_map['amount'], int) else row[col_map['amount']]
                    amount = self._parse_amount(amount_val, desc=desc)
                elif 'debit' in col_map and 'credit' in col_map:
                    deb_val = row.iloc[col_map['debit']] if isinstance(col_map['debit'], int) else row[col_map['debit']]
                    cre_val = row.iloc[col_map['credit']] if isinstance(col_map['credit'], int) else row[col_map['credit']]
                    debit = self._parse_amount(deb_val, desc=desc)
                    credit = self._parse_amount(cre_val, desc=desc)
                    amount = credit - debit
                
                # Logic for multi-line narration (Critical for Fawri/Salam Bank)
                # If No amount AND No date but has description -> Merge with previous
                if amount == 0 and desc and current_line:
                    # Avoid repeating the same text if it appears in multiple columns
                    if desc not in current_line['payment_ref']:
                        current_line['payment_ref'] += " | " + desc
                    continue
                
                # Skip rows with no content
                if amount == 0 and not desc:
                    continue

                # If we have a new transaction
                if amount != 0:
                    if current_line:
                        parsed_lines.append(current_line)
                    
                    # Sticky Date Logic: if no date on row, use previous row's date
                    final_date = date_val or last_date or pd.Timestamp.now().date()
                    
                    ref = ''
                    if 'ref' in col_map:
                        ref_val = row.iloc[col_map['ref']] if isinstance(col_map['ref'], int) else row[col_map['ref']]
                        ref = str(ref_val) if pd.notnull(ref_val) else ''

                    current_line = {
                        'date': final_date,
                        'transaction_date': tran_date_val or final_date,
                        'payment_ref': desc,
                        'ref': ref,
                        'amount': amount,
                    }
            except Exception as e:
                _logger.error("Error parsing row %s: %s", idx, e)
                continue
        
        # Add last line
        if current_line:
            parsed_lines.append(current_line)

        # Partner Matching & Duplicate Detection
        final_lines = []
        if seen_in_batch is None:
            seen_in_batch = set()
        
        for line in parsed_lines:
            partner_id = False
            desc_lower = line['payment_ref'].lower()
            for m in mappings:
                if m['name'].lower() in desc_lower:
                    partner_id = m['partner_id'][0]
                    break
            line['partner_id'] = partner_id

            # Unique ID for Duplicate Detection
            # Unique ID for Duplicate Detection: Include row index (idx) to allow identical transactions in one file
            clean_desc = re.sub(r'\s+', ' ', line['payment_ref']).strip()
            unique_id_base = f"{line['date']}{clean_desc}{line['amount']}{line.get('ref', '')}"
            unique_id = hashlib.md5(f"{unique_id_base}_{idx}".encode()).hexdigest()
            
            if self.wizard.env['account.bank.statement.line'].search_count([('unique_import_id', '=', unique_id), ('journal_id', '=', journal_id)]) > 0:
                skipped_duplicates += 1
                continue
            
            if unique_id in seen_in_batch:
                skipped_duplicates += 1
                continue
            
            seen_in_batch.add(unique_id)
            line['unique_import_id'] = unique_id
            line['journal_id'] = journal_id
            final_lines.append(line)
                
        return final_lines, skipped_duplicates, len(parsed_lines)

    def _extract_date(self, col_val):
        if pd.isnull(col_val) or not str(col_val).strip():
            return False, False
        
        # Handle if pandas already converted it to datetime
        if isinstance(col_val, (pd.Timestamp, datetime.datetime)):
            return True, col_val.date()
            
        date_str = str(col_val).replace('\n', ' ').strip()
        # Supports DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, YYYY/MM/DD, and formats with month names
        if re.search(r'\d{1,4}[/\-\s]\d{1,2}[/\-\s]\d{2,4}', date_str) or \
           re.search(r'\d{1,2}[/\-\s]\w{0,12}[/\-\s]\d{2,4}', date_str) or \
           re.search(r'\d{4}-\d{2}-\d{2}', date_str):
            try:
                # Try standard parsing first
                temp_date = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                if pd.isnull(temp_date):
                    # Try without dayfirst (for YYYY-MM-DD or other formats)
                    temp_date = pd.to_datetime(date_str, errors='coerce')
                
                if pd.notnull(temp_date):
                    return True, temp_date.date()
            except: pass
        return False, False

    def _parse_amount(self, val, desc=""):
        if pd.isna(val) or str(val).strip() == '':
            return 0.0
        try:
            val_str = str(val).lower().strip()
            desc_low = str(desc).lower().strip()
            # Remove commas (thousands separators)
            val_str = val_str.replace(',', '')
            
            # Polarity Logic - Hierarchical Detection
            multiplier = 1.0
            
            # 1. Absolute Positive Priority (Inward/Received/(+))
            if 'inward' in desc_low or 'received' in desc_low or '(+)' in val_str or '+' in val_str:
                multiplier = 1.0
            # 2. Absolute Negative Priority (Payment/Charge/VAT/Commission/(-))
            elif 'payment' in desc_low or 'charge' in desc_low or 'vat amount' in desc_low or \
                 'commission' in desc_low or 'paid' in desc_low or '(-)' in val_str or '-' in val_str:
                multiplier = -1.0
            # 3. Fallback for Explicit Amount Indicators
            elif 'cr' in val_str or 'credit' in val_str:
                multiplier = 1.0
            elif 'dr' in val_str or 'debit' in val_str:
                multiplier = -1.0

            # Clean number string: Keep ONLY dots and digits. 
            # We already calculated the polarity in the 'multiplier', so we don't want signs in the string.
            clean_num = "".join(c for c in val_str if c.isdigit() or c == '.')
            
            if not clean_num or clean_num == '.':
                return 0.0
            
            # If multiple dots, assume last one is decimal
            if clean_num.count('.') > 1:
                parts = clean_num.split('.')
                clean_num = "".join(parts[:-1]) + "." + parts[-1]
                
            return float(clean_num) * multiplier
        except Exception as e:
            _logger.debug("Failed to parse amount '%s': %s", val, e)
            return 0.0


class GenericBankParser(BaseBankParser):
    name = "Generic Bank Statement (AI Enhanced)"
    # Inherits all keywords and the new Scored Detection scoring logic

    def _match_partner(self, label, mappings):
        """ Fuzzy maps row label to Partner using provided keyword mappings """
        if not label: return False
        l_low = label.lower()
        
        # Priority 1: Exact Keyword Match
        for m in mappings:
            if m['name'].lower() in l_low:
                return m['partner_id'][0] # Return the ID
        
        # Priority 2: Pattern Match (e.g. Utility codes)
        if re.search(r'EWA|ELECTRIC|WATER', l_low):
            # Try to find a partner named EWA
            for m in mappings:
                if 'ewa' in m['name'].lower():
                    return m['partner_id'][0]
        
        return False

