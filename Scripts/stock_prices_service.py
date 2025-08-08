from flask import Flask, request, jsonify
import yfinance as yf
from datetime import datetime
from flask import Response

app = Flask(__name__)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


@app.get('/health')
def health() -> Response:
    return jsonify({"status": "ok"})


@app.get('/prices')
def get_prices() -> Response:
    ticker = request.args.get('ticker', type=str)
    start = request.args.get('start', type=str)
    end = request.args.get('end', type=str)
    interval = request.args.get('interval', default='1d', type=str)

    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    # yfinance accepts ISO strings directly; validate but pass through
    start_dt = parse_date(start)
    end_dt = parse_date(end)

    try:
        hist = yf.download(tickers=ticker, start=start if start_dt else None,
                           end=end if end_dt else None, interval=interval, auto_adjust=False, progress=False)
        if hist is None or hist.empty:
            return jsonify({"ticker": ticker.upper(), "prices": []})

        # Normalize index (DatetimeIndex) and columns
        hist = hist.reset_index()

        records = []
        for row in hist.itertuples(index=False):
            # yfinance can return either 'Date' or 'Datetime' as the index name depending on interval
            date_value = getattr(row, 'Date', None) or getattr(row, 'Datetime', None)
            records.append({
                "date": (date_value.isoformat() if hasattr(date_value, 'isoformat') else str(date_value)),
                "open": float(getattr(row, 'Open', 0.0)),
                "high": float(getattr(row, 'High', 0.0)),
                "low": float(getattr(row, 'Low', 0.0)),
                "close": float(getattr(row, 'Close', 0.0)),
                "adj_close": float(getattr(row, 'Adj Close', getattr(row, 'Adj_Close', getattr(row, 'AdjClose', 0.0)))),
                "volume": int(getattr(row, 'Volume', 0)),
            })

        return jsonify({
            "ticker": ticker.upper(),
            "interval": interval,
            "prices": records
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Default to port 8001 so Next.js can proxy to it locally
    app.run(host='0.0.0.0', port=8001)


