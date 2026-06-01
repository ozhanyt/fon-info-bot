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


# Distinct colors for each fund line
CHART_COLORS = ["#5AC8FA", "#30D158", "#BF5AF2", "#FF9F0A", "#FF453A", "#64D2FF", "#FFD60A", "#FF6482"]

def generate_combined_chart_html(tracked_dict, period_label):
    """Generate a single combined chart card showing all funds' cumulative returns."""
    datasets = []
    
    for i, (code, data) in enumerate(tracked_dict.items()):
        history = data.get('price_history', [])
        if len(history) < 2:
            continue
        color = CHART_COLORS[i % len(CHART_COLORS)]
        datasets.append({
            "code": code,
            "labels": [p["date"][-5:] for p in history],
            "values": [p["cum_return_pct"] for p in history],
            "color": color
        })
    
    if not datasets:
        return "", ""
    
    # Build legend HTML
    legend_items = []
    for ds in datasets:
        legend_items.append(
            f'<span class="chart-legend-item">'
            f'<span class="chart-legend-dot" style="background:{ds["color"]};"></span>'
            f'{ds["code"]}</span>'
        )
    legend_html = " ".join(legend_items)
    
    chart_card_html = f"""
    <div class="t-chart-card">
        <div class="t-chart-header">
            <span class="t-chart-title">Karşılaştırmalı {period_label} Getiri (%)</span>
            <div class="t-chart-legend">{legend_html}</div>
        </div>
        <div class="t-chart-container">
            <canvas id="combined-return-chart"></canvas>
        </div>
    </div>"""
    
    return chart_card_html, datasets


def generate_chart_script(datasets):
    """Generate a <script> block that renders a single combined Chart.js line chart."""
    if not datasets:
        return ""
    
    import json as _json
    datasets_json = _json.dumps(datasets, ensure_ascii=False)
    
    return f"""
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    const fundData = {datasets_json};
    
    // Merge all unique labels in order
    const allLabels = [];
    fundData.forEach(function(fd) {{
        fd.labels.forEach(function(l) {{
            if (allLabels.indexOf(l) === -1) allLabels.push(l);
        }});
    }});
    allLabels.sort();
    
    const chartDatasets = fundData.map(function(fd) {{
        const mappedValues = allLabels.map(function(l) {{
            const idx = fd.labels.indexOf(l);
            return idx >= 0 ? fd.values[idx] : null;
        }});
        return {{
            label: fd.code,
            data: mappedValues,
            borderColor: fd.color,
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            pointRadius: 0,
            pointHoverRadius: 5,
            fill: false,
            tension: 0.3,
            spanGaps: true
        }};
    }});
    
    const ctx = document.getElementById('combined-return-chart');
    if (!ctx) return;
    
    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: allLabels,
            datasets: chartDatasets
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                    backgroundColor: 'rgba(0,0,0,0.85)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 12,
                    bodyFont: {{ size: 13 }},
                    callbacks: {{
                        label: function(ctx) {{
                            return ' ' + ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(2) + '%';
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{
                    ticks: {{ color: 'rgba(255,255,255,0.5)', font: {{ size: 11 }}, maxRotation: 0 }},
                    grid: {{ color: 'rgba(255,255,255,0.06)' }}
                }},
                y: {{
                    position: 'right',
                    ticks: {{
                        color: 'rgba(255,255,255,0.5)',
                        font: {{ size: 11 }},
                        callback: function(v) {{ return v.toFixed(1) + '%'; }}
                    }},
                    grid: {{ color: 'rgba(255,255,255,0.06)' }}
                }}
            }}
        }}
    }});
}});
</script>"""


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

    # Combined chart as SEPARATE section
    chart_card_html = ""
    chart_script = ""
    tracked_data = data.get('tracked', {})
    if "return_chart" in sections and tracked_data:
        chart_card_html, chart_datasets = generate_combined_chart_html(tracked_data, period_label)
        chart_script = generate_chart_script(chart_datasets)
    
    
    portfolio_diff_html = generate_portfolio_diff_html(data.get('allocation_diffs', {}), config) if "portfolio_diff" in sections else ""
    fund_report_html = generate_fund_report_html(data.get('tracked', {}), data.get('allocation_diffs', {}), config, period_label) if "fund_report" in sections else ""
    
    top_gainers_html = generate_top_returns_html(data.get('top_gainers', []), True) if "top_gainers" in sections else ""
    top_losers_html = generate_top_returns_html(data.get('top_losers', []), False) if "top_losers" in sections else ""
    
    predictions = config.get("predictions", [])
    predictions_html = generate_predictions_html(predictions) if "predictions" in sections else ""
    
    per_investor_html = generate_per_investor_html(data.get('tracked', {})) if "per_investor_value" in sections else ""
    
    bg_url = config.get("bg_url", "")
    if not bg_url:
        bg_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=2564&auto=format&fit=crop"
    
    print(f"DEBUG: Generating image with sections: {sections}")
    print(f"DEBUG: Background URL: {bg_url}")

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    template = template.replace("{{TITLE}}", config.get("main_title") if config.get("main_title") else title)
    template = template.replace("{{SUBTITLE}}", config.get("subtitle") if config.get("subtitle") else "Paranın Yönü Nereye?")
    template = template.replace("{{DATE}}", format_turkish_date(date_str))
    template = template.replace("{{PERIOD_NOTE}}", period_note)
    template = template.replace("({{PERIOD_TYPE_LABEL}})", f"({period_label})")
    
    # Header Visibility
    show_main = config.get("header_show_main", True)
    show_sub = config.get("header_show_sub", True)
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
    template = template.replace("{{RETURN_CHART_HTML}}", chart_card_html)
    template = template.replace("{{PORTFOLIO_DIFF_HTML}}", portfolio_diff_html)
    template = template.replace("{{PORTFOLIO_COLS_CLASS}}", "cols-2" if int(config.get("portfolio_diff_cols", 1)) == 2 else "cols-1")
    template = template.replace("{{FUND_REPORT_HTML}}", fund_report_html)
    template = template.replace("{{TOP_GAINERS_HTML}}", top_gainers_html)
    template = template.replace("{{TOP_LOSERS_HTML}}", top_losers_html)
    template = template.replace("{{PREDICTIONS_HTML}}", predictions_html)
    template = template.replace("{{PER_INVESTOR_HTML}}", per_investor_html)
    template = template.replace("{{PRED_TITLE}}", config.get("pred_title", "Getiri Tahmini"))
    
    # Handle layout mode class
    if len(sections) == 1 and "predictions" in sections:
        layout_mode_class = "pred-only-layout"
    elif len(sections) == 1 and "portfolio_diff" in sections:
        layout_mode_class = "portfolio-only-layout"
        # Override title to be dynamic for portfolio diff
        diffs = data.get('allocation_diffs', {})
        if diffs:
            target_fund = config.get("portfolio_diff_fund", "").upper()
            if not target_fund:
                target_fund = list(diffs.keys())[0] if diffs else ""
            template = template.replace(config.get("main_title") if config.get("main_title") else title, f"{target_fund} Portföy Dağılımı")
    else:
        layout_mode_class = "normal-layout"
    template = template.replace("{{LAYOUT_MODE_CLASS}}", layout_mode_class)
    
    # Conditional Visibility and Positioning
    for s_name in ["inflows", "outflows", "cat_in", "cat_out", "inv_in", "inv_out", "divergent", "momentum", "crowding", "category_rotation", "tracked", "tracked_rs", "manager_actions", "predictions", "portfolio_diff", "fund_report", "top_gainers", "top_losers", "return_chart", "per_investor_value"]:
        placeholder_show = f"{{{{SHOW_{s_name.upper()}}}}}"
        placeholder_pos = f"/* POS_{s_name.upper()} */"
        
        is_enabled = s_name in sections
        template = template.replace(placeholder_show, "" if is_enabled else "hidden")
        
        # Aggressive hiding via inline style if disabled
        if not is_enabled:
            template = template.replace(placeholder_pos, "display: none !important;")
        else:
            # If enabled, handle positioning for normal mode
            pos_val = config.get("positions", {}).get(s_name, "")
            if pos_val and "," in pos_val:
                row, col = pos_val.split(",")
                template = template.replace(placeholder_pos, f"grid-row: {row}; grid-column: {col};")
            else:
                template = template.replace(placeholder_pos, "")

    # Hide footer if ONLY predictions are shown
    show_footer = "hidden" if len(sections) == 1 and "predictions" in sections else ""
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
    short_footer_sections = {"tracked", "per_investor_value", "portfolio_diff", "fund_report"}

    if any(s in long_footer_sections for s in sections):
        footer_note = clean_footer_note(data.get("footer_note", "* Veriler TEFAS üzerinden alınmıştır."))
    elif any(s in short_footer_sections for s in sections):
        footer_note = "* Veriler TEFAS üzerinden alınmıştır."
    else:
        footer_note = clean_footer_note(data.get("footer_note", "* Veriler TEFAS üzerinden alınmıştır."))

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
    
    # Watermark position is now handled relatively in index.html
    # We clear the placeholder to avoid CSS errors
    template = template.replace("/* POS_WATERMARK */", "")

    # Inject chart script before </body> if charts are enabled
    if chart_script:
        template = template.replace("</body>", chart_script + "\n</body>")

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
        
        # If charts are present, wait a bit for Chart.js to render
        if chart_script:
            import asyncio as _asyncio
            await _asyncio.sleep(1.5)

        await page.screenshot(path=output_img_path)
        await browser.close()
    
    print(f"Generated successfully: {output_img_path}")

if __name__ == "__main__":
    asyncio.run(main())
