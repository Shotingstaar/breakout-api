from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Tillåter anrop från GitHub Pages

@app.route('/')
def index():
    return jsonify({"status": "Breakout API körs!", "version": "1.0"})

@app.route('/stock')
def get_stock():
    ticker  = request.args.get('symbol', '').upper()
    days    = int(request.args.get('days', 100))

    if not ticker:
        return jsonify({"error": "Ingen ticker angiven"}), 400

    try:
        # Hämta extra dagar för att täcka helger/helgdagar
        period_days = days + 40
        end   = datetime.today()
        start = end - timedelta(days=period_days)

        stock = yf.Ticker(ticker)
        hist  = stock.history(start=start.strftime('%Y-%m-%d'),
                              end=end.strftime('%Y-%m-%d'))

        if hist.empty or len(hist) < 10:
            return jsonify({"error": "Ingen data tillgänglig"}), 404

        # Bygg svaret — nyast först
        hist = hist.sort_index(ascending=False)

        closes     = hist['Close'].tolist()
        highs      = hist['High'].tolist()
        volumes    = hist['Volume'].tolist()
        timestamps = [int(d.timestamp()) for d in hist.index]
        dates      = [d.strftime('%Y-%m-%d') for d in hist.index]

        return jsonify({
            "ticker":     ticker,
            "closes":     closes,
            "highs":      highs,
            "volumes":    volumes,
            "timestamps": timestamps,
            "dates":      dates,
            "count":      len(closes)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/quote')
def get_quote():
    ticker = request.args.get('symbol', '').upper()
    if not ticker:
        return jsonify({"error": "Ingen ticker angiven"}), 400
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
    app.run(debug=False, host='0.0.0.0', port=10000)
