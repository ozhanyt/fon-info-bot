import os
import sys
import json
from datetime import datetime

# ─── Tweepy optional import ──────────────────────────────────────────────────
try:
    import tweepy
    TWEEPY_OK = True
except ImportError:
    TWEEPY_OK = False
    print("UYARI: tweepy yuklu degil. Sadece onizleme modunda calisiyor.")
    print("Yuklemek icin: pip install tweepy\n")

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR         = os.path.dirname(__file__)
INFOGRAPHIC_PATH = os.path.join(BASE_DIR, "infographic.png")
DATA_PATH        = os.path.join(BASE_DIR, "data.json")
CONFIG_PATH      = os.path.join(BASE_DIR, "runtime_config.json")

# ─── Twitter API Credentials ─────────────────────────────────────────────────
# Bunları .env dosyasına taşıyabilir veya direkt buraya yazabilirsiniz.
API_KEY      = os.environ.get("TW_API_KEY",      "YOUR_API_KEY")
API_SECRET   = os.environ.get("TW_API_SECRET",   "YOUR_API_SECRET")
ACCESS_TOKEN = os.environ.get("TW_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
ACCESS_SECRET= os.environ.get("TW_ACCESS_SECRET","YOUR_ACCESS_SECRET")
BEARER_TOKEN = os.environ.get("TW_BEARER_TOKEN", "YOUR_BEARER_TOKEN")

# ─── Formatting helpers ───────────────────────────────────────────────────────
PERIOD_TR = {"daily": "Düne Göre", "weekly": "Haftaya Göre", "monthly": "Aya Göre", "custom": "Seçilen Aralığa Göre"}
PERIOD_LABEL = {"daily": "Günlük", "weekly": "Haftalık", "monthly": "Aylık", "custom": "Özel Aralık"}

def fmt_money(val):
    """₺639.9M  veya  -₺456.7M"""
    sign = "-" if val < 0 else "+"
    abs_v = abs(val)
    if abs_v >= 1_000_000_000:
        return f"{sign}₺{abs_v/1_000_000_000:.1f}Mlr"
    elif abs_v >= 1_000_000:
        return f"{sign}₺{abs_v/1_000_000:.1f}M"
    elif abs_v >= 1_000:
        return f"{sign}₺{abs_v/1_000:.0f}K"
    return f"{sign}₺{abs_v:.0f}"

def fmt_pct(val, sign=True):
    prefix = ("+" if val >= 0 else "") if sign else ""
    return f"{prefix}{val:.2f}%".replace(".", ",")

def tr_date(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        months = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                  "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
        return f"{d.day} {months[d.month-1]} {d.year}"
    except:
        return date_str

# ─── Per-Section Tweet Templates ─────────────────────────────────────────────

def tweet_inflows_outflows(data, period):
    """Para Girişi + Para Çıkışı birlikte ise"""
    ins  = data.get("top_inflows",  [])[:3]
    outs = data.get("top_outflows", [])[:3]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"📊 TEFAS {lbl} Para Hareketleri — {date}\n"]

    if ins:
        lines.append("🟢 En Fazla Giriş")
        for i, f in enumerate(ins, 1):
            lines.append(f"  {i}. #{f['fund_code']}  {fmt_money(f['net_flow'])}  ({fmt_pct(f['flow_pct'])})")

    if outs:
        lines.append("\n🔴 En Fazla Çıkış")
        for i, f in enumerate(outs, 1):
            lines.append(f"  {i}. #{f['fund_code']}  {fmt_money(f['net_flow'])}  ({fmt_pct(f['flow_pct'])})")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa #Yatırım")
    return "\n".join(lines)


def tweet_inflows_only(data, period):
    ins  = data.get("top_inflows", [])[:5]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"🟢 TEFAS {lbl} Para Girişi Liderleri — {date}\n"]
    for i, f in enumerate(ins, 1):
        lines.append(f"  {i}. #{f['fund_code']}  {fmt_money(f['net_flow'])}  ({fmt_pct(f['flow_pct'])})")
    lines.append("\n#TEFAS #FonYatırımı #Borsa")
    return "\n".join(lines)


def tweet_outflows_only(data, period):
    outs = data.get("top_outflows", [])[:5]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"🔴 TEFAS {lbl} Para Çıkışı Liderleri — {date}\n"]
    for i, f in enumerate(outs, 1):
        lines.append(f"  {i}. #{f['fund_code']}  {fmt_money(f['net_flow'])}  ({fmt_pct(f['flow_pct'])})")
    lines.append("\n#TEFAS #FonYatırımı #Borsa")
    return "\n".join(lines)


def tweet_categories(data, period):
    cat_in = data.get("top_cat_in", [])[:3]
    cat_out = data.get("top_cat_out", [])[:3]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"📊 TEFAS {lbl} Kategori Hareketleri — {date}\n"]

    if cat_in:
        lines.append("🟢 En Fazla Para Girişi")
        for i, c in enumerate(cat_in, 1):
            lines.append(f"  {i}. {c['fund_code']}  {fmt_money(c['net_flow'])}  ({fmt_pct(c['flow_pct'])})")

    if cat_out:
        lines.append("\n🔴 En Fazla Para Çıkışı")
        for i, c in enumerate(cat_out, 1):
            lines.append(f"  {i}. {c['fund_code']}  {fmt_money(c['net_flow'])}  ({fmt_pct(c['flow_pct'])})")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa #Yatırım")
    return "\n".join(lines)


def tweet_investors(data, period):
    inv_in  = data.get("top_inv_in",  [])[:3]
    inv_out = data.get("top_inv_out", [])[:3]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"👤 TEFAS {lbl} Yatırımcı Hareketleri — {date}\n"]

    if inv_in:
        lines.append("🟢 En Fazla Yeni Yatırımcı")
        for i, f in enumerate(inv_in, 1):
            pct = fmt_pct(f.get("inv_change_pct", 0))
            lines.append(f"  {i}. #{f['fund_code']}  {f['inv_change']:+d} kişi  ({pct})")

    if inv_out:
        lines.append("\n🔴 En Fazla Yatırımcı Kaybı")
        for i, f in enumerate(inv_out, 1):
            pct = fmt_pct(f.get("inv_change_pct", 0))
            lines.append(f"  {i}. #{f['fund_code']}  {f['inv_change']:+d} kişi  ({pct})")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Yatırımcı")
    return "\n".join(lines)


def tweet_tracked(data, period):
    tracked = data.get("tracked", {})
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"🎯 {lbl} Para Girişi ve Çıkışı — {date}\n"]
    
    tags = ["#TEFAS", "#FonYatırımı"]
    for code, f in tracked.items():
        flow_val = f.get("period_flow", 0)
        sign = "-" if flow_val < 0 else "+"
        formatted_flow = f"{sign}{abs(int(flow_val)):,}".replace(",", ".")
        lines.append(f"#{code.lower()} {formatted_flow}")
        tags.append(f"#{code.upper()}")

    lines.append("\n" + " ".join(tags))
    return "\n".join(lines)


def tweet_per_investor_value(data, period):
    tracked = data.get("tracked", {})
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"👤 TEFAS {lbl} Kişi Başı Yatırım Değeri — {date}\n"]

    def fmt_full_tl(val):
        return ("₺" + f"{val:,.0f}").replace(",", ".")

    for code, f in tracked.items():
        val = f.get("per_investor_value", 0)
        pct = f.get("per_investor_change_pct", 0)
        val_str = fmt_full_tl(val)
        pct_str = fmt_pct(pct)
        lines.append(f"  #{code} {val_str} ({pct_str})")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Yatırım")
    return "\n".join(lines)


def tweet_fund_report(data, config, period):
    tracked = data.get("tracked", {})
    diffs = data.get("allocation_diffs", {})
    target_fund = config.get("fund_report_fund", "").upper()
    if not target_fund:
        target_fund = next(iter(tracked.keys()), "")
    if not target_fund or target_fund not in tracked:
        return "Fon Karnesi için veri bulunamadı."

    item = tracked[target_fund]
    allocs = diffs.get(target_fund, [])
    top_inc = max(allocs, key=lambda x: x.get("diff", 0)) if allocs else {}
    top_dec = min(allocs, key=lambda x: x.get("diff", 0)) if allocs else {}
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "Günlük")

    flow = fmt_money(item.get("period_flow", 0))
    flow_pct = fmt_pct(item.get("period_flow_pct", 0))
    ret = fmt_pct(item.get("period_return_pct", 0))
    size = f"₺{item.get('fund_size', 0):,.0f}".replace(",", ".")
    investors = f"{int(item.get('investors', 0)):,}".replace(",", ".")
    inv_delta = f"{int(item.get('period_investor_change', 0)):+d}"
    per_inv = f"₺{item.get('per_investor_value', 0):,.0f}".replace(",", ".")
    per_inv_pct = fmt_pct(item.get("per_investor_change_pct", 0))

    lines = [f"📘 #{target_fund} Fon Karnesi — {date}\n"]
    lines.append(f"Getiri: {ret}")
    lines.append(f"Fon Büyüklüğü: {size}")
    lines.append(f"Para Giriş/Çıkışı: {flow} ({flow_pct})")
    lines.append(f"Yatırımcı: {investors} ({inv_delta} kişi)")
    lines.append(f"Kişi Başı Yatırım: {per_inv} ({per_inv_pct})")
    if top_inc:
        lines.append(f"En çok artan dağılım: {top_inc.get('asset_name', '')} ({top_inc.get('diff', 0):+.2f})".replace(".", ","))
    if top_dec:
        lines.append(f"En çok azalan dağılım: {top_dec.get('asset_name', '')} ({top_dec.get('diff', 0):+.2f})".replace(".", ","))
    lines.append(f"\nNot: {lbl.lower()} dönem karnesi; getiri, para akışı, yatırımcı ve portföy dağılımını birlikte özetler.")
    lines.append(f"\n#TEFAS #FonYatırımı #{target_fund}")
    return "\n".join(lines)


def tweet_predictions(data, config):
    preds = config.get("predictions", [])
    date  = tr_date(data["date"])
    title = config.get("pred_title", "Gün Ortası Tahmini")

    lines = [f"🔮 {title} — {date}\n"]
    for p in preds:
        code = p.get("code", "")
        val  = p.get("val", "")
        desc = p.get("desc", "")
        entry = f"  #{code}  {val}"
        if desc:
            entry += f"  ({desc})"
        lines.append(entry)

    lines.append("\n#TEFAS #Borsa #GünSonuTahmini")
    return "\n".join(lines)


def tweet_allocation_diff(data, config):
    # Target the specific fund from config
    target_fund = config.get("portfolio_diff_fund", "").upper()
    diffs = data.get("allocation_diffs", {})
    if not diffs:
        return "Portföy dağılım verisi bulunamadı."
        
    # Fallback only when no specific fund was requested
    if not target_fund:
        target_fund = list(diffs.keys())[0] if diffs else None
    elif target_fund not in diffs:
        return f"{target_fund} için portföy dağılım verisi alınamadı."
        
    if not target_fund:
        return "Portföy dağılım verisi bulunamadı."

    fund_data = diffs[target_fund]
    
    date = tr_date(data["date"])
    lines = [f"🎯 #{target_fund} Portföy Dağılımı (Düne Göre Değişim) — {date}\n"]
    
    if isinstance(fund_data, dict):
        allocations = fund_data.get("allocations", [])
    elif isinstance(fund_data, list):
        allocations = fund_data
    else:
        allocations = []

    for alloc in allocations:
        asset = alloc.get("asset") or alloc.get("asset_name", "")
        w = alloc.get("weight", 0)
        d = alloc.get("diff", 0)
        
        # Formatting difference
        if abs(d) < 0.01:
            diff_str = "(-)"
        else:
            sign = "+" if d > 0 else ""
            diff_str = f"({sign}%{d:.2f})".replace(".", ",")
            
        weight_str = f"%{w:.2f}".replace(".", ",")
        lines.append(f"{asset}: {weight_str} {diff_str}")
        
    lines.append(f"\n#TEFAS #FonYatırımı #{target_fund}")
    return "\n".join(lines)


def tweet_holdings_breakdown(data, config):
    hb = data.get("holdings_breakdown", {})
    if not hb:
        return "Etki analizi verisi bulunamadı."

    fund_code = hb.get("fund_code", "FON").upper()
    date = tr_date(data.get("date", ""))

    lines = [f"📊 #{fund_code} Portföy İçi Getiri Etki Analizi — {date}\n"]

    gainers = hb.get("top_gainers", [])[:3]
    if gainers:
        lines.append("🟢 En Çok Katkı Sağlayanlar:")
        for i, item in enumerate(gainers, 1):
            code = item.get("code", "")
            impact = item.get("impact_pct", 0)
            lines.append(f"  {i}. #{code}  {fmt_pct(impact)}")

    losers = hb.get("top_losers", [])[:3]
    if losers:
        lines.append("\n🔴 En Çok Kaybettirenler:")
        for i, item in enumerate(losers, 1):
            code = item.get("code", "")
            impact = item.get("impact_pct", 0)
            lines.append(f"  {i}. #{code}  {fmt_pct(impact)}")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa #Yatırım")
    return "\n".join(lines)


def tweet_top_returns(data, period):
    """En Çok Kazandıranlar + En Çok Kaybedenler"""
    gainers = data.get("top_gainers", [])[:3]
    losers  = data.get("top_losers",  [])[:3]
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"📊 TEFAS {lbl} Getiri — {date}\n"]

    if gainers:
        lines.append("🏆 En Çok Kazandıranlar")
        for i, f in enumerate(gainers, 1):
            lines.append(f"  {i}. #{f['fund_code']}  {fmt_pct(f.get('return_pct', 0))}")

    if losers:
        lines.append("\n💔 En Çok Kaybedenler")
        for i, f in enumerate(losers, 1):
            lines.append(f"  {i}. #{f['fund_code']}  {fmt_pct(f.get('return_pct', 0))}")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa #Yatırım")
    return "\n".join(lines)


def tweet_divergent_signals(data, period):
    signals = data.get("divergent_signals", [])[:3]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"🧭 TEFAS {lbl} Ayrışan Fonlar — {date}\n"]

    for i, s in enumerate(signals, 1):
        ret = fmt_pct(s.get("return_pct", 0))
        flow = fmt_pct(s.get("flow_pct", 0))
        inv = fmt_pct(s.get("inv_change_pct", 0))
        lines.append(f"  {i}. #{s['fund_code']}  {s.get('signal_title', '')}")
        lines.append(f"     Getiri {ret} | Para Giriş/Çıkışı {flow} | Yat. {inv}")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa #Yatırım")
    return "\n".join(lines)


def tweet_momentum_scores(data, period):
    items = data.get("momentum_scores", [])[:3]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "G\u00fcnl\u00fck")
    lines = [f"\u26a1 TEFAS {lbl} Ak\u0131ll\u0131 Skor - {date}\n"]
    for i, s in enumerate(items, 1):
        lines.append(f"  {i}. #{s['fund_code']}  Skor {s.get('momentum_score', 0):.1f}")
        lines.append(f"     Getiri {fmt_pct(s.get('return_pct', 0))} | Para Giri\u015f/\u00c7\u0131k\u0131\u015f\u0131 {fmt_pct(s.get('flow_pct', 0))}")
    lines.append("\nNot: Akıllı Skor; para girişi/çıkışı, yatırımcı değişimi ve getiri verilerinin ağırlıklı birleşiminden oluşan göreceli momentum puanıdır.")
    lines.append("\n#TEFAS #FonYat\u0131r\u0131m\u0131 #Borsa")
    return "\n".join(lines)

def tweet_crowding_signals(data, period):
    items = data.get("crowding_signals", [])[:3]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "G\u00fcnl\u00fck")
    lines = [f"\U0001f465 TEFAS {lbl} Kalabal\u0131kla\u015fma / Sakin Birikim - {date}\n"]
    for i, s in enumerate(items, 1):
        lines.append(f"  {i}. #{s['fund_code']}  {s.get('signal_title', '')}")
        lines.append(f"     Para Giri\u015f/\u00c7\u0131k\u0131\u015f\u0131 {fmt_pct(s.get('flow_pct', 0))} | Yat. {fmt_pct(s.get('inv_change_pct', 0))}")
    lines.append("\nNot: Bu bölüm, para hareketi ile yatırımcı artışının aynı hızda gitmediği fonları gösterir; yatırımcı artışı öndeyse kalabalıklaşma, para girişi öndeyse sakin birikim sinyali oluşur.")
    lines.append("\n#TEFAS #FonYat\u0131r\u0131m\u0131 #Borsa")
    return "\n".join(lines)

def tweet_category_rotation(data, period):
    items = data.get("category_rotation", [])[:3]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "G\u00fcnl\u00fck")
    lines = [f"\U0001f504 TEFAS {lbl} Kategori Rotasyonu - {date}\n"]
    for i, s in enumerate(items, 1):
        lines.append(f"  {i}. {s.get('category', '')}  {fmt_pct(s.get('flow_pct', 0))}")
        lines.append(f"     {s.get('signal_title', '')}")
    lines.append("\nNot: Kategori Rotasyonu, paranın hangi fon temalarına yöneldiğini ve hangi temalardan çıktığını gösteren özet akımdır.")
    lines.append("\n#TEFAS #FonYat\u0131r\u0131m\u0131 #Borsa")
    return "\n".join(lines)

def tweet_tracked_relative_strength(data, period):
    items = data.get("tracked_relative_strength", [])[:4]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "G\u00fcnl\u00fck")
    lines = [f"\U0001f4cf TEFAS {lbl} G\u00f6receli G\u00fc\u00e7 - {date}\n"]
    for i, s in enumerate(items, 1):
        rel = s.get('relative_strength', 0)
        rel_text = f"{'+' if rel >= 0 else ''}{rel:.2f}".replace(".", ",")
        lines.append(f"  {i}. #{s['fund_code']}  {rel_text} puan")
        lines.append(f"     Getiri {fmt_pct(s.get('period_return_pct', 0))}")
    lines.append("\nNot: Göreceli Güç, takipli fonun aynı listedeki diğer fonların ortalama performansına göre ne kadar güçlü ya da zayıf kaldığını gösterir.")
    lines.append("\n#TEFAS #FonYat\u0131r\u0131m\u0131 #Borsa")
    return "\n".join(lines)

def tweet_manager_actions(data, period):
    items = data.get("manager_actions", [])[:3]
    date = tr_date(data["date"])
    lbl = PERIOD_LABEL.get(period, "G\u00fcnl\u00fck")
    lines = [f"\U0001f9e0 TEFAS {lbl} Y\u00f6netici Hamlesi \u00d6zeti - {date}\n"]
    for i, s in enumerate(items, 1):
        inc = f"{s.get('top_increase_diff', 0):+.2f}".replace(".", ",")
        dec = f"{s.get('top_decrease_diff', 0):+.2f}".replace(".", ",")
        lines.append(f"  {i}. #{s['fund_code']}  {s.get('signal_title', '')}")
        lines.append(f"     {s.get('top_increase_asset', '')} {inc} | {s.get('top_decrease_asset', '')} {dec}")
    lines.append("\nNot: Yönetici Hamlesi Özeti, portföy dağılımındaki en belirgin artış ve azalışları özetleyerek fon yöneticisinin risk artırıp azaltmadığını hızlıca gösterir.")
    lines.append("\n#TEFAS #FonYat\u0131r\u0131m\u0131 #Borsa")
    return "\n".join(lines)


def tweet_comparison_chart(data, period):
    tracked = data.get("tracked", {})
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"📊 TEFAS {lbl} Getiri Performansları — {date}\n"]
    sorted_tracked = sorted(
        tracked.items(),
        key=lambda x: x[1].get("period_return_pct", 0),
        reverse=True
    )
    for i, (code, f) in enumerate(sorted_tracked, 1):
        ret_pct = f.get("period_return_pct", 0)
        lines.append(f"  {i}. #{code}  {'+' if ret_pct >= 0 else ''}{ret_pct:.4f}%".replace('.', ','))

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Borsa")
    return "\n".join(lines)

def tweet_flow_chart(data, period):
    tracked = data.get("tracked", {})
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"📊 TEFAS {lbl} Kümülatif Para Giriş/Çıkışı — {date}\n"]
    sorted_tracked = sorted(
        tracked.items(),
        key=lambda x: x[1].get("period_flow", 0),
        reverse=True
    )
    for i, (code, f) in enumerate(sorted_tracked, 1):
        flow_val = f.get("period_flow", 0)
        lines.append(f"  {i}. #{code}  {fmt_money(flow_val)}")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #ParaAkışı")
    return "\n".join(lines)

def tweet_investor_chart(data, period):
    tracked = data.get("tracked", {})
    date = tr_date(data["date"])
    lbl  = PERIOD_LABEL.get(period, "Günlük")

    lines = [f"👥 TEFAS {lbl} Kümülatif Yatırımcı Değişimi — {date}\n"]
    sorted_tracked = sorted(
        tracked.items(),
        key=lambda x: x[1].get("period_investor_change", 0),
        reverse=True
    )
    for i, (code, f) in enumerate(sorted_tracked, 1):
        inv_chg = f.get("period_investor_change", 0)
        pct = fmt_pct(f.get("period_investor_pct", 0))
        lines.append(f"  {i}. #{code}  {inv_chg:+d} kişi  ({pct})")

    lines.append("\n📈 Detaylar görselde ↓")
    lines.append("#TEFAS #FonYatırımı #Yatırımcı")
    return "\n".join(lines)


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


def tweet_fund_takas_diff(data, config=None):
    if config is None: config = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "fintables_history.json")
    if not os.path.exists(json_path):
        return "🏢 Hisselerdeki Yatırım Fonları Takas Akış Analizi güncellendi! Detaylar görselde ↓"
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Akış Analizi güncellendi! Detaylar görselde ↓"
        
    if not history or len(history) < 2:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Akış Analizi güncellendi! Detaylar görselde ↓"
        
    available_dates = sorted(list(history.keys()))
    s_date = config.get("custom_start_date")
    e_date = config.get("custom_end_date")
    if not s_date or s_date not in history:
        s_date = available_dates[0]
    if not e_date or e_date not in history:
        e_date = available_dates[-1]
        
    if s_date == e_date:
        s_idx = available_dates.index(s_date)
        if s_idx > 0:
            s_date = available_dates[s_idx - 1]
            
    start_data = history.get(s_date, {})
    end_data = history.get(e_date, {})
    
    capitals = load_capitals()
    
    diffs = []
    for ticker, end_info in end_data.items():
        start_info = start_data.get(ticker)
        if not start_info:
            continue
            
        capital = capitals.get(ticker, 100000000.0)
        lot_diff = end_info.get("lot", 0.0) - start_info.get("lot", 0.0)
        pct_diff = ((end_info.get("lot", 0.0) / capital) - (start_info.get("lot", 0.0) / capital)) * 100.0
        price = end_info.get("price", 0.0)
        tl_flow = lot_diff * price
        
        diffs.append({
            "ticker": ticker,
            "lot_diff": lot_diff,
            "pct_diff": pct_diff,
            "tl_flow": tl_flow
        })
        
    inflows = [d for d in diffs if d["tl_flow"] > 0]
    outflows = [d for d in diffs if d["tl_flow"] < 0]
    
    inflows = sorted(inflows, key=lambda x: x["tl_flow"], reverse=True)[:3]
    outflows = sorted(outflows, key=lambda x: x["tl_flow"])[:3]
    
    if not inflows and not outflows:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Akış Analizi güncellendi! Detaylar görselde ↓"
        
    lines = [f"🏢 Yatırım Fonları Takas Akış Analizi\n📅 {s_date} - {e_date}\n"]
    
    if inflows:
        lines.append("🟢 En Fazla Para Girişi")
        for i, d in enumerate(inflows, 1):
            lines.append(f"  {i}. #{d['ticker']}  {fmt_money(d['tl_flow'])}  ({fmt_pct(d['pct_diff'])})")
            
    if outflows:
        if inflows:
            lines.append("")
        lines.append("🔴 En Fazla Para Çıkışı")
        for i, d in enumerate(outflows, 1):
            lines.append(f"  {i}. #{d['ticker']}  {fmt_money(d['tl_flow'])}  ({fmt_pct(d['pct_diff'])})")
            
    lines.append("\n📊 Detaylar ve anomali analizi görselde ↓")
    lines.append("#Borsa #Hisse #KAP #TEFAS")
    return "\n".join(lines)



def tweet_fund_takas_diff_pct(data, config=None):
    if config is None: config = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "fintables_history.json")
    if not os.path.exists(json_path):
        return "🏢 Hisselerdeki Yatırım Fonları Takas Oran Değişim Analizi güncellendi! Detaylar görselde ↓"
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Oran Değişim Analizi güncellendi! Detaylar görselde ↓"
        
    if not history or len(history) < 2:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Oran Değişim Analizi güncellendi! Detaylar görselde ↓"
        
    available_dates = sorted(list(history.keys()))
    s_date = config.get("custom_start_date")
    e_date = config.get("custom_end_date")
    if not s_date or s_date not in history:
        s_date = available_dates[0]
    if not e_date or e_date not in history:
        e_date = available_dates[-1]
        
    if s_date == e_date:
        s_idx = available_dates.index(s_date)
        if s_idx > 0:
            s_date = available_dates[s_idx - 1]
            
    start_data = history.get(s_date, {})
    end_data = history.get(e_date, {})
    
    capitals = load_capitals()
    
    diffs = []
    for ticker, end_info in end_data.items():
        start_info = start_data.get(ticker)
        if not start_info:
            continue
            
        capital = capitals.get(ticker, 100000000.0)
        lot_diff = end_info.get("lot", 0.0) - start_info.get("lot", 0.0)
        pct_diff = ((end_info.get("lot", 0.0) / capital) - (start_info.get("lot", 0.0) / capital)) * 100.0
        price = end_info.get("price", 0.0)
        tl_flow = lot_diff * price
        
        diffs.append({
            "ticker": ticker,
            "lot_diff": lot_diff,
            "pct_diff": pct_diff,
            "tl_flow": tl_flow
        })
        
    inflows = [d for d in diffs if d["pct_diff"] > 0]
    outflows = [d for d in diffs if d["pct_diff"] < 0]
    
    inflows = sorted(inflows, key=lambda x: x["pct_diff"], reverse=True)[:3]
    outflows = sorted(outflows, key=lambda x: x["pct_diff"])[:3]
    
    if not inflows and not outflows:
        return "🏢 Hisselerdeki Yatırım Fonları Takas Oran Değişim Analizi güncellendi! Detaylar görselde ↓"
        
    lines = [f"🏢 Yatırım Fonları Takas Oran Değişim Analizi\n📅 {s_date} - {e_date}\n"]
    
    if inflows:
        lines.append("📈 En Fazla Oransal Artış")
        for i, d in enumerate(inflows, 1):
            lines.append(f"  {i}. #{d['ticker']}  {fmt_pct(d['pct_diff'])}  ({fmt_money(d['tl_flow'])})")
            
    if outflows:
        if inflows:
            lines.append("")
        lines.append("📉 En Fazla Oransal Azalış")
        for i, d in enumerate(outflows, 1):
            lines.append(f"  {i}. #{d['ticker']}  {fmt_pct(d['pct_diff'])}  ({fmt_money(d['tl_flow'])})")
            
    lines.append("\n📊 Detaylar ve oran değişim analizi görselde ↓")
    lines.append("#Borsa #Hisse #KAP #TEFAS")
    return "\n".join(lines)



# ─── Main Tweet Builder ───────────────────────────────────────────────────────

def generate_tweet_text(data, sections, config=None):
    """
    Aktif section listesine göre en uygun tweet şablonunu seçer.
    sections: ['inflows', 'outflows', 'inv_in', 'inv_out', 'tracked', 'predictions', 'portfolio_diff', ...]
    """
    if config is None: config = {}
    period = data.get("period_type", "daily")

    # Dynamically update custom period label if dates are available
    if period == "custom":
        start_date = data.get("actual_start_date")
        end_date = data.get("actual_end_date")
        if start_date and end_date:
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
                PERIOD_LABEL["custom"] = f"{parsed_start.strftime('%d.%m.%Y')} - {parsed_end.strftime('%d.%m.%Y')}"

    has = lambda s: s in sections

    # ==========================
    # Grafik Modülleri Yönlendirmeleri
    # ==========================
    chart_sections = [s for s in sections if s in ("comparison_chart", "flow_chart", "investor_chart")]
    if len(chart_sections) > 0 and len(sections) == len(chart_sections):
        if "flow_chart" in chart_sections:
            return tweet_flow_chart(data, period)
        elif "investor_chart" in chart_sections:
            return tweet_investor_chart(data, period)
        else:
            return tweet_comparison_chart(data, period)

    # ==========================
    # Tekil Şablon Seçimleri
    # ==========================
    if has("portfolio_diff") and len(sections) == 1:
        return tweet_allocation_diff(data, config)

    if has("holdings_breakdown") and len(sections) == 1:
        return tweet_holdings_breakdown(data, config)

    if has("predictions") and len(sections) == 1:
        return tweet_predictions(data, config)

    if has("tracked") and len(sections) == 1:
        return tweet_tracked(data, period)

    if has("fund_takas_diff") and len(sections) == 1:
        return tweet_fund_takas_diff(data, config)

    if has("fund_takas_diff_pct") and len(sections) == 1:
        return tweet_fund_takas_diff_pct(data, config)

    if has("divergent") and len(sections) == 1:
        return tweet_divergent_signals(data, period)

    if has("momentum") and len(sections) == 1:
        return tweet_momentum_scores(data, period)

    if has("crowding") and len(sections) == 1:
        return tweet_crowding_signals(data, period)

    if has("category_rotation") and len(sections) == 1:
        return tweet_category_rotation(data, period)

    if has("tracked_rs") and len(sections) == 1:
        return tweet_tracked_relative_strength(data, period)

    if has("manager_actions") and len(sections) == 1:
        return tweet_manager_actions(data, period)

    if has("per_investor_value") and len(sections) == 1:
        return tweet_per_investor_value(data, period)

    if has("fund_report") and len(sections) == 1:
        return tweet_fund_report(data, config, period)

    if (has("top_gainers") or has("top_losers")) and not has("inflows") and not has("outflows") and not has("cat_in") and not has("cat_out") and not has("inv_in") and not has("inv_out"):
        return tweet_top_returns(data, period)

    if has("inflows") and not has("outflows") and len(sections) == 1:
        return tweet_inflows_only(data, period)

    if has("outflows") and not has("inflows") and len(sections) == 1:
        return tweet_outflows_only(data, period)

    if (has("cat_in") or has("cat_out")) and not has("inflows") and not has("outflows") and not has("inv_in"):
        return tweet_categories(data, period)

    if (has("inv_in") or has("inv_out")) and len(sections) <= 2:
        return tweet_investors(data, period)

    # ==========================
    # Kombine Şablon Seçimleri 
    # ==========================
    if has("portfolio_diff"):
        return tweet_allocation_diff(data, config)

    if has("divergent"):
        return tweet_divergent_signals(data, period)

    if has("momentum"):
        return tweet_momentum_scores(data, period)

    if has("crowding"):
        return tweet_crowding_signals(data, period)

    if has("category_rotation"):
        return tweet_category_rotation(data, period)

    if has("tracked_rs"):
        return tweet_tracked_relative_strength(data, period)

    if has("fund_takas_diff"):
        return tweet_fund_takas_diff(data, config)

    if has("manager_actions"):
        return tweet_manager_actions(data, period)

    if has("per_investor_value"):
        return tweet_per_investor_value(data, period)

    if has("fund_report"):
        return tweet_fund_report(data, config, period)

    if has("top_gainers") or has("top_losers"):
        return tweet_top_returns(data, period)

    if has("cat_in") or has("cat_out"):
        return tweet_categories(data, period)

    if has("inv_in") or has("inv_out"):
        return tweet_investors(data, period)

    if has("inflows") and not has("outflows"):
        return tweet_inflows_only(data, period)

    if has("outflows") and not has("inflows"):
        return tweet_outflows_only(data, period)

    if has("holdings_breakdown"):
        return tweet_holdings_breakdown(data, config)

    # Fallback: her şey varsa inflows+outflows özeti
    return tweet_inflows_outflows(data, period)


# ─── Twitter Post ─────────────────────────────────────────────────────────────

def post_to_twitter(tweet_text):
    if not TWEEPY_OK:
        print("❌ tweepy yüklü değil, gönderilemedi.")
        return False

    if "YOUR_API_KEY" in API_KEY:
        print("❌ API anahtarları ayarlanmamış.")
        print("   Ortam değişkenlerini set edin veya twitter_bot.py'yi düzenleyin.")
        return False

    try:
        # v1.1 — medya yükleme
        auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
        api  = tweepy.API(auth)
        print("🖼️  Resim yükleniyor...")
        media = api.media_upload(INFOGRAPHIC_PATH)
        print(f"✅ Resim yüklendi. Media ID: {media.media_id}")

        # v2 — tweet gönder
        client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_SECRET
        )
        print("📤 Tweet gönderiliyor...")
        response = client.create_tweet(text=tweet_text, media_ids=[media.media_id])
        tweet_id = response.data['id']
        print(f"✅ Tweet paylaşıldı! https://x.com/i/web/status/{tweet_id}")
        return True

    except Exception as e:
        print(f"❌ Hata: {e}")
        return False


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    # 1. Dosya kontrolü
    for path, name in [(INFOGRAPHIC_PATH, "infographic.png"), (DATA_PATH, "data.json"), (CONFIG_PATH, "runtime_config.json")]:
        if not os.path.exists(path):
            print(f"❌ Dosya bulunamadı: {name}")
            sys.exit(1)

    # 2. Verileri yükle
    with open(DATA_PATH,   "r", encoding="utf-8") as f: data    = json.load(f)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f: config  = json.load(f)

    sections = config.get("sections", ["inflows", "outflows"])

    # 3. Tweet oluştur
    tweet_text = generate_tweet_text(data, sections, config)

    # 4. Önizleme
    print("=" * 60)
    print("📋 TWEET ÖNİZLEME")
    print("=" * 60)
    print(tweet_text)
    print(f"\n({len(tweet_text)} karakter / 280 max)")
    print("=" * 60)

    if len(tweet_text) > 280:
        print("⚠️  Tweet 280 karakteri aşıyor! Kısaltma yapılacak...")
        tweet_text = tweet_text[:277] + "..."

    # 5. Onay al
    answer = input("\nTweet gönderilsin mi? (e/h) → ").strip().lower()
    if answer != "e":
        print("İptal edildi.")
        return

    # 6. Gönder
    post_to_twitter(tweet_text)


if __name__ == "__main__":
    main()
