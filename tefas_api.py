import requests
import time
import logging
from datetime import datetime, timedelta

class TefasAPI:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.tefas.gov.tr"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.preflight_done = False

    def preflight(self, referer=None):
        url = referer if referer else f"{self.base_url}/tr/fon-verileri"
        try:
            self.session.get(url, headers=self.headers, timeout=15)
            self.preflight_done = True
            time.sleep(2)
        except Exception as e:
            logging.error(f"Preflight failed: {e}")

    def post(self, endpoint, payload, referer=None):
        time.sleep(1.0) # Avoid rate limiting
        if not self.preflight_done:
            self.preflight()
            
        url = f"{self.base_url}/api/funds/{endpoint}"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json; charset=UTF-8"
        headers["Origin"] = self.base_url
        headers["Referer"] = referer if referer else f"{self.base_url}/tr"
            
        for attempt in range(4):
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=25)
                response.raise_for_status()
                data = response.json()
                
                # Check for "Too many requests" message in JSON
                if isinstance(data, dict) and data.get('message') == 'Too many requests':
                     sleep_s = 5 * (attempt + 1)
                     logging.warning(f"TEFAS returned 'Too many requests' (Attempt {attempt+1}). Sleeping {sleep_s}s...")
                     time.sleep(sleep_s)
                     continue
                
                return data
            except Exception as e:
                logging.error(f"POST to {endpoint} failed (Attempt {attempt+1}): {e}")
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                return None
        return None

    def get_fund_info(self, fund_code):
        payload = {"fonKodu": fund_code, "dil": "TR"}
        data = self.post("fonBilgiGetir", payload)
        if data and "resultList" in data and data["resultList"]:
            return data["resultList"][0]
        return None

    def _fetch_fund_history_range(self, fund_code, start_date, end_date):
        import pandas as pd
        payload = {
            "fonTipi": "YAT",
            "fonKodu": fund_code, 
            "dil": "TR", 
            "basTarih": start_date, 
            "bitTarih": end_date,
            "basSira": 1,
            "bitSira": 2000
        }
        data = self.post("fonGnlBlgSiraliGetir", payload)
        if data is None:
            return None
        if data and data.get("resultList") is not None:
            records = []
            for item in data["resultList"]:
                records.append({
                    "Date": item["tarih"],
                    "Price": item["fiyat"],
                    "Investors": item.get("kisiSayisi", 0),
                    "FundSize": item.get("portfoyBuyukluk", 0),
                    "Shares": item.get("tedPaySayisi", 0)
                })
            df = pd.DataFrame(records)
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)
            return df
        return pd.DataFrame()

    def get_fund_history(self, fund_code, period_months=3):
        import pandas as pd

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=period_months * 30)
        total_days = max((end_dt - start_dt).days, 1)

        if total_days <= 30:
            df = self._fetch_fund_history_range(
                fund_code,
                start_dt.strftime("%Y%m%d"),
                end_dt.strftime("%Y%m%d"),
            )
        else:
            parts = []
            cursor = start_dt
            while cursor <= end_dt:
                chunk_end = min(cursor + timedelta(days=29), end_dt)
                part = self._fetch_fund_history_range(
                    fund_code,
                    cursor.strftime("%Y%m%d"),
                    chunk_end.strftime("%Y%m%d"),
                )
                if part is None:
                    logging.error(
                        "Fund history chunk fetch failed for %s (%s -> %s); aborting to avoid partial history.",
                        fund_code,
                        cursor.strftime("%Y%m%d"),
                        chunk_end.strftime("%Y%m%d"),
                    )
                    return pd.DataFrame()
                if not part.empty:
                    parts.append(part)
                cursor = chunk_end + timedelta(days=1)

            df = pd.concat(parts).sort_index() if parts else pd.DataFrame()
            if not df.empty:
                df = df[~df.index.duplicated(keep="last")]

        if not df.empty:
            info = self.get_fund_info(fund_code)
            if info:
                last_idx = df.index[-1]
                df.at[last_idx, "FundSize"] = info.get("portBuyukluk", 0)
                df.at[last_idx, "Investors"] = info.get("yatirimciSayi", 0)
                df.at[last_idx, "Shares"] = info.get("payAdet", 0)

        return df

    def get_fund_details_for_date(self, fund_code, date_str):
        # date_str should be YYYYMMDD
        payload = {
            "fonTipi": "YAT",
            "fonKod": fund_code,
            "dil": "TR",
            "basTarih": date_str,
            "bitTarih": date_str,
            "basSira": 1,
            "bitSira": 1
        }
        referer = f"{self.base_url}/tr/fon-getirileri"
        data = self.post("fonGnlBlgSiraliGetir", payload, referer=referer)
        if data and "resultList" in data and data["resultList"]:
            return data["resultList"][0]
        return None

    def get_fund_size_history(self, fund_code, start_date, end_date):
        # dates should be YYYYMMDD
        payload = {
            "fonTipi": "YAT",
            "fonKod": fund_code,
            "dil": "TR",
            "basTarih": start_date,
            "bitTarih": end_date,
            "calismaTipi": 1
        }
        referer = f"{self.base_url}/tr/fon-getirileri?fundType=YAT&listingTab=size&startDate={start_date}&endDate={end_date}"
        data = self.post("fonBuyuklukBazliBilgiGetir", payload, referer=referer)
        if data and "resultList" in data:
            return data["resultList"]
        return []

    def get_portfolio_distribution(self, fund_code, date_str):
        # date_str should be YYYYMMDD
        payload = {
            "fonTipi": "YAT",
            "fonKod": fund_code,
            "dil": "TR",
            "basTarih": date_str,
            "bitTarih": date_str,
            "basSira": 1,
            "bitSira": 1
        }
        referer = f"{self.base_url}/tr/fon-detayli-analiz/{fund_code}"
        data = self.post("dagilimSiraliGetirT", payload, referer=referer)
        if data and "resultList" in data and data["resultList"]:
            raw = data["resultList"][0]
            # Mapping of TEFAS short codes to names
            mapping = {
                "hs": "Hisse Senedi", "tr": "Ters Repo", "vmtl": "Mevduat (TL)",
                "vint": "VİOP Nakit Teminat", "fb": "Fon Katılma Payları",
                "yyf": "Yatırım Fonları", "r": "Repo", "km": "Kıymetli Madenler",
                "bpp": "Borsa Para Piyasası", "gykb": "Gayrimenkul Katılma Payları",
                "osks": "Özel Sektör Kira Sertifikası", "yhs": "Yabancı Hisse Senedi"
            }
            dist = []
            for k, v in raw.items():
                if k in mapping and v and v != 0:
                    dist.append({"asset_name": mapping[k], "weight": float(v)})
            return dist
        return []

    def get_summary_for_period(self, start_date, end_date):
        # dates should be YYYYMMDD
        payload = {
            "fonTipi": "YAT",
            "dil": "TR",
            "basTarih": start_date,
            "bitTarih": end_date,
            "basSira": 1,
            "bitSira": 3000
        }
        data = self.post("fonGnlBlgSiraliGetir", payload)
        if data and "resultList" in data:
            return data["resultList"]
        return []

    def get_all_funds_details(self, fund_type="YAT"):
        import pandas as pd
        payload = {"fonTipi": fund_type, "dil": "TR"}
        referer = f"{self.base_url}/tr/fon-getirileri?fundType={fund_type}&listingTab=return"
        data = self.post("fonDetayGetir", payload, referer=referer)
        if data and "resultList" in data:
            return pd.DataFrame(data["resultList"])
        return pd.DataFrame()
