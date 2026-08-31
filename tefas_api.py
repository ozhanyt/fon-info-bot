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
        time.sleep(1.2) # Avoid rate limiting
        if not self.preflight_done:
            self.preflight(referer)
            
        url = f"{self.base_url}/api/funds/{endpoint}"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json; charset=UTF-8"
        headers["Origin"] = self.base_url
        headers["Referer"] = referer if referer else f"{self.base_url}/tr"
            
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                response = self.session.post(url, json=payload, headers=headers, timeout=25)
                
                # Handle HTTP 429 Rate Limit
                if response.status_code == 429:
                    sleep_s = min(8 * (attempt + 1), 45)
                    logging.warning(f"TEFAS 429 Rate Limit for {endpoint} (Attempt {attempt+1}/{max_attempts}). Sleeping {sleep_s}s and refreshing session...")
                    time.sleep(sleep_s)
                    self.preflight(referer)
                    continue

                response.raise_for_status()
                data = response.json()
                
                # Check for "Too many requests" message in JSON payload
                if isinstance(data, dict) and data.get('message') == 'Too many requests':
                     sleep_s = min(8 * (attempt + 1), 45)
                     logging.warning(f"TEFAS returned 'Too many requests' JSON for {endpoint} (Attempt {attempt+1}/{max_attempts}). Sleeping {sleep_s}s...")
                     time.sleep(sleep_s)
                     self.preflight(referer)
                     continue
                
                return data
            except Exception as e:
                is_429 = (hasattr(e, 'response') and getattr(e.response, 'status_code', None) == 429) or ("429" in str(e))
                if is_429:
                    sleep_s = min(8 * (attempt + 1), 45)
                    logging.warning(f"POST to {endpoint} hit 429 (Attempt {attempt+1}/{max_attempts}): {e}. Sleeping {sleep_s}s...")
                    time.sleep(sleep_s)
                    self.preflight(referer)
                    if attempt < max_attempts - 1:
                        continue
                    return None

                logging.error(f"POST to {endpoint} failed (Attempt {attempt+1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
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

    def get_fund_history_between(self, fund_code, start_date, end_date):
        import pandas as pd

        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, "%Y%m%d")
        else:
            start_dt = start_date
        if isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, "%Y%m%d")
        else:
            end_dt = end_date
        total_days = max((end_dt - start_dt).days, 1)

        if total_days <= 30:
            df = None
            for single_attempt in range(3):
                df = self._fetch_fund_history_range(
                    fund_code,
                    start_dt.strftime("%Y%m%d"),
                    end_dt.strftime("%Y%m%d"),
                )
                if df is not None:
                    break
                logging.warning(f"Retrying single range fetch for {fund_code} (Attempt {single_attempt + 1}/3)...")
                time.sleep(5.0)
                self.preflight()
            if df is None:
                df = pd.DataFrame()
        else:
            parts = []
            cursor = start_dt
            while cursor <= end_dt:
                chunk_end = min(cursor + timedelta(days=29), end_dt)
                c_start_str = cursor.strftime("%Y%m%d")
                c_end_str = chunk_end.strftime("%Y%m%d")
                part = None
                for chunk_attempt in range(3):
                    part = self._fetch_fund_history_range(
                        fund_code,
                        c_start_str,
                        c_end_str,
                    )
                    if part is not None:
                        break
                    logging.warning(
                        "Retrying chunk fetch for %s (%s -> %s) (Attempt %d/3)...",
                        fund_code,
                        c_start_str,
                        c_end_str,
                        chunk_attempt + 1,
                    )
                    time.sleep(5.0)
                    self.preflight()

                if part is None:
                    logging.error(
                        "Fund history chunk fetch failed for %s (%s -> %s); aborting to avoid partial history.",
                        fund_code,
                        c_start_str,
                        c_end_str,
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

    def get_fund_history(self, fund_code, period_months=3):
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=period_months * 30)
        return self.get_fund_history_between(
            fund_code,
            start_dt.strftime("%Y%m%d"),
            end_dt.strftime("%Y%m%d"),
        )

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
