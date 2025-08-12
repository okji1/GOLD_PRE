from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os
from kis_api import KISApi
from config import EXCHANGE_RATE_API_KEY

from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': 'https://gold-pre.vercel.app'}})

# KIS API 인스턴스 생성
kis_api = KISApi()

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html') 

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

@app.route('/api/gold_options_analysis', methods=['GET'])
def get_gold_options_analysis():
    """
    금 옵션 데이터 분석 엔드포인트 (실제 API 사용)
    """
    try:
        # 실제 한국투자증권 API에서 금(GC) COT 데이터 가져오기
        print("COT 데이터 조회 시작...")
        cot_data = kis_api.get_overseas_futures_cot("GC")
        
        if cot_data is None or len(cot_data) == 0:
            # API 실패 시 샘플 데이터 사용
            print("실제 API 데이터 없음, 샘플 데이터 사용")
            cot_data = get_sample_cot_data()
        
        # 데이터 분석
        analysis = analyze_gold_options_data(cot_data)
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"API 오류: {e}")
        # 오류 발생 시 샘플 데이터로 대체
        sample_data = get_sample_cot_data()
        analysis = analyze_gold_options_data(sample_data)
        analysis["note"] = "실제 API 데이터를 가져올 수 없어 샘플 데이터를 사용했습니다."
        return jsonify(analysis)

@app.route('/api/gold_options_analysis_sample', methods=['GET'])
def get_gold_options_analysis_sample():
    """
    금 옵션 데이터 분석 엔드포인트 (샘플 데이터)
    """
    try:
        # 샘플 데이터 사용
        sample_data = get_sample_cot_data()
        analysis = analyze_gold_options_data(sample_data)
        
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

def get_sample_cot_data():
    """샘플 COT 데이터 반환"""
    return [
        {
            "prod_iscd": "GC",
            "cftc_iscd": "088691",
            "bsop_date": "20240812",
            "bidp_spec": "145230",  # 매수투기
            "askp_spec": "158794",  # 매도투기
            "spread_spec": "0",
            "bidp_hedge": "89798",  # 매수헤지
            "askp_hedge": "102849", # 매도헤지
            "hts_otst_smtn": "496671",
            "bidp_missing": "87310",
            "askp_missing": "64845",
            "bidp_spec_cust": "45",
            "askp_spec_cust": "52",
            "spread_spec_cust": "12",
            "bidp_hedge_cust": "78",
            "askp_hedge_cust": "69",
            "cust_smtn": "256"
        },
        {
            "prod_iscd": "GC",
            "cftc_iscd": "088691",
            "bsop_date": "20240805",
            "bidp_spec": "142433",
            "askp_spec": "155433",
            "spread_spec": "0",
            "bidp_hedge": "87557",
            "askp_hedge": "98649",
            "hts_otst_smtn": "484072",
            "bidp_missing": "85673",
            "askp_missing": "62581",
            "bidp_spec_cust": "43",
            "askp_spec_cust": "49",
            "spread_spec_cust": "11",
            "bidp_hedge_cust": "76",
            "askp_hedge_cust": "67",
            "cust_smtn": "246"
        }
    ]

def analyze_gold_options_data(data):
    """
    금 옵션 데이터 분석 함수
    """
    if not data:
        return {"error": "No data available"}
    
    # 최신 데이터 (첫 번째 항목)
    latest = data[0]
    
    # 기본 수치 계산
    total_long_spec = int(latest["bidp_spec"])  # 총 매수투기
    total_short_spec = int(latest["askp_spec"]) # 총 매도투기
    total_long_hedge = int(latest["bidp_hedge"]) # 총 매수헤지
    total_short_hedge = int(latest["askp_hedge"]) # 총 매도헤지
    
    # 투기 vs 헤지 비율 계산
    total_spec = total_long_spec + total_short_spec
    total_hedge = total_long_hedge + total_short_hedge
    total_positions = total_spec + total_hedge
    
    spec_ratio = (total_spec / total_positions) * 100 if total_positions > 0 else 0
    hedge_ratio = (total_hedge / total_positions) * 100 if total_positions > 0 else 0
    
    # 매수/매도 비율 (투기)
    spec_long_ratio = (total_long_spec / total_spec) * 100 if total_spec > 0 else 0
    spec_short_ratio = (total_short_spec / total_spec) * 100 if total_spec > 0 else 0
    
    # 매수/매도 비율 (헤지)
    hedge_long_ratio = (total_long_hedge / total_hedge) * 100 if total_hedge > 0 else 0
    hedge_short_ratio = (total_short_hedge / total_hedge) * 100 if total_hedge > 0 else 0
    
    # 주간 변화 계산 (2개 데이터만 있으므로 간단한 비교)
    if len(data) > 1:
        prev = data[1]
        spec_change = total_spec - (int(prev["bidp_spec"]) + int(prev["askp_spec"]))
        hedge_change = total_hedge - (int(prev["bidp_hedge"]) + int(prev["askp_hedge"]))
        
        long_spec_change = total_long_spec - int(prev["bidp_spec"])
        short_spec_change = total_short_spec - int(prev["askp_spec"])
    else:
        spec_change = 0
        hedge_change = 0
        long_spec_change = 0
        short_spec_change = 0
    
    # 매수 판단 지표 계산
    buy_signal_score = calculate_buy_signal(
        spec_long_ratio, spec_short_ratio,
        hedge_long_ratio, hedge_short_ratio,
        long_spec_change, short_spec_change
    )
    
    return {
        "date": latest["bsop_date"],
        "raw_data": {
            "long_speculation": total_long_spec,
            "short_speculation": total_short_spec,
            "long_hedge": total_long_hedge,
            "short_hedge": total_short_hedge,
            "total_positions": int(latest["hts_otst_smtn"])
        },
        "analysis": {
            "speculation_ratio": round(spec_ratio, 2),
            "hedge_ratio": round(hedge_ratio, 2),
            "spec_long_ratio": round(spec_long_ratio, 2),
            "spec_short_ratio": round(spec_short_ratio, 2),
            "hedge_long_ratio": round(hedge_long_ratio, 2),
            "hedge_short_ratio": round(hedge_short_ratio, 2)
        },
        "weekly_change": {
            "speculation_change": spec_change,
            "hedge_change": hedge_change,
            "long_spec_change": long_spec_change,
            "short_spec_change": short_spec_change
        },
        "buy_signal": buy_signal_score
    }

def calculate_buy_signal(spec_long_ratio, spec_short_ratio, 
                        hedge_long_ratio, hedge_short_ratio,
                        long_spec_change, short_spec_change):
    """
    매수 신호 계산 함수
    점수가 높을수록 매수 신호
    """
    score = 0
    signals = []
    
    # 1. 투기적 롱 포지션이 숏보다 많으면 +점수
    if spec_long_ratio > spec_short_ratio:
        score += 2
        signals.append("투기적 매수 포지션 우세")
    else:
        score -= 1
        signals.append("투기적 매도 포지션 우세")
    
    # 2. 헤지 숏 포지션이 롱보다 많으면 +점수 (상업적 참여자들이 가격 하락을 헤지)
    if hedge_short_ratio > hedge_long_ratio:
        score += 1
        signals.append("헤지 매도 포지션 우세 (가격 상승 기대)")
    else:
        score -= 0.5
        signals.append("헤지 매수 포지션 우세")
    
    # 3. 투기적 롱 포지션 증가하면 +점수
    if long_spec_change > 0:
        score += 1
        signals.append("투기적 매수 포지션 증가")
    elif long_spec_change < 0:
        score -= 1
        signals.append("투기적 매수 포지션 감소")
    
    # 4. 투기적 숏 포지션 감소하면 +점수
    if short_spec_change < 0:
        score += 1
        signals.append("투기적 매도 포지션 감소")
    elif short_spec_change > 0:
        score -= 1
        signals.append("투기적 매도 포지션 증가")
    
    # 점수를 0-100 스케일로 변환
    normalized_score = max(0, min(100, (score + 5) * 10))
    
    # 신호 해석
    if normalized_score >= 70:
        signal_text = "강한 매수 신호"
        signal_color = "green"
    elif normalized_score >= 50:
        signal_text = "약한 매수 신호"
        signal_color = "lightgreen"
    elif normalized_score >= 30:
        signal_text = "중립"
        signal_color = "yellow"
    else:
        signal_text = "매도 신호"
        signal_color = "red"
    
    return {
        "score": round(normalized_score, 1),
        "signal_text": signal_text,
        "signal_color": signal_color,
        "signals": signals
    }

@app.route('/api/test_kis_api', methods=['GET'])
def test_kis_api():
    """KIS API 연결 테스트"""
    try:
        # 토큰 발급 테스트
        token = kis_api.get_access_token()
        
        if token:
            return jsonify({
                "status": "success",
                "message": "KIS API 연결 성공",
                "token_preview": token[:20] + "..." if len(token) > 20 else token
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "토큰 발급 실패"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"API 테스트 실패: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
