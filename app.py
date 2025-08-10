from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': 'https://gold-pre.vercel.app'}})

# Replace with your actual API key for the exchange rate API
EXCHANGE_RATE_API_KEY = "LEp52OgdDZzH35k7eyu8cHvXWWbmGJeC" 

@app.route('/api/gold_premium', methods=['GET'])
def get_gold_premium():
    try:
        # 1. Get International Gold Price from Naver Finance
        international_gold_url = "https://m.stock.naver.com/marketindex/metals/GCcv1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(international_gold_url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.text, 'lxml')
        price_strong_tag = soup.find('strong', class_='DetailInfo_price__I_VJn')
        
        if not price_strong_tag:
            return jsonify({"error": "Could not find the price tag on the Naver Finance page."}), 500
            
        price_text = price_strong_tag.get_text(strip=True).split('USD')[0]
        international_price_oz = float(price_text.replace(',', ''))

        if international_price_oz is None:
            return jsonify({"error": "Could not parse international gold price from Naver Finance."}), 500


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

@app.route('/api/put_call_ratio', methods=['GET'])
def get_put_call_ratio():
    try:
        url = "https://www.barchart.com/stocks/quotes/GLD/options"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        page_text = soup.get_text(separator=' ')

        ratio_data = {}

        # Use regular expressions to find data next to labels
        vol_ratio_match = re.search(r"Put/Call Vol Ratio\s+([\d.]+)", page_text)
        oi_ratio_match = re.search(r"Put/Call Open Int Ratio\s+([\d.]+)", page_text)
        put_vol_match = re.search(r"Put Volume\s+([\d,]+)", page_text)
        call_vol_match = re.search(r"Call Volume\s+([\d,]+)", page_text)

        if vol_ratio_match:
            ratio_data['volume_ratio'] = vol_ratio_match.group(1)
        if oi_ratio_match:
            ratio_data['open_interest_ratio'] = oi_ratio_match.group(1)
        if put_vol_match:
            ratio_data['put_volume'] = put_vol_match.group(1)
        if call_vol_match:
            ratio_data['call_volume'] = call_vol_match.group(1)

        # Check if all necessary data was found
        if len(ratio_data) < 4:
            # Return the page text for debugging
            return jsonify({"error": "Data parsing failed.", "details": "Could not find all required data points.", "page_content_sample": page_text[:1000]}), 500

        return jsonify(ratio_data)

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request Timed Out", "details": "The request to barchart.com took too long to respond."}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Request Failed", "details": f"Failed to fetch data from barchart.com: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": "An Unexpected Server Error Occurred", "details": str(e)}), 500
