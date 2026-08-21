import http.server
import socketserver
import subprocess
import os
import urllib.parse
import json

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class WebServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/api/prices/extension':
            prices_file = os.path.join(DIRECTORY, "fintables_prices.json")
            stored_prices = {}
            if os.path.exists(prices_file):
                try:
                    with open(prices_file, "r", encoding="utf-8") as f:
                        stored_prices = json.load(f)
                except:
                    pass
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "prices": stored_prices}, ensure_ascii=False).encode("utf-8"))
            return

        if self.path.startswith('/api/kap/shareholders/history'):
            import urllib.parse
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            fund_code = params.get('fund', [''])[0].strip().upper()
            stock_code = params.get('stock', [''])[0].strip().upper()
            
            db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
            points = []
            
            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    
                    sorted_dates = sorted(history.keys())
                    for date_str in sorted_dates:
                        funds = history[date_str]
                        if fund_code in funds and stock_code in funds[fund_code]:
                            details = funds[fund_code][stock_code]
                            points.append({
                                "date": date_str,
                                "lot": details.get("lot", 0.0),
                                "ratio": details.get("ratio", 0.0),
                                "is_manual": details.get("is_manual", False)
                            })
                except Exception as e:
                    print(f"Error querying history: {e}")
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "history": points}, ensure_ascii=False).encode("utf-8"))
            return

        if self.path == '/api/kap/shareholders/selectors':
            db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
            selectors = {}
            
            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    
                    for date_str, funds in history.items():
                        for fund_code, stocks in funds.items():
                            if fund_code not in selectors:
                                selectors[fund_code] = set()
                            for stock_code in stocks.keys():
                                selectors[fund_code].add(stock_code)
                                
                    selectors = {f: sorted(list(s)) for f, s in selectors.items()}
                except Exception as e:
                    print(f"Error building selectors: {e}")
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "selectors": selectors}, ensure_ascii=False).encode("utf-8"))
            return

        if self.path == '/api/kap/shareholders/changes':
            db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
            changes = []
            yesterday_date = ""
            today_date = ""
            
            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    
                    sorted_dates = sorted(history.keys())
                    if len(sorted_dates) >= 2:
                        today_date = sorted_dates[-1]
                        yesterday_date = sorted_dates[-2]
                        
                        today_data = history[today_date]
                        yesterday_data = history[yesterday_date]
                        
                        for fund, stocks in today_data.items():
                            for stock, details in stocks.items():
                                today_lot = details.get("lot", 0.0)
                                yesterday_details = yesterday_data.get(fund, {}).get(stock)
                                yesterday_lot = yesterday_details.get("lot", 0.0) if yesterday_details else 0.0
                                
                                diff_lot = today_lot - yesterday_lot
                                if abs(diff_lot) > 0.01:
                                    pct_change = ((diff_lot / yesterday_lot) * 100) if yesterday_lot > 0 else 100.0
                                    changes.append({
                                        "fund": fund,
                                        "stock": stock,
                                        "yesterday_lot": yesterday_lot,
                                        "today_lot": today_lot,
                                        "diff_lot": diff_lot,
                                        "pct_change": pct_change,
                                        "yesterday_ratio": yesterday_details.get("ratio", 0.0) if yesterday_details else 0.0,
                                        "today_ratio": details.get("ratio", 0.0),
                                        "shareholder_name": details.get("shareholder_name", "MANUEL GİRİŞ"),
                                        "company_name": details.get("company_name", "MANUEL GİRİŞ")
                                    })
                                    
                        for fund, stocks in yesterday_data.items():
                            for stock, details in stocks.items():
                                if fund not in today_data or stock not in today_data[fund]:
                                    yesterday_lot = details.get("lot", 0.0)
                                    diff_lot = -yesterday_lot
                                    changes.append({
                                        "fund": fund,
                                        "stock": stock,
                                        "yesterday_lot": yesterday_lot,
                                        "today_lot": 0.0,
                                        "diff_lot": diff_lot,
                                        "pct_change": -100.0,
                                        "yesterday_ratio": details.get("ratio", 0.0),
                                        "today_ratio": 0.0,
                                        "shareholder_name": details.get("shareholder_name", "MANUEL GİRİŞ"),
                                        "company_name": details.get("company_name", "MANUEL GİRİŞ")
                                    })
                except Exception as e:
                    print(f"Error calculating changes: {e}")
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "changes": changes,
                "yesterday": yesterday_date,
                "today": today_date
            }, ensure_ascii=False).encode("utf-8"))
            return

        if self.path.startswith('/api/kap/shareholders/range-changes'):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            fund_filter  = params.get('fund', [None])[0]   # e.g. TLY
            stock_filter = params.get('stock', [None])[0]  # e.g. PASEU
            date_from    = params.get('from',  [None])[0]  # e.g. 2026-08-01
            date_to      = params.get('to',    [None])[0]  # e.g. 2026-08-21
            show_unchanged = params.get('unchanged', ['0'])[0] == '1'
            timeline_mode  = params.get('timeline',  ['0'])[0] == '1'

            db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
            result  = []
            dates_used = []
            available_stocks = []
            available_funds  = []

            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)

                    all_dates = sorted(history.keys())

                    # Collect unique stocks and funds for selectors
                    stocks_set = set()
                    funds_set  = set()
                    for d in all_dates:
                        for fn, stocks in history[d].items():
                            funds_set.add(fn)
                            for st in stocks:
                                stocks_set.add(st)
                    available_stocks = sorted(list(stocks_set))
                    available_funds  = sorted(list(funds_set))

                    # Filter dates by range
                    if date_from:
                        all_dates = [d for d in all_dates if d >= date_from]
                    if date_to:
                        all_dates = [d for d in all_dates if d <= date_to]

                    if len(all_dates) >= 2:
                        start_date = all_dates[0]
                        end_date   = all_dates[-1]
                        dates_used = [start_date, end_date]

                        if timeline_mode:
                            # --- GÜNLÜK HAREKET AKIŞI (TIMELINE) MODU ---
                            for idx in range(len(all_dates) - 1):
                                d_prev = all_dates[idx]
                                d_curr = all_dates[idx + 1]
                                
                                start_data = history[d_prev]
                                end_data   = history[d_curr]

                                if fund_filter:
                                    start_stocks = start_data.get(fund_filter, {})
                                    end_stocks   = end_data.get(fund_filter, {})
                                    all_tickers  = set(list(start_stocks.keys()) + list(end_stocks.keys()))

                                    for ticker in sorted(all_tickers):
                                        s_det = start_stocks.get(ticker)
                                        e_det = end_stocks.get(ticker)
                                        s_lot = s_det.get("lot", 0.0) if s_det else 0.0
                                        e_lot = e_det.get("lot", 0.0) if e_det else 0.0
                                        diff  = e_lot - s_lot

                                        if not show_unchanged and abs(diff) < 0.01:
                                            continue

                                        pct = ((diff / s_lot) * 100) if s_lot > 0 else (100.0 if e_lot > 0 else 0.0)
                                        status = "new" if s_lot == 0 and e_lot > 0 else \
                                                 "exit" if s_lot > 0 and e_lot == 0 else \
                                                 "up" if diff > 0 else \
                                                 "down" if diff < 0 else "same"

                                        result.append({
                                            "date": d_curr,
                                            "fund": fund_filter,
                                            "fund_name": (e_det or s_det or {}).get("shareholder_name", ""),
                                            "stock": ticker,
                                            "company_name": (e_det or s_det or {}).get("company_name", ""),
                                            "start_lot": s_lot,
                                            "end_lot": e_lot,
                                            "diff_lot": diff,
                                            "pct_change": round(pct, 2),
                                            "start_ratio": (s_det or {}).get("ratio", 0.0),
                                            "end_ratio": (e_det or {}).get("ratio", 0.0),
                                            "status": status
                                        })

                                elif stock_filter:
                                    # Gather all funds that ever touched this stock in these two days
                                    all_funds_for_stock = set()
                                    for fn, stocks in start_data.items():
                                        if stock_filter in stocks:
                                            all_funds_for_stock.add(fn)
                                    for fn, stocks in end_data.items():
                                        if stock_filter in stocks:
                                            all_funds_for_stock.add(fn)

                                    for fn in sorted(all_funds_for_stock):
                                        s_det = start_data.get(fn, {}).get(stock_filter)
                                        e_det = end_data.get(fn, {}).get(stock_filter)
                                        s_lot = s_det.get("lot", 0.0) if s_det else 0.0
                                        e_lot = e_det.get("lot", 0.0) if e_det else 0.0
                                        diff  = e_lot - s_lot

                                        if not show_unchanged and abs(diff) < 0.01:
                                            continue

                                        pct = ((diff / s_lot) * 100) if s_lot > 0 else (100.0 if e_lot > 0 else 0.0)
                                        status = "new" if s_lot == 0 and e_lot > 0 else \
                                                 "exit" if s_lot > 0 and e_lot == 0 else \
                                                 "up" if diff > 0 else \
                                                 "down" if diff < 0 else "same"

                                        result.append({
                                            "date": d_curr,
                                            "fund": fn,
                                            "fund_name": (e_det or s_det or {}).get("shareholder_name", ""),
                                            "stock": stock_filter,
                                            "company_name": (e_det or s_det or {}).get("company_name", ""),
                                            "start_lot": s_lot,
                                            "end_lot": e_lot,
                                            "diff_lot": diff,
                                            "pct_change": round(pct, 2),
                                            "start_ratio": (s_det or {}).get("ratio", 0.0),
                                            "end_ratio": (e_det or {}).get("ratio", 0.0),
                                            "status": status
                                        })
                        else:
                            # --- NET FARK (AÇILIŞ VS KAPANIŞ) MODU ---
                            start_data = history[start_date]
                            end_data   = history[end_date]

                            if fund_filter:
                                start_stocks = start_data.get(fund_filter, {})
                                end_stocks   = end_data.get(fund_filter, {})
                                all_tickers  = set(list(start_stocks.keys()) + list(end_stocks.keys()))

                                for ticker in sorted(all_tickers):
                                    s_det = start_stocks.get(ticker)
                                    e_det = end_stocks.get(ticker)
                                    s_lot = s_det.get("lot", 0.0) if s_det else 0.0
                                    e_lot = e_det.get("lot", 0.0) if e_det else 0.0
                                    diff  = e_lot - s_lot

                                    if not show_unchanged and abs(diff) < 0.01:
                                        continue

                                    pct = ((diff / s_lot) * 100) if s_lot > 0 else (100.0 if e_lot > 0 else 0.0)
                                    status = "new" if s_lot == 0 and e_lot > 0 else \
                                             "exit" if s_lot > 0 and e_lot == 0 else \
                                             "up" if diff > 0 else \
                                             "down" if diff < 0 else "same"

                                    result.append({
                                        "fund": fund_filter,
                                        "fund_name": (e_det or s_det or {}).get("shareholder_name", ""),
                                        "stock": ticker,
                                        "company_name": (e_det or s_det or {}).get("company_name", ""),
                                        "start_lot": s_lot,
                                        "end_lot": e_lot,
                                        "diff_lot": diff,
                                        "pct_change": round(pct, 2),
                                        "start_ratio": (s_det or {}).get("ratio", 0.0),
                                        "end_ratio": (e_det or {}).get("ratio", 0.0),
                                        "status": status
                                    })

                            elif stock_filter:
                                all_funds_for_stock = set()
                                for d in [start_date, end_date]:
                                    for fn, stocks in history[d].items():
                                        if stock_filter in stocks:
                                            all_funds_for_stock.add(fn)

                                for fn in sorted(all_funds_for_stock):
                                    s_det = start_data.get(fn, {}).get(stock_filter)
                                    e_det = end_data.get(fn, {}).get(stock_filter)
                                    s_lot = s_det.get("lot", 0.0) if s_det else 0.0
                                    e_lot = e_det.get("lot", 0.0) if e_det else 0.0
                                    diff  = e_lot - s_lot

                                    if not show_unchanged and abs(diff) < 0.01:
                                        continue

                                    pct = ((diff / s_lot) * 100) if s_lot > 0 else (100.0 if e_lot > 0 else 0.0)
                                    status = "new" if s_lot == 0 and e_lot > 0 else \
                                             "exit" if s_lot > 0 and e_lot == 0 else \
                                             "up" if diff > 0 else \
                                             "down" if diff < 0 else "same"

                                    result.append({
                                        "fund": fn,
                                        "fund_name": (e_det or s_det or {}).get("shareholder_name", ""),
                                        "stock": stock_filter,
                                        "company_name": (e_det or s_det or {}).get("company_name", ""),
                                        "start_lot": s_lot,
                                        "end_lot": e_lot,
                                        "diff_lot": diff,
                                        "pct_change": round(pct, 2),
                                        "start_ratio": (s_det or {}).get("ratio", 0.0),
                                        "end_ratio": (e_det or {}).get("ratio", 0.0),
                                        "status": status
                                    })

                    elif len(all_dates) == 1:
                        dates_used = [all_dates[0], all_dates[0]]

                except Exception as e:
                    print(f"Error calculating range changes: {e}")

            # Sort results
            if timeline_mode:
                # Timeline: Sort by date descending (newest first)
                result.sort(key=lambda x: x.get("date", ""), reverse=True)
            else:
                # Net: Exits first, then by absolute lot difference descending
                status_order = {"exit": 0, "new": 1, "up": 2, "down": 3, "same": 4}
                result.sort(key=lambda x: (status_order.get(x["status"], 9), -abs(x["diff_lot"])))

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "results": result,
                "dates": dates_used,
                "available_stocks": available_stocks,
                "available_funds": available_funds
            }, ensure_ascii=False).encode("utf-8"))
            return


        # ── /tweet  →  generate tweet text from current data.json ──────────
        if self.path == '/tweet':
            try:
                import sys
                sys.path.insert(0, DIRECTORY)
                import importlib
                import twitter_bot
                importlib.reload(twitter_bot)   # pick up any edits

                data_path   = os.path.join(DIRECTORY, "data.json")
                config_path = os.path.join(DIRECTORY, "runtime_config.json")

                with open(data_path,   "r", encoding="utf-8") as f: data   = json.load(f)
                with open(config_path, "r", encoding="utf-8") as f: config = json.load(f)

                sections   = config.get("sections", ["inflows", "outflows"])
                tweet_text = twitter_bot.generate_tweet_text(data, sections, config)

                payload = json.dumps({"tweet_text": tweet_text, "char_count": len(tweet_text)}, ensure_ascii=False)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        if self.path == '/filled_index':

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline' https: data:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https:;")
            self.end_headers()
            path = os.path.join(DIRECTORY, "template", "filled_index.html")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"HTML not generated yet.")
            return

        # Serve an index page if requesting root
        if self.path == '/':
            CONFIG_FILE = os.path.join(DIRECTORY, "dashboard_config.json")
            db_config = {}
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        db_config = json.load(f)
                except: pass
            
            def_canvas_width = db_config.get("canvas_width", 1600)
            def_item_font_size = db_config.get("item_font_size", 25)
            def_period_font_size = db_config.get("period_font_size", 25)
            def_tcode_font_size = db_config.get("tcode_font_size", 38)
            def_tracked_funds = db_config.get("tracked_funds", "TLY, DFI, PHE")
            def_bg_url = db_config.get("bg_url", "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&q=80&w=1964")
            def_main_title = db_config.get("main_title", "GÜNLÜK TEFAS ÖZETİ")
            def_sub_title = db_config.get("subtitle", "Paranın Yönü Nereye?")
            def_grid_cols = db_config.get("grid_cols", 2)
            def_tracked_grid_cols = db_config.get("tracked_grid_cols", 1)
            def_wm_anchor = db_config.get("watermark_anchor", "bottom")
            def_sort_mode = db_config.get("sort_mode", "tl")
            def_pred_title = db_config.get("pred_title", "Getiri Tahmini")
            def_port_cols = db_config.get("portfolio_diff_cols", 1)
            def_custom_start_date = db_config.get("custom_start_date", "")
            def_custom_end_date = db_config.get("custom_end_date", "")
            
            # Position defaults
            def_pos = db_config.get("positions", {})
            # Start with empty sections by default as requested
            def_sections = db_config.get("sections", [])
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline' https: data:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https:;")
            self.end_headers()
            
            html = r"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>TEFAS İnfografik Üretici</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #121214; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; min-height: 100vh; margin: 0; padding: 60px 20px; }
                    .card { background: #1c1c1e; padding: 50px; border-radius: 30px; text-align: left; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 20px 60px rgba(0,0,0,0.6); width: 1450px; max-width: 98%; }
                    h1 { margin-top: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.5px; text-align: center; width: 100%; margin-bottom: 8px; }
                    .subtitle-p { color: #8e8e93; font-size: 17px; margin-bottom: 45px; text-align: center; width: 100%; }
                    
                    .dashboard-grid-generator { display: grid; grid-template-columns: 1.1fr 1fr; gap: 40px; }
                    .dashboard-grid-calculator { display: grid; grid-template-columns: 1.2fr 1fr; gap: 40px; }
                    .tab-header { display: flex; gap: 12px; margin-bottom: 35px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 15px; width: 100%; }
                    .tab-btn { background: none; border: none; color: #8e8e93; font-size: 16px; font-weight: 700; padding: 10px 20px; cursor: pointer; border-radius: 12px; transition: all 0.2s; }
                    .tab-btn.active { background: #0a84ff !important; color: #fff !important; }
                    .tab-btn:hover:not(.active) { color: #fff; background: rgba(255,255,255,0.05); }
                    .tab-content.hidden { display: none !important; }
                    .section-title { font-size: 13px; color: #8e8e93; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 18px; display: block; }
                    .input-group { margin-bottom: 25px; }
                    label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #8e8e93; }
                    input, select, textarea { width: 100%; background: #000; border: 1px solid #1c1c1e; border-radius: 12px; padding: 14px 18px; color: #fff; font-size: 16px; box-sizing: border-box; transition: all 0.2s; outline: none; }
                    input:focus { border-color: #0a84ff; }
                    
                    /* Grid inputs */
                    .pos-grid-container { display: flex; flex-direction: column; gap: 12px; background: #000; padding: 20px; border-radius: 18px; }
                    .pos-row { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 15px; align-items: center; }
                    .pos-label { font-size: 14px; color: #fff; }
                    .pos-input { padding: 10px; text-align: center; font-weight: 700; }
                    
                    /* Categorized filters */
                    .cat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; background: #000; padding: 20px; border-radius: 18px; }
                    .cat-item { display: flex; align-items: center; gap: 10px; font-size: 14px; color: #fff; }
                    .cat-item input { width: auto; margin: 0; }
                    
                    /* Predictions area */
                    .pred-section { margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 30px; }
                    .pred-table { display: flex; flex-direction: column; gap: 10px; }
                    .pred-header { display: grid; grid-template-columns: 1fr 1.2fr 2fr; gap: 10px; font-size: 12px; color: #8e8e93; font-weight: 700; padding-bottom: 5px; }
                    .pred-row { display: grid; grid-template-columns: 1fr 1.2fr 2fr 40px; gap: 10px; align-items: center; }
                    .pred-row input { padding: 10px 14px; font-size: 14px; }
                    .remove-btn { background: #ff453a; color: #fff; border: none; width: 30px; height: 30px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: 700; opacity: 0.6; }
                    .remove-btn:hover { opacity: 1; }
                    .add-btn { background: #0a84ff; color: #fff; border: none; padding: 10px 15px; border-radius: 10px; font-size: 13px; font-weight: 700; cursor: pointer; margin-top: 10px; }
                    
                    /* Action buttons */
                    .button-group { display: flex; flex-direction: row; gap: 18px; margin-top: 50px; justify-content: center; width: 100%; }
                    .action-btn { background: #333; color: #fff; border: none; padding: 18px 30px; border-radius: 18px; font-size: 18px; font-weight: 700; cursor: pointer; transition: all 0.2s; min-width: 250px; display: flex; align-items: center; gap: 12px; justify-content: center; }
                    .action-btn:hover { background: #444; transform: translateY(-3px); }
                    .action-btn:active { transform: translateY(0); }
                    .action-btn.green { background: #32d74b; color: #fff; }
                    .action-btn.green:hover { background: #28cd41; }
                    
                    .loader { border: 3px solid rgba(255,255,255,0.1); border-top: 3px solid white; border-radius: 50%; width: 20px; height: 20px; animation: spin 0.8s linear infinite; display: none; }
                    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                    
                    .status-msg { margin-top: 30px; text-align: center; min-height: 24px; font-size: 15px; font-weight: 500; }
                    .hidden { display: none; }
                    hr { border: 0; border-top: 1px solid rgba(255,255,255,0.05); margin: 30px 0; }
                    
                    /* Download link style */
                    .result-link { display: none; margin-top: 20px; color: #0a84ff; text-decoration: none; font-weight: 600; font-size: 16px; border: 2px solid #0a84ff; padding: 12px 24px; border-radius: 12px; transition: all 0.2s; }
                    .result-link:hover { background: #0a84ff; color: #fff; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>TEFAS İnfografik Üretici</h1>
                    <p class="subtitle-p">Profesyonel veri görselleştirme paneli.</p>

                    <!-- Tab Buttons -->
                    <div class="tab-header">
                        <button class="tab-btn active" onclick="switchTab('tab-generator')">📊 İnfografik Üretici</button>
                        <button class="tab-btn" onclick="switchTab('tab-calculator')">🧮 Getiri Hesaplayıcı</button>
                        <button class="tab-btn" onclick="switchTab('tab-kap')">📈 KAP Ortaklık Takibi</button>
                    </div>

                    <!-- Tab 1: İnfografik Üretici -->
                    <div id="tab-generator" class="tab-content">
                        <div class="dashboard-grid-generator">
                        <!-- Column 1 -->
                        <div class="dash-column">
                            <span class="section-title">TEMEL BİLGİLER</span>
                            
                            <div class="input-group">
                                <label for="trackedFunds">Takipteki Fon Kodları:</label>
                                <input type="text" id="trackedFunds" value="{{TRACKED_FUNDS}}" placeholder="TLY, DFI, PHE">
                            </div>
                            
                            <div class="input-group">
                                <label for="bgUrl">Arka Plan Resmi URL:</label>
                                <input type="text" id="bgUrl" value="{{BG_URL}}" placeholder="URL linkini buraya yapıştırın...">
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="input-group">
                                    <label for="customStartDate">Başlangıç Tarihi (Opsiyonel):</label>
                                    <input type="date" id="customStartDate" value="{{CUSTOM_START_DATE}}">
                                </div>
                                <div class="input-group">
                                    <label for="customEndDate">Bitiş Tarihi (Opsiyonel):</label>
                                    <input type="date" id="customEndDate" value="{{CUSTOM_END_DATE}}">
                                </div>
                            </div>

                            <div class="input-group">
                                <label><input type="checkbox" id="headerShowMain" checked style="width:auto; margin-right:8px;"> Ana Başlık:</label>
                                <input type="text" id="mainTitle" value="{{MAIN_TITLE}}" placeholder="GÜNLÜK TEFAS ÖZETİ">
                            </div>

                            <div class="input-group">
                                <label><input type="checkbox" id="headerShowSub" checked style="width:auto; margin-right:8px;"> Alt Başlık:</label>
                                <input type="text" id="subtitle" value="{{SUB_TITLE}}" placeholder="Paranın Yönü Nereye?">
                            </div>

                            <span class="section-title" style="margin-top:20px;">YERLEŞİM VE SIRALAMA</span>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="input-group">
                                    <label for="gridCols">Ana Sütun:</label>
                                    <input type="number" id="gridCols" value="{{GRID_COLS}}" min="1" max="4">
                                </div>
                                <div class="input-group">
                                    <label for="sortMode">Sıralama Modu:</label>
                                    <select id="sortMode">
                                        <option value="tl" {{SEL_SORT_TL}}>Birim Bazlı (₺)</option>
                                        <option value="pct" {{SEL_SORT_PCT}}>Getiri Bazlı (%)</option>
                                    </select>
                                </div>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="input-group">
                                    <label for="canvasWidth">Tuval Genişliği (px):</label>
                                    <input type="number" id="canvasWidth" value="{{CANVAS_WIDTH}}" step="100">
                                </div>
                                <div class="input-group">
                                    <label for="trackedGridCols">Takip Izgarası:</label>
                                    <input type="number" id="trackedGridCols" value="{{TRACKED_GRID_COLS}}" min="1" max="4">
                                </div>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="input-group">
                                    <label for="itemFontSize">Liste Font (px):</label>
                                    <input type="number" id="itemFontSize" value="{{ITEM_FONT_SIZE}}">
                                </div>
                                <div class="input-group">
                                    <label for="periodFontSize">Etiket Font (px):</label>
                                    <input type="number" id="periodFontSize" value="{{PERIOD_FONT_SIZE}}">
                                </div>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div class="input-group">
                                    <label for="tcodeFontSize">Takip Kodu Font (px):</label>
                                    <input type="number" id="tcodeFontSize" value="{{TCODE_FONT_SIZE}}">
                                </div>
                                <div class="input-group" style="display:flex; align-items:center; gap:10px; padding-top:28px;">
                                </div>
                            </div>

                            <div class="input-group">
                                <label for="watermarkAnchor">Filigran Konumu:</label>
                                <select id="watermarkAnchor">
                                    <option value="bottom" {{SEL_WM_BOTTOM}}>En Alt Orta</option>
                                    <option value="inflows" {{SEL_WM_INFLOWS}}>Para Girişi Altı</option>
                                    <option value="outflows" {{SEL_WM_OUTFLOWS}}>Para Çıkışı Altı</option>
                                </select>
                            </div>
                        </div>

                        <!-- Column 2 -->
                        <div class="dash-column">
                            <span class="section-title">BÖLÜM KONUMLARI (SATIR, SÜTUN)</span>
                            
                            <div class="pos-grid-container">
                                <!-- Multi-position rows -->
                                {{POS_ROWS_HTML}}
                            </div>

                            <span class="section-title" style="margin-top:35px;">LİDERLER KATEGORİ FİLTRESİ</span>
                            <div class="cat-grid" id="categoryFilters">
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Hisse Senedi" checked> Hisse</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Değişken" checked> Değişken</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Karma" checked> Karma</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Fon Sepeti" checked> Fon Sepeti</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Borçlanma Araçları" checked> Borçlanma</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="K.Maden" checked> K.Maden</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Katılım" checked> Katılım</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Para Piy."> Para Piy.</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Serbest (Genel)" checked> Serbest (Genel)</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Serbest (P.Piy)"> Serbest (P.Piy)</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Serbest (Döviz)"> Serbest (Döviz)</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Serbest (K.Vade)"> Serbest (K.Vade)</label></div>
                                <div class="cat-item"><label><input type="checkbox" class="cat-chk" value="Serbest (Katılım)"> Serbest (Katılım)</label></div>
                            </div>
                        </div>
                        </div> <!-- Closes dashboard-grid-generator -->

                    <div class="pred-section">
                        <span class="section-title">GETİRİ TAHMİNLERİ</span>
                        <div class="input-group" style="margin-bottom:15px;">
                            <label for="predTitle">Bölüm Başlığı:</label>
                            <input type="text" id="predTitle" value="{{PRED_SECTION_TITLE}}" placeholder="Örn: Getiri Tahmini / Gün Ortası Tahmini">
                        </div>
                        <div id="predRowsContainer" class="pred-table">
                            <div class="pred-header">
                                <span>FON KODU</span>
                                <span>GETİRİ (%)</span>
                                <span>AÇIKLAMA (OPSİYONEL)</span>
                            </div>
                            {{PRED_ROWS}}
                        </div>
                        <button class="add-btn" onclick="addPredictionRow()">+ Satır Ekle</button>
                        <button class="add-btn" onclick="fetchPredictionsFromTracker()" style="background:#5AC8FA; color:#000; margin-left: 10px;">🔮 Tahminleri Getir</button>
                        <span id="predFetchStatus" style="font-size:13px; color:#8e8e93; margin-left:10px;"></span>
                        
                        <div style="margin-top:20px;">
                            <label>Tahmin Bölümü Sütun Sayısı</label>
                            <select id="predCols">
                                <option value="1" {{SEL_PRED_COL_1}}>1 Sütun (Dikey)</option>
                                <option value="2" {{SEL_PRED_COL_2}}>2 Sütun (Yan Yana)</option>
                            </select>
                        </div>
                    </div>

                    <!-- Fon İçi Etki Analizi paneli -->
                    <div class="pred-section" style="margin-top:30px; border-top:1px solid rgba(255,255,255,0.05); padding-top:30px;">
                        <span class="section-title">FON İÇİ ETKİ ANALİZİ</span>
                        <p style="color:#8e8e93; font-size:13px; margin-bottom:18px;">fon-portfoy-tracker (localhost:3032) üzerinden veri çeker. <b>holdings_breakdown</b> bölümünü açık tutun.</p>
                        <div style="display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;">
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                <label style="font-size:12px; color:#8e8e93; font-weight:700;">FON KODU</label>
                                <input type="text" id="holdingsFundCode" value="TLY" placeholder="TLY" style="width:90px; padding:10px 12px; font-size:15px; font-weight:800; text-transform:uppercase; background:#000; border:1px solid #333; border-radius:10px; color:#fff; text-align:center;">
                            </div>
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                <label style="font-size:12px; color:#8e8e93; font-weight:700;">FON TOPLAM DEĞERİ (₺, opsiyonel)</label>
                                <input type="text" id="holdingsFonToplam" value="" placeholder="220.000.000.000" style="width:200px; padding:10px 12px; font-size:14px; background:#000; border:1px solid #333; border-radius:10px; color:#fff;">
                            </div>
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                <label style="font-size:12px; color:#8e8e93; font-weight:700;">TOP N</label>
                                <input type="number" id="holdingsTopN" value="5" min="1" max="10" style="width:70px; padding:10px; font-size:14px; background:#000; border:1px solid #333; border-radius:10px; color:#fff; text-align:center;">
                            </div>
                            <button onclick="fetchHoldings()" style="background:#5AC8FA; color:#000; border:none; padding:12px 22px; border-radius:12px; font-size:14px; font-weight:800; cursor:pointer; letter-spacing:0.3px;">📊 Portföy Verisi Çek</button>
                            <span id="holdingsStatus" style="font-size:13px; color:#8e8e93;"></span>
                        </div>
                    </div>



                    <div class="status-msg" id="status"></div>
                    <center>
                        <a id="resultLink" href="/infographic.png" target="_blank" class="result-link">Görseli Yeni Sekmede Aç</a>
                    </center>

                    <div class="button-group">
                        <button id="btn-preds" class="action-btn green" onclick="generate('predictions')">
                            <div class="loader"></div>
                            <span class="btn-text">Tahmin Paylaş</span>
                        </button>
                        <button id="btn-daily" class="action-btn" onclick="generate('daily')">
                            <div class="loader"></div>
                            <span class="btn-text">Günlük İnfografik</span>
                        </button>
                        <button id="btn-weekly" class="action-btn" onclick="generate('weekly')">
                            <div class="loader"></div>
                            <span class="btn-text">Haftalık İnfografik</span>
                        </button>
                        <button id="btn-monthly" class="action-btn" onclick="generate('monthly')">
                            <div class="loader"></div>
                            <span class="btn-text">Aylık İnfografik</span>
                        </button>
                    </div> <!-- Closes button-group -->
                </div> <!-- Closes tab-generator -->

                    <!-- Tab 2: Getiri Hesaplayıcı -->
                    <div id="tab-calculator" class="tab-content hidden">
                        <div class="dashboard-grid-calculator">
                            <!-- Left panel: Calculator table -->
                            <div class="dash-column">
                                <span class="section-title">FON GETİRİ HESAPLAYICI</span>
                                <p style="color:#8e8e93; font-size:13px; margin-bottom:20px;">Önceki günün fiyatını manuel girebilir, güncel fiyatı ise Fintables eklentisi yardımıyla çekebilirsiniz.</p>
                                
                                <div class="pred-table" id="calcRowsContainer" style="margin-bottom: 20px;">
                                    <div class="pred-header" style="grid-template-columns: 1fr 1.2fr 1.2fr 1.2fr 40px; gap: 10px;">
                                        <span>FON KODU</span>
                                        <span>ÖNCEKİ FİYAT</span>
                                        <span>GÜNCEL FİYAT</span>
                                        <span>GETİRİ</span>
                                        <span></span>
                                    </div>
                                    <!-- Rows will load automatically -->
                                </div>
                                
                                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                                    <button class="add-btn" onclick="addCalculatorRow()">+ Ekle</button>
                                    <button class="add-btn" onclick="transferCurrentToPrevious()" style="background:#ff9f0a; color:#fff;">📋 Aktar</button>
                                    <button class="add-btn" onclick="calculateReturns()" style="background:#32d74b; color:#fff;">🧮 Hesapla</button>
                                </div>
                            </div>

                            <!-- Right panel: Share settings -->
                            <div class="dash-column" style="border-left: 1px solid rgba(255,255,255,0.05); padding-left: 30px;">
                                <span class="section-title">PAYLAŞIM AYARLARI</span>
                                <div class="input-group">
                                    <label for="quoteTweetUrl">Alıntı Linki:</label>
                                    <input type="text" id="quoteTweetUrl" placeholder="https://x.com/..." oninput="saveQuoteTweetState()">
                                </div>
                                <div class="input-group">
                                    <label for="calcSource">Veri Kaynağı:</label>
                                    <input type="text" id="calcSource" placeholder="@fintables" value="@fintables" oninput="saveQuoteTweetState()">
                                </div>
                                <div class="input-group">
                                    <label for="calcDate">Getiri Tarihi:</label>
                                    <input type="date" id="calcDate" oninput="saveQuoteTweetState()">
                                </div>
                                
                                <button class="add-btn" onclick="shareCalculatorReturnsOnX()" style="background:#1d9bf0; color:#fff; width: 100%; margin-top: 15px; font-size: 15px; font-weight: 800; display: flex; align-items: center; justify-content: center; gap: 8px; height: 44px; border-radius: 12px; cursor: pointer;">
                                    <svg width="16" height="16" viewBox="0 0 1200 1227" fill="white"><path d="M714.163 519.284L1160.89 0H1055.03L667.137 450.887L357.328 0H0L468.492 681.821L0 1226.37H105.866L515.491 750.218L842.672 1226.37H1200L714.137 519.284H714.163Z"/></svg>
                                    𝕏 Getiri Paylaş
                                </button>
                                <span id="calcStatus" style="font-size:13px; color:#8e8e93; display:block; margin-top:15px; font-weight:600;"></span>
                            </div>
                        </div>
                    </div>

                    <!-- Tab 3: KAP Ortaklık Takibi -->
                    <div id="tab-kap" class="tab-content hidden">
                        <div class="pred-section" style="margin-top: 0; padding-top: 0; border: none;">
                            <span class="section-title" style="color: #ff9f0a; font-size: 16px; margin-bottom: 8px;">📈 KAP BÜYÜK ORTAKLAR TAKİBİ (%5 VE ÜZERİ)</span>
                            <p style="color:#8e8e93; font-size:13px; margin-bottom:25px; margin-top:0;">Fonların şirketlerdeki pay değişimlerini interaktif grafik ve manuel lot kayıtlarıyla takip edin.</p>
                            
                            <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 30px; margin-bottom: 30px;">
                                <!-- Left panel: Chart and selectors -->
                                <div style="background: rgba(255,255,255,0.02); padding: 25px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.05); display: flex; flex-direction: column; min-width: 0;">
                                    <span style="font-size: 14px; font-weight: 700; color: #fff; display: block; margin-bottom: 18px;">📊 Tarihsel Değişim Grafiği</span>
                                    <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                                        <div style="display: flex; flex-direction: column; gap: 5px; flex: 1;">
                                            <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">TAKİPTEKİ FON</label>
                                            <select id="kapSelectorFund" onchange="onKapFundChanged()" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:10px; font-weight:800;"></select>
                                        </div>
                                        <div style="display: flex; flex-direction: column; gap: 5px; flex: 1;">
                                            <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">BÜYÜK ORTAK OLDUĞU HİSSE</label>
                                            <select id="kapSelectorStock" onchange="loadKapShareholderHistoryChart()" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:10px; font-weight:800;"></select>
                                        </div>
                                    </div>
                                    <div style="position: relative; height: 260px; width: 100%; background: #000; border-radius: 12px; padding: 15px; border: 1px solid #1c1c1e;">
                                        <canvas id="kapHistoryChart"></canvas>
                                    </div>
                                </div>
                                
                                <!-- Right panel: Manual input entry -->
                                <div style="background: rgba(255,255,255,0.02); padding: 25px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.05); display: flex; flex-direction: column; justify-content: space-between; min-width: 0;">
                                    <div>
                                        <span style="font-size: 14px; font-weight: 700; color: #fff; display: block; margin-bottom: 18px;">✍️ Manuel Lot/Pay Ekleme</span>
                                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                                <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">TARİH</label>
                                                <input type="date" id="kapManualDate" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px; font-size:13px;">
                                            </div>
                                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                                <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">FON KODU</label>
                                                <input type="text" id="kapManualFund" placeholder="Örn: TLY" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px; font-weight:800; text-transform:uppercase; text-align:center;">
                                            </div>
                                        </div>
                                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                                <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">HİSSE KODU</label>
                                                <input type="text" id="kapManualStock" placeholder="Örn: TERA" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px; font-weight:800; text-transform:uppercase; text-align:center;">
                                            </div>
                                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                                <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">LOT ADEDİ</label>
                                                <input type="number" id="kapManualLot" placeholder="10093782" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px;">
                                            </div>
                                            <div style="display: flex; flex-direction: column; gap: 5px;">
                                                <label style="font-size: 11px; color: #8e8e93; font-weight: 700;">PAY ORANI (%)</label>
                                                <input type="number" step="any" id="kapManualRatio" placeholder="9.01" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px;">
                                            </div>
                                        </div>
                                    </div>
                                    <button onclick="saveKapManualEntry()" style="background:#ff9f0a; color:#fff; border:none; padding:14px; border-radius:12px; font-size: 14px; font-weight: 800; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;">💾 Manuel Veri Kaydet</button>
                                    <span id="kapManualStatus" style="font-size: 13px; text-align: center; margin-top: 10px; font-weight: 600; display: block;"></span>
                                </div>
                            </div>

                            <!-- Pay Değişimleri Alt Bölüm -->
                            <div style="background: rgba(255,255,255,0.02); padding: 25px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.05); margin-top: 25px; min-width: 0;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px;">
                                    <div>
                                        <span style="font-size: 14px; font-weight: 700; color: #fff; display: block; margin-bottom: 4px;">🔄 Ortaklık Payı Değişimleri</span>
                                        <span id="kapChangesDates" style="font-size: 12px; color: #8e8e93; font-weight: 500;">Karşılaştırılan Tarihler: Yükleniyor...</span>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <label style="font-size: 12px; color: #8e8e93; font-weight: 700; margin-bottom: 0;">FON FİLTRESİ:</label>
                                        <select id="kapChangesFilter" onchange="renderKapChangesTable()" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:8px 12px; font-size:13px; font-weight:800; width: 160px;"></select>
                                    </div>
                                </div>
                                
                                <div style="overflow-x: auto;">
                                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                                        <thead>
                                            <tr style="border-bottom: 2px solid rgba(255,255,255,0.1); color: #8e8e93; font-weight: 700;">
                                                <th style="padding: 12px 10px;">Fon</th>
                                                <th style="padding: 12px 10px;">Hisse</th>
                                                <th style="padding: 12px 10px;">Şirket Unvanı</th>
                                                <th style="padding: 12px 10px; text-align: right;">Eski Lot</th>
                                                <th style="padding: 12px 10px; text-align: right;">Yeni Lot</th>
                                                <th style="padding: 12px 10px; text-align: right;">Değişim (Lot)</th>
                                                <th style="padding: 12px 10px; text-align: right;">Değişim (%)</th>
                                                <th style="padding: 12px 10px; text-align: right;">Yeni Pay (%)</th>
                                                <th style="padding: 12px 10px; text-align: center;">Tür</th>
                                            </tr>
                                        </thead>
                                        <tbody id="kapChangesTableBody">
                                            <tr>
                                                <td colspan="9" style="padding: 20px; text-align: center; color: #8e8e93;">Değişim hesaplanabilmesi için en az 2 farklı güne ait veri bulunmalıdır.</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        <!-- Tarih Aralığı Analizi Bölümü -->
                        <div style="background: rgba(255,159,10,0.06); padding: 25px; border-radius: 18px; border: 1px solid rgba(255,159,10,0.2); margin-top: 30px;">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
                                <div>
                                    <span style="font-size: 15px; font-weight: 700; color: #ff9f0a; display: block; margin-bottom: 3px;">🔍 Tarih Aralığı Analizi</span>
                                    <span style="font-size: 12px; color: #8e8e93;">Seçilen tarih aralığında fon veya hisse bazlı tüm ortaklık değişimlerini görün</span>
                                </div>
                                <!-- Mod Toggle -->
                                <div style="display: flex; background: #000; border-radius: 12px; padding: 4px; gap: 4px; border: 1px solid #333;">
                                    <button id="rangeModeFundBtn" onclick="setRangeMode('fund')"
                                        style="background:#ff9f0a; color:#000; border:none; padding:8px 18px; border-radius:9px; font-size:13px; font-weight:800; cursor:pointer; transition:all 0.2s;">
                                        🏦 Fon Bazlı
                                    </button>
                                    <button id="rangeModeStockBtn" onclick="setRangeMode('stock')"
                                        style="background:none; color:#8e8e93; border:none; padding:8px 18px; border-radius:9px; font-size:13px; font-weight:800; cursor:pointer; transition:all 0.2s;">
                                        📊 Hisse Bazlı
                                    </button>
                                </div>
                            </div>

                            <!-- Filtre Satırı -->
                            <div style="display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 20px;">
                                <!-- Fon modu: dropdown -->
                                <div id="rangeFundGroup" style="display:flex; flex-direction:column; gap:5px; min-width:130px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">FON KODU</label>
                                    <select id="rangeFundSelect" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:10px 12px; font-size:13px; font-weight:800;"></select>
                                </div>
                                <!-- Hisse modu: text input + datalist -->
                                <div id="rangeStockGroup" style="display:none; flex-direction:column; gap:5px; min-width:130px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">HİSSE KODU</label>
                                    <input id="rangeStockInput" list="rangeStockList" placeholder="Örn: PASEU"
                                        style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:10px 12px; font-size:13px; font-weight:800; text-transform:uppercase; width:130px;">
                                    <datalist id="rangeStockList"></datalist>
                                </div>
                                <!-- Başlangıç tarihi -->
                                <div style="display:flex; flex-direction:column; gap:5px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">BAŞLANGIÇ</label>
                                    <input type="date" id="rangeFromDate" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px 12px; font-size:13px;">
                                </div>
                                <!-- Bitiş tarihi -->
                                <div style="display:flex; flex-direction:column; gap:5px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">BİTİŞ</label>
                                    <input type="date" id="rangeToDate" style="background:#000; border:1px solid #333; border-radius:10px; color:#fff; padding:9px 12px; font-size:13px;">
                                </div>
                                <!-- Değişmeyenleri göster toggle -->
                                <div style="display:flex; flex-direction:column; gap:5px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">DEĞİŞMEYENLER</label>
                                    <label style="display:flex; align-items:center; gap:8px; cursor:pointer; padding:10px 12px; background:#000; border:1px solid #333; border-radius:10px;">
                                        <input type="checkbox" id="rangeShowUnchanged" style="width:16px; height:16px; cursor:pointer; accent-color:#ff9f0a;">
                                        <span style="font-size:13px; color:#8e8e93;">Göster</span>
                                    </label>
                                </div>
                                <!-- Günlük İşlem Akışı (Timeline) toggle -->
                                <div style="display:flex; flex-direction:column; gap:5px;">
                                    <label style="font-size:11px; color:#8e8e93; font-weight:700;">İŞLEM GÜNLÜĞÜ</label>
                                    <label style="display:flex; align-items:center; gap:8px; cursor:pointer; padding:10px 12px; background:#000; border:1px solid #333; border-radius:10px;">
                                        <input type="checkbox" id="rangeTimeline" style="width:16px; height:16px; cursor:pointer; accent-color:#ff9f0a;">
                                        <span style="font-size:13px; color:#8e8e93;">Günlük Akış</span>
                                    </label>
                                </div>
                                <!-- Analiz Butonu -->
                                <button onclick="loadRangeAnalysis()"
                                    style="background:#ff9f0a; color:#000; border:none; padding:11px 22px; border-radius:12px; font-size:14px; font-weight:800; cursor:pointer; align-self:flex-end; white-space:nowrap;">
                                    🔍 Analiz Et
                                </button>
                            </div>

                            <!-- Sonuç Başlığı -->
                            <div id="rangeResultHeader" style="display:none; margin-bottom:12px;">
                                <span id="rangeResultTitle" style="font-size:13px; font-weight:700; color:#ff9f0a;"></span>
                                <span id="rangeResultSub" style="font-size:12px; color:#8e8e93; margin-left:10px;"></span>
                            </div>

                            <!-- Sonuç Tablosu -->
                            <div style="overflow-x: auto;">
                                <table style="width:100%; border-collapse:collapse; text-align:left; font-size:13px;">
                                    <thead id="rangeTableHead" style="display:none;">
                                        <tr id="rangeTableHeadRow" style="border-bottom:2px solid rgba(255,255,255,0.1); color:#8e8e93; font-weight:700;">
                                            <!-- Dynamically populated in loadRangeAnalysis -->
                                        </tr>
                                    </thead>
                                    <tbody id="rangeTableBody">
                                        <tr>
                                            <td colspan="8" style="padding:25px; text-align:center; color:#8e8e93;">
                                                Fon veya hisse seçip tarih aralığı belirleyin, ardından "Analiz Et" butonuna basın.
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div> <!-- Closes card div -->
                <script>
                    const addPredictionRow = (code='', val='', desc='') => {
                        const container = document.getElementById('predRowsContainer');
                        const row = document.createElement('div');
                        row.className = 'pred-row';
                        row.innerHTML = `
                            <input type="text" class="pred-code" value="${code}" placeholder="KOD">
                            <input type="text" class="pred-val" value="${val}" placeholder="%2,5">
                            <input type="text" class="pred-desc" value="${desc}" placeholder="Açıklama...">
                            <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
                        `;
                        container.appendChild(row);
                    };

                    async function fetchPredictionsFromTracker() {
                        // Servisten gelmeyen, manuel girilen fonlar
                        const MANUAL_FUNDS = ['BIST100'];

                        const rows = document.querySelectorAll('#predRowsContainer .pred-row');
                        let allFunds = Array.from(rows)
                            .map(row => row.querySelector('.pred-code').value.trim().toUpperCase())
                            .filter(Boolean)
                            .filter(f => !MANUAL_FUNDS.includes(f));
                        
                        if (!allFunds.length) {
                            const raw = (document.getElementById('trackedFunds').value || '').trim();
                            allFunds = raw.split(/[,\s]+/).map(f => f.trim().toUpperCase()).filter(Boolean).filter(f => !MANUAL_FUNDS.includes(f));
                        }

                        
                        if (!allFunds.length) {
                            alert("Lütfen önce tablodaki 'FON KODU' alanlarını doldurun veya 'Takipteki Fon Kodları' alanını girin.");
                            return;
                        }
                        
                        const statusEl = document.getElementById('predFetchStatus');
                        const MAX_RETRIES = 5;
                        const RETRY_DELAY_MS = 1000;
                        const predMap = {};
                        let attempt = 0;
                        let pendingFunds = [...allFunds];

                        const doFetch = async (funds) => {
                            const resp = await fetch('/api/fetch-predictions', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({funds: funds.join(','), batch_size: 5, timeout: 20})
                            });
                            return resp.json();
                        };

                        const sleep = ms => new Promise(r => setTimeout(r, ms));

                        try {
                            while (pendingFunds.length > 0 && attempt <= MAX_RETRIES) {
                                if (attempt === 0) {
                                    statusEl.textContent = `⏳ Çekiliyor... (${pendingFunds.length} fon)`;
                                } else {
                                    statusEl.textContent = `🔄 Retry ${attempt}/${MAX_RETRIES} — eksik ${pendingFunds.length} fon yeniden deneniyor...`;
                                }
                                statusEl.style.color = '#8e8e93';

                                const d = await doFetch(pendingFunds);

                                if (!d.success) {
                                    statusEl.textContent = '❌ ' + (d.error || 'Hata');
                                    statusEl.style.color = '#ff453a';
                                    return;
                                }

                                // Gelen tahminleri predMap'e ekle
                                (d.predictions || []).forEach(p => {
                                    predMap[p.code.toUpperCase()] = p;
                                });

                                // Hâlâ eksik olanları bul
                                pendingFunds = allFunds.filter(f => !predMap[f]);

                                attempt++;
                                if (pendingFunds.length > 0 && attempt <= MAX_RETRIES) {
                                    await sleep(RETRY_DELAY_MS);
                                }
                            }

                            // Satırları güncelle
                            let updatedCount = 0;
                            rows.forEach(row => {
                                const code = row.querySelector('.pred-code').value.trim().toUpperCase();
                                if (code && predMap[code]) {
                                    row.querySelector('.pred-val').value = predMap[code].val;
                                    updatedCount++;
                                }
                            });

                            const missing = allFunds.filter(f => !predMap[f]);
                            let msg = `✅ ${updatedCount}/${allFunds.length} fon güncellendi`;
                            if (attempt > 1) msg += ` (${attempt} deneme)`;
                            let color = '#32d74b';
                            if (missing.length > 0) {
                                msg += ` ⚠️ Gelmeyenler: ${missing.join(', ')}`;
                                color = '#ff9f0a';
                            }
                            statusEl.textContent = msg;
                            statusEl.style.color = color;

                        } catch(e) {
                            statusEl.textContent = '❌ Bağlantı hatası: ' + e;
                            statusEl.style.color = '#ff453a';
                        }
                    }

                    async function fetchHoldings() {
                        const fundCode  = (document.getElementById('holdingsFundCode').value || 'TLY').trim().toUpperCase();
                        const fonToplam = document.getElementById('holdingsFonToplam').value.trim().replace(/\./g,'').replace(',','.');
                        const topN      = document.getElementById('holdingsTopN').value || '5';
                        const statusEl  = document.getElementById('holdingsStatus');
                        statusEl.textContent = '⏳ Çekiliyor...';
                        statusEl.style.color = '#8e8e93';
                        try {
                            const resp = await fetch('/api/fetch-holdings', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({fund_code: fundCode, fon_toplam: fonToplam, top_n: topN})
                            });
                            const d = await resp.json();
                            if (d.success) {
                                const t = d.fetched_at ? new Date(d.fetched_at).toLocaleTimeString('tr-TR') : '';
                                statusEl.textContent = `✅ ${fundCode} — ${d.item_count} kalem${t ? ' | ' + t : ''}`;
                                statusEl.style.color = '#32d74b';
                            } else {
                                statusEl.textContent = '❌ ' + (d.error || 'Hata');
                                statusEl.style.color = '#ff453a';
                            }
                        } catch(e) {
                            statusEl.textContent = '❌ Bağlantı hatası: ' + e;
                            statusEl.style.color = '#ff453a';
                        }
                    }

                    function generate(period) {
                        const btnId = period === 'predictions' ? 'btn-preds' : 'btn-' + period;
                        const btn = document.getElementById(btnId);
                        const loader = btn.querySelector('.loader');
                        const status = document.getElementById('status');
                        const resultLink = document.getElementById('resultLink');
                        
                        const bgUrl = document.getElementById('bgUrl').value;
                        const customStartDate = document.getElementById('customStartDate').value;
                        const customEndDate = document.getElementById('customEndDate').value;
                        const sections = [];
                        ['inflows', 'outflows', 'cat_in', 'cat_out', 'inv_in', 'inv_out', 'divergent', 'momentum', 'crowding', 'category_rotation', 'tracked', 'tracked_rs', 'manager_actions', 'predictions', 'portfolio_diff', 'per_investor_value', 'fund_report', 'top_gainers', 'top_losers', 'comparison_chart', 'return_chart', 'holdings_breakdown', 'flow_chart', 'investor_chart', 'fund_takas_diff', 'fund_takas_diff_pct'].forEach(s => {
                            const chk = document.getElementById('chk-' + s);
                            if (chk && chk.checked) sections.push(s);
                        });
                        
                        // Prediction Rows
                        const predictions = [];
                        document.querySelectorAll('#predRowsContainer .pred-row').forEach(row => {
                            const code = row.querySelector('.pred-code').value;
                            if (code) {
                                predictions.push({
                                    code: code,
                                    val: row.querySelector('.pred-val').value,
                                    desc: row.querySelector('.pred-desc').value
                                });
                            }
                        });

                        let finalSections = sections;
                        if (period === 'predictions') {
                            finalSections = ['predictions'];
                        }

                        const selectedCats = Array.from(document.querySelectorAll('.cat-chk:checked')).map(c => c.value);
                        
                        const positions = {};
                        ['inflows', 'outflows', 'cat_in', 'cat_out', 'inv_in', 'inv_out', 'divergent', 'momentum', 'crowding', 'category_rotation', 'tracked', 'tracked_rs', 'manager_actions', 'predictions', 'portfolio_diff', 'per_investor_value', 'fund_report', 'top_gainers', 'top_losers', 'comparison_chart', 'return_chart', 'holdings_breakdown', 'flow_chart', 'investor_chart', 'fund_takas_diff', 'fund_takas_diff_pct'].forEach(s => {
                            const chk = document.getElementById('chk-' + s);
                            if (chk) {
                                const r = document.getElementById('pos-' + s + '-r').value;
                                const c = document.getElementById('pos-' + s + '-c').value;
                                positions[s] = r + ',' + c;
                            }
                        });

                        btn.disabled = true;
                        loader.style.display = 'block';
                        status.textContent = period.toUpperCase() + " görseli hazırlanıyor... Lütfen bekleyin.";
                        status.style.color = "#8e8e93";
                        resultLink.style.display = "none";

                        fetch('/api/generate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                period: period === 'predictions' ? 'daily' : period,
                                custom_start_date: customStartDate,
                                custom_end_date: customEndDate,
                                tracked_funds: document.getElementById('trackedFunds').value,
                                bg_url: bgUrl,
                                sections: finalSections.join(','),
                                selected_categories: selectedCats.join(','),
                                grid_cols: document.getElementById('gridCols').value,
                                sort_mode: document.getElementById('sortMode').value,
                                canvas_width: document.getElementById('canvasWidth').value,
                                tracked_grid_cols: document.getElementById('trackedGridCols').value,
                                item_font_size: document.getElementById('itemFontSize').value,
                                period_font_size: document.getElementById('periodFontSize').value,
                                tcode_font_size: document.getElementById('tcodeFontSize').value,
                                watermark_anchor: document.getElementById('watermarkAnchor').value,
                                main_title: document.getElementById('mainTitle').value,
                                subtitle: document.getElementById('subtitle').value,
                                header_show_main: document.getElementById('headerShowMain').checked,
                                header_show_sub: document.getElementById('headerShowSub').checked,
                                pred_title: document.getElementById('predTitle').value,
                                predictions: predictions,
                                portfolio_diff_fund: document.getElementById('portfolioDiffFund') ? document.getElementById('portfolioDiffFund').value.trim() : 'PHE',
                                portfolio_diff_cols: document.getElementById('portfolioDiffCols') ? document.getElementById('portfolioDiffCols').value : 1,
                                fund_report_fund: document.getElementById('fundReportFund') ? document.getElementById('fundReportFund').value.trim() : 'PHE',
                                pred_cols: document.getElementById('predCols') ? document.getElementById('predCols').value : 1,
                                positions: positions
                            })
                        })
                        .then(res => res.json())
                        .then(data => {
                            btn.disabled = false;
                            loader.style.display = 'none';
                            if (data.success) {
                                status.textContent = "Görsel başarıyla oluşturuldu! ";
                                status.style.color = "#32d74b";
                                resultLink.style.display = "inline-block";
                                window.open('/infographic.png?v=' + Date.now(), '_blank');
                                
                                // HTML review link
                                const htmlLink = document.createElement('a');
                                htmlLink.href = '/filled_index';
                                htmlLink.target = '_blank';
                                htmlLink.innerText = ' [HTML Olarak İncele]';
                                htmlLink.style.cssText = 'color: #32d74b; margin-left:15px; text-decoration:none; font-weight:600;';
                                status.appendChild(htmlLink);

                                // X Share button
                                const xBtn = document.createElement('button');
                                xBtn.innerText = '𝕏 Paylaş';
                                xBtn.style.cssText = 'margin-left:15px; background:#000; color:#fff; border:none; padding:10px 20px; border-radius:20px; font-size:14px; font-weight:700; cursor:pointer; vertical-align:middle;';
                                xBtn.onclick = function() {
                                    fetch('/tweet')
                                        .then(r => r.json())
                                        .then(d => {
                                            if (d.error) { alert('Tweet oluşturulamadı: ' + d.error); return; }
                                            const modal = document.getElementById('tweet-modal');
                                            document.getElementById('tweet-preview-text').value = d.tweet_text;
                                            document.getElementById('tweet-char-count').textContent = d.char_count + ' / 280 karakter';
                                            modal.style.display = 'flex';
                                        })
                                        .catch(e => alert('Hata: ' + e));
                                };
                                status.appendChild(xBtn);

                            } else {
                                status.textContent = "HATA: " + data.error;
                                status.style.color = "#ff453a";
                            }
                        })
                        .catch(err => {
                            btn.disabled = false;
                            loader.style.display = 'none';
                            status.textContent = "Bağlantı hatası: " + err;
                            status.style.color = "#ff453a";
                        });
                    }
                    // Fon Getiri Hesaplayıcı Javascript Fonksiyonları
                    const addCalculatorRow = (code='', prevVal='', currVal='', retVal='') => {
                        const container = document.getElementById('calcRowsContainer');
                        const row = document.createElement('div');
                        row.className = 'pred-row';
                        row.style.gridTemplateColumns = '1fr 1.2fr 1.2fr 1.2fr 40px';
                        row.innerHTML = `
                            <input type="text" class="calc-code" value="${code}" placeholder="KOD" style="text-transform:uppercase;" oninput="saveCalculatorState()">
                            <input type="number" step="any" class="calc-prev" value="${prevVal}" placeholder="Manuel" oninput="saveCalculatorState()">
                            <input type="number" step="any" class="calc-curr" value="${currVal}" placeholder="0.000000" oninput="saveCalculatorState()">
                            <input type="text" class="calc-ret" value="${retVal}" placeholder="%" readonly style="background:#111; border-color:#222; text-align:center; font-weight:700; color:#32d74b;">
                            <button class="remove-btn" onclick="removeCalculatorRow(this)">✕</button>
                        `;
                        container.appendChild(row);
                        saveCalculatorState();
                    };

                    const removeCalculatorRow = (btn) => {
                        btn.parentElement.remove();
                        saveCalculatorState();
                    };

                    const saveCalculatorState = () => {
                        const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                        const state = Array.from(rows).map(row => ({
                            code: row.querySelector('.calc-code').value.trim().toUpperCase(),
                            prev: row.querySelector('.calc-prev').value.trim(),
                            curr: row.querySelector('.calc-curr').value.trim(),
                            ret: row.querySelector('.calc-ret').value.trim()
                        }));
                        localStorage.setItem('calc_rows_state', JSON.stringify(state));
                    };

                    const loadCalculatorState = async () => {
                        const saved = localStorage.getItem('calc_rows_state');
                        let state = [];
                        if (saved) {
                            try {
                                state = JSON.parse(saved);
                            } catch (e) {
                                console.error("Error loading calculator state:", e);
                            }
                        }
                        
                        if (!state || state.length === 0) {
                            state = [
                                { code: 'TLY', prev: '', curr: '', ret: '' },
                                { code: 'DFI', prev: '', curr: '', ret: '' }
                            ];
                        }

                        // Render rows
                        const container = document.getElementById('calcRowsContainer');
                        const header = container.querySelector('.pred-header');
                        container.innerHTML = '';
                        container.appendChild(header);

                        state.forEach(item => {
                            addCalculatorRow(item.code, item.prev, item.curr, item.ret);
                        });

                        // Silent initial fetch and calculation
                        await fetchPricesFromExtensionSilently();
                    };

                    async function fetchPricesFromExtensionSilently() {
                        try {
                            const resp = await fetch('/api/prices/extension');
                            const data = await resp.json();
                            if (data.success && data.prices) {
                                const prices = data.prices;
                                const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                                let changed = false;
                                
                                rows.forEach(row => {
                                    const codeEl = row.querySelector('.calc-code');
                                    const currEl = row.querySelector('.calc-curr');
                                    const code = codeEl.value.trim().toUpperCase();
                                    
                                    if (code && prices[code]) {
                                        const pVal = parseFloat(prices[code].price).toFixed(6);
                                        if (currEl.value !== pVal) {
                                            currEl.value = pVal;
                                            changed = true;
                                        }
                                    }
                                });
                                if (changed) {
                                    saveCalculatorState();
                                    calculateReturnsSilently();
                                }
                            }
                        } catch (err) {
                            // ignore silent errors
                        }
                    }

                    function calculateReturnsSilently() {
                        const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                        rows.forEach(row => {
                            const prevEl = row.querySelector('.calc-prev');
                            const currEl = row.querySelector('.calc-curr');
                            const retEl = row.querySelector('.calc-ret');
                            
                            const prevVal = parseFloat(prevEl.value);
                            const currVal = parseFloat(currEl.value);
                            
                            if (!isNaN(prevVal) && !isNaN(currVal) && prevVal > 0) {
                                const ret = ((currVal / prevVal) - 1) * 100;
                                const sign = ret >= 0 ? '+' : '';
                                retEl.value = `${sign}${ret.toFixed(4)}%`;
                                if (ret >= 0) {
                                    retEl.style.color = '#32d74b';
                                } else {
                                    retEl.style.color = '#ff453a';
                                }
                            }
                        });
                    }

                    function calculateReturns() {
                        const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                        let calculatedCount = 0;
                        
                        rows.forEach(row => {
                            const prevEl = row.querySelector('.calc-prev');
                            const currEl = row.querySelector('.calc-curr');
                            const retEl = row.querySelector('.calc-ret');
                            
                            const prevVal = parseFloat(prevEl.value);
                            const currVal = parseFloat(currEl.value);
                            
                            if (!isNaN(prevVal) && !isNaN(currVal) && prevVal > 0) {
                                const ret = ((currVal / prevVal) - 1) * 100;
                                const sign = ret >= 0 ? '+' : '';
                                retEl.value = `${sign}${ret.toFixed(4)}%`;
                                if (ret >= 0) {
                                    retEl.style.color = '#32d74b';
                                } else {
                                    retEl.style.color = '#ff453a';
                                }
                                calculatedCount++;
                            } else {
                                retEl.value = '';
                            }
                        });
                        
                        const statusEl = document.getElementById('calcStatus');
                        statusEl.textContent = `✅ ${calculatedCount} fonun getirisi hesaplandı!`;
                        statusEl.style.color = '#32d74b';
                        saveCalculatorState();
                    }

                    function transferCurrentToPrevious() {
                        const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                        let transferredCount = 0;
                        
                        rows.forEach(row => {
                            const prevEl = row.querySelector('.calc-prev');
                            const currEl = row.querySelector('.calc-curr');
                            const retEl = row.querySelector('.calc-ret');
                            
                            const currVal = currEl.value.trim();
                            if (currVal) {
                                prevEl.value = currVal;
                                retEl.value = '';
                                transferredCount++;
                            }
                        });
                        
                        const statusEl = document.getElementById('calcStatus');
                        statusEl.textContent = `📋 ${transferredCount} fon fiyatı önceki güne aktarıldı!`;
                        statusEl.style.color = '#ff9f0a';
                        saveCalculatorState();
                    }

                    const saveQuoteTweetState = () => {
                        const url = document.getElementById('quoteTweetUrl').value.trim();
                        const source = document.getElementById('calcSource').value.trim();
                        const date = document.getElementById('calcDate').value;
                        localStorage.setItem('quote_tweet_url', url);
                        localStorage.setItem('calc_source', source);
                        localStorage.setItem('calc_date', date);
                    };

                    const loadQuoteTweetState = () => {
                        const url = localStorage.getItem('quote_tweet_url');
                        if (url) {
                            document.getElementById('quoteTweetUrl').value = url;
                        }
                        const source = localStorage.getItem('calc_source');
                        if (source !== null) {
                            document.getElementById('calcSource').value = source;
                        } else {
                            document.getElementById('calcSource').value = '@fintables';
                        }
                        const date = localStorage.getItem('calc_date');
                        if (date) {
                            document.getElementById('calcDate').value = date;
                        } else {
                            const today = new Date();
                            const yyyy = today.getFullYear();
                            const mm = String(today.getMonth() + 1).padStart(2, '0');
                            const dd = String(today.getDate()).padStart(2, '0');
                            document.getElementById('calcDate').value = `${yyyy}-${mm}-${dd}`;
                        }
                    };

                    function formatTurkishDate(dateStr) {
                        if (!dateStr) return "";
                        const parts = dateStr.split('-');
                        if (parts.length !== 3) return dateStr;
                        const year = parts[0];
                        const month = parseInt(parts[1], 10);
                        const day = parseInt(parts[2], 10);
                        
                        const months = [
                            "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", 
                            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
                        ];
                        return `${day} ${months[month]} ${year}`;
                    }

                    function shareCalculatorReturnsOnX() {
                        const rows = document.querySelectorAll('#calcRowsContainer .pred-row');
                        const lines = [];
                        
                        rows.forEach(row => {
                            const codeEl = row.querySelector('.calc-code');
                            const retEl = row.querySelector('.calc-ret');
                            
                            const code = codeEl.value.trim().toUpperCase();
                            const retStr = retEl.value.trim();
                            
                            if (code && retStr && retStr !== '%') {
                                const numericVal = parseFloat(retStr.replace('%', ''));
                                // Bypass +0.0000%, -0.0000% and 0.0000%
                                if (!isNaN(numericVal) && Math.abs(numericVal) > 0.00001) {
                                    lines.push(`#${code} ${retStr}`);
                                }
                            }
                        });
                        
                        if (lines.length === 0) {
                            alert("Açıklanan ve sıfırdan farklı getirisi olan herhangi bir fon bulunamadı!");
                            return;
                        }

                        const dateInputVal = document.getElementById('calcDate').value;
                        let dateStr = "";
                        if (dateInputVal) {
                            dateStr = formatTurkishDate(dateInputVal);
                        } else {
                            const today = new Date();
                            const yyyy = today.getFullYear();
                            const mm = String(today.getMonth() + 1).padStart(2, '0');
                            const dd = String(today.getDate()).padStart(2, '0');
                            dateStr = formatTurkishDate(`${yyyy}-${mm}-${dd}`);
                        }
                        
                        let tweetText = `${dateStr} Getirisi Açıklanan Fonlar\n` + lines.join("\n");
                        
                        const sourceVal = document.getElementById('calcSource').value.trim();
                        if (sourceVal) {
                            tweetText += "\n\nKaynak: " + sourceVal;
                        }
                        
                        const quoteUrl = document.getElementById('quoteTweetUrl').value.trim();
                        if (quoteUrl) {
                            tweetText += "\n\n" + quoteUrl;
                        }
                        
                        const modal = document.getElementById('tweet-modal');
                        document.getElementById('tweet-preview-text').value = tweetText;
                        document.getElementById('tweet-char-count').textContent = tweetText.length + ' karakter';
                        modal.style.display = 'flex';
                    }
                    let kapChartInstance = null;
                    let kapSelectorsData = {};

                    async function initKapShareholdersTracker() {
                        const today = new Date();
                        const yyyy = today.getFullYear();
                        const mm = String(today.getMonth() + 1).padStart(2, '0');
                        const dd = String(today.getDate()).padStart(2, '0');
                        document.getElementById('kapManualDate').value = `${yyyy}-${mm}-${dd}`;
                        
                        try {
                            const resp = await fetch('/api/kap/shareholders/selectors');
                            const data = await resp.json();
                            if (data.success && data.selectors) {
                                kapSelectorsData = data.selectors;
                                
                                const fundSelect = document.getElementById('kapSelectorFund');
                                fundSelect.innerHTML = '';
                                
                                const funds = Object.keys(kapSelectorsData).sort();
                                if (funds.length === 0) {
                                    const opt = document.createElement('option');
                                    opt.text = "Veri Yok";
                                    fundSelect.appendChild(opt);
                                    return;
                                }
                                
                                funds.forEach(f => {
                                    const opt = document.createElement('option');
                                    opt.value = f;
                                    opt.text = f;
                                    fundSelect.appendChild(opt);
                                });
                                
                                if (funds.includes('TLY')) {
                                    fundSelect.value = 'TLY';
                                }
                                
                                onKapFundChanged();
                            }
                            loadKapChanges();
                            initRangeAnalysis();
                        } catch (err) {
                            console.error("Error initializing KAP tracker:", err);
                        }
                    }

                    let kapChangesData = [];

                    async function loadKapChanges() {
                        const datesEl = document.getElementById('kapChangesDates');
                        const filterSelect = document.getElementById('kapChangesFilter');
                        
                        try {
                            const resp = await fetch('/api/kap/shareholders/changes');
                            const data = await resp.json();
                            if (data.success) {
                                kapChangesData = data.changes;
                                
                                if (data.yesterday && data.today) {
                                    datesEl.textContent = `Karşılaştırılan Tarihler: ${data.yesterday} ➔ ${data.today}`;
                                } else {
                                    datesEl.textContent = "Karşılaştırılacak yeterli tarih bulunamadı.";
                                }
                                
                                const currentFilter = filterSelect.value;
                                filterSelect.innerHTML = '';
                                
                                const allOpt = document.createElement('option');
                                allOpt.value = 'ALL';
                                allOpt.text = 'TÜM FONLAR';
                                filterSelect.appendChild(allOpt);
                                
                                const uniqueFunds = [...new Set(kapChangesData.map(c => c.fund))].sort();
                                uniqueFunds.forEach(f => {
                                    const opt = document.createElement('option');
                                    opt.value = f;
                                    opt.text = f;
                                    filterSelect.appendChild(opt);
                                });
                                
                                if (uniqueFunds.includes(currentFilter)) {
                                    filterSelect.value = currentFilter;
                                } else if (uniqueFunds.includes('TLY')) {
                                    filterSelect.value = 'TLY';
                                } else {
                                    filterSelect.value = 'ALL';
                                }
                                
                                renderKapChangesTable();
                            }
                        } catch (err) {
                            console.error("Error loading KAP changes:", err);
                        }
                    }

                    function renderKapChangesTable() {
                        const filter = document.getElementById('kapChangesFilter').value;
                        const tbody = document.getElementById('kapChangesTableBody');
                        tbody.innerHTML = '';
                        
                        const filtered = kapChangesData.filter(c => filter === 'ALL' || c.fund === filter);
                        
                        if (filtered.length === 0) {
                            tbody.innerHTML = `
                                <tr>
                                    <td colspan="9" style="padding: 20px; text-align: center; color: #8e8e93;">Bu fona ait alım/satım hareketi bulunmamaktadır.</td>
                                </tr>
                            `;
                            return;
                        }
                        
                        filtered.sort((a, b) => Math.abs(b.diff_lot) - Math.abs(a.diff_lot));
                        
                        filtered.forEach(c => {
                            const isBuy = c.diff_lot > 0;
                            const badgeColor = isBuy ? '#32d74b' : '#ff453a';
                            const badgeText = isBuy ? 'ALIM 📈' : 'SATIM 📉';
                            const sign = isBuy ? '+' : '';
                            const colorStyle = `color: ${badgeColor}; font-weight: 700;`;
                            
                            const tr = document.createElement('tr');
                            tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                            tr.className = 'hover:bg-gray-50';
                            tr.innerHTML = `
                                <td style="padding: 12px 10px; font-weight:700;">${c.fund}</td>
                                <td style="padding: 12px 10px; font-weight:700; color:#ff9f0a;">#${c.stock}</td>
                                <td style="padding: 12px 10px; font-size:12px; color:#8e8e93; max-width:250px; overflow:hidden; text-ellipsis:ellipsis; white-space:nowrap;" title="${c.company_name}">${c.company_name}</td>
                                <td style="padding: 12px 10px; text-align: right; font-family:monospace;">${Math.round(c.yesterday_lot).toLocaleString('tr-TR')}</td>
                                <td style="padding: 12px 10px; text-align: right; font-family:monospace;">${Math.round(c.today_lot).toLocaleString('tr-TR')}</td>
                                <td style="padding: 12px 10px; text-align: right; font-family:monospace; ${colorStyle}">${sign}${Math.round(c.diff_lot).toLocaleString('tr-TR')}</td>
                                <td style="padding: 12px 10px; text-align: right; font-family:monospace; ${colorStyle}">${sign}${c.pct_change.toFixed(2)}%</td>
                                <td style="padding: 12px 10px; text-align: right; font-family:monospace;">%${c.today_ratio.toFixed(2)}</td>
                                <td style="padding: 12px 10px; text-align: center;"><span style="background: ${badgeColor}20; color: ${badgeColor}; padding: 4px 8px; border-radius: 8px; font-size: 11px; font-weight: 800; border: 1px solid ${badgeColor}40;">${badgeText}</span></td>
                            `;
                            tbody.appendChild(tr);
                        });
                    }

                    function onKapFundChanged() {
                        const fundSelect = document.getElementById('kapSelectorFund');
                        const stockSelect = document.getElementById('kapSelectorStock');
                        const selectedFund = fundSelect.value;
                        
                        stockSelect.innerHTML = '';
                        if (!selectedFund || !kapSelectorsData[selectedFund]) {
                            const opt = document.createElement('option');
                            opt.text = "Hisse Yok";
                            stockSelect.appendChild(opt);
                            return;
                        }
                        
                        const stocks = kapSelectorsData[selectedFund];
                        stocks.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s;
                            opt.text = s;
                            stockSelect.appendChild(opt);
                        });
                        
                        if (stocks.includes('TERA')) {
                            stockSelect.value = 'TERA';
                        }
                        
                        loadKapShareholderHistoryChart();
                    }

                    async function loadKapShareholderHistoryChart() {
                        const fund = document.getElementById('kapSelectorFund').value;
                        const stock = document.getElementById('kapSelectorStock').value;
                        
                        if (!fund || !stock || fund === "Veri Yok" || stock === "Hisse Yok") {
                            return;
                        }
                        
                        try {
                            const resp = await fetch(`/api/kap/shareholders/history?fund=${fund}&stock=${stock}`);
                            const data = await resp.json();
                            if (data.success && data.history) {
                                const history = data.history;
                                
                                const labels = history.map(h => {
                                    const parts = h.date.split('-');
                                    return parts.length === 3 ? `${parts[2]}.${parts[1]}` : h.date;
                                });
                                const lots = history.map(h => h.lot);
                                const ratios = history.map(h => h.ratio);
                                
                                drawKapChart(labels, lots, ratios, `${fund} Fonunun ${stock} Hissesindeki Lot Miktarı`);
                            }
                        } catch (err) {
                            console.error("Error loading KAP history chart:", err);
                        }
                    }

                    function drawKapChart(labels, lots, ratios, title) {
                        const ctx = document.getElementById('kapHistoryChart').getContext('2d');
                        
                        if (kapChartInstance) {
                            kapChartInstance.destroy();
                        }
                        
                        kapChartInstance = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Lot Miktarı',
                                    data: lots,
                                    borderColor: '#ff9f0a',
                                    backgroundColor: 'rgba(255, 159, 10, 0.1)',
                                    borderWidth: 3,
                                    pointBackgroundColor: '#ff9f0a',
                                    pointRadius: 4,
                                    tension: 0.15,
                                    fill: true,
                                    yAxisID: 'y'
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        display: false
                                    },
                                    tooltip: {
                                        mode: 'index',
                                        intersect: false,
                                        callbacks: {
                                            label: function(context) {
                                                const val = context.raw;
                                                const ratio = ratios[context.dataIndex];
                                                return ` Lot: ${val.toLocaleString('tr-TR')} (Pay: %${ratio.toFixed(2)})`;
                                            }
                                        }
                                    }
                                },
                                scales: {
                                    x: {
                                        grid: {
                                            color: 'rgba(255, 255, 255, 0.05)'
                                        },
                                        ticks: {
                                            color: '#8e8e93'
                                        }
                                    },
                                    y: {
                                        type: 'linear',
                                        display: true,
                                        position: 'left',
                                        grid: {
                                            color: 'rgba(255, 255, 255, 0.05)'
                                        },
                                        ticks: {
                                            color: '#8e8e93',
                                            callback: function(value) {
                                                if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M';
                                                if (value >= 1e3) return (value / 1e3).toFixed(0) + 'K';
                                                return value;
                                            }
                                        }
                                    }
                                }
                            }
                        });
                    }

                    async function saveKapManualEntry() {
                        const date = document.getElementById('kapManualDate').value;
                        const fund = document.getElementById('kapManualFund').value.trim().toUpperCase();
                        const stock = document.getElementById('kapManualStock').value.trim().toUpperCase();
                        const lot = parseFloat(document.getElementById('kapManualLot').value);
                        const ratio = parseFloat(document.getElementById('kapManualRatio').value);
                        
                        const statusEl = document.getElementById('kapManualStatus');
                        statusEl.textContent = "⏳ Kaydediliyor...";
                        statusEl.style.color = "#8e8e93";
                        
                        if (!date || !fund || !stock || isNaN(lot) || isNaN(ratio)) {
                            statusEl.textContent = "❌ Lütfen tüm alanları doldurun!";
                            statusEl.style.color = "#ff453a";
                            return;
                        }
                        
                        try {
                            const resp = await fetch('/api/kap/shareholders/manual', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ date, fund, stock, lot, ratio })
                            });
                            const data = await resp.json();
                            if (data.success) {
                                statusEl.textContent = "✅ Başarıyla kaydedildi!";
                                statusEl.style.color = "#32d74b";
                                
                                document.getElementById('kapManualFund').value = '';
                                document.getElementById('kapManualStock').value = '';
                                document.getElementById('kapManualLot').value = '';
                                document.getElementById('kapManualRatio').value = '';
                                
                                await initKapShareholdersTracker();
                            } else {
                                statusEl.textContent = "❌ Hata: " + data.error;
                                statusEl.style.color = "#ff453a";
                            }
                        } catch (err) {
                            statusEl.textContent = "❌ Bağlantı hatası: " + err.message;
                            statusEl.style.color = "#ff453a";
                        }
                    }

                    // ── Tarih Aralığı Analizi ──────────────────────────────
                    let rangeMode = 'fund'; // 'fund' | 'stock'
                    let rangeAvailableStocks = [];
                    let rangeAvailableFunds  = [];

                    function setRangeMode(mode) {
                        rangeMode = mode;
                        const fundBtn  = document.getElementById('rangeModeFundBtn');
                        const stockBtn = document.getElementById('rangeModeStockBtn');
                        const fundGrp  = document.getElementById('rangeFundGroup');
                        const stockGrp = document.getElementById('rangeStockGroup');

                        if (mode === 'fund') {
                            fundBtn.style.background  = '#ff9f0a';
                            fundBtn.style.color       = '#000';
                            stockBtn.style.background = 'none';
                            stockBtn.style.color      = '#8e8e93';
                            fundGrp.style.display  = 'flex';
                            stockGrp.style.display = 'none';
                        } else {
                            stockBtn.style.background = '#ff9f0a';
                            stockBtn.style.color      = '#000';
                            fundBtn.style.background  = 'none';
                            fundBtn.style.color       = '#8e8e93';
                            stockGrp.style.display = 'flex';
                            fundGrp.style.display  = 'none';
                        }
                    }

                    function populateRangeSelectors(funds, stocks) {
                        rangeAvailableFunds  = funds  || [];
                        rangeAvailableStocks = stocks || [];

                        // Fund dropdown
                        const fundSel = document.getElementById('rangeFundSelect');
                        if (fundSel) {
                            fundSel.innerHTML = '';
                            rangeAvailableFunds.forEach(f => {
                                const o = document.createElement('option');
                                o.value = f; o.text = f;
                                fundSel.appendChild(o);
                            });
                            if (rangeAvailableFunds.includes('TLY')) fundSel.value = 'TLY';
                        }

                        // Stock datalist
                        const dl = document.getElementById('rangeStockList');
                        if (dl) {
                            dl.innerHTML = '';
                            rangeAvailableStocks.forEach(s => {
                                const o = document.createElement('option');
                                o.value = s;
                                dl.appendChild(o);
                            });
                        }

                        // Default dates: oldest → today from history
                        const today = new Date().toISOString().slice(0, 10);
                        const fromEl = document.getElementById('rangeFromDate');
                        const toEl   = document.getElementById('rangeToDate');
                        if (fromEl && !fromEl.value) fromEl.value = today;
                        if (toEl && !toEl.value) toEl.value = today;
                    }

                    async function initRangeAnalysis() {
                        try {
                            const resp = await fetch('/api/kap/shareholders/range-changes');
                            const data = await resp.json();
                            if (data.success) {
                                populateRangeSelectors(data.available_funds, data.available_stocks);
                                const fromEl = document.getElementById('rangeFromDate');
                                const toEl   = document.getElementById('rangeToDate');
                                if (data.dates && data.dates.length === 2) {
                                    if (fromEl) fromEl.value = data.dates[0];
                                    if (toEl)   toEl.value   = data.dates[1];
                                }
                            }
                        } catch (err) {
                            console.error("Error initializing Range Analysis selectors:", err);
                        }
                    }

                    async function loadRangeAnalysis() {
                        const tbody  = document.getElementById('rangeTableBody');
                        const header = document.getElementById('rangeTableHead');
                        const resHdr = document.getElementById('rangeResultHeader');
                        tbody.innerHTML = `<tr><td colspan="8" style="padding:20px; text-align:center; color:#8e8e93;">Yükleniyor...</td></tr>`;

                        const fromDate      = document.getElementById('rangeFromDate').value;
                        const toDate        = document.getElementById('rangeToDate').value;
                        const showUnchanged = document.getElementById('rangeShowUnchanged').checked ? 1 : 0;
                        const isTimeline    = document.getElementById('rangeTimeline').checked;

                        let url = `/api/kap/shareholders/range-changes?from=${fromDate}&to=${toDate}&unchanged=${showUnchanged}&timeline=${isTimeline ? 1 : 0}`;

                        let labelPrimary = '';
                        const headRow = document.getElementById('rangeTableHeadRow');
                        const primaryColHeader = rangeMode === 'fund' ? 'Hisse' : 'Fon';
                        const secondaryColHeader = rangeMode === 'fund' ? 'Şirket Unvanı' : 'Fon Adı';

                        if (isTimeline) {
                            headRow.innerHTML = `
                                <th style="padding:10px; text-align:left;">Tarih</th>
                                <th style="padding:10px;">${primaryColHeader}</th>
                                <th style="padding:10px;">${secondaryColHeader}</th>
                                <th style="padding:10px; text-align:right;">Önceki Lot</th>
                                <th style="padding:10px; text-align:right;">Yeni Lot</th>
                                <th style="padding:10px; text-align:right;">İşlem (Lot)</th>
                                <th style="padding:10px; text-align:right;">İşlem (%)</th>
                                <th style="padding:10px; text-align:right;">Yeni Pay</th>
                                <th style="padding:10px; text-align:center;">İşlem Türü</th>
                            `;
                        } else {
                            headRow.innerHTML = `
                                <th style="padding:10px;">${primaryColHeader}</th>
                                <th style="padding:10px;">${secondaryColHeader}</th>
                                <th style="padding:10px; text-align:right;">Açılış Lotu</th>
                                <th style="padding:10px; text-align:right;">Kapanış Lotu</th>
                                <th style="padding:10px; text-align:right;">Değişim (Lot)</th>
                                <th style="padding:10px; text-align:right;">Değişim (%)</th>
                                <th style="padding:10px; text-align:right;">Pay Oranı</th>
                                <th style="padding:10px; text-align:center;">Durum</th>
                            `;
                        }

                        if (rangeMode === 'fund') {
                            const fund = document.getElementById('rangeFundSelect').value;
                            if (!fund) { tbody.innerHTML = `<tr><td colspan="9" style="padding:20px; text-align:center; color:#ff453a;">Lütfen bir fon seçin.</td></tr>`; return; }
                            url += `&fund=${fund}`;
                            labelPrimary = fund;
                        } else {
                            const stock = document.getElementById('rangeStockInput').value.trim().toUpperCase();
                            if (!stock) { tbody.innerHTML = `<tr><td colspan="9" style="padding:20px; text-align:center; color:#ff453a;">Lütfen bir hisse kodu girin.</td></tr>`; return; }
                            url += `&stock=${stock}`;
                            labelPrimary = stock;
                        }

                        try {
                            const resp = await fetch(url);
                            const data = await resp.json();

                            if (data.available_stocks) populateRangeSelectors(data.available_funds, data.available_stocks);

                            const results = data.results || [];
                            const dates   = data.dates   || [];

                            // Update header
                            resHdr.style.display = 'block';
                            document.getElementById('rangeResultTitle').textContent =
                                `${labelPrimary} — ${results.length} kayıt`;
                            document.getElementById('rangeResultSub').textContent =
                                dates.length === 2 ? `${dates[0]}  →  ${dates[1]}` : '';

                            renderRangeTable(results, isTimeline);
                            header.style.display = '';

                        } catch (err) {
                            tbody.innerHTML = `<tr><td colspan="9" style="padding:20px; text-align:center; color:#ff453a;">Hata: ${err.message}</td></tr>`;
                        }
                    }

                    function renderRangeTable(results, isTimeline) {
                        const tbody = document.getElementById('rangeTableBody');
                        tbody.innerHTML = '';

                        if (!results.length) {
                            tbody.innerHTML = `<tr><td colspan="9" style="padding:20px; text-align:center; color:#8e8e93;">Seçilen tarih aralığında değişim bulunamadı.</td></tr>`;
                            return;
                        }

                        const statusMap = isTimeline ? {
                            new:  { label: 'YENİ GİRDİ 🆕', bg: '#30d158', color: '#000' },
                            exit: { label: 'TAMAMEN ÇIKTI ❌', bg: '#ff453a', color: '#fff' },
                            up:   { label: 'ALIM 📈', bg: '#30d15820', color: '#30d158', border: '#30d15840' },
                            down: { label: 'SATIM 📉', bg: '#ff453a20', color: '#ff453a', border: '#ff453a40' },
                            same: { label: 'DEĞİŞMEDİ ➡️', bg: '#8e8e9320', color: '#8e8e93', border: '#8e8e9340' }
                        } : {
                            new:  { label: 'YENİ GİRDİ 🆕', bg: '#30d158', color: '#000' },
                            exit: { label: 'TAMAMEN ÇIKTI ❌', bg: '#ff453a', color: '#fff' },
                            up:   { label: 'ARTIRDI 📈', bg: '#30d15820', color: '#30d158', border: '#30d15840' },
                            down: { label: 'AZALTTI 📉', bg: '#ff453a20', color: '#ff453a', border: '#ff453a40' },
                            same: { label: 'DEĞİŞMEDİ ➡️', bg: '#8e8e9320', color: '#8e8e93', border: '#8e8e9340' }
                        };

                        results.forEach(r => {
                            const st    = statusMap[r.status] || statusMap.same;
                            const sign  = r.diff_lot > 0 ? '+' : '';
                            const diffC = r.diff_lot > 0 ? '#30d158' : r.diff_lot < 0 ? '#ff453a' : '#8e8e93';
                            const primaryLabel = rangeMode === 'fund' ? r.stock : r.fund;
                            const secondaryLabel = rangeMode === 'fund' ? r.company_name : r.fund_name;

                            const badge = `<span style="background:${st.bg}; color:${st.color}; ${st.border ? 'border:1px solid '+st.border+';' : ''} padding:3px 9px; border-radius:7px; font-size:11px; font-weight:800; white-space:nowrap;">${st.label}</span>`;

                            const ratioHtml = isTimeline 
                                ? (r.end_ratio ? '%' + r.end_ratio.toFixed(2) : '—')
                                : `${r.start_ratio ? '%' + r.start_ratio.toFixed(2) : '—'} → ${r.end_ratio ? '%' + r.end_ratio.toFixed(2) : '—'}`;

                            const tr = document.createElement('tr');
                            tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                            
                            let htmlContent = '';
                            if (isTimeline) {
                                htmlContent += `<td style="padding:10px; font-weight:700; color:#8e8e93;">${r.date || '—'}</td>`;
                            }
                            
                            htmlContent += `
                                <td style="padding:10px; font-weight:800; color:#ff9f0a;">${primaryLabel}</td>
                                <td style="padding:10px; font-size:12px; color:#8e8e93; max-width:220px; overflow:hidden; white-space:nowrap;" title="${secondaryLabel}">${secondaryLabel}</td>
                                <td style="padding:10px; text-align:right; font-family:monospace; color:#8e8e93;">${r.start_lot > 0 ? Math.round(r.start_lot).toLocaleString('tr-TR') : '—'}</td>
                                <td style="padding:10px; text-align:right; font-family:monospace;">${r.end_lot > 0 ? Math.round(r.end_lot).toLocaleString('tr-TR') : '—'}</td>
                                <td style="padding:10px; text-align:right; font-family:monospace; color:${diffC}; font-weight:700;">${r.diff_lot !== 0 ? sign + Math.round(r.diff_lot).toLocaleString('tr-TR') : '—'}</td>
                                <td style="padding:10px; text-align:right; font-family:monospace; color:${diffC}; font-weight:700;">${r.pct_change !== 0 ? sign + r.pct_change.toFixed(2) + '%' : '—'}</td>
                                <td style="padding:10px; text-align:right; font-family:monospace; font-size:12px; color:#8e8e93;">${ratioHtml}</td>
                                <td style="padding:10px; text-align:center;">${badge}</td>
                            `;
                            tr.innerHTML = htmlContent;
                            tbody.appendChild(tr);
                        });
                    }

                    function switchTab(tabId) {
                        document.querySelectorAll('.tab-content').forEach(el => {
                            el.classList.add('hidden');
                        });
                        document.getElementById(tabId).classList.remove('hidden');
                        
                        document.querySelectorAll('.tab-btn').forEach(btn => {
                            btn.classList.remove('active');
                        });
                        
                        let btnSelector = '';
                        if (tabId === 'tab-generator') btnSelector = '[onclick="switchTab(\'tab-generator\')"]';
                        else if (tabId === 'tab-calculator') btnSelector = '[onclick="switchTab(\'tab-calculator\')"]';
                        else if (tabId === 'tab-kap') btnSelector = '[onclick="switchTab(\'tab-kap\')"]';
                        
                        const activeBtn = document.querySelector(btnSelector);
                        if (activeBtn) {
                            activeBtn.classList.add('active');
                        }
                    }

                    // Auto load and smart time-based polling on start
                    window.addEventListener('DOMContentLoaded', () => {
                        loadCalculatorState();
                        loadQuoteTweetState();
                        initKapShareholdersTracker();
                        checkAndPoll();
                    });

                    function checkAndPoll() {
                        const now = new Date();
                        const hours = now.getHours();
                        const minutes = now.getMinutes();
                        const totalMinutes = hours * 60 + minutes;
                        
                        const startMinutes = 21 * 60 + 40; // 21:40
                        const endMinutes = 23 * 60;       // 23:00
                        
                        if (totalMinutes >= startMinutes && totalMinutes < endMinutes) {
                            fetchPricesFromExtensionSilently();
                            setTimeout(checkAndPoll, 2000);
                        } else {
                            fetchPricesFromExtensionSilently();
                            setTimeout(checkAndPoll, 60000); // 1 minute
                        }
                    }
                </script>

                <!-- Tweet Preview Modal -->
                <div id="tweet-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:9999; align-items:center; justify-content:center;">
                    <div style="background:#15202b; border-radius:20px; padding:30px; width:560px; max-width:95vw; color:#fff; font-family:sans-serif; box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                        <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
                            <svg width="24" height="24" viewBox="0 0 1200 1227" fill="white"><path d="M714.163 519.284L1160.89 0H1055.03L667.137 450.887L357.328 0H0L468.492 681.821L0 1226.37H105.866L515.491 750.218L842.672 1226.37H1200L714.137 519.284H714.163Z"/></svg>
                            <strong style="font-size:18px;">Tweet Önizleme</strong>
                        </div>
                        <textarea id="tweet-preview-text" style="width:100%; height:200px; background:#192734; color:#fff; border:1px solid #38444d; border-radius:12px; padding:14px; font-size:14px; line-height:1.6; resize:vertical; box-sizing:border-box;"></textarea>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                            <span id="tweet-char-count" style="color:#8899a6; font-size:13px;"></span>
                            <div style="display:flex; gap:10px;">
                                <button onclick="document.getElementById('tweet-modal').style.display='none'" style="background:transparent; color:#fff; border:1px solid #38444d; padding:10px 20px; border-radius:20px; cursor:pointer; font-size:14px;">İptal</button>
                                <button onclick="
                                    const txt = document.getElementById('tweet-preview-text').value;
                                    window.open('https://twitter.com/intent/tweet?text=' + encodeURIComponent(txt), '_blank');
                                    document.getElementById('tweet-modal').style.display='none';
                                " style="background:#1d9bf0; color:#fff; border:none; padding:10px 24px; border-radius:20px; cursor:pointer; font-size:14px; font-weight:700;">X'te Gönder →</button>
                            </div>
                        </div>
                    </div>
                </div>

            </body>
            </html>
            """
            
            # Position Rows HTML Generation
            pos_labels = {
                "inflows": "Para Girişi (Top 5)", 
                "outflows": "Para Çıkışı (Top 5)", 
                "cat_in": "Kategori Giriş (Top 5)", 
                "cat_out": "Kategori Çıkış (Top 5)",
                "inv_in": "Yatırımcı Giriş (Top 5)", 
                "inv_out": "Yatırımcı Kaybı (Top 5)",
                "top_gainers": "En Çok Kazandıranlar", 
                "top_losers": "En Çok Kaybedenler",
                "tracked": "Takipteki Fonlar", 
                "comparison_chart": "📈 Fon Karşılaştırma Grafiği",
                "flow_chart": "📈 Kümülatif Para Giriş Grafiği",
                "investor_chart": "👥 Kümülatif Yatırımcı Grafiği",
                "per_investor_value": "Kişi Başı Yatırım Değeri",
                "fund_report": "Fon Karnesi",
                "predictions": "Tahminler (Serbest Bölüm)", 
                "portfolio_diff": "Portföy Değişimleri",
                "holdings_breakdown": "Fon İçi Etki Analizi",
                "fund_takas_diff": "🏢 Yatırım Fonları Takas Fark Analizi",
                "fund_takas_diff_pct": "📊 Yatırım Fonları Takas Oran Değişim Analizi"
            }
            pos_rows_html = ""
            for key, label in pos_labels.items():
                r, c = pget(key, "R"), pget(key, "C")
                is_checked = "checked" if key in def_sections else ""
                
                # Özel fon kodu input'u sadece portfolio_diff için
                extra_input = ""
                if key == "portfolio_diff":
                    def_port_fund = db_config.get("portfolio_diff_fund", "PHE")
                    def_port_cols = db_config.get("portfolio_diff_cols", 1)
                    extra_input = f'''
                    <input type="text" id="portfolioDiffFund" value="{def_port_fund}" style="width:70px; margin-left:10px; padding:6px; font-size:12px;" placeholder="PHE">
                    <select id="portfolioDiffCols" style="width:70px; margin-left:5px; padding:6px; font-size:12px;">
                        <option value="1" {"selected" if def_port_cols == 1 else ""}>1 Sütun</option>
                        <option value="2" {"selected" if def_port_cols == 2 else ""}>2 Sütun</option>
                    </select>
                    '''
                elif key == "fund_report":
                    def_fund_report = db_config.get("fund_report_fund", "PHE")
                    extra_input = f'''
                    <input type="text" id="fundReportFund" value="{def_fund_report}" style="width:70px; margin-left:10px; padding:6px; font-size:12px;" placeholder="PHE">
                    '''
                    
                pos_rows_html += f"""
                <div class="pos-row">
                    <div class="pos-label">
                        <input type="checkbox" id="chk-{key}" {is_checked} style="width:auto; margin-right:8px;"> {label} {extra_input}
                    </div>
                    <input type="number" id="pos-{key}-r" class="pos-input" value="{r}">
                    <input type="number" id="pos-{key}-c" class="pos-input" value="{c}">
                </div>
                """
            html = html.replace("{{POS_ROWS_HTML}}", pos_rows_html)

            # Prediction rows
            pred_rows_html = ""
            saved_preds = db_config.get("predictions", [])
            if not saved_preds:
                saved_preds = [{"code": "", "val": "", "desc": ""}]
            for p in saved_preds:
                pred_rows_html += f"""
                <div class="pred-row">
                    <input type="text" class="pred-code" value="{p.get('code', '')}" placeholder="KOD">
                    <input type="text" class="pred-val" value="{p.get('val', '')}" placeholder="%2,5">
                    <input type="text" class="pred-desc" value="{p.get('desc', '')}" placeholder="Açıklama...">
                    <button class="remove-btn" onclick="this.parentElement.remove()">✕</button>
                </div>
                """
            html = html.replace("{{PRED_ROWS}}", pred_rows_html)

            # Standard replacements
            html = html.replace("{{TRACKED_FUNDS}}", str(def_tracked_funds))
            html = html.replace("{{BG_URL}}", str(def_bg_url))
            html = html.replace("{{MAIN_TITLE}}", str(def_main_title))
            html = html.replace("{{SUB_TITLE}}", str(def_sub_title))
            html = html.replace("{{GRID_COLS}}", str(def_grid_cols))
            html = html.replace("{{TRACKED_GRID_COLS}}", str(def_tracked_grid_cols))
            html = html.replace("{{CANVAS_WIDTH}}", str(def_canvas_width))
            html = html.replace("{{ITEM_FONT_SIZE}}", str(def_item_font_size))
            html = html.replace("{{PERIOD_FONT_SIZE}}", str(def_period_font_size))
            html = html.replace("{{TCODE_FONT_SIZE}}", str(def_tcode_font_size))
            html = html.replace("{{CUSTOM_START_DATE}}", str(def_custom_start_date))
            html = html.replace("{{CUSTOM_END_DATE}}", str(def_custom_end_date))
            # Removed standard SHOW_CHART_CHECKED as it's now a section
            html = html.replace("{{PRED_SECTION_TITLE}}", str(def_pred_title))
            
            html = html.replace("{{SEL_WM_BOTTOM}}", "selected" if def_wm_anchor == "bottom" else "")
            html = html.replace("{{SEL_WM_INFLOWS}}", "selected" if def_wm_anchor == "inflows" else "")
            html = html.replace("{{SEL_WM_OUTFLOWS}}", "selected" if def_wm_anchor == "outflows" else "")
            html = html.replace("{{SEL_SORT_TL}}", "selected" if def_sort_mode == "tl" else "")
            html = html.replace("{{SEL_SORT_PCT}}", "selected" if def_sort_mode == "pct" else "")

            html = html.replace("{{SEL_PRED_COL_1}}", "selected" if db_config.get("pred_cols", 1) == 1 else "")
            html = html.replace("{{SEL_PRED_COL_2}}", "selected" if db_config.get("pred_cols", 1) == 2 else "")
            
            self.wfile.write(html.encode("utf-8"))
            return
        
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/prices/extension':
            from datetime import datetime
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            prices = req_data.get('prices', [])
            
            prices_file = os.path.join(DIRECTORY, "fintables_prices.json")
            stored_prices = {}
            if os.path.exists(prices_file):
                try:
                    with open(prices_file, "r", encoding="utf-8") as f:
                        stored_prices = json.load(f)
                except:
                    pass
            
            for item in prices:
                code = str(item.get("code", "")).strip().upper()
                if not code:
                    continue
                stored_prices[code] = {
                    "price": float(item.get("price", 0.0)),
                    "changePercent": float(item.get("changePercent", 0.0)) if item.get("changePercent") is not None else None,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
            with open(prices_file, "w", encoding="utf-8") as f:
                json.dump(stored_prices, f, ensure_ascii=False, indent=4)
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "count": len(prices)}).encode("utf-8"))
            return

        if self.path == '/api/kap/shareholders/manual':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            
            date_str = req_data.get('date', '').strip()
            fund_code = req_data.get('fund', '').strip().upper()
            stock_code = req_data.get('stock', '').strip().upper()
            lot_val = float(req_data.get('lot', 0.0))
            ratio_val = float(req_data.get('ratio', 0.0))
            
            if not date_str or not fund_code or not stock_code:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Geçersiz parametreler."}).encode("utf-8"))
                return
                
            db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
            history = {}
            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except:
                    pass
                    
            if date_str not in history:
                history[date_str] = {}
            if fund_code not in history[date_str]:
                history[date_str][fund_code] = {}
                
            history[date_str][fund_code][stock_code] = {
                "lot": lot_val,
                "ratio": ratio_val,
                "is_manual": True,
                "shareholder_name": "MANUEL GİRİŞ",
                "company_name": "MANUEL GİRİŞ"
            }
            
            try:
                with open(db_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=4)
                success = True
                error_msg = ""
            except Exception as e:
                success = False
                error_msg = str(e)
                
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "error": error_msg}).encode("utf-8"))
            return

        if self.path == '/api/save_takas':
            from datetime import datetime
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            rows = req_data.get('rows', [])
            dates = req_data.get('dates', {})
            
            # Map exact dates from extension, fallback to estimated or today
            base_date_str = dates.get("today")
            if not base_date_str:
                base_date_str = datetime.now().strftime("%Y-%m-%d")
                
            dates_mapping = {
                "today": base_date_str,
                "yesterday": dates.get("yesterday") or base_date_str,
                "weekly": dates.get("weekly") or base_date_str,
                "monthly": dates.get("monthly") or base_date_str,
                "three_month": dates.get("three_month") or base_date_str,
            }
            
            db_path = os.path.join(DIRECTORY, "fintables_history.json")
            history = {}
            if os.path.exists(db_path):
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except:
                    pass
                    
            for d_str in dates_mapping.values():
                if d_str not in history:
                    history[d_str] = {}
                    
            for r in rows:
                code = r.get("code")
                lot = float(r.get("lot", 0.0))
                val = float(r.get("val", 0.0))
                price = (val / lot) if lot > 0 else 0.0
                
                daily_chg = float(r.get("daily_chg", 0.0))
                weekly_chg = float(r.get("weekly_chg", 0.0))
                monthly_chg = float(r.get("monthly_chg", 0.0))
                three_month_chg = float(r.get("three_month_chg", 0.0))
                
                if not code or lot <= 0:
                    continue
                    
                # Today
                history[dates_mapping["today"]][code] = {
                    "lot": lot,
                    "val": val,
                    "price": price
                }
                
                # Yesterday
                if dates.get("yesterday"):
                    lot_y = lot - daily_chg
                    if lot_y > 0:
                        history[dates_mapping["yesterday"]][code] = {
                            "lot": lot_y,
                            "val": lot_y * price,
                            "price": price
                        }
                    
                # Weekly
                if dates.get("weekly"):
                    lot_w = lot - weekly_chg
                    if lot_w > 0:
                        history[dates_mapping["weekly"]][code] = {
                            "lot": lot_w,
                            "val": lot_w * price,
                            "price": price
                        }
                    
                # Monthly
                if dates.get("monthly"):
                    lot_m = lot - monthly_chg
                    if lot_m > 0:
                        history[dates_mapping["monthly"]][code] = {
                            "lot": lot_m,
                            "val": lot_m * price,
                            "price": price
                        }
                    
                # Three Month
                if dates.get("three_month"):
                    lot_3m = lot - three_month_chg
                    if lot_3m > 0:
                        history[dates_mapping["three_month"]][code] = {
                            "lot": lot_3m,
                            "val": lot_3m * price,
                            "price": price
                        }
            
            if rows:
                with open(db_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=4)
                    
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": f"Successfully saved {len(rows)} rows for {base_date_str} to database."}).encode('utf-8'))
            return

        if self.path == '/api/generate':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            
            # Extract and map fields
            period = req_data.get('period', 'daily')
            tracked_funds = req_data.get('tracked_funds', 'TLY, DFI, PHE')
            bg_url = req_data.get('bg_url', '')
            sections = req_data.get('sections', 'inflows,outflows,cat_in,cat_out,inv_in,inv_out,divergent,momentum,crowding,category_rotation,tracked,tracked_rs,manager_actions,portfolio_diff,per_investor_value,fund_takas_diff')
            selected_categories = req_data.get('selected_categories', 'Hisse Senedi,Değişken,Karma,Borçlanma Araçları,Katılım,Para Piy.,Serbest')
            grid_cols = req_data.get('grid_cols', '2')
            sort_mode = req_data.get('sort_mode', 'tl')
            canvas_width = req_data.get('canvas_width', 1600)
            tracked_grid_cols = req_data.get('tracked_grid_cols', '1')
            item_font_size = req_data.get('item_font_size', 25)
            period_font_size = req_data.get('period_font_size', 25)
            tcode_font_size = req_data.get('tcode_font_size', 38)
            show_chart = req_data.get('show_chart', False)
            watermark_anchor = req_data.get('watermark_anchor', 'bottom')
            main_title_custom = req_data.get('main_title', '')
            subtitle_custom = req_data.get('subtitle', '')
            header_show_main = req_data.get('header_show_main', True)
            header_show_sub = req_data.get('header_show_sub', True)
            pred_title = req_data.get('pred_title', 'Getiri Tahmini')
            pred_cols = int(req_data.get('pred_cols', 1))
            portfolio_diff_fund = req_data.get('portfolio_diff_fund', 'PHE')
            portfolio_diff_cols = int(req_data.get('portfolio_diff_cols', 1))
            fund_report_fund = req_data.get('fund_report_fund', 'PHE')
            custom_start_date = req_data.get('custom_start_date', '')
            custom_end_date = req_data.get('custom_end_date', '')
            predictions = req_data.get('predictions', [])
            positions = req_data.get('positions', {})
            
            # Save settings
            CONFIG_FILE = os.path.join(DIRECTORY, "dashboard_config.json")
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "tracked_funds": tracked_funds, "bg_url": bg_url,
                    "main_title": main_title_custom, "subtitle": subtitle_custom,
                    "grid_cols": int(grid_cols), "sort_mode": sort_mode,
                    "canvas_width": int(canvas_width), "tracked_grid_cols": int(tracked_grid_cols),
                    "item_font_size": int(item_font_size), "period_font_size": int(period_font_size),
                    "tcode_font_size": int(tcode_font_size),
                    "show_chart": bool(show_chart),
                    "watermark_anchor": watermark_anchor, "header_show_main": header_show_main,
                    "header_show_sub": header_show_sub, "pred_title": pred_title, "pred_cols": pred_cols,
                    "custom_start_date": custom_start_date,
                    "custom_end_date": custom_end_date,
                    "portfolio_diff_fund": portfolio_diff_fund,
                    "portfolio_diff_cols": int(req_data.get('portfolio_diff_cols', 1)),
                    "fund_report_fund": fund_report_fund,
                    "predictions": predictions, "positions": positions
                }, f)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            try:
                # 1. Run Data Fetcher
                # Ensure data fetcher runs if any Tefas section is requested
                tefas_sections = ["inflows", "outflows", "cat_in", "cat_out", "inv_in", "inv_out", "divergent", "momentum", "crowding", "category_rotation", "tracked", "tracked_rs", "manager_actions", "portfolio_diff", "per_investor_value", "fund_report", "top_gainers", "top_losers", "comparison_chart", "return_chart", "flow_chart", "investor_chart"]
                section_list = sections.split(",")
                needs_data = any(s in section_list for s in tefas_sections)
                
                if needs_data:
                    # If portfolio_diff is active, make sure that fund is in tracked_funds so it is fetched properly
                    current_tracked = [t.strip().upper() for t in tracked_funds.split(',') if t.strip()]
                    priority_funds = []
                    if "fund_report" in section_list and fund_report_fund.strip():
                        priority_funds.append(fund_report_fund.upper())
                    if "portfolio_diff" in section_list and portfolio_diff_fund.strip():
                        priority_funds.append(portfolio_diff_fund.upper())
                    for target_code in reversed(priority_funds):
                        current_tracked = [t for t in current_tracked if t != target_code]
                        current_tracked.insert(0, target_code)
                    tracked_funds = ", ".join(current_tracked)

                    print(f"Running data fetcher for {period}...")
                    cmd = ["python", os.path.join(DIRECTORY, "data_fetcher.py"), period, tracked_funds, selected_categories, "--sort", sort_mode]
                    if custom_start_date and custom_end_date:
                        cmd.extend(["--start-date", custom_start_date, "--end-date", custom_end_date])
                    subprocess.run(cmd, check=True)
                
                # Write runtime config
                runtime_path = os.path.join(DIRECTORY, "runtime_config.json")
                print(f"DEBUG: Sections to generate: {sections}")
                print(f"DEBUG: Background URL: {bg_url}")
                print(f"DEBUG: Writing runtime config to {runtime_path} with encoding utf-8")
                with open(runtime_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "bg_url": bg_url, "sections": sections.split(","),
                        "grid_cols": int(grid_cols), "tracked_grid_cols": int(tracked_grid_cols),
                        "watermark_anchor": watermark_anchor, "main_title": main_title_custom,
                        "subtitle": subtitle_custom, "header_show_main": header_show_main,
                        "header_show_sub": header_show_sub, "pred_title": pred_title,
                        "custom_start_date": custom_start_date,
                        "custom_end_date": custom_end_date,
                        "portfolio_diff_fund": portfolio_diff_fund,
                        "portfolio_diff_cols": portfolio_diff_cols,
                        "fund_report_fund": fund_report_fund,
                        "pred_cols": pred_cols,
                        "canvas_width": int(canvas_width), "item_font_size": int(item_font_size),
                        "period_font_size": int(period_font_size), "tcode_font_size": int(tcode_font_size),
                        "positions": positions,
                        "predictions": predictions
                    }, f, ensure_ascii=False)
                
                # 2. Run Image Generator
                print("Running image generator...")
                subprocess.run(["python", os.path.join(DIRECTORY, "image_generator.py")], check=True)
                
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            except Exception as e:
                print(f"Error: {e}")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        if self.path == '/api/fetch-holdings':
            import urllib.request as _req
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            fund_code  = req_data.get('fund_code', 'TLY').strip().upper()
            fon_toplam = str(req_data.get('fon_toplam', '')).strip()
            top_n      = str(req_data.get('top_n', '5')).strip()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            try:
                url = f"http://localhost:3032/api/portfolio/{fund_code}/top-holdings?topN={top_n}"
                if fon_toplam:
                    url += f"&fonToplam={fon_toplam}"
                print(f"[fetch-holdings] Fetching: {url}")
                with _req.urlopen(url, timeout=30) as resp:
                    holdings = json.loads(resp.read().decode('utf-8'))
                data_path = os.path.join(DIRECTORY, "data.json")
                with open(data_path, "r", encoding="utf-8") as f:
                    data_json = json.load(f)
                data_json["holdings_breakdown"] = holdings
                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump(data_json, f, ensure_ascii=False, indent=2)
                print(f"[fetch-holdings] OK: {holdings.get('item_count', 0)} items for {fund_code}")
                self.wfile.write(json.dumps({
                    "success": True,
                    "fund_code": fund_code,
                    "item_count": holdings.get("item_count", 0),
                    "fetched_at": holdings.get("fetched_at", "")
                }, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                print(f"[fetch-holdings] Error: {e}")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return

        if self.path == '/api/fetch-predictions':
            import urllib.request as _req
            import concurrent.futures
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            funds_raw = req_data.get('funds', 'TLY, DFI, PHE').strip()
            batch_size = int(req_data.get('batch_size', 5))
            timeout_per_batch = int(req_data.get('timeout', 45))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()

            try:
                fund_list = [f.strip().upper() for f in funds_raw.replace(',', ' ').split() if f.strip()]
                batches = [fund_list[i:i+batch_size] for i in range(0, len(fund_list), batch_size)]

                def fetch_batch(batch):
                    batch_str = ','.join(batch)
                    encoded = urllib.parse.quote(batch_str)
                    url = f"http://localhost:3032/api/portfolio/all-predictions?funds={encoded}"
                    print(f"[fetch-predictions] → {batch_str}")
                    try:
                        with _req.urlopen(url, timeout=timeout_per_batch) as resp:
                            res_data = json.loads(resp.read().decode('utf-8'))
                            preds = res_data.get("predictions", [])
                            print(f"[fetch-predictions] ✓ {batch_str}: {len(preds)} predictions")
                            return preds, None
                    except Exception as e:
                        print(f"[fetch-predictions] ✗ {batch_str}: {e}")
                        return [], batch_str

                all_predictions = []
                failed_batches = []

                # Tüm batch'leri aynı anda (paralel) ateşle
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(batches)) as executor:
                    futures = {executor.submit(fetch_batch, batch): batch for batch in batches}
                    for future in concurrent.futures.as_completed(futures):
                        preds, failed = future.result()
                        all_predictions.extend(preds)
                        if failed:
                            failed_batches.append(failed)

                result = {
                    "success": True,
                    "predictions": all_predictions,
                    "total": len(all_predictions),
                    "batches_total": len(batches),
                    "batches_failed": len(failed_batches),
                }
                if failed_batches:
                    result["warning"] = f"Başarısız batch'ler: {' | '.join(failed_batches)}"
                print(f"[fetch-predictions] Done: {len(all_predictions)} total, {len(failed_batches)} failed batches")
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                print(f"[fetch-predictions] Fatal: {e}")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
            return


def pget(key, sub):
    CONFIG_FILE = os.path.join(DIRECTORY, "dashboard_config.json")
    if not os.path.exists(CONFIG_FILE): return "1"
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            pos = cfg.get("positions", {}).get(key, "1,1")
            return pos.split(",")[0 if sub=="R" else 1]
    except: return "1"

def start_capitals_updater():
    import time
    from datetime import datetime, timedelta
    import threading
    import subprocess
    db_path = os.path.join(DIRECTORY, "bist_capitals.json")
    script_path = os.path.join(DIRECTORY, "build_capitals_db.py")
    
    # 1. First run: if capitals file doesn't exist, build it immediately in background
    if not os.path.exists(db_path) and os.path.exists(script_path):
        def first_run():
            print("No BIST capitals file found. Building immediately in background...")
            try:
                subprocess.run(["python", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Initial BIST capitals database built successfully!")
            except Exception as e:
                print(f"Failed to build initial capitals database: {e}")
        threading.Thread(target=first_run, daemon=True).start()

    # 2. Start daily scheduler thread
    def run_loop():
        if not os.path.exists(script_path):
            return
        while True:
            now = datetime.now()
            target_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += timedelta(days=1)
                
            seconds_to_wait = (target_time - now).total_seconds()
            print(f"[Capitals Updater] Next daily KAP update scheduled at {target_time.strftime('%Y-%m-%d %H:%M:%S')} (waiting {seconds_to_wait:.1f}s)")
            
            # Sleep in 60s intervals to remain responsive
            slept = 0
            while slept < seconds_to_wait:
                time.sleep(min(60, seconds_to_wait - slept))
                slept += 60
                
            print("Updating bist_capitals.json daily at 10:00 AM from KAP...")
            try:
                subprocess.run(["python", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Daily KAP capitals database updated successfully!")
            except Exception as e:
                print(f"Failed to update daily capitals database: {e}")
                
    threading.Thread(target=run_loop, daemon=True).start()

def start_kap_shareholders_updater():
    import time
    from datetime import datetime, timedelta
    import threading
    import subprocess
    
    db_path = os.path.join(DIRECTORY, "kap_shareholders_history.json")
    script_path = os.path.join(DIRECTORY, "scrape_kap_shareholders.py")
    
    # 1. First run: if today's data is missing in history, run the scraper immediately
    today_str = datetime.now().strftime("%Y-%m-%d")
    needs_run = True
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                if today_str in history:
                    needs_run = False
        except:
            pass
            
    if needs_run and os.path.exists(script_path):
        def first_run():
            print("Today's KAP shareholder data is missing. Scraping immediately in background...")
            try:
                subprocess.run(["python", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Initial daily KAP shareholder data scraped successfully!")
            except Exception as e:
                print(f"Failed to run initial KAP shareholder scraper: {e}")
        threading.Thread(target=first_run, daemon=True).start()

    # 2. Start daily scheduler thread
    def run_loop():
        if not os.path.exists(script_path):
            return
        while True:
            now = datetime.now()
            target_time = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += timedelta(days=1)
                
            seconds_to_wait = (target_time - now).total_seconds()
            print(f"[KAP Shareholders Updater] Next daily update scheduled at {target_time.strftime('%Y-%m-%d %H:%M:%S')} (waiting {seconds_to_wait:.1f}s)")
            
            slept = 0
            while slept < seconds_to_wait:
                time.sleep(min(60, seconds_to_wait - slept))
                slept += 60
                
            print("Running daily KAP shareholder scraper at 11:00 AM...")
            try:
                subprocess.run(["python", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Daily KAP shareholder data updated successfully!")
            except Exception as e:
                print(f"Failed to run daily KAP shareholder scraper: {e}")
                
    threading.Thread(target=run_loop, daemon=True).start()

def start_server():
    start_capitals_updater()
    start_kap_shareholders_updater()
    with socketserver.TCPServer(("", PORT), WebServerHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
