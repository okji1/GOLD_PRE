import requests
import json
from datetime import datetime, timedelta
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL

class KISApi:
    """한국투자증권 API 클래스"""
    
    def __init__(self):
        self.base_url = KIS_BASE_URL
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.access_token = None
        
    def get_access_token(self):
        """OAuth 토큰 발급"""
        url = f"{self.base_url}/oauth2/tokenP"
        
        headers = {
            "content-type": "application/json; charset=utf-8"
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            print(f"토큰 발급 성공: {self.access_token[:20]}...")
            return self.access_token
            
        except Exception as e:
            print(f"토큰 발급 실패: {e}")
            return None
    
    def get_overseas_futures_cot(self, prod_code="GC", date=None):
        """
        해외선물 미결제추이 조회
        prod_code: 상품코드 (GC=금, SI=은, PL=백금 등)
        date: 조회일자 (YYYYMMDD), None이면 최근 주
        """
        
        if not self.access_token:
            self.get_access_token()
            
        if not date:
            # 최근 화요일 찾기 (COT 데이터는 매주 화요일 기준)
            today = datetime.now()
            days_since_tuesday = (today.weekday() - 1) % 7
            last_tuesday = today - timedelta(days=days_since_tuesday)
            date = last_tuesday.strftime("%Y%m%d")
        
        url = f"{self.base_url}/uapi/overseas-futureoption/v1/quotations/investor-unpd-trend"
        
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDDB95030000",
            "custtype": "P"  # 개인
        }
        
        params = {
            "PROD_ISCD": prod_code,
            "BSOP_DATE": date,
            "UPMU_GUBUN": "0",  # 0:수량, 1:증감
            "CTS_KEY": ""
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("rt_cd") == "0":
                print(f"COT 데이터 조회 성공: {prod_code}, {date}")
                return data.get("output2", [])
            else:
                print(f"COT 데이터 조회 실패: {data.get('msg1', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"API 호출 실패: {e}")
            return None
    
    def get_futures_tick_data(self, prod_code="GC"):
        """
        해외선물 체결추이(틱) 조회
        """
        
        if not self.access_token:
            self.get_access_token()
            
        url = f"{self.base_url}/uapi/overseas-futureoption/v1/quotations/inquire-ccnl"
        
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDFC55020200",
            "custtype": "P"
        }
        
        params = {
            "PROD_ISCD": prod_code,
            "CTS_KEY": ""
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("rt_cd") == "0":
                print(f"틱 데이터 조회 성공: {prod_code}")
                return data.get("output2", [])
            else:
                print(f"틱 데이터 조회 실패: {data.get('msg1', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"API 호출 실패: {e}")
            return None
