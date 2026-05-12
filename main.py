from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import psycopg2
import json
import os
import threading

app = Flask(__name__)
CORS(app)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://breakout_db_9v3a_user:RTb5LlHo3BpJCnewkV0970Lx1OxIsSY4@dpg-d80efknavr4c73b0vucg-a/breakout_db_9v3a')

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Skapa tabeller om de inte finns och lägg till saknade kolumner"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id SERIAL PRIMARY KEY,
                scan_date DATE NOT NULL,
                scan_time TIME NOT NULL,
                scan_mode VARCHAR(20) NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                index_name VARCHAR(50),
                price FLOAT,
                change_pct FLOAT,
                high100 FLOAT,
                vol_today FLOAT,
                vol_avg FLOAT,
                vol_ratio FLOAT,
                days INT,
                rsi FLOAT,
                sector VARCHAR(100),
                sector_bullish BOOLEAN,
                ma50 FLOAT,
                ma200 FLOAT,
                ma50_pct FLOAT,
                ma200_pct FLOAT,
                macd FLOAT,
                macd_hist FLOAT,
                atr FLOAT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        # Migration: lägg till nya kolumner om de saknas
        for col in ['rsi FLOAT', 'sector VARCHAR(100)', 'sector_bullish BOOLEAN', 'ma50 FLOAT', 'ma200 FLOAT', 
                    'ma50_pct FLOAT', 'ma200_pct FLOAT',
                    'macd FLOAT', 'macd_hist FLOAT', 'atr FLOAT',
                    'scan_mode VARCHAR(20)']:
            col_name = col.split()[0]
            cur.execute(f'ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS {col}')
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized!")
    except Exception as e:
        print(f"DB init error: {e}")

# Aktielista för automatisk skanning
SP500 = [
    'MMM','AOS','ABT','ABBV','ACN','ADBE','AMD','AES','AFL','A','APD','ABNB','AKAM','ALB',
    'ALLE','LNT','ALL','GOOGL','AMZN','AEE','AAL','AEP','AXP','AIG','AMT','AWK','AMP',
    'AME','AMGN','APH','ADI','ANSS','AON','APA','AAPL','AMAT','APTV','ADM','ANET','AIZ',
    'T','ATO','ADSK','ADP','AZO','AVB','AVY','AXON','BKR','BALL','BAC','BK','BBWI','BAX',
    'BDX','BBY','BIO','BIIB','BLK','BX','BA','BMY','AVGO','BR','BRO','BG','CDNS','CPT',
    'CPB','COF','CAH','KMX','CCL','CARR','CAT','CBOE','CBRE','CDW','CE','COR','CNC','CNP',
    'CF','CRL','SCHW','CHTR','CVX','CMG','CB','CHD','CI','CINF','CTAS','CSCO','C','CFG',
    'CLX','CME','CMS','KO','CTSH','CL','CMCSA','CAG','COP','ED','STZ','CEG','COO','CPRT',
    'GLW','COST','CTRA','CCI','CSX','CMI','CVS','DHI','DHR','DRI','DVA','DECK','DE','DAL',
    'DVN','DXCM','FANG','DLR','DFS','DG','DLTR','D','DPZ','DOV','DOW','DTE','DUK','DD',
    'EMN','ETN','EBAY','ECL','EIX','EW','EA','ELV','LLY','EMR','ENPH','ETR','EOG','EQT',
    'EFX','EQIX','EQR','ESS','EL','ETSY','EG','ES','EXC','EXPE','EXPD','EXR','XOM','FFIV',
    'FDS','FICO','FAST','FRT','FDX','FIS','FITB','FSLR','FE','FI','FMC','F','FTNT','FTV',
    'BEN','FCX','GRMN','IT','GE','GEHC','GEN','GNRC','GD','GIS','GM','GPC','GILD','GS',
    'HAL','HIG','HAS','HCA','HSIC','HSY','HES','HPE','HLT','HOLX','HD','HON','HRL','HST',
    'HWM','HPQ','HUBB','HUM','HBAN','IBM','IEX','IDXX','ITW','INCY','IR','PODD','INTC',
    'ICE','IFF','IP','IPG','INTU','ISRG','IVZ','INVH','IQV','IRM','JPM','JNJ','JCI',
    'K','KVUE','KDP','KEY','KEYS','KMB','KIM','KMI','KLAC','KHC','KR','LHX','LH','LRCX',
    'LW','LVS','LDOS','LEN','LKQ','LLY','LMT','L','LOW','LULU','LYB','MTB','MRO','MPC',
    'MAR','MMC','MLM','MAS','MA','MKC','MCD','MCK','MDT','MRK','META','MET','MTD','MGM',
    'MCHP','MU','MSFT','MAA','MRNA','MHK','MOH','TAP','MDLZ','MPWR','MNST','MCO','MS',
    'MOS','MSI','MSCI','NDAQ','NTAP','NFLX','NEM','NEE','NKE','NI','NDSN','NSC','NTRS',
    'NOC','NCLH','NRG','NUE','NVDA','NVR','NXPI','ORLY','OXY','ODFL','OMC','ON','OKE',
    'ORCL','OTIS','PCAR','PKG','PANW','PH','PAYX','PAYC','PYPL','PNR','PEP','PFE','PM',
    'PSX','PNC','POOL','PPG','PPL','PFG','PG','PGR','PRU','PEG','PTC','PSA','PHM','QCOM',
    'RL','RJF','RTX','O','REG','REGN','RF','RSG','RMD','ROK','ROL','ROP','ROST','RCL',
    'SPGI','CRM','SBAC','SLB','STX','SRE','NOW','SHW','SPG','SJM','SNA','SO','LUV','SWK',
    'SBUX','STT','STLD','STE','SYK','SYF','SNPS','SYY','TMUS','TROW','TTWO','TGT','TEL',
    'TDY','TFX','TER','TSLA','TXN','TXT','TMO','TJX','TSCO','TT','TDG','TRV','TRMB',
    'TFC','TYL','TSN','USB','UBER','UDR','ULTA','UNP','UAL','UPS','URI','UNH','UHS',
    'VLO','VTR','VRSN','VRSK','VZ','VRTX','V','VST','VMC','WMT','DIS','WM','WAT','WEC',
    'WFC','WELL','WST','WDC','WY','WHR','WMB','WTW','XEL','XYL','YUM','ZBRA','ZBH','ZTS'
]

DOW = ['AAPL','MSFT','UNH','GS','HD','MCD','CAT','V','AMGN','TRV',
       'AXP','HON','JPM','IBM','BA','MMM','DIS','JNJ','CVX','MRK',
       'WMT','NKE','PG','CRM','CSCO','INTC','VZ','KO','DOW','WBA']

def calculate_ma(closes, period):
    """Beräkna glidande medelvärde"""
    if len(closes) < period:
        return None
    # closes är nyast först
    return round(sum(closes[:period]) / period, 2)

def calculate_macd(closes):
    """Beräkna MACD (12,26,9)"""
    if len(closes) < 35:
        return None, None
    prices = list(reversed(closes[:35]))
    
    def ema(data, period):
        k = 2 / (period + 1)
        ema_val = sum(data[:period]) / period
        for price in data[period:]:
            ema_val = price * k + ema_val * (1 - k)
        return ema_val
    
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd_line = round(ema12 - ema26, 2)
    
    # Signal line (9-period EMA of MACD) — simplified
    signal = round(macd_line * 0.9, 2)
    histogram = round(macd_line - signal, 2)
    return macd_line, histogram

def calculate_atr(highs, lows, closes, period=14):
    """Beräkna ATR (Average True Range)"""
    if len(highs) < period + 1:
        return None
    # Data är nyast först, vänd för beräkning
    h = list(reversed(highs[:period+2]))
    l = list(reversed(lows[:period+2]))
    c = list(reversed(closes[:period+2]))
    
    trs = []
    for i in range(1, len(h)):
        tr = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        trs.append(tr)
    
    atr = sum(trs[:period]) / period
    return round(atr, 2)

def calculate_rsi(closes, period=14):
    """Beräkna RSI (Relative Strength Index)"""
    if len(closes) < period + 1:
        return None
    # closes är nyast först, vänd för beräkning
    prices = list(reversed(closes[:period + 10]))
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def analyze_ticker(ticker, hist, mode='breakout', days=100, vol_factor=1.5, consol_days=20, consol_range=10):
    """Analysera en aktie för breakout eller konsolidering"""
    hist = hist.sort_index(ascending=False)
    closes  = hist['Close'].tolist()
    highs   = hist['High'].tolist()
    lows    = hist['Low'].tolist()
    volumes = hist['Volume'].tolist()

    if len(closes) < days + 2:
        return None

    today_close = closes[0]
    today_vol   = volumes[0]
    prev_close  = closes[1]
    change_pct  = ((today_close - prev_close) / prev_close) * 100
    avg_vol     = sum(volumes[1:21]) / 20

    if mode == 'breakout':
        lookback = closes[1:days+1]
        high100  = max(lookback)
        if today_close > high100 and today_vol >= avg_vol * vol_factor:
            rsi   = calculate_rsi(closes)
            ma50  = calculate_ma(closes, 50)
            ma200 = calculate_ma(closes, 200)
            macd_line, macd_hist = calculate_macd(closes)
            atr   = calculate_atr(highs, lows, closes)
            ma50_pct  = round(((today_close - ma50) / ma50 * 100), 1) if ma50 else None
            ma200_pct = round(((today_close - ma200) / ma200 * 100), 1) if ma200 else None
            sector = get_ticker_sector(ticker)
            sector_info = sector_status_cache.get(sector, {})
            sector_bullish = sector_info.get('bullish', None)
            return {
                'mode': 'breakout',
                'sector': sector,
                'sector_bullish': sector_bullish,
                'change_pct': change_pct,
                'high100': high100,
                'today_vol': today_vol,
                'avg_vol': avg_vol,
                'vol_ratio': today_vol / avg_vol,
                'price': today_close,
                'rsi': rsi,
                'ma50': ma50,
                'ma200': ma200,
                'ma50_pct': ma50_pct,
                'ma200_pct': ma200_pct,
                'macd': macd_line,
                'macd_hist': macd_hist,
                'atr': atr
            }

    elif mode == 'consol':
        if len(closes) < consol_days + 2:
            return None
        consol_closes  = closes[1:consol_days+1]
        consol_volumes = volumes[1:consol_days+1]
        consol_high    = max(consol_closes)
        consol_low     = min(consol_closes)
        range_pct      = ((consol_high - consol_low) / consol_low) * 100
        avg_vol        = sum(consol_volumes) / len(consol_volumes)

        if range_pct <= consol_range and today_close > consol_high and today_vol >= avg_vol * vol_factor:
            rsi   = calculate_rsi(closes)
            ma50  = calculate_ma(closes, 50)
            ma200 = calculate_ma(closes, 200)
            macd_line, macd_hist = calculate_macd(closes)
            atr   = calculate_atr(highs, lows, closes)
            ma50_pct  = round(((today_close - ma50) / ma50 * 100), 1) if ma50 else None
            ma200_pct = round(((today_close - ma200) / ma200 * 100), 1) if ma200 else None
            sector = get_ticker_sector(ticker)
            sector_info = sector_status_cache.get(sector, {})
            sector_bullish = sector_info.get('bullish', None)
            return {
                'mode': 'consol',
                'sector': sector,
                'sector_bullish': sector_bullish,
                'change_pct': change_pct,
                'high100': consol_high,
                'today_vol': today_vol,
                'avg_vol': avg_vol,
                'vol_ratio': today_vol / avg_vol,
                'price': today_close,
                'range_pct': range_pct,
                'rsi': rsi,
                'ma50': ma50,
                'ma200': ma200,
                'ma50_pct': ma50_pct,
                'ma200_pct': ma200_pct,
                'macd': macd_line,
                'macd_hist': macd_hist,
                'atr': atr
            }
    return None

# Sektors-ETF mapping
SECTOR_ETFS = {
    'XLK': 'Technology',
    'XLV': 'Healthcare', 
    'XLF': 'Financials',
    'XLE': 'Energy',
    'XLY': 'Consumer Cyclical',
    'XLP': 'Consumer Defensive',
    'XLI': 'Industrials',
    'XLB': 'Basic Materials',
    'XLRE': 'Real Estate',
    'XLU': 'Utilities',
    'XLC': 'Communication Services'
}

sector_status_cache = {}

def get_sector_status():
    """Hämta bullish/bearish status för varje sektor baserat på MA20"""
    global sector_status_cache
    try:
        end   = datetime.today()
        start = end - timedelta(days=40)
        for etf, sector in SECTOR_ETFS.items():
            try:
                stock = yf.Ticker(etf)
                hist  = stock.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
                if hist.empty or len(hist) < 20:
                    continue
                hist = hist.sort_index(ascending=False)
                closes = hist['Close'].tolist()
                price  = closes[0]
                ma20   = sum(closes[:20]) / 20
                sector_status_cache[sector] = {
                    'bullish': price > ma20,
                    'etf': etf,
                    'price': round(price, 2),
                    'ma20':  round(ma20, 2)
                }
            except:
                continue
        print(f"Sektorstatus uppdaterad: {len(sector_status_cache)} sektorer")
    except Exception as e:
        print(f"Sektor-fel: {e}")

# Hårdkodad sektormappning för S&P 500 vanligaste aktier
TICKER_SECTORS = {
    'AAPL':'Technology','MSFT':'Technology','NVDA':'Technology','GOOGL':'Communication Services',
    'AMZN':'Consumer Cyclical','META':'Communication Services','TSLA':'Consumer Cyclical',
    'AVGO':'Technology','JPM':'Financials','LLY':'Healthcare','V':'Financials',
    'UNH':'Healthcare','XOM':'Energy','MA':'Financials','JNJ':'Healthcare',
    'PG':'Consumer Defensive','COST':'Consumer Defensive','HD':'Consumer Cyclical',
    'ABBV':'Healthcare','CRM':'Technology','MRK':'Healthcare','CVX':'Energy',
    'NFLX':'Communication Services','AMD':'Technology','PEP':'Consumer Defensive',
    'ADBE':'Technology','CSCO':'Technology','WMT':'Consumer Defensive','BAC':'Financials',
    'ACN':'Technology','INTC':'Technology','QCOM':'Technology','TXN':'Technology',
    'MU':'Technology','AMAT':'Technology','LRCX':'Technology','KLAC':'Technology',
    'PANW':'Technology','FTNT':'Technology','CRWD':'Technology','NOW':'Technology',
    'AKAM':'Technology','GLW':'Technology','MNST':'Consumer Defensive',
    'GE':'Industrials','CAT':'Industrials','HON':'Industrials','RTX':'Industrials',
    'UPS':'Industrials','DE':'Industrials','BA':'Industrials','LMT':'Industrials',
    'GS':'Financials','MS':'Financials','BLK':'Financials','SCHW':'Financials','CBOE':'Financials',
    'AMGN':'Healthcare','GILD':'Healthcare','BIIB':'Healthcare','VRTX':'Healthcare',
    'CVS':'Healthcare','CI':'Healthcare','HUM':'Healthcare','ELV':'Healthcare',
    'XOM':'Energy','CVX':'Energy','COP':'Energy','SLB':'Energy','EOG':'Energy',
    'NEE':'Utilities','DUK':'Utilities','SO':'Utilities','AEP':'Utilities',
    'AMT':'Real Estate','PLD':'Real Estate','EQIX':'Real Estate',
    'LIN':'Basic Materials','APD':'Basic Materials','FCX':'Basic Materials',
}

_sector_cache = {}

def get_hist(ticker, start, end):
    """Hämta historik från yfinance med retry och konsekvent sortering."""
    for attempt in range(3):
        try:
            h = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
            if not h.empty and len(h) >= 10:
                # Sortera alltid på samma sätt för konsekvent data
                return h.sort_index(ascending=True)
        except Exception as e:
            print(f"yfinance retry {attempt+1} för {ticker}: {e}")
    return None

def get_ticker_sector(ticker):
    """Hämta sektor via yfinance med cache så vi inte anropar API:et upprepade gånger"""
    if ticker in _sector_cache:
        return _sector_cache[ticker]
    # Kolla hårdkodad karta först (snabbare)
    if ticker in TICKER_SECTORS:
        _sector_cache[ticker] = TICKER_SECTORS[ticker]
        return TICKER_SECTORS[ticker]
    # Annars hämta från yfinance
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector') or info.get('sectorDisp') or 'Unknown'
        _sector_cache[ticker] = sector
        return sector
    except Exception:
        _sector_cache[ticker] = 'Unknown'
        return 'Unknown' 

def run_auto_scan():
    """Kör automatisk skanning — både breakout och konsolidering"""
    print(f"Startar automatisk skanning {datetime.now()}")

    # Hämta sektorstatus först
    get_sector_status()

    all_tickers = list(set(SP500 + DOW))
    days       = 100
    vol_factor = 1.5
    consol_days  = 20
    consol_range = 10
    found = 0

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("DELETE FROM scan_results WHERE scan_date = CURRENT_DATE")
        conn.commit()

        for ticker in all_tickers:
            try:
                end   = datetime.today()
                start = end - timedelta(days=380)  # 380 dagar täcker MA200 (200 handelsdagar)
                stock = yf.Ticker(ticker)
                hist = get_hist(ticker, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
                if hist is None:
                    continue

                index_name = 'DOW' if ticker in DOW else 'S&P 500'

                # Kör båda skanningarna
                for mode in ['breakout', 'consol']:
                    result = analyze_ticker(ticker, hist, mode=mode, days=days,
                                          vol_factor=vol_factor, consol_days=consol_days,
                                          consol_range=consol_range)
                    if result:
                        cur.execute('''
                            INSERT INTO scan_results
                            (scan_date, scan_time, scan_mode, ticker, index_name, price,
                             change_pct, high100, vol_today, vol_avg, vol_ratio, days,
                             rsi, sector, sector_bullish, ma50, ma200, ma50_pct, ma200_pct, macd, macd_hist, atr)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ''', (
                            datetime.now().date(),
                            datetime.now().time(),
                            mode, ticker, index_name,
                            round(result['price'], 2),
                            round(result['change_pct'], 2),
                            round(result['high100'], 2),
                            result['today_vol'],
                            result['avg_vol'],
                            round(result['vol_ratio'], 2),
                            days,
                            result.get('rsi'),
                            result.get('sector'),
                            result.get('sector_bullish'),
                            result.get('ma50'),
                            result.get('ma200'),
                            result.get('ma50_pct'),
                            result.get('ma200_pct'),
                            result.get('macd'),
                            result.get('macd_hist'),
                            result.get('atr')
                        ))
                        conn.commit()
                        found += 1
                        print(f"{mode.upper()}: {ticker} ${result['price']:.2f} vol {result['vol_ratio']:.1f}x")

            except Exception as e:
                print(f"Fel för {ticker}: {e}")
                continue

        cur.close()
        conn.close()
        print(f"Automatisk skanning klar — {found} träffar hittade")

    except Exception as e:
        print(f"Auto-scan fel: {e}")

def schedule_scan():
    """Schemalägg skanning kl 22:05 varje vardag"""
    while True:
        now = datetime.now()
        # Kl 22:05 svensk tid (UTC+2 sommartid = 20:05 UTC)
        target = now.replace(hour=20, minute=5, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        print(f"Nästa skanning om {wait_seconds/3600:.1f} timmar")
        
        import time
        time.sleep(wait_seconds)
        
        # Kör bara på vardagar
        if datetime.now().weekday() < 5:
            run_auto_scan()

@app.route('/')
def index():
    init_db()  # Säkerställ att tabellen finns
    return jsonify({"status": "Breakout API körs!", "version": "3.3", "endpoints": ["/stock", "/analyze", "/scan_live", "/latest_scan", "/trigger_scan", "/history"]})

@app.route('/stock')
def get_stock():
    ticker = request.args.get('symbol', '').upper()
    days   = int(request.args.get('days', 100))
    if not ticker:
        return jsonify({"error": "Ingen ticker angiven"}), 400
    try:
        end   = datetime.today()
        start = end - timedelta(days=380)  # 380 dagar täcker MA200 (200 handelsdagar)
        stock = yf.Ticker(ticker)
        hist  = stock.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), interval="1d")
        if hist.empty or len(hist) < 10:
            return jsonify({"error": "Ingen data"}), 404
        hist = hist.sort_index(ascending=False)
        response = make_response(jsonify({
            "ticker":      ticker,
            "closes":      hist['Close'].tolist(),
            "highs":       hist['High'].tolist(),
            "volumes":     hist['Volume'].tolist(),
            "timestamps":  [int(d.timestamp()) for d in hist.index],
            "dates":       [d.strftime('%Y-%m-%d') for d in hist.index],
            "count":       len(hist),
            "latest_date": hist.index[0].strftime('%Y-%m-%d'),
            "fetched_at":  datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/latest_scan')
def latest_scan():
    """Hämta senaste automatiska skanningsresultat"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT DISTINCT ON (ticker, scan_mode) ticker, index_name, price, change_pct, high100,
                   vol_today, vol_avg, vol_ratio, days, scan_date, scan_time,
                   scan_mode, rsi, ma50, ma200, ma50_pct, ma200_pct, macd, macd_hist, atr,
                   sector, sector_bullish
            FROM scan_results 
            WHERE scan_date = (SELECT MAX(scan_date) FROM scan_results)
            ORDER BY ticker, scan_mode, vol_ratio DESC
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        results = [{
            "ticker":    r[0],
            "index":     r[1],
            "price":     r[2],
            "change":    r[3],
            "high100":   r[4],
            "todayVol":  r[5],
            "avgVol":    r[6],
            "volRatio":  r[7],
            "days":      r[8],
            "scan_date": str(r[9]),
            "scan_time": str(r[10]),
            "scan_mode": r[11],
            "rsi":       r[12],
            "ma50":      r[13],
            "ma200":     r[14],
            "ma50_pct":  r[15],
            "ma200_pct": r[16],
            "macd":      r[17],
            "macd_hist": r[18],
            "atr":       r[19],
            "sector":    r[20],
            "sector_bullish": r[21]
        } for r in rows]
        
        return jsonify({
            "results": results,
            "count": len(results),
            "scan_date": str(rows[0][9]) if rows else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history')
def get_history():
    """Hämta historik — en rad per skanningsdag med alla träffar"""
    try:
        conn = get_db()
        cur = conn.cursor()
        # Hämta unika skanningsdagar
        cur.execute('''
            SELECT DISTINCT scan_date, scan_time
            FROM scan_results
            ORDER BY scan_date DESC, scan_time DESC
            LIMIT 30
        ''')
        days = cur.fetchall()
        history = []
        for scan_date, scan_time in days:
            # Hämta alla träffar för denna dag
            cur.execute('''
                SELECT DISTINCT ON (ticker) ticker, index_name, price, change_pct, high100,
                       vol_today, vol_avg, vol_ratio, days, rsi, ma50, ma200,
                       ma50_pct, ma200_pct, macd, macd_hist, atr, sector, sector_bullish, scan_mode
                FROM scan_results
                WHERE scan_date = %s
                ORDER BY ticker, scan_time DESC
            ''', (scan_date,))
            results = cur.fetchall()
            cols = ['ticker','index','price','change','high100','todayVol','avgVol','volRatio',
                    'days','rsi','ma50','ma200','ma50_pct','ma200_pct','macd','macd_hist',
                    'atr','sector','sector_bullish','scan_mode']
            mapped = []
            for r in results:
                d = dict(zip(cols, r))
                d['price']   = float(d['price']) if d['price'] else None
                d['change']  = float(d['change']) if d['change'] else None
                d['high100'] = float(d['high100']) if d['high100'] else None
                d['isConsol'] = d['scan_mode'] == 'consol'
                d['dateStr'] = str(scan_date)
                d['badge']   = 'badge-dj' if d['index'] == 'DOW' else 'badge-sp'
                mapped.append(d)
            history.append({
                "scan_date":   str(scan_date),
                "scan_time":   str(scan_time)[:5] if scan_time else '',
                "total_found": len(mapped),
                "results":     mapped
            })
        cur.close()
        conn.close()
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scan_by_date')
def scan_by_date():
    """Hämta skanningsresultat för ett specifikt datum"""
    date = request.args.get('date', str(datetime.now().date()))
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT ticker, index_name, price, change_pct, high100,
                   vol_today, vol_avg, vol_ratio, days, scan_date, scan_time
            FROM scan_results WHERE scan_date = %s ORDER BY vol_ratio DESC
        ''', (date,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        results = [{
            "ticker":   r[0], "index": r[1], "price": r[2],
            "change":   r[3], "high100": r[4], "todayVol": r[5],
            "avgVol":   r[6], "volRatio": r[7], "days": r[8],
            "scan_date": str(r[9]), "scan_time": str(r[10])
        } for r in rows]
        return jsonify({"results": results, "count": len(results), "date": date})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trigger_scan', methods=['GET', 'POST'])
def trigger_scan():
    """Kör skanning manuellt i bakgrunden (sparar till DB)"""
    thread = threading.Thread(target=run_auto_scan)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "Skanning startad!", "message": "Klar om ca 10 minuter"})

@app.route('/scan_live')
def scan_live():
    """Live-skanning: tar en batch tickers, returnerar träffar direkt utan att spara till DB."""
    tickers_param = request.args.get('tickers', '')
    days         = int(request.args.get('days', 100))
    vol_factor   = float(request.args.get('vol_factor', 1.5))
    mode         = request.args.get('mode', 'breakout')
    consol_days  = int(request.args.get('consol_days', 20))
    consol_range = float(request.args.get('consol_range', 10))

    if not tickers_param:
        return jsonify({"error": "Inga tickers angivna"}), 400

    tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()][:50]
    results = []
    end   = datetime.today()
    start = end - timedelta(days=380)

    from datetime import date as date_cls

    for ticker in tickers:
        try:
            hist = get_hist(ticker, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
            if hist is None:
                continue

            # Kör BÅDA lägena för varje aktie — breakout och konsolidering
            for scan_mode in ['breakout', 'consol']:
                result = analyze_ticker(ticker, hist, mode=scan_mode, days=days,
                                        vol_factor=vol_factor, consol_days=consol_days, consol_range=consol_range)
                if not result:
                    continue

                # Träff! Beräkna tekniska indikatorer (bara för träffar)
                hist_s = hist.sort_index(ascending=False)
                closes = hist_s["Close"].tolist()
                highs  = hist_s["High"].tolist()
                lows   = hist_s["Low"].tolist()
                dates  = [d.strftime("%Y-%m-%d") for d in hist_s.index]
                price_history = list(reversed(closes[:days+1]))

                rsi        = calculate_rsi(closes)
                ma50       = calculate_ma(closes, 50)
                ma200      = calculate_ma(closes, 200)
                ma50_pct   = round((closes[0] - ma50)  / ma50  * 100, 1) if ma50  else None
                ma200_pct  = round((closes[0] - ma200) / ma200 * 100, 1) if ma200 else None
                macd, macd_hist = calculate_macd(closes)
                atr        = calculate_atr(highs, lows, closes)
                sector     = get_ticker_sector(ticker)
                sector_info = sector_status_cache.get(sector, {})
                diff_days  = (date_cls.today() - hist_s.index[0].date()).days

                results.append({
                    "ticker":         ticker,
                    "index":          "DOW" if ticker in DOW else "S&P 500",
                    "price":          round(result["price"], 2),
                    "high100":        round(result["high100"], 2),
                    "change_pct":     round(result["change_pct"], 2),
                    "today_vol":      result["today_vol"],
                    "avg_vol":        result["avg_vol"],
                    "vol_ratio":      round(result["vol_ratio"], 2),
                    "rsi":            rsi,
                    "ma50":           ma50,
                    "ma200":          ma200,
                    "ma50_pct":       ma50_pct,
                    "ma200_pct":      ma200_pct,
                    "macd":           macd,
                    "macd_hist":      macd_hist,
                    "atr":            atr,
                    "sector":         sector,
                    "sector_bullish": sector_info.get("bullish"),
                    "scan_mode":      scan_mode,
                    "date":           dates[0] if dates else "",
                    "diff_days":      diff_days,
                    "price_history":  price_history
                })
        except Exception as e:
            print(f"scan_live fel for {ticker}: {e}")
            continue

    return jsonify({"results": results, "count": len(results), "scanned": len(tickers)})

@app.route('/debug_ma')
def debug_ma():
    """Debug: visa hur mycket data vi hämtar och om MA200 kan beräknas"""
    ticker = request.args.get('symbol', 'AAPL').upper()
    try:
        end   = datetime.today()
        start = end - timedelta(days=380)
        stock = yf.Ticker(ticker)
        hist  = stock.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), interval="1d")
        hist_s = hist.sort_index(ascending=False)
        closes = hist_s['Close'].tolist()
        ma50  = calculate_ma(closes, 50)
        ma200 = calculate_ma(closes, 200)
        return jsonify({
            "ticker":          ticker,
            "calendar_days":   380,
            "trading_days":    len(closes),
            "ma50":            ma50,
            "ma200":           ma200,
            "ma200_works":     ma200 is not None,
            "latest_date":     hist_s.index[0].strftime('%Y-%m-%d') if len(hist_s) > 0 else None,
            "oldest_date":     hist_s.index[-1].strftime('%Y-%m-%d') if len(hist_s) > 0 else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/quote')
def get_quote():
    ticker = request.args.get('symbol', '').upper()
    if not ticker:
        return jsonify({"error": "Ingen ticker"}), 400
    try:
        stock = yf.Ticker(ticker)
        info  = stock.fast_info
        return jsonify({
            "ticker": ticker,
            "price":  round(info.last_price, 2),
            "change_pct": round(((info.last_price - info.previous_close) / info.previous_close) * 100, 2)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Starta schemaläggaren i bakgrunden
    scheduler = threading.Thread(target=schedule_scan)
    scheduler.daemon = True
    scheduler.start()
    app.run(debug=False, host='0.0.0.0', port=10000)
