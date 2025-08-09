from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Replace with your actual API key for the exchange rate API
EXCHANGE_RATE_API_KEY = "LEp52OgdDZzH35k7eyu8cHvXWWbmGJeC" 

@app.route('/api/gold_premium', methods=['GET'])
def get_gold_premium():
    try:
        # 1. Get International Gold Price
        international_gold_url = "https://www.samsunggold.co.kr/realtime/ajax/getMarketData.php?onlyInter=1"
        international_gold_response = requests.get(international_gold_url)
        print(f"International Gold API Response Status: {international_gold_response.status_code}")
        print(f"International Gold API Raw Response: {international_gold_response.text}")
        try:
            international_gold_data = international_gold_response.json()
            print(f"Type of international_gold_data: {type(international_gold_data)}")
        except json.JSONDecodeError:
            return jsonify({"error": f"International Gold API did not return valid JSON. Raw response: {international_gold_response.text}"}), 500
        
        # Assuming the structure is like {"gold_price": "2300.00"} or similar
        # You might need to inspect the actual JSON response to get the correct key
        # For now, let's assume it's directly accessible or needs parsing
        # Example: {"data": [{"item": "GOLD", "price": "2300.00"}]}
        # Let's try to find a common key or assume a simple structure
        
        # A more robust way would be to parse the HTML if it's not a clean JSON API
        # For now, let's assume it returns a JSON with a key like 'price' or 'gold_price'
        # If the API returns HTML, we'll need to use a library like BeautifulSoup
        
        # Let's assume the international gold price is in 'data' array, first element, 'price' key
        international_price_oz = None
        if isinstance(international_gold_data, dict) and 'data' in international_gold_data and 'interMarketPriceApiDTO' in international_gold_data['data']:
            inter_market_data = international_gold_data['data']['interMarketPriceApiDTO']
            # Prioritize 'gold_ask' if available, otherwise 'gold_bid'
            if 'gold_ask' in inter_market_data and inter_market_data['gold_ask'] != '0.00':
                international_price_oz = float(inter_market_data['gold_ask'].replace(',', ''))
            elif 'gold_bid' in inter_market_data and inter_market_data['gold_bid'] != '0.00':
                international_price_oz = float(inter_market_data['gold_bid'].replace(',', ''))
        
        if international_price_oz is None:
            return jsonify({"error": "Could not parse international gold price from API response."}), 500


        # 2. Get Domestic Gold Price (Naver Stock API)
        domestic_gold_url = "https://m.stock.naver.com/front-api/marketIndex/prices?category=metals&reutersCode=M04020000&page=1"
        domestic_gold_response = requests.get(domestic_gold_url)
        print(f"Domestic Gold API Response Status: {domestic_gold_response.status_code}")
        print(f"Domestic Gold API Raw Response: {domestic_gold_response.text}")
        try:
            domestic_gold_data = domestic_gold_response.json()
            print(f"Type of domestic_gold_data: {type(domestic_gold_data)}")
        except json.JSONDecodeError:
            return jsonify({"error": f"Domestic Gold API did not return valid JSON. Raw response: {domestic_gold_response.text}"}), 500

        korean_price_gram = None
        if isinstance(domestic_gold_data, dict) and 'result' in domestic_gold_data and domestic_gold_data['result']:
            # Assuming the first item in the 'result' list contains the gold price
            gold_info = domestic_gold_data['result'][0]
            # The price is likely in 'closePrice' or similar, and needs to be converted to per gram
            # Naver API usually provides price per unit (e.g., per don, or per gram directly)
            # Let's assume 'closePrice' is the relevant field and it's already per gram or needs conversion
            # Based on typical gold prices, it's likely per gram or per don (3.75g)
            # We need to confirm the unit from Naver Stock API documentation or by inspecting the data.
            # For now, let's assume 'closePrice' is the price per gram.
            if 'closePrice' in gold_info:
                korean_price_gram = float(gold_info['closePrice'].replace(',', ''))
            elif 'tradePrice' in gold_info: # Sometimes 'tradePrice' is used for current price
                korean_price_gram = float(gold_info['tradePrice'].replace(',', ''))

        if korean_price_gram is None:
            return jsonify({"error": "Could not parse domestic gold price from Naver Stock API response. Check 'closePrice' or 'tradePrice' field."}), 500


        # 3. Get Exchange Rate (KRW/USD)
        print("Attempting to fetch exchange rate...")
        exchange_rate_url = f"https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={EXCHANGE_RATE_API_KEY}&searchdate={datetime.now().strftime('%Y%m%d')}&data=AP01"
        exchange_rate_response = requests.get(exchange_rate_url)
        print(f"Exchange Rate API Response Status: {exchange_rate_response.status_code}")
        print(f"Exchange Rate API Raw Response: {exchange_rate_response.text}")
        try:
            exchange_rate_data = exchange_rate_response.json()
            print(f"Type of exchange_rate_data: {type(exchange_rate_data)}")
        except json.JSONDecodeError:
            return jsonify({"error": f"Exchange Rate API did not return valid JSON. Raw response: {exchange_rate_response.text}"}), 500

        if not isinstance(exchange_rate_data, list):
            return jsonify({"error": f"Exchange Rate API response is not a list. Raw response: {exchange_rate_response.text}"}), 500

        exchange_rate = None
        # Try to get exchange rate for today
        current_date = datetime.now()
        for _ in range(7): # Try up to 7 days back to find a weekday
            exchange_rate_url = f"https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={EXCHANGE_RATE_API_KEY}&searchdate={current_date.strftime('%Y%m%d')}&data=AP01"
            exchange_rate_response = requests.get(exchange_rate_url)
            print(f"Exchange Rate API Response Status: {exchange_rate_response.status_code}")
            print(f"Exchange Rate API Raw Response: {exchange_rate_response.text}")
            try:
                exchange_rate_data = exchange_rate_response.json()
                print(f"Type of exchange_rate_data: {type(exchange_rate_data)}")
            except json.JSONDecodeError:
                current_date -= timedelta(days=1)
                continue

            if not isinstance(exchange_rate_data, list) or not exchange_rate_data:
                current_date -= timedelta(days=1)
                continue

            for currency in exchange_rate_data:
                if currency.get('cur_unit') == 'USD':
                    exchange_rate = float(currency.get('deal_bas_r').replace(',', '')) # Use 'deal_bas_r' for standard rate
                    break
            
            if exchange_rate is not None:
                break
            current_date -= timedelta(days=1)

        if exchange_rate is None:
            return jsonify({"error": "Could not find USD exchange rate from API response after trying several days. Check API key or date."}), 500

        # 4. Calculate Gold Premium
        OUNCE_TO_GRAM = 31.1035

        # 해외 금 시세: USD/oz -> USD/g -> KRW/g
        international_price_gram_usd = international_price_oz / OUNCE_TO_GRAM
        converted_price_krw = international_price_gram_usd * exchange_rate

        # 김치 프리미엄 계산
        premium = ((korean_price_gram - converted_price_krw) / converted_price_krw) * 100

        return jsonify({
            "international_price_oz": international_price_oz,
            "korean_price_gram": korean_price_gram,
            "exchange_rate": exchange_rate,
            "converted_price_krw_per_gram": converted_price_krw,
            "premium_percentage": premium
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
