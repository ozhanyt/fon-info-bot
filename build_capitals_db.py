import json
import os
import requests
from bs4 import BeautifulSoup

KAP_FREE_FLOAT_URL = "https://www.kap.org.tr/tr/tumKalemler/kpy41_acc5_fiili_dolasimdaki_pay"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CAPITALS_FILE = os.path.join(DIRECTORY, "bist_capitals.json")
MANUAL_FILE = os.path.join(DIRECTORY, "manual_capitals.json")

# Fallback free float shares for major companies (in case KAP is offline)
FALLBACK_FREE_FLOATS = {
    "THYAO": 694774856.72,
    "AKSEN": 447487726.0,
    "TEHOL": 1126826117.45,
    "AKBNK": 2704000000.0,
    "ASELS": 1540000000.0,
    "ISCTR": 9400000000.0,
    "GARAN": 630000000.0,
    "YKBNK": 3209879789.0,
    "BIMAS": 364320000.0,
    "SASA": 1330400000.0,
    "TCELL": 1188000000.0,
    "HEDEF": 347232862.0
}

def main():
    capitals = FALLBACK_FREE_FLOATS.copy()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Fetch free float shares from KAP
    print("Fetching free float shares (fiili dolaşımdaki paylar) from KAP...")
    try:
        r = requests.get(KAP_FREE_FLOAT_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                scraped_count = 0
                for row in rows:
                    cols = [c.get_text().strip() for c in row.find_all(["td", "th"])]
                    if len(cols) < 3:
                        continue
                    
                    ticker = cols[1]
                    shares_str = cols[2].replace(".", "").replace(",", ".").strip()
                    
                    if not ticker or len(ticker) < 3 or len(ticker) > 6:
                        continue
                        
                    try:
                        shares = float(shares_str)
                        capitals[ticker] = round(shares, 2)
                        scraped_count += 1
                    except ValueError:
                        pass
                print(f"Successfully scraped {scraped_count} free floats from KAP.")
            else:
                print("Table not found on KAP page.")
        else:
            print(f"KAP request failed with status code {r.status_code}.")
    except Exception as e:
        print(f"Error fetching free floats: {e}")
        
    # 2. Load manual overrides from manual_capitals.json if exists
    if os.path.exists(MANUAL_FILE):
        try:
            with open(MANUAL_FILE, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
            
            applied_count = 0
            for ticker, val in manual_data.items():
                if isinstance(val, dict):
                    # Sum Bireysel and Kurumsal if provided as a dict
                    bireysel = val.get("bireysel", 0.0)
                    kurumsal = val.get("kurumsal", 0.0)
                    total = bireysel + kurumsal
                    if total > 0:
                        capitals[ticker] = total
                        applied_count += 1
                elif isinstance(val, (int, float)):
                    capitals[ticker] = float(val)
                    applied_count += 1
            print(f"Applied {applied_count} manual overrides from manual_capitals.json.")
        except Exception as e:
            print(f"Error reading manual_capitals.json: {e}")
    else:
        # Create empty template for the user
        try:
            template = {
                "HEDEF": {
                    "bireysel": 418997333.0,
                    "kurumsal": 561208189.0
                }
            }
            with open(MANUAL_FILE, "w", encoding="utf-8") as f:
                json.dump(template, f, ensure_ascii=False, indent=4)
            print(f"Created template manual_capitals.json at {MANUAL_FILE}")
            # Also apply it
            capitals["HEDEF"] = 418997333.0 + 561208189.0
        except:
            pass

    # Save to file
    with open(CAPITALS_FILE, "w", encoding="utf-8") as f:
        json.dump(capitals, f, ensure_ascii=False, indent=4)
        
    print(f"Saved {len(capitals)} free floats to {CAPITALS_FILE}")

if __name__ == "__main__":
    main()
