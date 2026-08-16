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
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #121214; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; min-height: 100vh; margin: 0; padding: 60px 20px; }
                    .card { background: #1c1c1e; padding: 50px; border-radius: 30px; text-align: left; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 20px 60px rgba(0,0,0,0.6); width: 1000px; max-width: 95%; }
                    h1 { margin-top: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.5px; text-align: center; width: 100%; margin-bottom: 8px; }
                    .subtitle-p { color: #8e8e93; font-size: 17px; margin-bottom: 45px; text-align: center; width: 100%; }
                    
                    .dashboard-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 50px; }
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

                    <div class="dashboard-grid">
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
                    </div>

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
                    </div>
                </div>

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

                        const rows = document.querySelectorAll('.pred-row');
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
                        ['inflows', 'outflows', 'cat_in', 'cat_out', 'inv_in', 'inv_out', 'divergent', 'momentum', 'crowding', 'category_rotation', 'tracked', 'tracked_rs', 'manager_actions', 'predictions', 'portfolio_diff', 'per_investor_value', 'fund_report', 'top_gainers', 'top_losers', 'comparison_chart', 'return_chart', 'holdings_breakdown', 'flow_chart', 'investor_chart', 'fund_takas_diff'].forEach(s => {
                            const chk = document.getElementById('chk-' + s);
                            if (chk && chk.checked) sections.push(s);
                        });
                        
                        // Prediction Rows
                        const predictions = [];
                        document.querySelectorAll('.pred-row').forEach(row => {
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
                        ['inflows', 'outflows', 'cat_in', 'cat_out', 'inv_in', 'inv_out', 'divergent', 'momentum', 'crowding', 'category_rotation', 'tracked', 'tracked_rs', 'manager_actions', 'predictions', 'portfolio_diff', 'per_investor_value', 'fund_report', 'top_gainers', 'top_losers', 'comparison_chart', 'return_chart', 'holdings_breakdown', 'flow_chart', 'investor_chart', 'fund_takas_diff'].forEach(s => {
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
                "fund_takas_diff": "🏢 Yatırım Fonları Takas Fark Analizi"
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

    def do_POST(self):
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
                tefas_sections = ["inflows", "outflows", "cat_in", "cat_out", "inv_in", "inv_out", "divergent", "momentum", "crowding", "category_rotation", "tracked", "tracked_rs", "manager_actions", "portfolio_diff", "per_investor_value", "fund_report", "top_gainers", "top_losers", "comparison_chart", "return_chart", "flow_chart", "investor_chart", "fund_takas_diff"]
                section_list = sections.split(",")
                needs_data = any(s in section_list for s in tefas_sections)
                
                if "fund_takas_diff" in section_list:
                    print("Running fintables_history_fetcher.py to fetch today's data...")
                    cmd_ft = ["python", os.path.join(DIRECTORY, "fintables_history_fetcher.py")]
                    subprocess.run(cmd_ft)
                
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

def start_server():
    with socketserver.TCPServer(("", PORT), WebServerHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
