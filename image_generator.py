import os
import json
import asyncio
import subprocess
from playwright.async_api import async_playwright
from datetime import datetime

# Translation/Formatting Helpers
def format_money(val):
    sign = "+" if val >= 0 else "-"
    abs_val = abs(val)
    # Full value format: +₺639.945.848
    v_str = f"{abs_val:,.0f}".replace(",", ".")
    return f"{sign}₺{v_str}"

def format_pct(val, decimals=2):
    fmt = "{:." + str(decimals) + "f}%"
    return fmt.format(val).replace(".", ",")

def format_turkish_date(date_str):
    months = {
        "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan",
        "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos",
        "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık"
    }
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return f"{dt.day} {months[dt.strftime('%m')]} {dt.year}"
        except:
            pass
    return date_str

calculated_takas_date_range = ""
calculated_takas_pct_date_range = ""

def format_custom_period_label(start_date, end_date):
    if not start_date or not end_date:
        return "Özel Aralık"
    parsed_start = None
    parsed_end = None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            if not parsed_start:
                parsed_start = datetime.strptime(start_date, fmt)
        except:
            pass
        try:
            if not parsed_end:
                parsed_end = datetime.strptime(end_date, fmt)
        except:
            pass
    if parsed_start and parsed_end:
        return f"{parsed_start.strftime('%d.%m.%Y')} - {parsed_end.strftime('%d.%m.%Y')}"
    return "Özel Aralık"

def generate_fund_list_html(funds, is_inflow=True, sort_mode='tl'):
    html = ""
    for f in funds:
        trend_class = "trend-up" if is_inflow else "trend-down"
        val = f['net_flow'] if 'net_flow' in f else f.get('return_pct', 0)
        
        if sort_mode == 'tl' and 'net_flow' in f:
            val_str = format_money(val)
            pct_val = f.get('flow_pct', f.get('return_pct', 0))
            # Resim 1 style: (+1,17%)
            sign = "+" if pct_val >= 0 else "" # format_pct might handle or we add manually
            pct_str = f"({sign}{format_pct(pct_val)})"
        else:
            val_str = format_pct(f.get('return_pct', 0))
            pct_str = ""
            
        name = f.get('name', f.get('fund_name', ''))
        
        html += f"""
        <li class="fund-item">
            <div class="f-left">
                <span class="f-code">{f['fund_code']}</span>
                <span class="f-name">{name}</span>
            </div>
            <div class="f-right">
                <span class="f-val {trend_class}">{val_str}</span>
                <span class="f-pct {trend_class}">{pct_str}</span>
            </div>
        </li>
        """
    return html

def generate_investor_list_html(funds):
    html = ""
    for f in funds:
        inv_pct = f.get('inv_change_pct', 0)   # was: 'inv_pct' — field is saved as 'inv_change_pct' by data_fetcher
        inv_change = f.get('inv_change', 0)
        val_class = "trend-up" if inv_change >= 0 else "trend-down"
        inv_str = f"{inv_change:+d}"
        pct_prefix = "+" if inv_pct >= 0 else ""
        
        name = f.get('name', f.get('fund_name', ''))
        
        html += f"""
        <li class="fund-item">
            <div class="f-left">
                <span class="f-code">{f['fund_code']}</span>
                <span class="f-name">{name}</span>
            </div>
            <div class="f-right">
                <div class="val {val_class}">{inv_str} Kişi</div>
                <div class="pct {val_class}">({pct_prefix}{format_pct(inv_pct)})</div>
            </div>
        </li>
        """
    return html

def generate_predictions_html(predictions):
    html = ""
    for p in predictions:
        code = p.get('code', '').upper()
        val = p.get('val', '')
        desc = p.get('desc', '')
        if not code and not val: continue
        
        # Resim 1 & 2 style: Dark background, stacked code and desc
        val_str = val if "%" in val else f"%{val}"
        
        # Check if negative for coloring
        is_negative = "-" in val
        trend_class = "trend-down" if is_negative else "trend-up"
        
        html += f"""
        <div class="pred-item fund-item">
            <div class="f-left">
                <span class="f-code">{code}</span>
                <span class="f-name">{desc}</span>
            </div>
            <div class="f-right">
                <span class="f-val {trend_class}">{val_str}</span>
            </div>
        </div>
        """
    return html

def generate_portfolio_diff_html(diffs_dict, config):
    html = ""
    if not diffs_dict: return html
    
    # Target the specific fund from config
    target_fund = config.get("portfolio_diff_fund", "").upper()
    cols = int(config.get("portfolio_diff_cols", 1))
    
    # Fallback only when no specific fund was requested
    if not target_fund:
        target_fund = list(diffs_dict.keys())[0] if diffs_dict else None
    elif target_fund not in diffs_dict:
        return f'<div class="fund-list"><li class="fund-item"><div class="f-left"><span class="f-name">{target_fund} için portföy dağılım verisi alınamadı.</span></div></li></div>'
        
    if not target_fund:
        return ""
        
    data = diffs_dict[target_fund]
    if isinstance(data, dict):
        allocations = data.get("allocations", [])
    elif isinstance(data, list):
        allocations = data
    else:
        allocations = []
    
    def get_item_html(alloc):
        asset = alloc.get("asset") or alloc.get("asset_name", "")
        w = alloc.get("weight", 0)
        d = alloc.get("diff", 0)
        
        if abs(d) < 0.01:
            diff_str = "(-)"
            trend_class = "trend-neutral"
        else:
            sign = "+" if d > 0 else ""
            diff_str = f"({sign}%{d:.2f})".replace(".", ",")
            trend_class = "trend-up" if d > 0 else "trend-down"
            
        weight_str = f"%{w:.2f}".replace(".", ",")
        
        return f"""
        <li class="fund-item portfolio-fund-item">
            <div class="f-left">
                <span class="f-name">{asset}</span>
            </div>
            <div class="f-right">
                <span class="f-val">{weight_str}</span>
                <span class="f-pct {trend_class}">{diff_str}</span>
            </div>
        </li>
        """

    if cols == 2 and len(allocations) > 1:
        # Split into two columns
        mid = (len(allocations) + 1) // 2
        col1 = allocations[:mid]
        col2 = allocations[mid:]
        
        html = '<div class="portfolio-grid-2col">'
        html += '<ul class="fund-list">' + "".join([get_item_html(a) for a in col1]) + '</ul>'
        html += '<ul class="fund-list">' + "".join([get_item_html(a) for a in col2]) + '</ul>'
        html += '</div>'
    else:
        html = '<ul class="fund-list">' + "".join([get_item_html(a) for a in allocations]) + '</ul>'
        
    return html

def generate_top_returns_html(funds, is_gainer=True):
    html = ""
    for f in funds:
        ret = f.get('return_pct', 0)
        trend_class = "trend-up" if ret >= 0 else "trend-down"
        sign = "+" if ret >= 0 else ""
        ret_str = f"{sign}{format_pct(ret, 2)}"
        name = f.get('name', '')
        
        html += f"""
        <li class="fund-item">
            <div class="f-left">
                <span class="f-code">{f['fund_code']}</span>
                <span class="f-name">{name}</span>
            </div>
            <div class="f-right">
                <span class="f-val {trend_class}">{ret_str}</span>
            </div>
        </li>
        """
    return html


def clean_footer_note(note):
    if not note:
        return "* Veriler TEFAS üzerinden alınmıştır."

    replacements = {
        "De?i?ken": "Değişken",
        "Bor?lanma Ara?lar?": "Borçlanma Araçları",
        "Kat?l?m": "Katılım",
        "D?viz": "Döviz",
        "üzerinden al?nm??t?r": "üzerinden alınmıştır",
    }
    for old, new in replacements.items():
        note = note.replace(old, new)
    return note

def generate_divergent_signals_html(signals):
    html = ""
    for s in signals:
        ret = s.get('return_pct', 0)
        flow = s.get('flow_pct', 0)
        inv_pct = s.get('inv_change_pct', 0)
        ret_class = "trend-up" if ret >= 0 else "trend-down"
        flow_class = "trend-up" if flow >= 0 else "trend-down"
        inv_class = "trend-up" if inv_pct >= 0 else "trend-down"
        ret_str = f"{'+' if ret >= 0 else ''}{format_pct(ret, 2)}"
        flow_str = f"Para Giri\u015f/\u00c7\u0131k\u0131\u015f\u0131 {'+' if flow >= 0 else ''}{format_pct(flow, 2)}"
        flow_str = f"Para Giriş/Çıkışı {'+' if flow >= 0 else ''}{format_pct(flow, 2)}"
        inv_str = f"Yat. {'+' if inv_pct >= 0 else ''}{format_pct(inv_pct, 2)}"

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{s.get('fund_code', '')}</span>
                    <span class="signal-fund-name">{s.get('name', '')}</span>
                </div>
                <span class="f-name">{s.get('signal_title', '')}</span>
            </div>
            <div class="f-right">
                <span class="f-val {ret_class}">{ret_str}</span>
                <span class="f-pct {flow_class}">{flow_str}</span>
                <span class="signal-meta {inv_class}">{inv_str}</span>
            </div>
        </li>
        """
    return html

def generate_momentum_scores_html(items):
    html = ""
    for s in items:
        score = s.get('momentum_score', 0)
        score_class = "trend-up" if score >= 50 else "trend-down"
        score_str = f"Skor {score:.1f}".replace(".", ",")
        flow_str = f"Para Giriş/Çıkışı {'+' if s.get('flow_pct', 0) >= 0 else ''}{format_pct(s.get('flow_pct', 0), 2)}"
        meta_str = f"Getiri {'+' if s.get('return_pct', 0) >= 0 else ''}{format_pct(s.get('return_pct', 0), 2)} | Yat. {'+' if s.get('inv_change_pct', 0) >= 0 else ''}{format_pct(s.get('inv_change_pct', 0), 2)}"
        flow_class = "trend-up" if s.get('flow_pct', 0) >= 0 else "trend-down"

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{s.get('fund_code', '')}</span>
                    <span class="signal-fund-name">{s.get('name', '')}</span>
                </div>
                <span class="f-name">Akıllı Momentum Skoru</span>
            </div>
            <div class="f-right">
                <span class="f-val {score_class}">{score_str}</span>
                <span class="f-pct {flow_class}">{flow_str}</span>
                <span class="signal-meta">{meta_str}</span>
            </div>
        </li>
        """
    return html

def generate_crowding_signals_html(items):
    html = ""
    for s in items:
        flow_class = "trend-up" if s.get('flow_pct', 0) >= 0 else "trend-down"
        inv_class = "trend-up" if s.get('inv_change_pct', 0) >= 0 else "trend-down"
        ret_class = "trend-up" if s.get('return_pct', 0) >= 0 else "trend-down"
        ret_str = f"{'+' if s.get('return_pct', 0) >= 0 else ''}{format_pct(s.get('return_pct', 0), 2)}"
        flow_str = f"Para Giriş/Çıkışı {'+' if s.get('flow_pct', 0) >= 0 else ''}{format_pct(s.get('flow_pct', 0), 2)}"
        inv_str = f"Yat. {'+' if s.get('inv_change_pct', 0) >= 0 else ''}{format_pct(s.get('inv_change_pct', 0), 2)}"

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{s.get('fund_code', '')}</span>
                    <span class="signal-fund-name">{s.get('name', '')}</span>
                </div>
                <span class="f-name">{s.get('signal_title', '')}</span>
            </div>
            <div class="f-right">
                <span class="f-val {ret_class}">{ret_str}</span>
                <span class="f-pct {flow_class}">{flow_str}</span>
                <span class="signal-meta {inv_class}">{inv_str}</span>
            </div>
        </li>
        """
    return html

def generate_category_rotation_html(items):
    html = ""
    for s in items:
        flow_class = "trend-up" if s.get('flow_pct', 0) >= 0 else "trend-down"
        flow_str = f"{'+' if s.get('flow_pct', 0) >= 0 else ''}{format_pct(s.get('flow_pct', 0), 2)}"
        money_str = format_money(s.get('net_flow', 0))

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">KATEGORİ</span>
                    <span class="signal-fund-name">{s.get('category', '')}</span>
                </div>
                <span class="f-name">{s.get('signal_title', '')}</span>
            </div>
            <div class="f-right">
                <span class="f-val {flow_class}">{flow_str}</span>
                <span class="signal-meta {flow_class}">{money_str}</span>
            </div>
        </li>
        """
    return html

def generate_relative_strength_html(items):
    html = ""
    for s in items:
        rs = s.get('relative_strength', 0)
        rs_class = "trend-up" if rs >= 0 else "trend-down"
        rs_str = f"{'+' if rs >= 0 else ''}{str(f'{rs:.2f}').replace('.', ',')} puan"
        ret_str = f"Getiri {'+' if s.get('period_return_pct', 0) >= 0 else ''}{format_pct(s.get('period_return_pct', 0), 2)}"
        flow_str = f"Para Giriş/Çıkışı {'+' if s.get('period_flow_pct', 0) >= 0 else ''}{format_pct(s.get('period_flow_pct', 0), 2)}"
        flow_class = "trend-up" if s.get('period_flow_pct', 0) >= 0 else "trend-down"

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{s.get('fund_code', '')}</span>
                    <span class="signal-fund-name">{s.get('name', '')}</span>
                </div>
                <span class="f-name">{s.get('signal_title', '')}</span>
            </div>
            <div class="f-right">
                <span class="f-val {rs_class}">{rs_str}</span>
                <span class="f-pct {rs_class}">{ret_str}</span>
                <span class="signal-meta {flow_class}">{flow_str}</span>
            </div>
        </li>
        """
    return html

def generate_manager_actions_html(items):
    html = ""
    for s in items:
        top_inc = s.get('top_increase_diff', 0)
        top_dec = s.get('top_decrease_diff', 0)
        inc_class = "trend-up" if top_inc >= 0 else "trend-down"
        dec_class = "trend-up" if top_dec >= 0 else "trend-down"
        inc_str = f"{s.get('top_increase_asset', '')} ({'+' if top_inc >= 0 else ''}{str(f'{top_inc:.2f}').replace('.', ',')})"
        dec_str = f"{s.get('top_decrease_asset', '')} ({str(f'{top_dec:.2f}').replace('.', ',')})"

        html += f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{s.get('fund_code', '')}</span>
                    <span class="signal-fund-name">{s.get('name', '')}</span>
                </div>
                <span class="f-name">{s.get('signal_title', '')}</span>
            </div>
            <div class="f-right">
                <span class="signal-meta {inc_class}">{inc_str}</span>
                <span class="signal-meta {dec_class}">{dec_str}</span>
            </div>
        </li>
        """
    return html


def generate_holdings_breakdown_html(holdings_data):
    """En çok kazandıran ve kaybettiren varlıkları etkileri ile listeler."""
    if not holdings_data:
        return ""

    fund_code    = holdings_data.get('fund_code', '')
    total_return = holdings_data.get('total_return_pct', 0)
    top_gainers  = holdings_data.get('top_gainers', [])
    top_losers   = holdings_data.get('top_losers', [])
    fetched_at   = holdings_data.get('fetched_at', '')
    ret_class    = "trend-up" if total_return >= 0 else "trend-down"
    ret_sign     = "+" if total_return >= 0 else ""

    def item_html(item, is_gainer):
        impact = item.get('impact_pct', 0)
        ret    = item.get('return_pct', 0)
        weight = item.get('weight_pct', 0)
        current_weight = item.get('current_weight_pct', weight)
        code   = item.get('code', '')
        name   = item.get('name', '') or ''
        ic     = "trend-up" if impact >= 0 else "trend-down"
        impact_str = f"{'+' if impact >= 0 else ''}{format_pct(impact, 2)}"
        ret_str    = f"Getiri {'+' if ret >= 0 else ''}{format_pct(ret, 2)}"
        if abs(weight - current_weight) >= 0.005:
            weight_str = f"Tahmini Ağırlık %{weight:.2f} ➔ %{current_weight:.2f}".replace('.', ',')
        else:
            weight_str = f"Tahmini Ağırlık %{weight:.2f}".replace('.', ',')
        return f"""
        <li class="fund-item signal-item">
            <div class="f-left">
                <div class="signal-code-row">
                    <span class="f-code">{code}</span>
                    <span class="signal-fund-name">{name[:30]}</span>
                </div>
                <span class="f-name">{weight_str}</span>
            </div>
            <div class="f-right">
                <span class="f-val {ic}">{impact_str}</span>
                <span class="signal-meta">{ret_str}</span>
            </div>
        </li>
        """

    gainers_html = "".join(item_html(i, True)  for i in top_gainers) or "<li class='fund-item'><div class='f-left'><span class='f-name'>Veri yok</span></div></li>"
    losers_html  = "".join(item_html(i, False) for i in top_losers)  or "<li class='fund-item'><div class='f-left'><span class='f-name'>Veri yok</span></div></li>"

    time_str = ""
    if fetched_at:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M')
        except:
            pass

    return f"""
    <div class="holdings-breakdown-body">
        <div class="holdings-cols">
            <div class="holdings-col">
                <div class="holdings-col-title trend-up">▲ En Çok Katkı Sağlayan</div>
                <ul class="fund-list">{gainers_html}</ul>
            </div>
            <div class="holdings-col">
                <div class="holdings-col-title trend-down">▼ En Çok Kaybettiren</div>
                <ul class="fund-list">{losers_html}</ul>
            </div>
        </div>
        
        <!-- Büyük KPI Alanı -->
        <div class="holdings-kpi-card" style="margin-top: 28px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 20px; padding: 32px; text-align: center;">
            <span style="font-size: calc(var(--item-font-size) * 0.8); color: rgba(255, 255, 255, 0.4); text-transform: uppercase; font-weight: 700; letter-spacing: 2px; margin-bottom: 12px;">TAHMİNİ GETİRİ</span>
            <div style="display: flex; align-items: center; justify-content: center; gap: 24px;">
                <span style="font-size: calc(var(--item-font-size) * 5); font-weight: 800; opacity: 0.1; color: #fff; font-family: 'Space Grotesk', sans-serif;">{fund_code}</span>
                <span class="{ret_class}" style="font-size: calc(var(--item-font-size) * 3); font-weight: 800; font-family: 'Space Grotesk', sans-serif; line-height: 1;">{ret_sign}{format_pct(total_return, 4)}</span>
            </div>
        </div>
    </div>
    """

def generate_per_investor_html(tracked_dict):
    html = ""
    for code, data in tracked_dict.items():
        val = data.get('per_investor_value', 0)
        prev_val = data.get('per_investor_value_prev', 0)
        pct = data.get('per_investor_change_pct', 0)
        name = data.get('name', '')
        
        val_str = f"₺{val:,.0f}".replace(",", ".")
        prev_val_str = f"₺{prev_val:,.0f}".replace(",", ".")
        pct_str = f"({'+' if pct >= 0 else ''}{format_pct(pct)})"
        trend_class = "trend-up" if pct >= 0 else "trend-down"
        
        html += f"""
        <div class="per-inv-card">
            <div class="t-header" style="margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <span class="t-code" style="font-size:var(--tcode-font-size);">{code}</span>
                    <span class="t-name" style="font-size:calc(var(--item-font-size) * 0.45); color:rgba(255,255,255,0.5); font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">{name}</span>
                </div>
                <span class="t-label" style="font-size:calc(var(--item-font-size) * 0.3); color:rgba(255,255,255,0.4); text-transform:uppercase; font-weight:700; letter-spacing:1px;">Kişi Başı Yatırım</span>
            </div>
            <div class="t-values-row" style="display:flex; justify-content:space-between; align-items:flex-end;">
                <div style="display:flex; align-items:baseline; gap:10px;">
                    <span class="t-val-main" style="font-size:var(--item-font-size) !important; color:#fff; line-height:1;">{val_str}</span>
                    <span class="t-val-sub {trend_class}" style="font-size:calc(var(--item-font-size) * 0.6) !important; font-weight:800;">{pct_str}</span>
                </div>
                <div style="display:flex; flex-direction:column; align-items:flex-end; gap:2px;">
                    <span style="font-size:calc(var(--item-font-size) * 0.3); color:rgba(255,255,255,0.4); text-transform:uppercase; font-weight:700; letter-spacing:1px;">Önceki Değer</span>
                    <span style="font-size:calc(var(--item-font-size) * 0.6); color:rgba(255,255,255,0.6); font-weight:700; font-family:'Space Grotesk', sans-serif;">{prev_val_str}</span>
                </div>
            </div>
        </div>
        """
    return html


def load_capitals():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    capitals_path = os.path.join(base_dir, "bist_capitals.json")
    manual_path = os.path.join(base_dir, "manual_capitals.json")
    
    capitals = {}
    if os.path.exists(capitals_path):
        try:
            with open(capitals_path, "r", encoding="utf-8") as f:
                capitals = json.load(f)
        except:
            pass
            
    # Apply manual overrides in-memory at runtime
    if os.path.exists(manual_path):
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
            for ticker, val in manual_data.items():
                if isinstance(val, dict):
                    bireysel = val.get("bireysel", 0.0)
                    kurumsal = val.get("kurumsal", 0.0)
                    total = bireysel + kurumsal
                    if total > 0:
                        capitals[ticker] = total
                elif isinstance(val, (int, float)):
                    capitals[ticker] = float(val)
        except:
            pass
            
    if not capitals:
        capitals = {
            "HEDEF": 347232862.0,
            "DSTKF": 333333333.0,
            "ACSEL": 10721700.0,
            "BAYRK": 250000000.0,
            "BURVA": 7350000.0,
            "CWENE": 1078000000.0,
            "ERBOS": 20000000.0,
            "FZLGY": 1250000000.0,
        }
    return capitals


def generate_fund_takas_diff_html(start_date=None, end_date=None):
    """Tarih aralığına göre Yatırım Fonları takas adedi değişimlerini listeler."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "fintables_history.json")
    if not os.path.exists(json_path):
        return '<div class="comp-empty">Takas geçmiş verisi bulunamadı.</div>'
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        return f'<div class="comp-empty">Veri tabanı yükleme hatası: {e}</div>'
        
    if not history or len(history) < 2:
        return '<div class="comp-empty">Karşılaştırma için yeterli geçmiş veri bulunmamaktadır.</div>'
        
    available_dates = sorted(list(history.keys()))
    
    s_date = start_date
    e_date = end_date
    if not s_date or s_date not in history:
        s_date = available_dates[0]
    if not e_date or e_date not in history:
        e_date = available_dates[-1]
        
    if s_date == e_date:
        s_idx = available_dates.index(s_date)
        if s_idx > 0:
            s_date = available_dates[s_idx - 1]
        else:
            s_date = available_dates[0]
            if len(available_dates) > 1:
                e_date = available_dates[1]
                
    global calculated_takas_date_range
    calculated_takas_date_range = f"{format_turkish_date(s_date)} - {format_turkish_date(e_date)}"

    start_data = history.get(s_date, {})
    end_data = history.get(e_date, {})
    
    capitals = load_capitals()
    
    # Analyze differences
    diffs = []
    for ticker, end_info in end_data.items():
        start_info = start_data.get(ticker)
        if not start_info:
            continue
            
        capital = capitals.get(ticker, 100000000.0)
        
        lot_start = start_info.get("lot", 0.0)
        lot_end = end_info.get("lot", 0.0)
        lot_diff = lot_end - lot_start
        
        pct_start = (lot_start / capital) * 100.0
        pct_end = (lot_end / capital) * 100.0
        pct_diff = pct_end - pct_start
        
        price_end = end_info.get("price", 0.0)
        if price_end == 0.0 and lot_end > 0:
            price_end = end_info.get("val", 0.0) / lot_end
            
        tl_flow = lot_diff * price_end
        
        diffs.append({
            "ticker": ticker,
            "lot_start": lot_start,
            "lot_end": lot_end,
            "lot_diff": lot_diff,
            "pct_start": pct_start,
            "pct_end": pct_end,
            "pct_diff": pct_diff,
            "price": price_end,
            "tl_flow": tl_flow
        })
        
    inflows = [d for d in diffs if d["tl_flow"] > 0]
    outflows = [d for d in diffs if d["tl_flow"] < 0]
    
    inflows = sorted(inflows, key=lambda x: x["tl_flow"], reverse=True)[:10]
    outflows = sorted(outflows, key=lambda x: x["tl_flow"])[:10]
    
    if not inflows and not outflows:
        return '<div class="comp-empty">Seçilen tarihler arasında ortak takas verisi bulunmamaktadır.</div>'
        
    def generate_column_html(items):
        html_rows = ""
        for d in items:
            ticker = d["ticker"]
            pct_start_str = f"{d['pct_start']:.2f}%".replace('.', ',')
            pct_end_str = f"{d['pct_end']:.2f}%".replace('.', ',')
            pct_diff = d["pct_diff"]
            
            pct_diff_sign = "+" if pct_diff >= 0 else ""
            pct_diff_class = "trend-up" if pct_diff >= 0 else "trend-down"
            pct_diff_str = f"{pct_diff_sign}{pct_diff:.2f}%".replace('.', ',')
            
            lot_diff = d["lot_diff"]
            lot_diff_sign = "+" if lot_diff >= 0 else ""
            lot_diff_str = f"{lot_diff_sign}{lot_diff:,.0f}".replace(',', '.')
            
            tl_flow = d["tl_flow"]
            tl_flow_sign = "+" if tl_flow >= 0 else "-"
            tl_flow_class = "trend-up" if tl_flow >= 0 else "trend-down"
            tl_flow_str = f"{tl_flow_sign}₺{abs(tl_flow):,.0f}".replace(',', '.')
            
            price_str = f"₺{d['price']:.2f}".replace('.', ',')
            
            html_rows += f"""
            <div class="takas-diff-row-card">
                <div class="row-left">
                    <span class="bist-ticker-badge">{ticker}</span>
                    <span class="row-price">{price_str}</span>
                </div>
                <div class="row-middle">
                    <div class="row-pct-change">{pct_start_str} ➔ {pct_end_str}</div>
                    <div class="row-lot-change">{lot_diff_str} Lot</div>
                </div>
                <div class="row-right">
                    <span class="status-badge {pct_diff_class}">{pct_diff_str} Fark</span>
                    <div class="row-flow-val {tl_flow_class}">{tl_flow_str}</div>
                </div>
            </div>
            """
        return html_rows

    inflow_html = generate_column_html(inflows)
    outflow_html = generate_column_html(outflows)
    
    html = f"""
    <div class="takas-columns-container">
        <div class="takas-column">
            <div class="column-title-bar green-title">📈 EN ÇOK GİRİŞ YAPILANLAR (TOP 10)</div>
            <div class="column-rows">{inflow_html}</div>
        </div>
        <div class="takas-column">
            <div class="column-title-bar red-title">📉 EN ÇOK ÇIKIŞ YAPILANLAR (TOP 10)</div>
            <div class="column-rows">{outflow_html}</div>
        </div>
    </div>
    """
        
    return html



def generate_fund_takas_diff_pct_html(start_date=None, end_date=None):
    """Tarih aralığına göre Yatırım Fonları takas oran değişimlerini (yüzdesel farka göre) listeler."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "fintables_history.json")
    if not os.path.exists(json_path):
        return '<div class="comp-empty">Takas geçmiş verisi bulunamadı.</div>'
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        return f'<div class="comp-empty">Veri tabanı yükleme hatası: {e}</div>'
        
    if not history or len(history) < 2:
        return '<div class="comp-empty">Karşılaştırma için yeterli geçmiş veri bulunmamaktadır.</div>'
        
    available_dates = sorted(list(history.keys()))
    
    s_date = start_date
    e_date = end_date
    if not s_date or s_date not in history:
        s_date = available_dates[0]
    if not e_date or e_date not in history:
        e_date = available_dates[-1]
        
    if s_date == e_date:
        s_idx = available_dates.index(s_date)
        if s_idx > 0:
            s_date = available_dates[s_idx - 1]
        else:
            s_date = available_dates[0]
            if len(available_dates) > 1:
                e_date = available_dates[1]
                
    global calculated_takas_pct_date_range
    calculated_takas_pct_date_range = f"{format_turkish_date(s_date)} - {format_turkish_date(e_date)}"

    start_data = history.get(s_date, {})
    end_data = history.get(e_date, {})
    
    capitals = load_capitals()
    
    diffs = []
    for ticker, end_info in end_data.items():
        start_info = start_data.get(ticker)
        if not start_info:
            continue
            
        capital = capitals.get(ticker, 100000000.0)
        
        lot_start = start_info.get("lot", 0.0)
        lot_end = end_info.get("lot", 0.0)
        lot_diff = lot_end - lot_start
        
        pct_start = (lot_start / capital) * 100.0
        pct_end = (lot_end / capital) * 100.0
        pct_diff = pct_end - pct_start
        
        price_end = end_info.get("price", 0.0)
        if price_end == 0.0 and lot_end > 0:
            price_end = end_info.get("val", 0.0) / lot_end
            
        tl_flow = lot_diff * price_end
        
        diffs.append({
            "ticker": ticker,
            "lot_start": lot_start,
            "lot_end": lot_end,
            "lot_diff": lot_diff,
            "pct_start": pct_start,
            "pct_end": pct_end,
            "pct_diff": pct_diff,
            "price": price_end,
            "tl_flow": tl_flow
        })
        
    inflows = [d for d in diffs if d["pct_diff"] > 0]
    outflows = [d for d in diffs if d["pct_diff"] < 0]
    
    inflows = sorted(inflows, key=lambda x: x["pct_diff"], reverse=True)[:10]
    outflows = sorted(outflows, key=lambda x: x["pct_diff"])[:10]
    
    if not inflows and not outflows:
        return '<div class="comp-empty">Seçilen tarihler arasında ortak takas verisi bulunmamaktadır.</div>'
        
    def generate_column_html(items):
        html_rows = ""
        for d in items:
            ticker = d["ticker"]
            pct_start_str = f"{d['pct_start']:.2f}%".replace('.', ',')
            pct_end_str = f"{d['pct_end']:.2f}%".replace('.', ',')
            pct_diff = d["pct_diff"]
            
            pct_diff_sign = "+" if pct_diff >= 0 else ""
            pct_diff_class = "trend-up" if pct_diff >= 0 else "trend-down"
            pct_diff_str = f"{pct_diff_sign}{pct_diff:.2f}%".replace('.', ',')
            
            lot_diff = d["lot_diff"]
            lot_diff_sign = "+" if lot_diff >= 0 else ""
            lot_diff_str = f"{lot_diff_sign}{lot_diff:,.0f}".replace(',', '.')
            
            tl_flow = d["tl_flow"]
            tl_flow_sign = "+" if tl_flow >= 0 else "-"
            tl_flow_class = "trend-up" if tl_flow >= 0 else "trend-down"
            tl_flow_str = f"{tl_flow_sign}₺{abs(tl_flow):,.0f}".replace(',', '.')
            
            price_str = f"₺{d['price']:.2f}".replace('.', ',')
            
            html_rows += f"""
            <div class="takas-diff-row-card">
                <div class="row-left">
                    <span class="bist-ticker-badge">{ticker}</span>
                    <span class="row-price">{price_str}</span>
                </div>
                <div class="row-middle">
                    <div class="row-pct-change">{pct_start_str} ➔ {pct_end_str}</div>
                    <div class="row-lot-change">{lot_diff_str} Lot</div>
                </div>
                <div class="row-right">
                    <span class="status-badge {pct_diff_class}">{pct_diff_str} Fark</span>
                    <div class="row-flow-val {tl_flow_class}">{tl_flow_str}</div>
                </div>
            </div>
            """
        return html_rows

    inflow_html = generate_column_html(inflows)
    outflow_html = generate_column_html(outflows)
    
    html = f"""
    <div class="takas-columns-container">
        <div class="takas-column">
            <div class="column-title-bar green-title">📈 ORANSAL PAYI EN ÇOK ARTANLAR (TOP 10)</div>
            <div class="column-rows">{inflow_html}</div>
        </div>
        <div class="takas-column">
            <div class="column-title-bar red-title">📉 ORANSAL PAYI EN ÇOK AZALANLAR (TOP 10)</div>
            <div class="column-rows">{outflow_html}</div>
        </div>
    </div>
    """
        
    return html



def generate_fund_report_sparkline(price_history, chart_title):
    if not price_history or len(price_history) < 2:
        return '<div class="fund-report-chart-empty">Grafik verisi alınamadı.</div>'

    values = [float(p.get("cum_return_pct", 0)) for p in price_history]
    labels = [p.get("date", "")[-5:] for p in price_history]
    min_v = min(values)
    max_v = max(values)
    span = (max_v - min_v) or 1.0
    width = 760
    height = 180
    pad_x = 16
    pad_y = 18
    usable_w = width - pad_x * 2
    usable_h = height - pad_y * 2

    points = []
    for idx, value in enumerate(values):
        x = pad_x + (usable_w * idx / (len(values) - 1))
        y = pad_y + usable_h - ((value - min_v) / span) * usable_h
        points.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"{pad_x:.1f},{height-pad_y:.1f} " + polyline + f" {width-pad_x:.1f},{height-pad_y:.1f}"
    last_val = values[-1]
    line_class = "#30D158" if last_val >= 0 else "#FF453A"
    fill_color = "rgba(48,209,88,0.18)" if last_val >= 0 else "rgba(255,69,58,0.18)"
    latest_str = f"{'+' if last_val >= 0 else ''}{format_pct(last_val, 2)}"

    tick_html = ""
    if len(labels) >= 2:
        tick_html = f"""
        <div class="fund-report-chart-axis">
            <span>{labels[0]}</span>
            <span>{labels[len(labels)//2]}</span>
            <span>{labels[-1]}</span>
        </div>
        """

    return f"""
    <div class="fund-report-chart-wrap">
        <div class="fund-report-chart-meta">
            <span class="fund-report-chart-title">{chart_title}</span>
            <span class="fund-report-chart-badge {'trend-up' if last_val >= 0 else 'trend-down'}">{latest_str}</span>
        </div>
        <svg class="fund-report-chart-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
            <defs>
                <linearGradient id="fundReportArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="{fill_color}" />
                    <stop offset="100%" stop-color="rgba(255,255,255,0)" />
                </linearGradient>
            </defs>
            <line x1="{pad_x}" y1="{height-pad_y:.1f}" x2="{width-pad_x}" y2="{height-pad_y:.1f}" stroke="rgba(255,255,255,0.10)" stroke-width="1" />
            <polygon points="{area}" fill="url(#fundReportArea)"></polygon>
            <polyline points="{polyline}" fill="none" stroke="{line_class}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
            <circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="5" fill="{line_class}"></circle>
        </svg>
        {tick_html}
    </div>
    """


def generate_fund_report_html(tracked_dict, allocation_diffs, config, period_label):
    if not tracked_dict:
        return ""

    target_fund = config.get("fund_report_fund", "").upper()
    if not target_fund:
        target_fund = list(tracked_dict.keys())[0] if tracked_dict else ""
    if target_fund not in tracked_dict:
        return f"""
        <div class="fund-report-body">
            <div class="card-header">
                <div class="header-icon inflow-icon" style="background:rgba(10,132,255,0.2); color:#0A84FF;">📘</div>
                <h2>Fon Karnesi <span class="period-label">({period_label})</span></h2>
            </div>
            <div class="fund-report-kpi"><span class="fund-report-kpi-sub">{target_fund} için veri alınamadı.</span></div>
        </div>
        """

    data = tracked_dict[target_fund]
    allocations = allocation_diffs.get(target_fund, [])[:8]

    price_str = f"₺{data.get('price', 0):,.6f}".replace(",", "X").replace(".", ",").replace("X", ".")
    size_str = "₺" + f"{data.get('fund_size', 0):,.0f}".replace(",", ".")
    flow_str = format_money(data.get("period_flow", 0))
    flow_pct = f"{'+' if data.get('period_flow_pct', 0) >= 0 else ''}{format_pct(data.get('period_flow_pct', 0), 2)}"
    ret_decimals = 4 if period_label == "Günlük" else 2
    ret_str = f"{'+' if data.get('period_return_pct', 0) >= 0 else ''}{format_pct(data.get('period_return_pct', 0), ret_decimals)}"
    investor_delta = int(data.get("period_investor_change", 0))
    investor_delta_str = f"{investor_delta:+,}".replace(",", ".")
    investor_pct_str = f"{'+' if data.get('period_investor_pct', 0) >= 0 else ''}{format_pct(data.get('period_investor_pct', 0), 2)}"
    investor_count_str = f"{int(data.get('investors', 0)):,}".replace(",", ".")
    per_inv_str = "₺" + f"{data.get('per_investor_value', 0):,.0f}".replace(",", ".")
    per_inv_prev_str = "₺" + f"{data.get('per_investor_value_prev', 0):,.0f}".replace(",", ".")
    per_inv_pct_str = f"{'+' if data.get('per_investor_change_pct', 0) >= 0 else ''}{format_pct(data.get('per_investor_change_pct', 0), 2)}"
    investor_delta_class = "trend-up" if investor_delta >= 0 else "trend-down"
    ret_class = "trend-up" if data.get('period_return_pct', 0) >= 0 else "trend-down"
    flow_class = "trend-up" if data.get('period_flow', 0) >= 0 else "trend-down"
    per_inv_class = "trend-up" if data.get('per_investor_change_pct', 0) >= 0 else "trend-down"
    report_history = data.get("fund_report_history") or data.get("price_history", [])
    report_history_title = data.get("fund_report_history_title", "Performans Eğrisi")
    chart_html = generate_fund_report_sparkline(report_history, report_history_title)

    alloc_html = ""
    for alloc in allocations:
        diff = float(alloc.get("diff", 0))
        diff_str = f"{'+' if diff >= 0 else ''}{str(f'{diff:.2f}').replace('.', ',')}"
        diff_class = "trend-up" if diff >= 0 else "trend-down"
        weight_str = f"%{alloc.get('weight', 0):.2f}".replace(".", ",")
        alloc_html += f"""
        <div class="fund-report-alloc-item">
            <span class="fund-report-alloc-name">{alloc.get('asset_name', '')}</span>
            <span class="fund-report-alloc-val {diff_class}">{weight_str} ({diff_str})</span>
        </div>
        """

    return f"""
    <div class="fund-report-body">
        <div class="card-header">
            <div class="header-icon inflow-icon" style="background:rgba(10,132,255,0.2); color:#0A84FF;">📘</div>
            <h2>Fon Karnesi <span class="period-label">({period_label})</span></h2>
        </div>
        <div class="fund-report-header">
            <div class="fund-report-title">
                <span class="fund-report-code">{target_fund}</span>
                <span class="fund-report-name">{data.get('name', '')}</span>
            </div>
            <div class="fund-report-price">
                <span class="fund-report-price-label">Güncel Fiyat</span>
                <span class="fund-report-price-value">{price_str}</span>
            </div>
        </div>
        <div class="fund-report-kpis">
            <div class="fund-report-kpi fund-report-kpi-compact fund-report-kpi-accent {'fund-report-kpi-pos' if data.get('period_return_pct', 0) >= 0 else 'fund-report-kpi-neg'}">
                <span class="fund-report-kpi-label">{period_label} Getirisi</span>
                <span class="fund-report-kpi-value {ret_class}">{ret_str}</span>
            </div>
            <div class="fund-report-kpi fund-report-kpi-compact fund-report-kpi-accent fund-report-kpi-size">
                <span class="fund-report-kpi-label">Fon Büyüklüğü</span>
                <span class="fund-report-kpi-value">{size_str}</span>
            </div>
            <div class="fund-report-kpi fund-report-kpi-compact fund-report-kpi-accent fund-report-kpi-flow {'fund-report-kpi-pos' if data.get('period_flow', 0) >= 0 else 'fund-report-kpi-neg'}">
                <span class="fund-report-kpi-label">Para Giriş/Çıkışı</span>
                <div class="fund-report-kpi-inline">
                    <span class="fund-report-kpi-value {flow_class}">{flow_str}</span>
                    <span class="fund-report-kpi-sub fund-report-kpi-sub-strong {flow_class}">{flow_pct}</span>
                </div>
            </div>
            <div class="fund-report-kpi fund-report-kpi-compact">
                <span class="fund-report-kpi-label">Mevcut Yatırımcı Sayısı</span>
                <span class="fund-report-kpi-value">{investor_count_str}</span>
            </div>
            <div class="fund-report-kpi fund-report-kpi-compact fund-report-kpi-accent fund-report-kpi-investor {'fund-report-kpi-pos' if investor_delta >= 0 else 'fund-report-kpi-neg'}">
                <span class="fund-report-kpi-label">{period_label} Yatırımcı Değişimi</span>
                <div class="fund-report-kpi-inline">
                    <span class="fund-report-kpi-value fund-report-kpi-big {investor_delta_class}">{investor_delta_str} kişi</span>
                    <span class="fund-report-kpi-sub fund-report-kpi-sub-strong {investor_delta_class}">{investor_pct_str}</span>
                </div>
            </div>
            <div class="fund-report-kpi fund-report-kpi-accent fund-report-kpi-perinv {'fund-report-kpi-pos' if data.get('per_investor_change_pct', 0) >= 0 else 'fund-report-kpi-neg'}">
                <span class="fund-report-kpi-label">Kişi Başı Yatırım</span>
                <div class="fund-report-kpi-inline fund-report-kpi-inline-wrap">
                    <span class="fund-report-kpi-value {per_inv_class}">{per_inv_str}</span>
                    <span class="fund-report-kpi-sub fund-report-kpi-sub-strong {per_inv_class}">Önceki: {per_inv_prev_str} ({per_inv_pct_str})</span>
                </div>
            </div>
        </div>
        <div class="fund-report-bottom">
            <div class="fund-report-panel fund-report-chart-panel">
                {chart_html}
            </div>
            <div class="fund-report-panel fund-report-alloc-panel">
                <div class="fund-report-panel-title">Portföy Dağılımı</div>
                <div class="fund-report-alloc-grid">
                    {alloc_html if alloc_html else '<div class="fund-report-kpi-sub">Portföy dağılım verisi alınamadı.</div>'}
                </div>
            </div>
        </div>
    </div>
    """

def generate_tracked_html(tracked_dict, period_label, show_chart=False):
    html = ""
    for code, data in tracked_dict.items():
        price = data.get('price', 0)
        p_flow = data.get('period_flow', 0)
        p_ret = data.get('period_return_pct', 0)
        inv_change = data.get('period_investor_change', 0)
        inv_pct = data.get('period_investor_pct', 0)
        current_investors = int(data.get('investors', 0) or 0)
        total_size = data.get('fund_size', 0)
        flow_pct = data.get('period_flow_pct', 0)

        price_str = f"₺{price:,.6f}".replace(",", "X").replace(".", ",").replace("X", ".")
        flow_str = format_money(p_flow)
        flow_class = "trend-up" if p_flow >= 0 else "trend-down"
        flow_pct_str = f"({'+' if flow_pct >= 0 else ''}{format_pct(flow_pct)})"
        
        ret_str = f"{'+' if p_ret >= 0 else ''}{format_pct(p_ret, 4)}"
        ret_class = "trend-up" if p_ret >= 0 else "trend-down"
        
        inv_str = f"{inv_change:+d} Kişi"
        inv_class = "trend-up" if inv_change >= 0 else "trend-down"
        inv_pct_str = f"({'+' if inv_pct >= 0 else ''}{format_pct(inv_pct)})"
        current_inv_str = f"{current_investors:,.0f}".replace(",", ".")
        
        size_str = '₺' + f"{total_size:,.0f}".replace(",", ".")
        
        html += f"""
        <div class="tracked-card">
            <div class="t-header">
                <span class="t-code">{code}</span>
                <span class="t-price">Fiyat: <span class="t-price-value">{price_str}</span></span>
            </div>
            <div class="t-stats-grid">
                <div class="t-stat-block">
                    <span class="t-label">{period_label} Giriş</span>
                    <div class="t-values-row">
                        <span class="t-val-main {flow_class}">{flow_str}</span>
                        <span class="t-val-sub {flow_class}">{flow_pct_str}</span>
                    </div>
                </div>
                <div class="t-stat-block">
                    <span class="t-label">{period_label} Getiri</span>
                    <div class="t-values-row">
                        <span class="t-val-main {ret_class}">{ret_str}</span>
                    </div>
                </div>
                <div class="t-stat-block">
                    <span class="t-label">Yeni Kişi ({period_label})</span>
                    <div class="t-values-row">
                        <span class="t-val-main {inv_class}">{inv_str}</span>
                        <span class="t-val-sub {inv_class}">{inv_pct_str}</span>
                        <span class="t-val-sub t-val-total">Mevcut: {current_inv_str}</span>
                    </div>
                </div>
                <div class="t-stat-block">
                    <span class="t-label">Toplam Büyüklük</span>
                    <div class="t-values-row">
                        <span class="t-val-main">{size_str}</span>
                    </div>
                </div>
            </div>
        </div>
        """
        
    return html


# Rich Neon Palette for multi-fund comparison
COMP_COLORS = [
    "#FF9500",  # Neon Orange
    "#00C7BE",  # Bright Teal
    "#30D158",  # Vibrant Green
    "#0A84FF",  # Electric Blue
    "#FF375F",  # Vivid Pink
    "#BF5AF2",  # Purple
    "#FFD60A",  # Gold Yellow
    "#64D2FF",  # Sky Blue
    "#FF6482",  # Coral Rose
    "#34C759",  # Mint
    "#AF52DE",  # Violet
    "#5856D6"   # Indigo
]

def generate_comparison_chart_html(tracked_dict, period_label):
    if not tracked_dict:
        return '<div class="comp-empty">Takip listesinde veri bulunamadı.</div>'
        
    funds_data = []
    all_dates_set = set()
    
    for code, data in tracked_dict.items():
        history = data.get('price_history', [])
        if not history or len(history) < 2:
            continue
        for p in history:
            all_dates_set.add(p['date'])
        funds_data.append({
            'code': code,
            'name': data.get('name', code),
            'history': history,
            'final_return': float(history[-1].get('cum_return_pct', 0))
        })
        
    if not funds_data:
        return '<div class="comp-empty">Karşılaştırma grafiği için en az 2 günlük veri gereklidir.</div>'
        
    all_dates = sorted(list(all_dates_set))
    if len(all_dates) < 2:
        return '<div class="comp-empty">Karşılaştırma grafiği için en az 2 farklı tarih gereklidir.</div>'
        
    # Sort funds by final return descending for leaderboard
    funds_data.sort(key=lambda x: x['final_return'], reverse=True)
    
    # Assign colors
    for i, f in enumerate(funds_data):
        f['color'] = COMP_COLORS[i % len(COMP_COLORS)]
        
    # Calculate min & max for Y-Axis
    all_vals = []
    for f in funds_data:
        for p in f['history']:
            all_vals.append(float(p.get('cum_return_pct', 0)))
            
    min_v = min(all_vals)
    max_v = max(all_vals)
    min_v = min(min_v, 0.0)
    max_v = max(max_v, 0.0)
    
    span = max_v - min_v
    if span <= 0:
        span = 1.0
    pad_span = max(span * 0.15, 0.4)
    y_min = min_v - pad_span
    y_max = max_v + pad_span
    total_y_range = y_max - y_min
    
    # SVG Dimensions
    width = 1000
    height = 430
    pad_l = 85
    pad_r = 135
    pad_t = 30
    pad_b = 45
    usable_w = width - pad_l - pad_r
    usable_h = height - pad_t - pad_b
    
    def get_x(date_str):
        if date_str not in all_dates:
            return pad_l
        idx = all_dates.index(date_str)
        return pad_l + (usable_w * idx / (len(all_dates) - 1))
        
    def get_y(val):
        return pad_t + usable_h - ((val - y_min) / total_y_range) * usable_h
        
    # Y-Grid lines & labels
    y_zero = get_y(0.0)
    num_ticks = 5
    y_ticks = []
    for i in range(num_ticks):
        v = y_min + (total_y_range * i / (num_ticks - 1))
        y_ticks.append(v)
        
    grid_svg = ""
    for v in y_ticks:
        y_pos = get_y(v)
        pct_label = f"{'+' if v > 0.01 else ''}{v:.1f}%".replace('.', ',')
        grid_svg += f'<line x1="{pad_l}" y1="{y_pos:.1f}" x2="{width-pad_r}" y2="{y_pos:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1" />'
        grid_svg += f'<text x="{pad_l-12}" y="{y_pos+4:.1f}" fill="rgba(255,255,255,0.45)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="end">{pct_label}</text>'
        
    # Prominent 0.0% Baseline
    zero_line_svg = f"""
    <line x1="{pad_l}" y1="{y_zero:.1f}" x2="{width-pad_r}" y2="{y_zero:.1f}" stroke="rgba(255,255,255,0.30)" stroke-width="1.5" stroke-dasharray="5,4" />
    """
    
    # X-Axis date ticks
    x_ticks_svg = ""
    date_step = max(1, len(all_dates) // 6)
    display_date_indices = list(range(0, len(all_dates), date_step))
    if (len(all_dates) - 1) not in display_date_indices:
        display_date_indices.append(len(all_dates) - 1)
        
    for idx in display_date_indices:
        d_str = all_dates[idx]
        x_pos = pad_l + (usable_w * idx / (len(all_dates) - 1))
        try:
            formatted_date = datetime.strptime(d_str, "%Y-%m-%d").strftime("%d.%m")
        except:
            formatted_date = d_str[-5:]
        x_ticks_svg += f'<text x="{x_pos:.1f}" y="{height-14}" fill="rgba(255,255,255,0.55)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="middle">{formatted_date}</text>'
        x_ticks_svg += f'<line x1="{x_pos:.1f}" y1="{height-pad_b}" x2="{x_pos:.1f}" y2="{height-pad_b+6}" stroke="rgba(255,255,255,0.25)" stroke-width="1" />'

    # Draw Fund Lines & End Tags
    curves_svg = ""
    end_tags_svg = ""
    
    # Calculate end label positions with collision avoidance
    end_positions = []
    for f in funds_data:
        h = f['history']
        coords = []
        for p in h:
            cx = get_x(p['date'])
            cy = get_y(float(p.get('cum_return_pct', 0)))
            coords.append((cx, cy))
            
        if not coords:
            continue
            
        if len(coords) == 2:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f} L {coords[1][0]:.1f},{coords[1][1]:.1f}"
        else:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f}"
            for i in range(len(coords) - 1):
                p0 = coords[i]
                p1 = coords[i+1]
                mid_x = (p0[0] + p1[0]) / 2.0
                d_path += f" C {mid_x:.1f},{p0[1]:.1f} {mid_x:.1f},{p1[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
                
        color = f['color']
        curves_svg += f'<path d="{d_path}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow-{f["code"]})" />'
        
        last_pt = coords[-1]
        end_positions.append({
            'fund': f,
            'last_pt': last_pt,
            'color': color,
            'target_y': last_pt[1] - 11.0
        })

    # Collision resolution for end badges
    min_gap = 25.0
    for i in range(1, len(end_positions)):
        prev_y = end_positions[i-1]['target_y']
        curr_y = end_positions[i]['target_y']
        if curr_y - prev_y < min_gap:
            end_positions[i]['target_y'] = prev_y + min_gap
            
    for item in end_positions:
        f = item['fund']
        last_pt = item['last_pt']
        color = item['color']
        badge_y = item['target_y']
        final_ret = f['final_return']
        ret_str = f"{'+' if final_ret >= 0 else ''}{final_ret:.4f}%".replace('.', ',')
        
        end_tags_svg += f"""
        <circle cx="{last_pt[0]:.1f}" cy="{last_pt[1]:.1f}" r="5.5" fill="{color}" stroke="#000" stroke-width="1.5" />
        <g transform="translate({last_pt[0]+8:.1f}, {badge_y:.1f})">
            <rect x="0" y="0" width="88" height="22" rx="6" fill="rgba(15,15,22,0.92)" stroke="{color}" stroke-width="1" />
            <text x="6" y="15" fill="#fff" font-size="11" font-family="Space Grotesk, sans-serif" font-weight="700">{f['code']}</text>
            <text x="82" y="15" fill="{color}" font-size="11" font-family="Space Grotesk, sans-serif" font-weight="700" text-anchor="end">{ret_str}</text>
        </g>
        """

    # SVG Filters
    filters_svg = "<defs>"
    for f in funds_data:
        filters_svg += f"""
        <filter id="glow-{f['code']}" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="{f['color']}" flood-opacity="0.65"/>
        </filter>
        """
    filters_svg += "</defs>"

    svg_full = f"""
    <div class="comp-chart-canvas-wrap">
        <svg viewBox="0 0 {width} {height}" class="comp-svg-chart" xmlns="http://www.w3.org/2000/svg">
            {filters_svg}
            {grid_svg}
            {zero_line_svg}
            {x_ticks_svg}
            {curves_svg}
            {end_tags_svg}
        </svg>
    </div>
    """
    
    # Leaderboard HTML
    leaderboard_cards = ""
    for idx, f in enumerate(funds_data):
        rank = idx + 1
        if rank == 1:
            rank_html = '<span class="comp-rank-badge rank-gold">🥇 1</span>'
        elif rank == 2:
            rank_html = '<span class="comp-rank-badge rank-silver">🥈 2</span>'
        elif rank == 3:
            rank_html = '<span class="comp-rank-badge rank-bronze">🥉 3</span>'
        else:
            rank_html = f'<span class="comp-rank-badge">{rank}</span>'
            
        ret = f['final_return']
        badge_cls = "trend-up" if ret >= 0 else "trend-down"
        ret_formatted = f"{'+' if ret >= 0 else ''}{ret:.4f}%".replace('.', ',')
        
        # Mini bar
        max_abs = max(abs(max_v), abs(min_v), 1.0)
        bar_pct = min(100, max(8, (abs(ret) / max_abs) * 100))
        bar_color = f['color']
        
        leaderboard_cards += f"""
        <div class="comp-leader-card">
            <div class="comp-leader-top">
                <div class="comp-leader-left">
                    {rank_html}
                    <span class="comp-dot" style="background:{f['color']};"></span>
                    <span class="comp-code">{f['code']}</span>
                </div>
                <span class="comp-return-badge {badge_cls}">{ret_formatted}</span>
            </div>
            <div class="comp-bar-track">
                <div class="comp-bar-fill" style="width:{bar_pct}%; background:{bar_color};"></div>
            </div>
        </div>
        """

    card_body = f"""
    <div class="comp-card-body">
        <div class="comp-card-header">
            <div class="comp-title-group">
                <div class="header-icon" style="background:rgba(255,149,0,0.18); color:#FF9500;">📈</div>
                <div>
                    <h2>Fon Kümülatif Getiri Karşılaştırması</h2>
                    <span class="comp-subtitle">{period_label}</span>
                </div>
            </div>
        </div>
        
        {svg_full}
        
        <div class="comp-leaderboard-section">
            <div class="comp-section-title">🏆 DÖNEM GETİRİ LİDERLİK TABLOSU</div>
            <div class="comp-leaderboard-grid">
                {leaderboard_cards}
            </div>
        </div>
    </div>
    """
    
    return card_body

def format_flow_value_short(val):
    sign = "+" if val >= 0.01 else ("-" if val < -0.01 else "")
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.1f} Mr".replace('.', ',')
    elif abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.1f} Mn".replace('.', ',')
    elif abs_val >= 1000:
        return f"{sign}{abs_val / 1000:.1f} Bin".replace('.', ',')
    else:
        return f"{sign}{int(abs_val)}"

def format_flow_value_full(val):
    sign = "+" if val >= 0 else "-"
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f} Milyar ₺".replace('.', ',')
    elif abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f} Milyon ₺".replace('.', ',')
    else:
        return f"{sign}{int(abs_val):,} ₺".replace(',', '.')

def format_investor_value_short(val):
    sign = "+" if val >= 0.01 else ("-" if val < -0.01 else "")
    abs_val = abs(val)
    return f"{sign}{int(abs_val):,}".replace(',', '.')

def format_investor_value_full(val):
    sign = "+" if val >= 0 else ""
    return f"{sign}{int(val):,}".replace(',', '.')

def generate_flow_chart_html(tracked_dict, period_label):
    if not tracked_dict:
        return '<div class="comp-empty">Takip listesinde veri bulunamadı.</div>'
        
    funds_data = []
    all_dates_set = set()
    
    for code, data in tracked_dict.items():
        history = sorted(data.get('price_history', []), key=lambda x: x['date'])
        if not history or len(history) < 2:
            continue
            
        start_shares = None
        flow_history = []
        
        for p in history:
            all_dates_set.add(p['date'])
            shares = float(p.get('shares', 0) or 0)
            price = float(p.get('price', 0) or 0)
            
            if start_shares is None:
                start_shares = shares
                flow_history.append({
                    "date": p["date"],
                    "value": 0.0
                })
            else:
                flow_val = (shares - start_shares) * price
                flow_history.append({
                    "date": p["date"],
                    "value": flow_val
                })
                
        cum_flow = flow_history[-1]["value"] if flow_history else 0.0
        funds_data.append({
            'code': code,
            'name': data.get('name', code),
            'history': flow_history,
            'final_value': cum_flow
        })
        
    if not funds_data:
        return '<div class="comp-empty">Para akış grafiği için en az 2 günlük veri gereklidir.</div>'
        
    all_dates = sorted(list(all_dates_set))
    if len(all_dates) < 2:
        return '<div class="comp-empty">Para akış grafiği için en az 2 farklı tarih gereklidir.</div>'
        
    funds_data.sort(key=lambda x: x['final_value'], reverse=True)
    
    for i, f in enumerate(funds_data):
        f['color'] = COMP_COLORS[i % len(COMP_COLORS)]
        
    all_vals = []
    for f in funds_data:
        for p in f['history']:
            all_vals.append(p['value'])
            
    min_v = min(all_vals)
    max_v = max(all_vals)
    min_v = min(min_v, 0.0)
    max_v = max(max_v, 0.0)
    
    span = max_v - min_v
    if span <= 0:
        span = 1.0
    pad_span = max(span * 0.15, 1000.0)
    y_min = min_v - pad_span
    y_max = max_v + pad_span
    total_y_range = y_max - y_min
    
    width = 1000
    height = 430
    pad_l = 95
    pad_r = 145
    pad_t = 30
    pad_b = 45
    usable_w = width - pad_l - pad_r
    usable_h = height - pad_t - pad_b
    
    def get_x(date_str):
        if date_str not in all_dates:
            return pad_l
        idx = all_dates.index(date_str)
        return pad_l + (usable_w * idx / (len(all_dates) - 1))
        
    def get_y(val):
        return pad_t + usable_h - ((val - y_min) / total_y_range) * usable_h
        
    y_zero = get_y(0.0)
    num_ticks = 5
    y_ticks = []
    for i in range(num_ticks):
        v = y_min + (total_y_range * i / (num_ticks - 1))
        y_ticks.append(v)
        
    grid_svg = ""
    for v in y_ticks:
        y_pos = get_y(v)
        flow_lbl = format_flow_value_short(v)
        grid_svg += f'<line x1="{pad_l}" y1="{y_pos:.1f}" x2="{width-pad_r}" y2="{y_pos:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1" />'
        grid_svg += f'<text x="{pad_l-12}" y="{y_pos+4:.1f}" fill="rgba(255,255,255,0.45)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="end">{flow_lbl}</text>'
        
    zero_line_svg = f"""
    <line x1="{pad_l}" y1="{y_zero:.1f}" x2="{width-pad_r}" y2="{y_zero:.1f}" stroke="rgba(255,255,255,0.30)" stroke-width="1.5" stroke-dasharray="5,4" />
    """
    
    x_ticks_svg = ""
    date_step = max(1, len(all_dates) // 6)
    display_date_indices = list(range(0, len(all_dates), date_step))
    if (len(all_dates) - 1) not in display_date_indices:
        display_date_indices.append(len(all_dates) - 1)
        
    for idx in display_date_indices:
        d_str = all_dates[idx]
        x_pos = pad_l + (usable_w * idx / (len(all_dates) - 1))
        try:
            formatted_date = datetime.strptime(d_str, "%Y-%m-%d").strftime("%d.%m")
        except:
            formatted_date = d_str[-5:]
        x_ticks_svg += f'<text x="{x_pos:.1f}" y="{height-14}" fill="rgba(255,255,255,0.55)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="middle">{formatted_date}</text>'
        x_ticks_svg += f'<line x1="{x_pos:.1f}" y1="{height-pad_b}" x2="{x_pos:.1f}" y2="{height-pad_b+6}" stroke="rgba(255,255,255,0.25)" stroke-width="1" />'

    curves_svg = ""
    end_tags_svg = ""
    
    end_positions = []
    for f in funds_data:
        h = f['history']
        coords = []
        for p in h:
            cx = get_x(p['date'])
            cy = get_y(p['value'])
            coords.append((cx, cy))
            
        if not coords:
            continue
            
        if len(coords) == 2:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f} L {coords[1][0]:.1f},{coords[1][1]:.1f}"
        else:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f}"
            for i in range(len(coords) - 1):
                p0 = coords[i]
                p1 = coords[i+1]
                mid_x = (p0[0] + p1[0]) / 2.0
                d_path += f" C {mid_x:.1f},{p0[1]:.1f} {mid_x:.1f},{p1[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
                
        color = f['color']
        curves_svg += f'<path d="{d_path}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow-flow-{f["code"]})" />'
        
        last_pt = coords[-1]
        end_positions.append({
            'fund': f,
            'last_pt': last_pt,
            'color': color,
            'target_y': last_pt[1] - 11.0
        })

    min_gap = 25.0
    for i in range(1, len(end_positions)):
        prev_y = end_positions[i-1]['target_y']
        curr_y = end_positions[i]['target_y']
        if curr_y - prev_y < min_gap:
            end_positions[i]['target_y'] = prev_y + min_gap
            
    for item in end_positions:
        f = item['fund']
        last_pt = item['last_pt']
        color = item['color']
        badge_y = item['target_y']
        final_val = f['final_value']
        val_str = format_flow_value_short(final_val)
        
        end_tags_svg += f"""
        <circle cx="{last_pt[0]:.1f}" cy="{last_pt[1]:.1f}" r="5.5" fill="{color}" stroke="#000" stroke-width="1.5" />
        <g transform="translate({last_pt[0]+8:.1f}, {badge_y:.1f})">
            <rect x="0" y="0" width="88" height="22" rx="6" fill="rgba(15,15,22,0.92)" stroke="{color}" stroke-width="1" />
            <text x="6" y="15" fill="#fff" font-size="11" font-family="Space Grotesk, sans-serif" font-weight="700">{f['code']}</text>
            <text x="82" y="15" fill="{color}" font-size="10" font-family="Space Grotesk, sans-serif" font-weight="700" text-anchor="end">{val_str}</text>
        </g>
        """

    filters_svg = "<defs>"
    for f in funds_data:
        filters_svg += f"""
        <filter id="glow-flow-{f['code']}" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="{f['color']}" flood-opacity="0.65"/>
        </filter>
        """
    filters_svg += "</defs>"

    svg_full = f"""
    <div class="comp-chart-canvas-wrap">
        <svg viewBox="0 0 {width} {height}" class="comp-svg-chart" xmlns="http://www.w3.org/2000/svg">
            {filters_svg}
            {grid_svg}
            {zero_line_svg}
            {x_ticks_svg}
            {curves_svg}
            {end_tags_svg}
        </svg>
    </div>
    """
    
    leaderboard_cards = ""
    for idx, f in enumerate(funds_data):
        rank = idx + 1
        if rank == 1:
            rank_html = '<span class="flow-rank-badge rank-gold">🥇 1</span>'
        elif rank == 2:
            rank_html = '<span class="flow-rank-badge rank-silver">🥈 2</span>'
        elif rank == 3:
            rank_html = '<span class="flow-rank-badge rank-bronze">🥉 3</span>'
        else:
            rank_html = f'<span class="flow-rank-badge">{rank}</span>'
            
        val = f['final_value']
        badge_cls = "trend-up" if val >= 0 else "trend-down"
        val_formatted = format_flow_value_full(val)
        
        max_abs = max(abs(max_v), abs(min_v), 1.0)
        bar_pct = min(100, max(8, (abs(val) / max_abs) * 100))
        bar_color = f['color']
        
        leaderboard_cards += f"""
        <div class="comp-leader-card">
            <div class="comp-leader-top">
                <div class="comp-leader-left">
                    {rank_html}
                    <span class="comp-dot" style="background:{f['color']};"></span>
                    <span class="flow-code">{f['code']}</span>
                </div>
                <span class="flow-return-badge {badge_cls}">{val_formatted}</span>
            </div>
            <div class="comp-bar-track">
                <div class="comp-bar-fill" style="width:{bar_pct}%; background:{bar_color};"></div>
            </div>
        </div>
        """

    card_body = f"""
    <div class="comp-card-body">
        <div class="comp-card-header">
            <div class="comp-title-group">
                <div class="header-icon" style="background:rgba(10,132,255,0.18); color:#0A84FF;">📈</div>
                <div>
                    <h2>Fon Kümülatif Para Giriş/Çıkışı</h2>
                    <span class="comp-subtitle">{period_label}</span>
                </div>
            </div>
        </div>
        
        {svg_full}
        
        <div class="comp-leaderboard-section">
            <div class="comp-section-title">🏆 DÖNEM NET NAKİT AKIŞ LİDERLİK TABLOSU</div>
            <div class="comp-leaderboard-grid">
                {leaderboard_cards}
            </div>
        </div>
    </div>
    """
    
    return card_body

def generate_investor_chart_html(tracked_dict, period_label):
    if not tracked_dict:
        return '<div class="comp-empty">Takip listesinde veri bulunamadı.</div>'
        
    funds_data = []
    all_dates_set = set()
    
    for code, data in tracked_dict.items():
        history = sorted(data.get('price_history', []), key=lambda x: x['date'])
        if not history or len(history) < 2:
            continue
            
        start_investors = None
        investor_history = []
        
        for p in history:
            all_dates_set.add(p['date'])
            investors = int(p.get('investors', 0) or 0)
            
            if start_investors is None:
                start_investors = investors
                investor_history.append({
                    "date": p["date"],
                    "value": 0
                })
            else:
                cum_inv = investors - start_investors
                investor_history.append({
                    "date": p["date"],
                    "value": cum_inv
                })
                
        funds_data.append({
            'code': code,
            'name': data.get('name', code),
            'history': investor_history,
            'final_value': investor_history[-1]['value']
        })
        
    if not funds_data:
        return '<div class="comp-empty">Yatırımcı grafiği için en az 2 günlük veri gereklidir.</div>'
        
    all_dates = sorted(list(all_dates_set))
    if len(all_dates) < 2:
        return '<div class="comp-empty">Yatırımcı grafiği için en az 2 farklı tarih gereklidir.</div>'
        
    funds_data.sort(key=lambda x: x['final_value'], reverse=True)
    
    for i, f in enumerate(funds_data):
        f['color'] = COMP_COLORS[i % len(COMP_COLORS)]
        
    all_vals = []
    for f in funds_data:
        for p in f['history']:
            all_vals.append(p['value'])
            
    min_v = min(all_vals)
    max_v = max(all_vals)
    min_v = min(min_v, 0)
    max_v = max(max_v, 0)
    
    span = max_v - min_v
    if span <= 0:
        span = 1.0
    pad_span = max(span * 0.15, 5.0)
    y_min = min_v - pad_span
    y_max = max_v + pad_span
    total_y_range = y_max - y_min
    
    width = 1000
    height = 430
    pad_l = 85
    pad_r = 135
    pad_t = 30
    pad_b = 45
    usable_w = width - pad_l - pad_r
    usable_h = height - pad_t - pad_b
    
    def get_x(date_str):
        if date_str not in all_dates:
            return pad_l
        idx = all_dates.index(date_str)
        return pad_l + (usable_w * idx / (len(all_dates) - 1))
        
    def get_y(val):
        return pad_t + usable_h - ((val - y_min) / total_y_range) * usable_h
        
    y_zero = get_y(0.0)
    num_ticks = 5
    y_ticks = []
    for i in range(num_ticks):
        v = y_min + (total_y_range * i / (num_ticks - 1))
        y_ticks.append(v)
        
    grid_svg = ""
    for v in y_ticks:
        y_pos = get_y(v)
        inv_lbl = format_investor_value_short(v)
        grid_svg += f'<line x1="{pad_l}" y1="{y_pos:.1f}" x2="{width-pad_r}" y2="{y_pos:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1" />'
        grid_svg += f'<text x="{pad_l-12}" y="{y_pos+4:.1f}" fill="rgba(255,255,255,0.45)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="end">{inv_lbl}</text>'
        
    zero_line_svg = f"""
    <line x1="{pad_l}" y1="{y_zero:.1f}" x2="{width-pad_r}" y2="{y_zero:.1f}" stroke="rgba(255,255,255,0.30)" stroke-width="1.5" stroke-dasharray="5,4" />
    """
    
    x_ticks_svg = ""
    date_step = max(1, len(all_dates) // 6)
    display_date_indices = list(range(0, len(all_dates), date_step))
    if (len(all_dates) - 1) not in display_date_indices:
        display_date_indices.append(len(all_dates) - 1)
        
    for idx in display_date_indices:
        d_str = all_dates[idx]
        x_pos = pad_l + (usable_w * idx / (len(all_dates) - 1))
        try:
            formatted_date = datetime.strptime(d_str, "%Y-%m-%d").strftime("%d.%m")
        except:
            formatted_date = d_str[-5:]
        x_ticks_svg += f'<text x="{x_pos:.1f}" y="{height-14}" fill="rgba(255,255,255,0.55)" font-size="13" font-family="Space Grotesk, sans-serif" font-weight="600" text-anchor="middle">{formatted_date}</text>'
        x_ticks_svg += f'<line x1="{x_pos:.1f}" y1="{height-pad_b}" x2="{x_pos:.1f}" y2="{height-pad_b+6}" stroke="rgba(255,255,255,0.25)" stroke-width="1" />'

    curves_svg = ""
    end_tags_svg = ""
    
    end_positions = []
    for f in funds_data:
        h = f['history']
        coords = []
        for p in h:
            cx = get_x(p['date'])
            cy = get_y(p['value'])
            coords.append((cx, cy))
            
        if not coords:
            continue
            
        if len(coords) == 2:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f} L {coords[1][0]:.1f},{coords[1][1]:.1f}"
        else:
            d_path = f"M {coords[0][0]:.1f},{coords[0][1]:.1f}"
            for i in range(len(coords) - 1):
                p0 = coords[i]
                p1 = coords[i+1]
                mid_x = (p0[0] + p1[0]) / 2.0
                d_path += f" C {mid_x:.1f},{p0[1]:.1f} {mid_x:.1f},{p1[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
                
        color = f['color']
        curves_svg += f'<path d="{d_path}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow-inv-{f["code"]})" />'
        
        last_pt = coords[-1]
        end_positions.append({
            'fund': f,
            'last_pt': last_pt,
            'color': color,
            'target_y': last_pt[1] - 11.0
        })

    min_gap = 25.0
    for i in range(1, len(end_positions)):
        prev_y = end_positions[i-1]['target_y']
        curr_y = end_positions[i]['target_y']
        if curr_y - prev_y < min_gap:
            end_positions[i]['target_y'] = prev_y + min_gap
            
    for item in end_positions:
        f = item['fund']
        last_pt = item['last_pt']
        color = item['color']
        badge_y = item['target_y']
        final_val = f['final_value']
        val_str = format_investor_value_short(final_val)
        
        end_tags_svg += f"""
        <circle cx="{last_pt[0]:.1f}" cy="{last_pt[1]:.1f}" r="5.5" fill="{color}" stroke="#000" stroke-width="1.5" />
        <g transform="translate({last_pt[0]+8:.1f}, {badge_y:.1f})">
            <rect x="0" y="0" width="88" height="22" rx="6" fill="rgba(15,15,22,0.92)" stroke="{color}" stroke-width="1" />
            <text x="6" y="15" fill="#fff" font-size="11" font-family="Space Grotesk, sans-serif" font-weight="700">{f['code']}</text>
            <text x="82" y="15" fill="{color}" font-size="10" font-family="Space Grotesk, sans-serif" font-weight="700" text-anchor="end">{val_str}</text>
        </g>
        """

    filters_svg = "<defs>"
    for f in funds_data:
        filters_svg += f"""
        <filter id="glow-inv-{f['code']}" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="{f['color']}" flood-opacity="0.65"/>
        </filter>
        """
    filters_svg += "</defs>"

    svg_full = f"""
    <div class="comp-chart-canvas-wrap">
        <svg viewBox="0 0 {width} {height}" class="comp-svg-chart" xmlns="http://www.w3.org/2000/svg">
            {filters_svg}
            {grid_svg}
            {zero_line_svg}
            {x_ticks_svg}
            {curves_svg}
            {end_tags_svg}
        </svg>
    </div>
    """
    
    leaderboard_cards = ""
    for idx, f in enumerate(funds_data):
        rank = idx + 1
        if rank == 1:
            rank_html = '<span class="inv-rank-badge rank-gold">🥇 1</span>'
        elif rank == 2:
            rank_html = '<span class="inv-rank-badge rank-silver">🥈 2</span>'
        elif rank == 3:
            rank_html = '<span class="inv-rank-badge rank-bronze">🥉 3</span>'
        else:
            rank_html = f'<span class="inv-rank-badge">{rank}</span>'
            
        val = f['final_value']
        badge_cls = "trend-up" if val >= 0 else "trend-down"
        val_formatted = format_investor_value_full(val)
        
        max_abs = max(abs(max_v), abs(min_v), 1.0)
        bar_pct = min(100, max(8, (abs(val) / max_abs) * 100))
        bar_color = f['color']
        
        leaderboard_cards += f"""
        <div class="comp-leader-card">
            <div class="comp-leader-top">
                <div class="comp-leader-left">
                    {rank_html}
                    <span class="comp-dot" style="background:{f['color']};"></span>
                    <span class="inv-code">{f['code']}</span>
                </div>
                <span class="inv-return-badge {badge_cls}">{val_formatted}</span>
            </div>
            <div class="comp-bar-track">
                <div class="comp-bar-fill" style="width:{bar_pct}%; background:{bar_color};"></div>
            </div>
        </div>
        """

    card_body = f"""
    <div class="comp-card-body">
        <div class="comp-card-header">
            <div class="comp-title-group">
                <div class="header-icon" style="background:rgba(52,199,89,0.18); color:#34C759;">👥</div>
                <div>
                    <h2>Fon Kümülatif Yatırımcı Sayısı Değişimi</h2>
                    <span class="comp-subtitle">{period_label}</span>
                </div>
            </div>
        </div>
        
        {svg_full}
        
        <div class="comp-leaderboard-section">
            <div class="comp-section-title">🏆 DÖNEM KÜMÜLATİF YATIRIMCI DEĞİŞİM LİDERLİK TABLOSU</div>
            <div class="comp-leaderboard-grid">
                {leaderboard_cards}
            </div>
        </div>
    </div>
    """
    
    return card_body

# Backwards compatibility alias
def generate_combined_chart_html(tracked_dict, period_label):
    return generate_comparison_chart_html(tracked_dict, period_label), []

def generate_chart_script(datasets):
    return ""


async def main():
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "data.json")
    config_path = os.path.join(base_dir, "runtime_config.json")
    template_path = os.path.join(base_dir, "template", "index.html")
    output_html_path = os.path.join(base_dir, "template", "filled_index.html")
    output_img_path = os.path.join(base_dir, "infographic.png")
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    config = {
        "bg_url": "", 
        "sections": ["inflows", "outflows", "cat_in", "cat_out", "tracked"],
        "grid_cols": 2,
        "tracked_grid_cols": 1,
        "watermark_anchor": "bottom",
        "positions": {
            "inflows": "1,1",
            "outflows": "1,2",
            "cat_in": "2,1",
            "cat_out": "2,2",
            "divergent": "3,1",
            "momentum": "3,2",
            "crowding": "4,1",
            "category_rotation": "4,2",
            "tracked": "5,1",
            "tracked_rs": "5,2",
            "manager_actions": "6,1",
            "per_investor_value": "7,1",
            "predictions": "8,1"
        },
        "predictions": []
    }
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
    date_str = data['date']
    period_type = data.get('period_type', 'daily')
    actual_start_date = data.get('actual_start_date')
    actual_end_date = data.get('actual_end_date')
    
    if period_type == "daily":
        title = "GÜNLÜK TEFAS ÖZETİ"
        period_label = "Günlük"
        period_note = "(Düne Göre)"
    elif period_type == "weekly":
        title = "HAFTALIK TEFAS ÖZETİ"
        period_label = "Haftalık"
        period_note = "(Geçen Haftaya Göre)"
    elif period_type == "custom":
        title = "TEFAS TARİH ARALIĞI ÖZETİ"
        period_label = format_custom_period_label(actual_start_date, actual_end_date)
        if actual_start_date and actual_end_date:
            period_note = f"({format_turkish_date(actual_start_date)} - {format_turkish_date(actual_end_date)})"
        else:
            period_note = "(Seçilen Tarih Aralığı)"
    else:
        title = "AYLIK TEFAS ÖZETİ"
        period_label = "Aylık"
        period_note = "(Geçen Aya Göre)"
    
    # Generate HTML content based on enabled sections
    sections = config.get("sections", [])
    
    sort_mode = data.get('sort_mode', 'tl')
    
    inflows_html = generate_fund_list_html(data.get('top_inflows', []), True, sort_mode) if "inflows" in sections else ""
    outflows_html = generate_fund_list_html(data.get('top_outflows', []), False, sort_mode) if "outflows" in sections else ""
    
    cat_in_html = generate_fund_list_html(data.get('top_cat_in', []), True, sort_mode) if "cat_in" in sections else ""
    cat_out_html = generate_fund_list_html(data.get('top_cat_out', []), False, sort_mode) if "cat_out" in sections else ""
    
    inv_in_html = generate_investor_list_html(data.get('top_inv_in', [])) if "inv_in" in sections else ""
    inv_out_html = generate_investor_list_html(data.get('top_inv_out', [])) if "inv_out" in sections else ""
    divergent_html = generate_divergent_signals_html(data.get('divergent_signals', [])) if "divergent" in sections else ""
    momentum_html = generate_momentum_scores_html(data.get('momentum_scores', [])) if "momentum" in sections else ""
    crowding_html = generate_crowding_signals_html(data.get('crowding_signals', [])) if "crowding" in sections else ""
    category_rotation_html = generate_category_rotation_html(data.get('category_rotation', [])) if "category_rotation" in sections else ""

    tracked_html = generate_tracked_html(data.get('tracked', {}), period_label) if "tracked" in sections else ""
    tracked_rs_html = generate_relative_strength_html(data.get('tracked_relative_strength', [])) if "tracked_rs" in sections else ""
    manager_actions_html = generate_manager_actions_html(data.get('manager_actions', [])) if "manager_actions" in sections else ""
    # Comparison chart section
    comparison_chart_html = ""
    flow_chart_html = ""
    investor_chart_html = ""
    tracked_data = data.get('tracked', {})
    if ("comparison_chart" in sections or "return_chart" in sections) and tracked_data:
        comparison_chart_html = generate_comparison_chart_html(tracked_data, period_label)
    if "flow_chart" in sections and tracked_data:
        flow_chart_html = generate_flow_chart_html(tracked_data, period_label)
    if "investor_chart" in sections and tracked_data:
        investor_chart_html = generate_investor_chart_html(tracked_data, period_label)
    
    portfolio_diff_html = generate_portfolio_diff_html(data.get('allocation_diffs', {}), config) if "portfolio_diff" in sections else ""
    fund_report_html = generate_fund_report_html(data.get('tracked', {}), data.get('allocation_diffs', {}), config, period_label) if "fund_report" in sections else ""
    
    top_gainers_html = generate_top_returns_html(data.get('top_gainers', []), True) if "top_gainers" in sections else ""
    top_losers_html = generate_top_returns_html(data.get('top_losers', []), False) if "top_losers" in sections else ""
    
    predictions = config.get("predictions", [])
    predictions_html = generate_predictions_html(predictions) if "predictions" in sections else ""
    
    per_investor_html = generate_per_investor_html(data.get('tracked', {})) if "per_investor_value" in sections else ""
    holdings_breakdown_html = generate_holdings_breakdown_html(data.get('holdings_breakdown')) if "holdings_breakdown" in sections else ""
    
    bg_url = config.get("bg_url", "")
    if not bg_url:
        bg_url = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=2070&auto=format&fit=crop"
        
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    template = template.replace("{{BG_URL}}", bg_url)
    actual_title = config.get("main_title") if config.get("main_title") else title
    if len(sections) == 1 and "portfolio_diff" in sections:
        diffs = data.get('allocation_diffs', {})
        if diffs:
            target_fund = config.get("portfolio_diff_fund", "").upper()
            if not target_fund:
                target_fund = list(diffs.keys())[0] if diffs else ""
            actual_title = f"{target_fund} Portföy Dağılımı"
            
    template = template.replace("{{TITLE}}", actual_title)
    template = template.replace("{{SUBTITLE}}", config.get("subtitle") if config.get("subtitle") else "Paranın Yönü Nereye?")
    template = template.replace("{{DATE}}", format_turkish_date(date_str))
    template = template.replace("{{PERIOD_TYPE_LABEL}}", period_label)
    template = template.replace("{{PERIOD_NOTE}}", period_note)
    
    header_show_main = config.get("header_show_main", True)
    header_show_sub = config.get("header_show_sub", True)
    show_main = header_show_main if isinstance(header_show_main, bool) else (str(header_show_main).lower() == "true")
    show_sub = header_show_sub if isinstance(header_show_sub, bool) else (str(header_show_sub).lower() == "true")
    if len(sections) == 1 and ("predictions" in sections or "holdings_breakdown" in sections or "comparison_chart" in sections or "flow_chart" in sections or "investor_chart" in sections):
        show_main = False
        show_sub = False
    template = template.replace("{{SHOW_MAIN}}", "" if show_main else "hidden")
    template = template.replace("{{SHOW_SUB}}", "" if show_sub else "hidden")
    template = template.replace("{{TOP_INFLOWS_HTML}}", inflows_html)
    template = template.replace("{{TOP_OUTFLOWS_HTML}}", outflows_html)
    template = template.replace("{{TOP_CAT_IN_HTML}}", cat_in_html)
    template = template.replace("{{TOP_CAT_OUT_HTML}}", cat_out_html)
    template = template.replace("{{TOP_INV_IN_HTML}}", inv_in_html)
    template = template.replace("{{TOP_INV_OUT_HTML}}", inv_out_html)
    template = template.replace("{{DIVERGENT_HTML}}", divergent_html)
    template = template.replace("{{MOMENTUM_HTML}}", momentum_html)
    template = template.replace("{{CROWDING_HTML}}", crowding_html)
    template = template.replace("{{CATEGORY_ROTATION_HTML}}", category_rotation_html)
    template = template.replace("{{TRACKED_FUNDS_HTML}}", tracked_html)
    template = template.replace("{{TRACKED_RS_HTML}}", tracked_rs_html)
    template = template.replace("{{MANAGER_ACTIONS_HTML}}", manager_actions_html)
    template = template.replace("{{COMPARISON_CHART_HTML}}", comparison_chart_html)
    template = template.replace("{{RETURN_CHART_HTML}}", comparison_chart_html)
    template = template.replace("{{FLOW_CHART_HTML}}", flow_chart_html)
    template = template.replace("{{INVESTOR_CHART_HTML}}", investor_chart_html)
    template = template.replace("{{PORTFOLIO_DIFF_HTML}}", portfolio_diff_html)
    template = template.replace("{{PORTFOLIO_COLS_CLASS}}", "cols-2" if int(config.get("portfolio_diff_cols", 1)) == 2 else "cols-1")
    template = template.replace("{{FUND_REPORT_HTML}}", fund_report_html)
    template = template.replace("{{TOP_GAINERS_HTML}}", top_gainers_html)
    template = template.replace("{{TOP_LOSERS_HTML}}", top_losers_html)
    template = template.replace("{{PREDICTIONS_HTML}}", predictions_html)
    template = template.replace("{{PER_INVESTOR_HTML}}", per_investor_html)
    template = template.replace("{{HOLDINGS_BREAKDOWN_HTML}}", holdings_breakdown_html)
    template = template.replace("{{FUND_TAKAS_DIFF_HTML}}", generate_fund_takas_diff_html(config.get("custom_start_date"), config.get("custom_end_date")))
    template = template.replace("{{TAKAS_PERIOD_NOTE}}", calculated_takas_date_range)
    template = template.replace("{{FUND_TAKAS_DIFF_PCT_HTML}}", generate_fund_takas_diff_pct_html(config.get("custom_start_date"), config.get("custom_end_date")))
    template = template.replace("{{TAKAS_PCT_PERIOD_NOTE}}", calculated_takas_pct_date_range)
    template = template.replace("{{PRED_TITLE}}", config.get("pred_title", "Getiri Tahmini"))
    
    # Handle layout mode class
    if len(sections) == 1 and "predictions" in sections:
        layout_mode_class = "pred-only-layout"
    elif len(sections) == 1 and "portfolio_diff" in sections:
        layout_mode_class = "portfolio-only-layout"
    elif len(sections) == 1 and "holdings_breakdown" in sections:
        layout_mode_class = "holdings-only-layout"
    elif len(sections) == 1 and "comparison_chart" in sections:
        layout_mode_class = "comparison-only-layout"
    elif len(sections) == 1 and "flow_chart" in sections:
        layout_mode_class = "flow-only-layout"
    elif len(sections) == 1 and "investor_chart" in sections:
        layout_mode_class = "investor-only-layout"
    else:
        layout_mode_class = "normal-layout"
    template = template.replace("{{LAYOUT_MODE_CLASS}}", layout_mode_class)
    
    # Conditional Visibility and Positioning
    for s_name in ["inflows", "outflows", "cat_in", "cat_out", "inv_in", "inv_out", "divergent", "momentum", "crowding", "category_rotation", "tracked", "tracked_rs", "manager_actions", "predictions", "portfolio_diff", "fund_report", "top_gainers", "top_losers", "comparison_chart", "return_chart", "per_investor_value", "holdings_breakdown", "flow_chart", "investor_chart", "fund_takas_diff", "fund_takas_diff_pct"]:
        placeholder_show = f"{{{{SHOW_{s_name.upper()}}}}}"
        placeholder_pos = f"/* POS_{s_name.upper()} */"
        
        is_enabled = (s_name in sections) or (s_name == "comparison_chart" and "return_chart" in sections) or (s_name == "return_chart" and "comparison_chart" in sections)
        template = template.replace(placeholder_show, "" if is_enabled else "hidden")
        
        # Aggressive hiding via inline style if disabled
        if not is_enabled:
            template = template.replace(placeholder_pos, "display: none !important;")
        else:
            # If enabled, handle positioning for normal mode
            pos_val = config.get("positions", {}).get(s_name, "")
            if not pos_val and s_name == "comparison_chart":
                pos_val = config.get("positions", {}).get("return_chart", "")
            if pos_val and "," in pos_val:
                row, col = pos_val.split(",")
                template = template.replace(placeholder_pos, f"grid-row: {row}; grid-column: {col};")
            else:
                template = template.replace(placeholder_pos, "")

    # Hide footer if predictions, holdings_breakdown, or fund_takas_diff / fund_takas_diff_pct are shown
    hide_footer_sections = {"predictions", "holdings_breakdown", "fund_takas_diff", "fund_takas_diff_pct"}
    show_footer = "hidden" if any(s in hide_footer_sections for s in sections) else ""
    if show_footer:
        template = template.replace("{{SHOW_FOOTER}}", "hidden")
        # Also hide via inline if possible or just rely on class
    else:
        template = template.replace("{{SHOW_FOOTER}}", "")
    
    # Twitter Hashtags Generation
    all_fund_codes = set()
    for f in data.get('top_inflows', []): all_fund_codes.add(f['fund_code'])
    for f in data.get('top_outflows', []): all_fund_codes.add(f['fund_code'])
    for code in data.get('tracked', {}).keys(): all_fund_codes.add(code)
    hashtags = " ".join([f"#{c}" for c in sorted(list(all_fund_codes))[:10]])
    template = template.replace("{{HASHTAGS}}", hashtags)
    
    # Final cleanup substitutions
    template = template.replace("{{BG_URL}}", bg_url)
    template = template.replace("{{CANVAS_WIDTH}}", str(config.get("canvas_width", 1080)))
    template = template.replace("{{TRACKED_GRID_COLS}}", str(config.get("tracked_grid_cols", 1)))
    template = template.replace("{{GRID_COLS}}", str(config.get("grid_cols", 2)))
    template = template.replace("{{PRED_COLS}}", str(config.get("pred_cols", 1)))
    print(f"DEBUG: pred_cols from config is: {config.get('pred_cols')} (type: {type(config.get('pred_cols'))})")
    template = template.replace("{{PRED_COLS_CLASS}}", "cols-2" if int(config.get("pred_cols", 1)) == 2 else "cols-1")
    long_footer_sections = {"inflows", "outflows", "inv_in", "inv_out", "top_gainers", "top_losers", "cat_in", "cat_out"}
    short_footer_sections = {"tracked", "per_investor_value", "portfolio_diff", "fund_report", "holdings_breakdown", "comparison_chart", "return_chart", "flow_chart", "investor_chart", "fund_takas_diff", "fund_takas_diff_pct"}

    if any(s in short_footer_sections for s in sections) and not any(s in long_footer_sections for s in sections):
        footer_note = "* Veriler TEFAS üzerinden alınmıştır."
    elif any(s in long_footer_sections for s in sections):
        footer_note = clean_footer_note(data.get("footer_note", "* Veriler TEFAS üzerinden alınmıştır."))
    else:
        footer_note = "* Veriler TEFAS üzerinden alınmıştır."

    template = template.replace("{{FOOTER_NOTE}}", footer_note)
    
    # Positions and Dynamic Grid Styles
    positions = config.get("positions", {})
    grid_cols = config.get("grid_cols", 2)
    template = template.replace("/* DYNAMIC_GRID_STYLE */", f"grid-template-columns: repeat({grid_cols}, 1fr); gap: 30px;")
    
    tracked_grid_cols = config.get("tracked_grid_cols", 1)
    tracked_grid_style = f"display: grid; grid-template-columns: repeat({tracked_grid_cols}, 1fr); gap: 25px;"
    template = template.replace("/* DYNAMIC_TRACKED_GRID */", tracked_grid_style)

    # Font size replacements — inject as a <style> block to avoid IDE placeholder corruption
    item_font_size = config.get("item_font_size", 32)
    period_font_size = config.get("period_font_size", 22)
    tcode_font_size = config.get("tcode_font_size", 38)
    font_style_injection = f"""<style>
:root {{
    --item-font-size: {item_font_size}px;
    --period-font-size: {period_font_size}px;
    --tcode-font-size: {tcode_font_size}px;
}}
</style>"""
    template = template.replace("</head>", font_style_injection + "\n</head>")
    # Also do string replace as fallback in case placeholders survived
    template = template.replace("{{ITEM_FONT_SIZE}}", str(item_font_size))
    template = template.replace("{{PERIOD_FONT_SIZE}}", str(period_font_size))
    template = template.replace("{{TCODE_FONT_SIZE}}", str(tcode_font_size))
    
    # Helper to parse "r,c" and generate grid styles
    def get_grid_pos(name):
        pos = positions.get(name, "")
        if not pos or "," not in pos: return ""
        r, c = pos.split(",")
        return f"grid-row: {r}; grid-column: {c};"

    template = template.replace("/* POS_INFLOWS */", get_grid_pos("inflows"))
    template = template.replace("/* POS_OUTFLOWS */", get_grid_pos("outflows"))
    template = template.replace("/* POS_CAT_IN */", get_grid_pos("cat_in"))
    template = template.replace("/* POS_CAT_OUT */", get_grid_pos("cat_out"))
    template = template.replace("/* POS_INV_IN */", get_grid_pos("inv_in"))
    template = template.replace("/* POS_INV_OUT */", get_grid_pos("inv_out"))
    template = template.replace("/* POS_DIVERGENT */", get_grid_pos("divergent"))
    template = template.replace("/* POS_MOMENTUM */", get_grid_pos("momentum"))
    template = template.replace("/* POS_CROWDING */", get_grid_pos("crowding"))
    template = template.replace("/* POS_CATEGORY_ROTATION */", get_grid_pos("category_rotation"))
    template = template.replace("/* POS_TRACKED */", get_grid_pos("tracked"))
    template = template.replace("/* POS_TRACKED_RS */", get_grid_pos("tracked_rs"))
    template = template.replace("/* POS_MANAGER_ACTIONS */", get_grid_pos("manager_actions"))
    template = template.replace("/* POS_PREDICTIONS */", get_grid_pos("predictions"))
    template = template.replace("/* POS_PORTFOLIO_DIFF */", get_grid_pos("portfolio_diff"))
    template = template.replace("/* POS_FUND_REPORT */", get_grid_pos("fund_report"))
    template = template.replace("/* POS_TOP_GAINERS */", get_grid_pos("top_gainers"))
    template = template.replace("/* POS_TOP_LOSERS */", get_grid_pos("top_losers"))
    template = template.replace("/* POS_HOLDINGS_BREAKDOWN */", get_grid_pos("holdings_breakdown"))
    template = template.replace("/* POS_FUND_TAKAS_DIFF */", get_grid_pos("fund_takas_diff"))
    template = template.replace("/* POS_FUND_TAKAS_DIFF_PCT */", get_grid_pos("fund_takas_diff_pct"))
    
    # Watermark position is now handled relatively in index.html
    # We clear the placeholder to avoid CSS errors
    template = template.replace("/* POS_WATERMARK */", "")

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(template)
        
    # Launch Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Set canvas width to 1080 for Twitter 4:5 Native Portrait
        c_width = config.get("canvas_width", 1080)
        # device_scale_factor=2 applies retina (2160x2700 max physical output)
        page = await browser.new_page(viewport={"width": c_width, "height": 1350}, device_scale_factor=2)
        
        await page.goto(f"file:///{output_html_path}")
        
        # Wait for background image and other resources to load
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            print("Warning: Network idle timeout reached. Proceeding with screenshot.")
        
        # Adjust height according to content
        await page.wait_for_selector(".infographic-container")
        container = await page.query_selector(".infographic-container")
        box = await container.bounding_box()
        if box:
            await page.set_viewport_size({"width": c_width, "height": int(box['height'])})

        await page.screenshot(path=output_img_path)
        await browser.close()
    
    print(f"Generated successfully: {output_img_path}")

if __name__ == "__main__":
    asyncio.run(main())
