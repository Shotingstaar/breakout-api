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
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        # Lägg till rsi-kolumn om den inte finns (migration)
        cur.execute('''
            ALTER TABLE scan_results 
            ADD COLUMN IF NOT EXISTS rsi FLOAT
        ''')
        # Lägg till scan_mode om den inte finns
        cur.execute('''
            ALTER TABLE scan_results 
            ADD COLUMN IF NOT EXISTS scan_mode VARCHAR(20)
        ''')
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
            rsi = calculate_rsi(closes)
            return {
                'mode': 'breakout',
                'change_pct': change_pct,
                'high100': high100,
                'today_vol': today_vol,
                'avg_vol': avg_vol,
                'vol_ratio': today_vol / avg_vol,
                'price': today_close,
                'rsi': rsi
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
            rsi = calculate_rsi(closes)
            return {
                'mode': 'consol',
                'change_pct': change_pct,
                'high100': consol_high,
                'today_vol': today_vol,
                'avg_vol': avg_vol,
                'vol_ratio': today_vol / avg_vol,
                'price': today_close,
                'range_pct': range_pct,
                'rsi': rsi
            }
    return None

def run_auto_scan():
    """Kör automatisk skanning — både breakout och konsolidering"""
    print(f"Startar automatisk skanning {datetime.now()}")

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
                start = end - timedelta(days=days + 60)
                stock = yf.Ticker(ticker)
                hist  = stock.history(
                    start=start.strftime('%Y-%m-%d'),
                    end=end.strftime('%Y-%m-%d'),
                    interval="1d"
                )
                if hist.empty or len(hist) < 10:
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
                             change_pct, high100, vol_today, vol_avg, vol_ratio, days, rsi)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            datetime.now().date(),
                            datetime.now().time(),
                            mode,
                            ticker,
                            index_name,
                            round(result['price'], 2),
                            round(result['change_pct'], 2),
                            round(result['high100'], 2),
                            result['today_vol'],
                            result['avg_vol'],
                            round(result['vol_ratio'], 2),
                            days,
                            result.get('rsi')
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
    return jsonify({"status": "Breakout API körs!", "version": "2.0"})

@app.route('/stock')
def get_stock():
    ticker = request.args.get('symbol', '').upper()
    days   = int(request.args.get('days', 100))
    if not ticker:
        return jsonify({"error": "Ingen ticker angiven"}), 400
    try:
        end   = datetime.today()
        start = end - timedelta(days=days + 60)
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
            SELECT ticker, index_name, price, change_pct, high100, 
                   vol_today, vol_avg, vol_ratio, days, scan_date, scan_time,
                   scan_mode, rsi
            FROM scan_results 
            WHERE scan_date = (SELECT MAX(scan_date) FROM scan_results)
            ORDER BY vol_ratio DESC
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
            "rsi":       r[12]
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
    """Hämta historik över skanningsdagar"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT scan_date, COUNT(*) as total, scan_mode
            FROM scan_results 
            GROUP BY scan_date, scan_mode
            ORDER BY scan_date DESC
            LIMIT 30
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"history": [{"date": str(r[0]), "count": r[1], "mode": r[2]} for r in rows]})
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
    """Kör skanning manuellt"""
    thread = threading.Thread(target=run_auto_scan)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "Skanning startad!", "message": "Klar om ca 10 minuter"})

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
