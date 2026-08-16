document.getElementById('sendBtn').addEventListener('click', async () => {
  const statusDiv = document.getElementById('status');
  const sendBtn = document.getElementById('sendBtn');
  const shouldScroll = document.getElementById('scrollChk').checked;
  
  statusDiv.style.display = 'none';
  sendBtn.disabled = true;
  sendBtn.textContent = 'Veriler Çekiliyor...';
  
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.url.includes('fintables.com/araci-kurumlar/YATFON/takas-analizi')) {
    statusDiv.className = 'error';
    statusDiv.textContent = 'Hata: Doğru Fintables sayfasında değilsiniz!';
    statusDiv.style.display = 'block';
    sendBtn.disabled = false;
    sendBtn.textContent = 'Verileri Gönder ➔';
    return;
  }
  
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: autoScrollAndScrapePage,
    args: [shouldScroll]
  }, async (results) => {
    if (!results || !results[0] || !results[0].result) {
      statusDiv.className = 'error';
      statusDiv.textContent = 'Tablo verisi okunamadı. Sayfanın yüklendiğinden emin olun.';
      statusDiv.style.display = 'block';
      sendBtn.disabled = false;
      sendBtn.textContent = 'Verileri Gönder ➔';
      return;
    }
    
    const { dates, rows } = results[0].result;
    sendBtn.textContent = 'Sunucuya Gönderiliyor...';
    
    try {
      const response = await fetch('http://127.0.0.1:8080/api/save_takas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dates, rows })
      });
      
      const resData = await response.json();
      if (response.ok && resData.status === 'success') {
        statusDiv.className = 'success';
        statusDiv.textContent = `Başarılı! ${dates.today ? dates.today : 'Bugün'} tarihli ${rows.length} hisse verisi kaydedildi.`;
      } else {
        throw new Error(resData.message || 'Sunucu hatası');
      }
    } catch (err) {
      statusDiv.className = 'error';
      statusDiv.textContent = `Bağlantı Hatası: ${err.message}`;
    }
    
    statusDiv.style.display = 'block';
    sendBtn.disabled = false;
    sendBtn.textContent = 'Verileri Gönder ➔';
  });
});

async function autoScrollAndScrapePage(shouldScroll) {
  function findHeadersDates() {
    const months = {
      'oca': '01', 'sub': '02', 'mar': '03', 'nis': '04', 'may': '05', 'haz': '06',
      'tem': '07', 'agu': '08', 'eyl': '09', 'eki': '10', 'kas': '11', 'ara': '12'
    };
    
    // Find all potential texts in headers
    const ths = Array.from(document.querySelectorAll('th, td, span, div')).map(el => el.textContent.trim());
    
    const dates = {
      today: null,
      yesterday: null,
      weekly: null,
      monthly: null,
      three_month: null
    };
    
    function parseShortDate(str) {
      if (!str) return null;
      const match = str.match(/(\d{1,2})\s+([A-Za-zŞĞÜÖÇİşğüöçi]{3})/);
      if (match) {
        const day = match[1].padStart(2, '0');
        const mName = match[2].toLowerCase().replace(/ı/g, 'i').replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's').replace(/ö/g, 'o').replace(/ç/g, 'c');
        const month = months[mName];
        if (month) {
          const year = new Date().getFullYear();
          return `${year}-${month}-${day}`;
        }
      }
      return null;
    }
    
    for (let i = 0; i < ths.length; i++) {
      if (ths[i] === 'Son Lot' && ths[i+1]) {
        dates.today = parseShortDate(ths[i+1]);
      }
      if (ths[i] === 'Günlük' && ths[i+1]) {
        dates.yesterday = parseShortDate(ths[i+1]);
      }
      if (ths[i] === 'Haftalık' && ths[i+1]) {
        dates.weekly = parseShortDate(ths[i+1]);
      }
      if (ths[i] === 'Aylık' && ths[i+1]) {
        dates.monthly = parseShortDate(ths[i+1]);
      }
      if (ths[i] === '3 Aylık' && ths[i+1]) {
        dates.three_month = parseShortDate(ths[i+1]);
      }
    }
    
    return dates;
  }

  function scrapeVisible(map) {
    const table = document.querySelector('table:not(.native-scrollable table)') || document.querySelector('table');
    if (!table) return;
    
    const trs = table.querySelectorAll('tr');
    for (let i = 1; i < trs.length; i++) {
      const tds = Array.from(trs[i].querySelectorAll('td')).map(td => td.textContent.trim());
      if (tds.length >= 6) {
        const code = tds[1].toUpperCase();
        if (/^[A-Z0-9]{4,6}$/.test(code)) {
          const pctStr = tds[3].replace('%', '').replace(/\./g, '').replace(',', '.');
          const valStr = tds[4].replace(/\./g, '').replace(',', '.');
          const lotStr = tds[5].replace(/\./g, '').replace(',', '.');
          
          const dailyChgStr = tds[6] ? tds[6].replace(/\./g, '').replace(',', '.') : '0';
          const weeklyChgStr = tds[7] ? tds[7].replace(/\./g, '').replace(',', '.') : '0';
          const monthlyChgStr = tds[8] ? tds[8].replace(/\./g, '').replace(',', '.') : '0';
          const threeMonthChgStr = tds[9] ? tds[9].replace(/\./g, '').replace(',', '.') : '0';
          
          const pct = parseFloat(pctStr) || 0.0;
          const val = parseFloat(valStr) || 0.0;
          const lot = parseFloat(lotStr) || 0.0;
          
          const daily_chg = parseFloat(dailyChgStr) || 0.0;
          const weekly_chg = parseFloat(weeklyChgStr) || 0.0;
          const monthly_chg = parseFloat(monthlyChgStr) || 0.0;
          const three_month_chg = parseFloat(threeMonthChgStr) || 0.0;
          
          if (lot > 0) {
            map.set(code, { code, pct, val, lot, daily_chg, weekly_chg, monthly_chg, three_month_chg });
          }
        }
      }
    }
  }

  const collected = new Map();
  const dates = findHeadersDates();
  
  scrapeVisible(collected);
  
  if (shouldScroll) {
    const scrollContainer = document.querySelector('.native-scrollable') || window;
    let scrollElement = scrollContainer === window ? document.documentElement : scrollContainer;
    
    let lastScrollTop = -1;
    let lastCollectedSize = 0;
    let noChangeSteps = 0;
    
    for (let i = 0; i < 300; i++) {
      scrollElement.scrollTop += 300;
      await new Promise(r => setTimeout(r, 100));
      scrapeVisible(collected);
      
      if (collected.size === lastCollectedSize) {
        noChangeSteps++;
      } else {
        noChangeSteps = 0;
      }
      
      if (scrollElement.scrollTop === lastScrollTop || noChangeSteps > 15) {
        break;
      }
      
      lastScrollTop = scrollElement.scrollTop;
      lastCollectedSize = collected.size;
    }
    
    scrollElement.scrollTop = 0;
  }
  
  return {
    dates: dates,
    rows: Array.from(collected.values())
  };
}
