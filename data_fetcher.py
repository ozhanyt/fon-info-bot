import sys
import os
import json
import logging
import time
import unicodedata
from datetime import datetime, timedelta
import concurrent.futures
import argparse

sys.path.append(r"C:\Users\svkto\.gemini\antigravity\scratch\borsapy_repo")
import borsapy as bp
import pandas as pd
from tefas_api import TefasAPI

tapi = TefasAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def parse_yyyymmdd(date_str):
    return datetime.strptime(date_str, "%Y%m%d")


def parse_iso_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")


def period_month_window(period_type):
    if period_type == "monthly":
        return 2
    if period_type == "weekly":
        return 1
    return 1


def find_previous_available_date(target_date_str, max_days_back=10):
    target_dt = parse_yyyymmdd(target_date_str)
    for i in range(max_days_back + 1):
        d_str = (target_dt - timedelta(days=i)).strftime("%Y%m%d")
        res = tapi.get_summary_for_period(d_str, d_str)
        if res and len(res) > 0:
            return res, d_str
    return [], target_date_str


def resolve_period_dates(period_type, custom_start_date=None, custom_end_date=None):
    if custom_start_date and custom_end_date:
        requested_start = parse_iso_date(custom_start_date).strftime("%Y%m%d")
        requested_end = parse_iso_date(custom_end_date).strftime("%Y%m%d")
        if requested_start > requested_end:
            raise ValueError("Başlangıç tarihi bitiş tarihinden büyük olamaz.")

        end_summary, actual_end_date = find_previous_available_date(requested_end, max_days_back=10)
        start_summary, actual_start_date = find_previous_available_date(requested_start, max_days_back=10)
        return {
            "requested_start_date": requested_start,
            "requested_end_date": requested_end,
            "actual_start_date": actual_start_date,
            "actual_end_date": actual_end_date,
            "start_summary": start_summary,
            "end_summary": end_summary,
            "period_key": "custom",
        }

    today = datetime.now()
    if period_type == "daily":
        target_end_date = today.strftime("%Y%m%d")
        if today.weekday() == 0:
            target_start = (today - timedelta(days=3)).strftime("%Y%m%d")
        else:
            target_start = (today - timedelta(days=1)).strftime("%Y%m%d")
    elif period_type == "weekly":
        target_end_date = today.strftime("%Y%m%d")
        target_start = (today - timedelta(days=7)).strftime("%Y%m%d")
    else:
        target_end_date = today.strftime("%Y%m%d")
        target_start = (today - timedelta(days=30)).strftime("%Y%m%d")

    end_summary, actual_end_date = find_previous_available_date(target_end_date, max_days_back=7)
    actual_end_dt = parse_yyyymmdd(actual_end_date)
    if period_type == "daily":
        back_target = (actual_end_dt - timedelta(days=1)).strftime("%Y%m%d")
    elif period_type == "weekly":
        back_target = (actual_end_dt - timedelta(days=7)).strftime("%Y%m%d")
    else:
        first_day_current_month = actual_end_dt.replace(day=1)
        back_target = (first_day_current_month - timedelta(days=1)).strftime("%Y%m%d")

    start_summary, actual_start_date = find_previous_available_date(back_target, max_days_back=10)
    return {
        "requested_start_date": target_start,
        "requested_end_date": target_end_date,
        "actual_start_date": actual_start_date,
        "actual_end_date": actual_end_date,
        "start_summary": start_summary,
        "end_summary": end_summary,
        "period_key": period_type,
    }


def log_resolved_range(resolved):
    requested_start = resolved.get("requested_start_date", "-")
    requested_end = resolved.get("requested_end_date", "-")
    actual_start = resolved.get("actual_start_date", "-")
    actual_end = resolved.get("actual_end_date", "-")
    period_key = resolved.get("period_key", "-")
    logging.info(
        "Resolved date range [%s] requested=%s -> %s | actual=%s -> %s",
        period_key,
        requested_start,
        requested_end,
        actual_start,
        actual_end,
    )


def get_prev_row(df, period_type):
    latest_date = df.index[-1]
    if period_type == "daily":
        return df.iloc[-2] if len(df) > 1 else df.iloc[0]
    elif period_type == "weekly":
        target = latest_date - timedelta(days=7)
    elif period_type == "monthly":
        # Target the last day of the previous calendar month
        first_day_of_current_month = latest_date.replace(day=1)
        target = first_day_of_current_month - timedelta(days=1)
    else:
        return df.iloc[-2]
        
    past_df = df[df.index <= target]
    return past_df.iloc[-1] if not past_df.empty else df.iloc[0]

def get_fund_flow(fund_code, period_type):
    try:
        df = tapi.get_fund_history(fund_code, period_months=3)
        if df.empty or len(df) < 2:
            return None
            
        shares_col = 'Shares' if 'Shares' in df.columns else 'Tedavüldeki Pay Sayısı' if 'Tedavüldeki Pay Sayısı' in df.columns else None
        if shares_col is None:
            df['Shares'] = df['FundSize'] / df['Price']
            shares_col = 'Shares'
            
        latest = df.iloc[-1]
        prev = get_prev_row(df, period_type)
        
        latest_shares = latest[shares_col]
        prev_shares = prev[shares_col]
        
        # Inflow/Outflow calculation
        net_flow = (latest_shares - prev_shares) * latest['Price']
        flow_pct = (net_flow / prev['FundSize']) * 100 if prev['FundSize'] > 0 else 0
        
        # Price-based return calculation
        return_pct = ((latest['Price'] - prev['Price']) / prev['Price']) * 100 if prev['Price'] > 0 else 0
        
        # Investor change
        inv_latest = latest.get('Investors', 0)
        inv_prev = prev.get('Investors', 0)
        inv_change = inv_latest - inv_prev
        inv_change_pct = (inv_change / inv_prev * 100) if inv_prev > 0 else 0
        
        info = tapi.get_fund_info(fund_code)
        return {
            'fund_code': fund_code,
            'name': info.get('fonUnvan', '') if info else fund_code,
            'net_flow': float(net_flow),
            'fund_size': float(latest['FundSize']),
            'flow_pct': float(flow_pct),
            'return_pct': float(return_pct),
            'investors': int(inv_latest),
            'inv_change': int(inv_change),
            'inv_change_pct': float(inv_change_pct)
        }
    except Exception as e:
        logging.error(f"Error fetching fund {fund_code}: {e}")
        return None

def normalize(s):
    if not s:
        return ""
    s = str(s).strip().lower()
    for src, dst in {'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c'}.items():
        s = s.replace(src, dst)
    if any(mark in s for mark in ("Ã", "Ä", "Å", "Ì", "ã", "ä", "å", "ì")):
        try:
            repaired = s.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if repaired:
                s = repaired
        except Exception:
            pass
    for src, dst in {'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c'}.items():
        s = s.replace(src, dst)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return s

def build_divergent_signals(results_filtered):
    signals = []

    for r in results_filtered:
        flow_pct = float(r.get('flow_pct', 0))
        return_pct = float(r.get('return_pct', 0))
        inv_change = int(r.get('inv_change', 0))
        inv_change_pct = float(r.get('inv_change_pct', 0))
        candidates = []

        if flow_pct < 0 and return_pct > 0:
            candidates.append(("flow_down_return_up", "Çıkışa rağmen getiri güçlü", "Çıkış var ama performans pozitif", abs(flow_pct) * 1.4 + abs(return_pct) * 1.1))
        if flow_pct > 0 and return_pct < 0:
            candidates.append(("flow_up_return_down", "Girişe rağmen getiri zayıf", "Para girişi var ama performans negatif", abs(flow_pct) * 1.4 + abs(return_pct) * 1.1))
        if flow_pct < 0 and inv_change > 0:
            candidates.append(("flow_down_investor_up", "Çıkışa rağmen yatırımcı artıyor", "Para çıkıyor ama yatırımcı sayısı artıyor", abs(flow_pct) * 1.2 + abs(inv_change_pct)))
        if flow_pct > 0 and inv_change < 0:
            candidates.append(("flow_up_investor_down", "Girişe rağmen yatırımcı azalıyor", "Para giriyor ama yatırımcı sayısı düşüyor", abs(flow_pct) * 1.2 + abs(inv_change_pct)))

        if not candidates:
            continue

        signal_key, signal_title, signal_summary, signal_score = max(candidates, key=lambda x: x[3])
        signals.append({
            'fund_code': r['fund_code'],
            'name': r.get('name', ''),
            'signal_key': signal_key,
            'signal_title': signal_title,
            'signal_summary': signal_summary,
            'signal_score': float(signal_score),
            'flow_pct': flow_pct,
            'return_pct': return_pct,
            'inv_change': inv_change,
            'inv_change_pct': inv_change_pct,
            'net_flow': float(r.get('net_flow', 0)),
            'fund_size': float(r.get('fund_size', 0)),
            'investors': int(r.get('investors', 0))
        })

    signals.sort(key=lambda x: x['signal_score'], reverse=True)
    return signals[:5]

def build_rank_map(results, key):
    if not results:
        return {}
    sorted_results = sorted(results, key=lambda x: x.get(key, 0))
    total = max(len(sorted_results) - 1, 1)
    rank_map = {}
    for idx, item in enumerate(sorted_results):
        rank_map[item['fund_code']] = (idx / total) * 100
    return rank_map

def build_momentum_scores(results_filtered):
    if not results_filtered:
        return []

    flow_ranks = build_rank_map(results_filtered, 'flow_pct')
    ret_ranks = build_rank_map(results_filtered, 'return_pct')
    inv_ranks = build_rank_map(results_filtered, 'inv_change_pct')
    scores = []

    for r in results_filtered:
        code = r['fund_code']
        score = flow_ranks.get(code, 0) * 0.45 + inv_ranks.get(code, 0) * 0.35 + ret_ranks.get(code, 0) * 0.20
        scores.append({
            'fund_code': code,
            'name': r.get('name', ''),
            'momentum_score': round(score, 2),
            'flow_pct': float(r.get('flow_pct', 0)),
            'return_pct': float(r.get('return_pct', 0)),
            'inv_change_pct': float(r.get('inv_change_pct', 0)),
            'inv_change': int(r.get('inv_change', 0))
        })

    scores.sort(key=lambda x: x['momentum_score'], reverse=True)
    return scores[:5]

def build_crowding_signals(results_filtered):
    signals = []

    for r in results_filtered:
        flow_pct = float(r.get('flow_pct', 0))
        inv_change_pct = float(r.get('inv_change_pct', 0))
        return_pct = float(r.get('return_pct', 0))

        if flow_pct <= 0 and inv_change_pct <= 0:
            continue

        crowd_gap = inv_change_pct - flow_pct
        quiet_gap = flow_pct - inv_change_pct

        if crowd_gap >= 1.0 and inv_change_pct > 0:
            label = "Kalabal\u0131kla\u015fma"
            summary = "Yat\u0131r\u0131mc\u0131 art\u0131\u015f\u0131 para giri\u015finden h\u0131zl\u0131"
            signal_score = crowd_gap + max(inv_change_pct, 0) * 0.35
        elif quiet_gap >= 1.0 and flow_pct > 0:
            label = "Sakin Birikim"
            summary = "Para giri\u015fi yat\u0131r\u0131mc\u0131 art\u0131\u015f\u0131ndan g\u00fc\u00e7l\u00fc"
            signal_score = quiet_gap + max(flow_pct, 0) * 0.35
        else:
            continue

        signals.append({
            'fund_code': r['fund_code'],
            'name': r.get('name', ''),
            'signal_title': label,
            'signal_summary': summary,
            'signal_score': round(signal_score, 2),
            'flow_pct': flow_pct,
            'return_pct': return_pct,
            'inv_change_pct': inv_change_pct
        })

    signals.sort(key=lambda x: x['signal_score'], reverse=True)
    return signals[:5]

def build_category_rotation(cat_list):
    rotations = []

    for c in cat_list:
        flow_pct = float(c.get('flow_pct', 0))
        net_flow = float(c.get('net_flow', 0))
        if abs(flow_pct) < 0.05:
            continue
        rotations.append({
            'category': c.get('fund_code', ''),
            'signal_title': "Rotasyon G\u00fc\u00e7leniyor" if flow_pct > 0 else "Rotasyon Zay\u0131fl\u0131yor",
            'signal_summary': "Kategoriye para giri\u015fi var" if flow_pct > 0 else "Kategoriden para \u00e7\u0131k\u0131\u015f\u0131 var",
            'flow_pct': flow_pct,
            'net_flow': net_flow,
            'rotation_score': round(abs(flow_pct), 2)
        })

    rotations.sort(key=lambda x: x['rotation_score'], reverse=True)
    return rotations[:5]

def build_relative_strength(tracked_data):
    if not tracked_data:
        return []

    returns = [float(v.get('period_return_pct', 0)) for v in tracked_data.values()]
    avg_return = sum(returns) / len(returns) if returns else 0
    ranked = []

    for code, item in tracked_data.items():
        rel = float(item.get('period_return_pct', 0)) - avg_return
        ranked.append({
            'fund_code': code,
            'name': item.get('name', ''),
            'period_return_pct': float(item.get('period_return_pct', 0)),
            'relative_strength': round(rel, 2),
            'period_flow_pct': float(item.get('period_flow_pct', 0)),
            'signal_title': "Grup \u00fcst\u00fc" if rel >= 0 else "Grup alt\u0131",
            'signal_summary': "Takip listesinin ortalamas\u0131na g\u00f6re"
        })

    ranked.sort(key=lambda x: x['relative_strength'], reverse=True)
    return ranked

def build_manager_actions(allocation_diffs, tracked_data=None):
    if not allocation_diffs:
        return []
    tracked_data = tracked_data or {}

    risk_assets = ("Hisse Senedi", "Gayrimenkul Yat\u0131r\u0131m Fonu", "Giri\u015fim Sermayesi Yat\u0131r\u0131m Fonu")
    defensive_assets = ("Repo", "Para Piyasas\u0131", "Mevduat", "Nakit Teminat")
    actions = []

    for code, allocations in allocation_diffs.items():
        if not allocations:
            continue
        top_inc = max(allocations, key=lambda x: x.get('diff', 0))
        top_dec = min(allocations, key=lambda x: x.get('diff', 0))
        risk_delta = sum(float(a.get('diff', 0)) for a in allocations if any(k in a.get('asset_name', '') for k in risk_assets))
        defensive_delta = sum(float(a.get('diff', 0)) for a in allocations if any(k in a.get('asset_name', '') for k in defensive_assets))

        if risk_delta > 0.2 and defensive_delta < -0.2:
            title = "Risk art\u0131r\u0131yor"
        elif risk_delta < -0.2 and defensive_delta > 0.2:
            title = "Defansifle\u015fiyor"
        else:
            title = "Portf\u00f6y ayar\u0131 yap\u0131yor"

        actions.append({
            'fund_code': code,
            'name': tracked_data.get(code, {}).get('name', ''),
            'signal_title': title,
            'signal_summary': f"Artan: {top_inc.get('asset_name', '')} | Azalan: {top_dec.get('asset_name', '')}",
            'top_increase_asset': top_inc.get('asset_name', ''),
            'top_increase_diff': float(top_inc.get('diff', 0)),
            'top_decrease_asset': top_dec.get('asset_name', ''),
            'top_decrease_diff': float(top_dec.get('diff', 0)),
            'risk_delta': round(risk_delta, 2),
            'defensive_delta': round(defensive_delta, 2)
        })

    return actions

def fetch_all_flows(period_type, selected_cats=None, sort_mode='tl', resolved_dates=None):
    mode_label = resolved_dates.get("period_key", period_type)
    logging.info(f"Screening funds for {mode_label} period (Sort: {sort_mode})...")
    
    display_categories = [
        "Hisse Senedi", "Değişken", "Karma", "Fon Sepeti", "Borçlanma Araçları",
        "K.Maden", "Katılım", "Para Piy.", "Serbest (Genel)", "Serbest (P.Piy)",
        "Serbest (Döviz)", "Serbest (K.Vade)", "Serbest (Katılım)"
    ]
    cat_rules = {
        "hisse senedi": {"any": ["hisse senedi"], "none": ["serbest"]},
        "degisken": {"any": ["degisken"], "none": ["serbest"]},
        "karma": {"any": ["karma"], "none": ["serbest"]},
        "fon sepeti": {"any": ["fon sepeti"], "none": ["serbest"]},
        "borclanma araclari": {"any": ["borclanma araclari"], "none": ["serbest"]},
        "k.maden": {"any": ["kiymetli maden", "altin"], "none": ["serbest"]},
        "katilim": {"any": ["katilim"], "none": ["serbest"]},
        "para piy.": {"any": ["para piyasas"], "none": ["serbest"]},
        "serbest (genel)": {"all": ["serbest"], "none": ["para piyasas", "doviz", "kisa vadeli", "katilim"]},
        "serbest (p.piy)": {"all": ["serbest", "para piyasas"]},
        "serbest (doviz)": {"all": ["serbest", "doviz"]},
        "serbest (k.vade)": {"all": ["serbest", "kisa vadeli"]},
        "serbest (katilim)": {"all": ["serbest", "katilim"]},
    }
    
    def check_match(ftype, fund_name, rule):
        ftype_l = normalize(f"{ftype or ''} {fund_name or ''}")
        if "all" in rule:
            if not all(kw in ftype_l for kw in rule["all"]):
                return False
        if "any" in rule:
            if not any(kw in ftype_l for kw in rule["any"]):
                return False
        if "none" in rule:
            if any(kw in ftype_l for kw in rule["none"]):
                return False
        return True

    all_cats = display_categories[:]
    normalized_cat_rules = {normalize(k): v for k, v in cat_rules.items()}
    
    summary_data = resolved_dates["end_summary"]
    prev_summary_data = resolved_dates["start_summary"]
    actual_start_date = resolved_dates["actual_start_date"]
    actual_end_date = resolved_dates["actual_end_date"]

    if not summary_data or not prev_summary_data:
        logging.error("No summary data received from TEFAS!")
        return [], [], [], [], [], [], [], [], [], [], [], [], "Hata: TEFAS verisi alınamadı."

    prev_inv_map = {item['fonKodu']: item.get('kisiSayisi', 0) for item in prev_summary_data}
    prev_map = {item['fonKodu']: item for item in prev_summary_data}
    results_all = []
    code_to_type = {}

    for end_item in summary_data:
        code = end_item['fonKodu']
        start_item = prev_map.get(code)
        if not start_item:
            continue

        code_to_type[code] = end_item.get('fonTurAciklama', 'Diğer')
        investors = int(end_item.get('kisiSayisi', 0) or 0)
        if investors < 500:
            continue

        inv_prev = prev_inv_map.get(code, 0)
        inv_change = investors - inv_prev if inv_prev > 0 else 0
        inv_change_pct = (inv_change / inv_prev * 100) if inv_prev > 0 else 0

        end_price = float(end_item.get('fiyat', 0) or 0)
        start_price = float(start_item.get('fiyat', 0) or 0)
        end_shares = float(end_item.get('tedPaySayisi', 0) or 0)
        start_shares = float(start_item.get('tedPaySayisi', 0) or 0)
        end_size = float(end_item.get('portfoyBuyukluk', 0) or 0)
        start_size = float(start_item.get('portfoyBuyukluk', 0) or 0)
        if end_shares <= 0 or start_shares <= 0:
            continue

        net_flow = (end_shares - start_shares) * end_price
        flow_pct = (net_flow / start_size * 100) if start_size > 0 else 0
        return_pct = ((end_price - start_price) / start_price * 100) if start_price > 0 else 0

        results_all.append({
            'fund_code': code,
            'name': end_item.get('fonUnvan', ''),
            'net_flow': float(net_flow),
            'fund_size': float(end_size),
            'flow_pct': float(flow_pct),
            'return_pct': return_pct,
            'investors': investors,
            'inv_change': int(inv_change),
            'inv_change_pct': float(inv_change_pct)
        })

    results_filtered = []
    if selected_cats:
        for r in results_all:
            code = r['fund_code']
            ftype = code_to_type.get(code, 'Diğer')
            fund_name = r.get('name', '')
            matched = False
            for cat_name in selected_cats:
                rule = normalized_cat_rules.get(normalize(cat_name))
                if rule and check_match(ftype, fund_name, rule):
                    matched = True
                    break
            if matched:
                results_filtered.append(r)
    else:
        for r in results_all:
            code = r['fund_code']
            ftype = code_to_type.get(code, 'Diğer').lower()
            if "para piyasası" in ftype or "döviz" in ftype:
                continue
            results_filtered.append(r)
    
    # SORT LEADERS
    sort_key = 'net_flow' if sort_mode == 'tl' else 'flow_pct'
    inflows_only = [r for r in results_filtered if r[sort_key] > 0]
    outflows_only = [r for r in results_filtered if r[sort_key] < 0]
    inflows_only.sort(key=lambda x: x[sort_key], reverse=True)
    outflows_only.sort(key=lambda x: x[sort_key], reverse=False)
    
    top_inflows = inflows_only[:5]
    top_outflows = outflows_only[:5]
    
    # TOP GAINERS / LOSERS
    valid_returns = [r for r in results_filtered if r.get('return_pct', 0) != -100]
    gainers = sorted([r for r in valid_returns if r.get('return_pct', 0) > 0], key=lambda x: x['return_pct'], reverse=True)
    losers = sorted([r for r in valid_returns if r.get('return_pct', 0) < 0], key=lambda x: x['return_pct'])
    top_gainers = gainers[:5]
    top_losers = losers[:5]

    # INVESTOR LEADERS
    inv_gainers = sorted([r for r in results_filtered if r.get('inv_change', 0) > 0], key=lambda x: x['inv_change'], reverse=True)
    inv_losers = sorted([r for r in results_filtered if r.get('inv_change', 0) < 0], key=lambda x: x['inv_change'])
    top_inv_in = inv_gainers[:5]
    top_inv_out = inv_losers[:5]
    
    # Category flows
    cat_flows = {}
    for res in results_all:
        code = res['fund_code']
        ftype = code_to_type.get(code, 'Diğer').replace("Şemsiye Fonu", "").strip()
        if ftype not in cat_flows:
            cat_flows[ftype] = {'fund_code': ftype, 'name': '', 'net_flow': 0, 'fund_size': 0}
        cat_flows[ftype]['net_flow'] += res.get('net_flow', 0)
        cat_flows[ftype]['fund_size'] += res.get('fund_size', 0)
        
    for k, v in cat_flows.items():
        v['flow_pct'] = (v['net_flow'] / v['fund_size']) * 100 if v['fund_size'] > 0 else 0
        
    cat_list = list(cat_flows.values())
    cat_list_in = sorted([c for c in cat_list if c['net_flow'] > 0], key=lambda x: x['net_flow'], reverse=True)[:5]
    cat_list_out = sorted([c for c in cat_list if c['net_flow'] < 0], key=lambda x: x['net_flow'])[:5]
    
    # Footer
    if selected_cats:
        excl = [cat for cat in all_cats if cat not in selected_cats]
        footer_detail = f"{', '.join(excl)} kategorileri hariç tutulmuştur." if excl else "Tüm ana kategoriler dahil edilmiştir."
    else:
        footer_detail = "Para Piyasası ve Döviz fonları hariç tutulmuştur."
    footer_note = f"* Veriler TEFAS üzerinden alınmıştır. 500+ yatırımcısı olan fonlar dahil edilmiştir. {footer_detail}"
    
    return top_inflows, top_outflows, cat_list_in, cat_list_out, top_inv_in, top_inv_out, top_gainers, top_losers, [], [], [], [], footer_note


def build_fund_report_history(df, period_type, custom_range=False):
    if df.empty or len(df) < 2:
        return [], "Performans Eğrisi"

    if custom_range:
        chart_df = df
        title = "Seçilen Aralık Performansı"
    elif period_type == "daily":
        chart_df = df.tail(min(len(df), 22))
        title = "Son 1 Ay Performans Eğrisi"
    elif period_type == "weekly":
        weekly_df = df.resample("W-FRI").last().dropna(subset=["Price"])
        chart_df = weekly_df.tail(min(len(weekly_df), 8))
        title = "Son 1 Ay Haftalık Performans"
    else:
        monthly_df = df.resample("ME").last().dropna(subset=["Price"])
        if len(monthly_df) >= 2:
            chart_df = monthly_df.tail(min(len(monthly_df), 3))
        else:
            chart_df = df.resample("W-FRI").last().dropna(subset=["Price"]).tail(min(len(df), 6))
        title = "Aylık Görünüm Performansı"

    if chart_df.empty or len(chart_df) < 2:
        return [], title

    base_price = float(chart_df.iloc[0]["Price"])
    history = []
    for idx, row in chart_df.iterrows():
        cum_ret = ((float(row["Price"]) - base_price) / base_price) * 100 if base_price > 0 else 0
        history.append({
            "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
            "price": float(row["Price"]),
            "cum_return_pct": round(cum_ret, 4),
        })
    return history, title


def fetch_tracked_funds(tracked_codes, period_type, resolved_dates):
    tracked_data = {}
    custom_range = resolved_dates.get("period_key") == "custom"
    actual_start_date = resolved_dates["actual_start_date"]
    actual_end_date = resolved_dates["actual_end_date"]

    for code in tracked_codes:
        try:
            if custom_range:
                df = tapi.get_fund_history_between(code, actual_start_date, actual_end_date)
            else:
                period_months = 2 if period_type == "monthly" else 1
                df = tapi.get_fund_history(code, period_months=period_months)

            if df is None or df.empty or len(df) < 2:
                continue

            latest = df.iloc[-1]
            info = tapi.get_fund_info(code)
            prev = df.iloc[0] if custom_range else get_prev_row(df, period_type)
            return_pct = ((latest['Price'] - prev['Price']) / prev['Price']) * 100 if prev['Price'] > 0 else 0

            prev_shares = 0
            latest_shares = 0
            flow = 0
            flow_pct = 0
            inv_latest = int(info.get('yatirimciSayi', 0)) if info else int(latest.get('Investors', 0) or 0)
            inv_prev = int(prev.get('Investors', 0) or 0)
            inv_change = inv_latest - inv_prev if inv_prev > 0 else 0
            inv_change_pct = (inv_change / inv_prev * 100) if inv_prev > 0 else 0

            if len(df) >= 2:
                start_date_str = prev.name.strftime("%Y%m%d")
                end_date_str = latest.name.strftime("%Y%m%d")
                size_data = tapi.get_fund_size_history(code, start_date_str, end_date_str)
                fund_item = next((x for x in size_data if x['fonKodu'] == code), None)
                if fund_item:
                    prev_shares = fund_item.get('ilkPayAdedi', 0)
                    latest_shares = fund_item.get('sonPayAdedi', 0)
                    son_size = fund_item.get('sonPortfoyDegeri', 0)
                    latest_price = (son_size / latest_shares) if latest_shares > 0 else latest['Price']
                    flow = (latest_shares - prev_shares) * latest_price if prev_shares > 0 else 0
                    flow_pct = fund_item.get('payAdetDegisim', 0)

            latest_fund_size = info.get('portBuyukluk', 0) if info else float(latest['FundSize'])
            per_inv_value = latest_fund_size / inv_latest if inv_latest > 0 else 0

            prev_fund_size = prev.get('FundSize', 0)
            per_inv_value_prev = prev_fund_size / inv_prev if inv_prev > 0 else 0

            per_inv_change_pct = ((per_inv_value - per_inv_value_prev) / per_inv_value_prev * 100) if per_inv_value_prev > 0 else 0

            prev_date = prev.name if hasattr(prev, 'name') else df.index[0]
            history_df = df[df.index >= prev_date]
            base_price = float(prev['Price'])
            price_history = []
            for idx, row in history_df.iterrows():
                cum_ret = ((float(row['Price']) - base_price) / base_price) * 100 if base_price > 0 else 0
                date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)
                price_history.append({
                    "date": date_str,
                    "price": float(row['Price']),
                    "cum_return_pct": round(cum_ret, 4)
                })

            fund_report_history, fund_report_history_title = build_fund_report_history(df, period_type, custom_range=custom_range)

            tracked_data[code] = {
                'fund_code': code,
                'name': info.get('fonUnvan', '') if info else code,
                'price': float(latest['Price']),
                'fund_size': float(latest_fund_size),
                'investors': int(inv_latest),
                'period_flow': float(flow),
                'period_flow_pct': float(flow_pct),
                'period_investor_change': int(inv_change),
                'period_investor_pct': float(inv_change_pct),
                'period_return_pct': float(return_pct),
                'per_investor_value': float(per_inv_value),
                'per_investor_value_prev': float(per_inv_value_prev),
                'per_investor_change_pct': float(per_inv_change_pct),
                'price_history': price_history,
                'fund_report_history': fund_report_history,
                'fund_report_history_title': fund_report_history_title
            }
        except Exception as e:
            logging.error(f"Error fetching tracked fund {code}: {e}")
    return tracked_data


def fetch_allocation_diff(fund_code, period_type, resolved_dates):
    try:
        start_date_str = resolved_dates["actual_start_date"]
        end_date_str = resolved_dates["actual_end_date"]
        
        dist_latest = tapi.get_portfolio_distribution(fund_code, end_date_str)
        dist_prev = tapi.get_portfolio_distribution(fund_code, start_date_str)
        
        if not dist_latest or not dist_prev:
            return None
            
        df_latest = pd.DataFrame(dist_latest)
        df_prev = pd.DataFrame(dist_prev)
        
        merged = pd.merge(df_latest, df_prev, on='asset_name', how='outer', suffixes=('_latest', '_prev'))
        merged['weight_latest'] = merged['weight_latest'].fillna(0)
        merged['weight_prev'] = merged['weight_prev'].fillna(0)
        merged['diff'] = merged['weight_latest'] - merged['weight_prev']
        
        merged = merged.sort_values(by='weight_latest', ascending=False)
        
        results = []
        for _, row in merged.iterrows():
            if row['weight_latest'] == 0 and row['weight_prev'] == 0:
                continue
            results.append({
                'asset_name': row['asset_name'],
                'weight': round(float(row['weight_latest']), 2),
                'diff': round(float(row['diff']), 2)
            })
            
        return results
            
    except Exception as e:
        logging.error(f"Error fetching allocation diff for {fund_code}: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("period", choices=["daily", "weekly", "monthly"], default="daily", nargs="?")
    parser.add_argument("tracked", default="TLY, DFI, PHE", nargs="?")
    parser.add_argument("cats", default="", nargs="?")
    parser.add_argument("--sort", choices=["tl", "pct"], default="tl")
    parser.add_argument("--start-date", dest="start_date")
    parser.add_argument("--end-date", dest="end_date")
    args = parser.parse_args()
    
    selected_cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    raw_tracked = args.tracked.split(",")
    tracked_codes = [code.strip().upper() for code in raw_tracked if code.strip()]
    if not tracked_codes: tracked_codes = ['TLY', 'DFI', 'PHE']
        
    resolved_dates = resolve_period_dates(args.period, args.start_date, args.end_date)
    log_resolved_range(resolved_dates)
    
    tracked_data = fetch_tracked_funds(tracked_codes, args.period, resolved_dates)

    # Fetch allocation diffs early before heavier market-wide calls trigger rate limits
    allocation_diffs = {}
    for code in tracked_codes:
        diff_data = fetch_allocation_diff(code, args.period, resolved_dates)
        if diff_data:
            allocation_diffs[code] = diff_data

    top_inflows, top_outflows, top_cat_in, top_cat_out, top_inv_in, top_inv_out, top_gainers, top_losers, divergent_signals, momentum_scores, crowding_signals, category_rotation, footer_note = fetch_all_flows(
        args.period,
        selected_cats,
        args.sort,
        resolved_dates
    )

    tracked_relative_strength = build_relative_strength(tracked_data)
    manager_actions = build_manager_actions(allocation_diffs, tracked_data)
    period_key = resolved_dates.get("period_key", args.period)
    
    output = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'period_type': period_key,
        'sort_mode': args.sort,
        'requested_start_date': resolved_dates.get("requested_start_date"),
        'requested_end_date': resolved_dates.get("requested_end_date"),
        'actual_start_date': resolved_dates.get("actual_start_date"),
        'actual_end_date': resolved_dates.get("actual_end_date"),
        'top_inflows': top_inflows,
        'top_outflows': top_outflows,
        'top_cat_in': top_cat_in,
        'top_cat_out': top_cat_out,
        'top_inv_in': top_inv_in,
        'top_inv_out': top_inv_out,
        'top_gainers': top_gainers,
        'top_losers': top_losers,
        'divergent_signals': divergent_signals,
        'momentum_scores': momentum_scores,
        'crowding_signals': crowding_signals,
        'category_rotation': category_rotation,
        'tracked': tracked_data,
        'tracked_relative_strength': tracked_relative_strength,
        'allocation_diffs': allocation_diffs,
        'manager_actions': manager_actions,
        'footer_note': footer_note
    }
    
    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logging.info(f"Data saved to {out_path}")
