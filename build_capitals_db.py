import json
import os
import re
import requests
from bs4 import BeautifulSoup

KAP_DIRECT_URL = "https://kap.org.tr/tr/tumKalemler/kpy41_acc5_sermayede_dogrudan"
KAP_BIST_URL = "https://www.kap.org.tr/tr/bist-sirketler"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CAPITALS_FILE = os.path.join(DIRECTORY, "bist_capitals.json")

FALLBACK_CAPITALS = {
    "HEDEF": 980451883.0,
    "DSTKF": 333333333.0,
    "ACSEL": 10721700.0,
    "BAYRK": 250000000.0,
    "BURVA": 7350000.0,
    "CWENE": 1078000000.0,
    "ERBOS": 20000000.0,
    "FZLGY": 1250000000.0,
    "THYAO": 1380000000.0,
    "AKSEN": 1226338000.0,
    "TEHOL": 1995840000.0,
    "AKBNK": 5200000000.0,
    "ASELS": 4560000000.0,
    "ISCTR": 25000000000.0,
    "GARAN": 4200000000.0,
    "YKBNK": 8447051288.0,
    "EREGL": 3500000000.0,
    "KCHOL": 2535898000.0,
    "SAHOL": 2040404000.0,
    "BIMAS": 607200000.0,
    "SASA": 5321600000.0,
    "TUPRS": 1924440000.0,
    "SISE": 3063300000.0,
    "TOASO": 500000000.0,
    "FROTO": 350910000.0,
    "PGSUS": 500000000.0,
    "TCELL": 2200000000.0,
    "HALKB": 7184000000.0,
    "VAKBN": 9915300000.0,
    "DOHOL": 2616938288.0,
    "SOKM": 593290008.0,
    "MGROS": 181054233.0,
    "PETKM": 2534400000.0,
    "HEKTS": 8530000000.0,
}

def clean_text(text):
    if not text:
        return ""
    text = text.upper()
    text = text.replace("İ", "I").replace("Ğ", "G").replace("Ü", "U").replace("Ş", "S").replace("Ö", "O").replace("Ç", "C")
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text

def main():
    capitals = FALLBACK_CAPITALS.copy()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Fetch BIST mapping from KAP
    print("Fetching BIST company tickers from KAP...")
    bist_mapping = {}
    try:
        r = requests.get(KAP_BIST_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cols = [c.get_text().strip() for c in row.find_all(["td", "th"])]
                    if len(cols) >= 2 and len(cols[0]) >= 4 and len(cols[0]) <= 6:
                        ticker = cols[0]
                        unvan = cols[1]
                        bist_mapping[clean_text(unvan)] = ticker
    except Exception as e:
        print(f"Error fetching BIST mapping: {e}")
        
    # 2. Fetch direct shareholdings page
    print("Fetching capitals from KAP direct shareholdings...")
    try:
        r = requests.get(KAP_DIRECT_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                current_company = ""
                for row in rows:
                    cols = [c.get_text().strip() for c in row.find_all(["td", "th"])]
                    if not cols:
                        continue
                        
                    if len(cols) == 5:
                        current_company = cols[0]
                        
                    if cols[0] == 'Total' and len(cols) >= 3:
                        amount_str = cols[1].replace(".", "").replace(",", ".").strip()
                        try:
                            total_shares = float(amount_str)
                            
                            ticker = None
                            comp_clean = clean_text(current_company)
                            for unvan_clean, code in bist_mapping.items():
                                if comp_clean == unvan_clean or unvan_clean in comp_clean or comp_clean in unvan_clean:
                                    ticker = code
                                    break
                                    
                            if ticker and ticker not in FALLBACK_CAPITALS:
                                capitals[ticker] = round(total_shares, 2)
                        except ValueError:
                            pass
    except Exception as e:
        print(f"Error fetching direct shareholdings: {e}")
        
    # Save to file
    with open(CAPITALS_FILE, "w", encoding="utf-8") as f:
        json.dump(capitals, f, ensure_ascii=False, indent=4)
        
    print(f"Saved {len(capitals)} capitals to {CAPITALS_FILE}")

if __name__ == "__main__":
    main()
