# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify, request
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
import json

# Blueprint 생성
gold_option_bp = Blueprint('gold_option', __name__)

# --- KIS API 연동 및 토큰 관리 --- #

class KISApiWrapper:
    """한국투자증권 API 연동을 위한 래퍼 클래스"""

    def __init__(self):
        # 환경 변수에서 설정값 로드
        self.app_key = os.environ.get('APP_KEY')
        self.app_secret = os.environ.get('APP_SECRET')
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        
        self.mode = os.environ.get('KIS_API_MODE', 'prod')
        
        domain_config_str = os.environ.get('KIS_DOMAIN_CONFIG', '{}')
        paths_config_str = os.environ.get('KIS_PATH_CONFIG', '{}')

        try:
            domain_config = json.loads(domain_config_str)
            self.paths = json.loads(paths_config_str)
        except json.JSONDecodeError:
            print("환경변수 KIS_DOMAIN_CONFIG 또는 KIS_PATH_CONFIG가 올바른 JSON 형식이 아닙니다.")
            # 기본값으로 설정하거나 오류 처리
            domain_config = {
                "prod": "https://openapi.koreainvestment.com:9443",
                "vps": "https://openapivts.koreainvestment.com:29443"
            }
            self.paths = {
                "auth": "/oauth2/tokenP",
                "execution_trend": "/uapi/overseas-futureoption/v1/quotations/inquire-daily-price",
                "open_interest_trend": "/uapi/overseas-futureoption/v1/trading/inquire-unsettled-trend"
            }

        self.base_url = domain_config.get(self.mode)
        self.supabase: Client | None = None

        if not all([self.app_key, self.app_secret, supabase_url, supabase_key, self.base_url]):
            print("하나 이상의 필수 환경변수가 설정되지 않았습니다. (APP_KEY, APP_SECRET, SUPABASE_URL, SUPABASE_KEY, KIS_API_MODE)")

        if supabase_url and supabase_key:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
            except Exception as e:
                print(f"Supabase 연결 실패: {e}")

    def get_access_token(self):
        """Supabase에서 토큰을 로드하거나, 없으면 새로 발급받아 저장"""
        if self.supabase:
            try:
                response = self.supabase.table('api_tokens').select('token_data').eq('api_name', 'KIS_API').single().execute()
                if response.data and response.data.get('token_data'):
                    token_data = response.data['token_data']
                    issue_time = datetime.fromisoformat(token_data['issue_timestamp'])
                    if datetime.now() < issue_time + timedelta(hours=23, minutes=50):
                        return token_data['access_token']
            except Exception as e:
                print(f"Supabase 토큰 로드 오류: {e}")

        headers = {"content-type": "application/json"}
        body = {"grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret}
        url = f"{self.base_url}{self.paths.get('auth')}"
        
        try:
            res = requests.post(url, headers=headers, json=body)
            res.raise_for_status()
            new_token_data = res.json()
            new_token = new_token_data['access_token']
        except requests.RequestException as e:
            print(f"KIS 토큰 발급 API 오류: {e}")
            return None

        if self.supabase and new_token:
            try:
                token_to_store = {'access_token': new_token, 'issue_timestamp': datetime.now().isoformat()}
                self.supabase.table('api_tokens').upsert({
                    'api_name': 'KIS_API',
                    'token_data': token_to_store,
                    'updated_at': datetime.now().isoformat()
                }).execute()
            except Exception as e:
                print(f"Supabase 토큰 저장 오류: {e}")
        
        return new_token

    def _get_api_data(self, url_path_key, tr_id, params):
        """API 데이터 요청 공통 함수"""
        token = self.get_access_token()
        if not token:
            raise Exception("Access Token 발급 실패")

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {token}",
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id
        }
        url = f"{self.base_url}{self.paths.get(url_path_key)}"
        
        try:
            res = requests.get(url, headers=headers, params=params)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            print(f"{tr_id} API 요청 오류: {e}")
            return None

    def get_execution_trend(self, symbol='GC'):
        params = {"fid_cond_mrkt_div_code": "F", "fid_input_iscd": symbol, "fid_period_div_code": "D", "fid_org_adj_prc": "0"}
        return self._get_api_data('execution_trend', 'OFUP2002R', params)

    def get_open_interest_trend(self, symbol='GC'):
        params = {"fid_cond_mrkt_div_code": "F", "fid_input_iscd": symbol}
        return self._get_api_data('open_interest_trend', 'OFUP2004R', params)

# --- 데이터 분석 로직 --- #
def analyze_investment_strategy(execution_data, open_interest_data):
    if not execution_data or not execution_data.get('output1') or not open_interest_data or not open_interest_data.get('output1'):
        return {"error": "API로부터 유효한 데이터를 받지 못했습니다."}
    try:
        df_exec = pd.DataFrame(execution_data['output1'])
        df_exec['ovrs_diff'] = pd.to_numeric(df_exec['ovrs_diff'])
        df_exec['ovrs_vol'] = pd.to_numeric(df_exec['ovrs_vol'])
        latest_exec = df_exec.iloc[0]
        price_change = latest_exec['ovrs_diff']
        volume = latest_exec['ovrs_vol']
        
        trend_signal = "중립"
        if price_change > 0 and volume > df_exec['ovrs_vol'].mean(): trend_signal = "신뢰도 높은 상승 추세"
        elif price_change < 0 and volume > df_exec['ovrs_vol'].mean(): trend_signal = "신뢰도 높은 하락 추세"
        elif volume < df_exec['ovrs_vol'].mean(): trend_signal = "추세 약화 가능성"

        df_oi = pd.DataFrame(open_interest_data['output1'])
        df_oi['bidp_spec'] = pd.to_numeric(df_oi['bidp_spec'])
        df_oi['askp_spec'] = pd.to_numeric(df_oi['askp_spec'])
        df_oi['hts_otst_smtn'] = pd.to_numeric(df_oi['hts_otst_smtn'])
        latest_oi = df_oi.iloc[0]
        prev_oi = df_oi.iloc[1] if len(df_oi) > 1 else latest_oi
        net_spec_position = latest_oi['bidp_spec'] - latest_oi['askp_spec']
        net_spec_change = net_spec_position - (prev_oi['bidp_spec'] - prev_oi['askp_spec'])
        oi_change = latest_oi['hts_otst_smtn'] - prev_oi['hts_otst_smtn']
        
        psychology_signal = "혼조"
        if trend_signal == "신뢰도 높은 상승 추세" and net_spec_change > 0 and oi_change > 0: psychology_signal = "'진짜 상승장': 신규 자금 유입 및 상승 베팅 강화"
        elif trend_signal == "신뢰도 높은 하락 추세" and net_spec_change < 0 and oi_change > 0: psychology_signal = "'진짜 하락장': 신규 자금 유입 및 하락 베팅 강화"
        elif trend_signal == "신뢰도 높은 상승 추세" and net_spec_change < 0: psychology_signal = "'가짜 상승장': 추세 전환 위험 신호"

        final_recommendation = "관망 또는 보수적 접근 필요"
        if psychology_signal.startswith("'진짜 상승장'"): final_recommendation = "강력 매수 신호. 콜(Call) 옵션 매수 또는 풋(Put) 옵션 매도 고려."
        elif psychology_signal.startswith("'진짜 하락장'"): final_recommendation = "강력 매도 신호. 풋(Put) 옵션 매수 또는 콜(Call) 옵션 매도 고려."
        elif psychology_signal.startswith("'가짜 상승장'"): final_recommendation = "추세 전환 위험. 기존 포지션 청산 고려."

        return {
            "trend_analysis": trend_signal,
            "psychology_analysis": psychology_signal,
            "final_recommendation": final_recommendation,
            "raw_data_summary": {
                "latest_price_change": price_change,
                "latest_volume": volume,
                "latest_net_speculative_position": net_spec_position,
                "change_in_net_spec_position": net_spec_change,
                "change_in_open_interest": oi_change
            }
        }
    except Exception as e:
        return {"error": f"데이터 분석 중 오류 발생: {e}"}

# --- Flask API 엔드포인트 --- #
@gold_option_bp.route('/api/gold_options_analysis', methods=['GET'])
def get_gold_options_analysis():
    symbol = request.args.get('symbol', default='GC', type=str)
    try:
        api = KISApiWrapper()
        execution_data = api.get_execution_trend(symbol)
        open_interest_data = api.get_open_interest_trend(symbol)
        analysis_result = analyze_investment_strategy(execution_data, open_interest_data)
        return jsonify(analysis_result)
    except Exception as e:
        return jsonify({"error": f"API 처리 중 심각한 오류 발생: {str(e)}"}), 500
