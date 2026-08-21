import os
import sys
import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Add project directory to path for tefas_api import
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIRECTORY)

from tefas_api import TefasAPI

KAP_SHAREHOLDERS_URL = "https://www.kap.org.tr/tr/tumKalemler/kpy41_acc5_sermayede_dogrudan"
KAP_FREE_FLOAT_URL = "https://www.kap.org.tr/tr/tumKalemler/kpy41_acc5_fiili_dolasimdaki_pay"
HISTORY_FILE = os.path.join(DIRECTORY, "kap_shareholders_history.json")

def normalize_tr(s):
    if not s:
        return ""
    s = str(s).strip().upper()
    # Replace Turkish chars with normalized uppercase
    s = s.replace('I', 'I').replace('İ', 'I').replace('Ğ', 'G').replace('Ü', 'U').replace('Ş', 'S').replace('Ö', 'O').replace('Ç', 'C')
    # Remove non-alphanumeric chars for loose matching, but keep spaces
    s = re.sub(r'[^A-Z0-9\s]', '', s)
    # Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def get_bist_ticker_mapping():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    mapping = {}
    print("Fetching BIST company ticker mapping from KAP...")
    try:
        r = requests.get(KAP_FREE_FLOAT_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cols = [c.get_text().strip() for c in row.find_all(["td", "th"])]
                    if len(cols) >= 2:
                        company_name = cols[0].strip()
                        ticker = cols[1].strip()
                        if ticker and len(ticker) >= 3 and len(ticker) <= 6:
                            mapping[normalize_tr(company_name)] = ticker.upper()
                print(f"Loaded {len(mapping)} BIST ticker mappings.")
            else:
                print("Ticker table not found on KAP page.")
        else:
            print(f"Failed to fetch tickers: Status {r.status_code}")
    except Exception as e:
        print(f"Error fetching BIST tickers: {e}")
    return mapping

def get_tefas_fund_mapping():
    tapi = TefasAPI()
    mapping = {}
    print("Fetching fund list from TEFAS...")
    try:
        # Fetch yesterday's summary to get all active funds
        import datetime as dt
        for i in range(1, 10):
            date_str = (dt.date.today() - dt.timedelta(days=i)).strftime("%Y%m%d")
            data = tapi.get_summary_for_period(date_str, date_str)
            if data:
                for item in data:
                    code = item.get("fonKodu")
                    name = item.get("fonUnvan")
                    if code and name:
                        mapping[normalize_tr(name)] = code.upper()
                print(f"Loaded {len(mapping)} active funds from TEFAS summary of {date_str}.")
                break
        else:
            print("Could not fetch fund list from TEFAS.")
    except Exception as e:
        print(f"Error fetching fund mappings: {e}")
    return mapping

def parse_float_tr(val_str):
    if not val_str:
        return 0.0
    try:
        # In Turkish, dot is thousands separator, comma is decimal separator
        clean_str = val_str.replace('.', '').replace(',', '.').strip()
        return float(clean_str)
    except:
        return 0.0

def match_fund_code(shareholder_name, fund_map):
    sh_norm = normalize_tr(shareholder_name)
    if not sh_norm:
        return None
        
    # 1. Exact Match
    if sh_norm in fund_map:
        return fund_map[sh_norm]
        
    # 2. Substring Match or Stripped Match
    sh_stripped = sh_norm.rstrip('UIOOU') # strip trailing Turkish possessive vowels
    for f_name, f_code in fund_map.items():
        f_name_stripped = f_name.rstrip('UIOOU')
        if f_name in sh_norm or sh_norm in f_name:
            return f_code
        if f_name_stripped in sh_stripped or sh_stripped in f_name_stripped:
            return f_code
            
    # 3. Special Keyword Matching (e.g. "TLY" or other codes embedded in parenthesized shareholder name)
    # e.g., "TERA PORTFOY BIRINCI SERBEST FON (TLY)"
    code_match = re.search(r'\b([A-Z]{3})\b', sh_norm)
    if code_match:
        code = code_match.group(1)
        if code in fund_map.values():
            return code
            
    return None

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"--- Starting KAP Shareholder Scraper for {today} ---")
    
    # 1. Load mappings
    ticker_map = get_bist_ticker_mapping()
    fund_map = get_tefas_fund_mapping()
    
    # 2. Load existing history
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            print(f"Loaded existing history with {len(history)} dates.")
        except Exception as e:
            print(f"Error loading history file: {e}")
            
    # Prepare today's node in history, preserving any manual entries
    today_scraped = {}
    today_manual = {}
    
    if today in history:
        for f_code, stocks in history[today].items():
            for s_code, details in stocks.items():
                if details.get("is_manual", False):
                    if f_code not in today_manual:
                        today_manual[f_code] = {}
                    today_manual[f_code][s_code] = details
                    
    # 3. Fetch shareholder table from KAP
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    print("Fetching shareholder table from KAP...")
    try:
        r = requests.get(KAP_SHAREHOLDERS_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if not table:
                print("Shareholders table not found on KAP page.")
                return
                
            rows = table.find_all("tr")
            current_company_name = None
            current_ticker = None
            matched_count = 0
            
            for row in rows[1:]:
                cols = [c.get_text().strip() for c in row.find_all(["td", "th"])]
                if not cols:
                    continue
                    
                shareholder = None
                lot_val = 0.0
                ratio_val = 0.0
                
                if len(cols) == 5:
                    current_company_name = cols[0].strip()
                    current_ticker = ticker_map.get(normalize_tr(current_company_name))
                    shareholder = cols[1].strip()
                    lot_val = parse_float_tr(cols[2])
                    ratio_val = parse_float_tr(cols[3])
                elif len(cols) == 4:
                    if cols[0].strip().lower() == 'total':
                        continue
                    shareholder = cols[0].strip()
                    lot_val = parse_float_tr(cols[1])
                    ratio_val = parse_float_tr(cols[2])
                    
                if shareholder and current_ticker:
                    fund_code = match_fund_code(shareholder, fund_map)
                    if fund_code:
                        if fund_code not in today_scraped:
                            today_scraped[fund_code] = {}
                        today_scraped[fund_code][current_ticker] = {
                            "lot": lot_val,
                            "ratio": ratio_val,
                            "is_manual": False,
                            "shareholder_name": shareholder,
                            "company_name": current_company_name
                        }
                        matched_count += 1
                        
            print(f"Parsed {matched_count} fund holdings from KAP.")
            
            # Combine scraped and manual data
            # Manual data takes priority
            combined_today = today_scraped.copy()
            for f_code, stocks in today_manual.items():
                if f_code not in combined_today:
                    combined_today[f_code] = {}
                for s_code, details in stocks.items():
                    combined_today[f_code][s_code] = details
                    
            # Update history
            history[today] = combined_today
            
            # Save history back to file
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
            print(f"Successfully saved shareholder history to {HISTORY_FILE}")
            
        else:
            print(f"Failed to fetch shareholders: Status {r.status_code}")
    except Exception as e:
        print(f"Error fetching/parsing shareholders: {e}")

if __name__ == "__main__":
    main()
