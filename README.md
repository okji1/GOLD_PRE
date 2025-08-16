# GOLD_PRE

금 프리미엄 계산 및 금 옵션 데이터 분석 Flask 애플리케이션

## 프로젝트 구조

- `gold_premium.py` - 메인 Flask 애플리케이션 (금 프리미엄 계산)
- `gold_option.py` - 금 옵션 데이터 분석 모듈 (Blueprint)
- `config.py` - 설정 파일 (API 키 등)
- `index.html` - 프론트엔드 HTML 파일

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python -m venv venv

# Windows에서 가상환경 활성화
venv\Scripts\activate

# macOS/Linux에서 가상환경 활성화
source venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 설정

`config.py` 파일에서 필요한 API 키를 설정하세요:

```python
EXCHANGE_RATE_API_KEY = "your_exchange_rate_api_key"
```

### 4. 애플리케이션 실행

```bash
python gold_premium.py
```

애플리케이션은 http://127.0.0.1:5000 에서 실행됩니다.

## API 엔드포인트

### 금 프리미엄 계산
- `GET /api/gold_premium` - 금 김치 프리미엄 계산

### 금 옵션 분석
- `GET /api/gold_options_analysis` - 금 옵션 데이터 분석 (실제 API)
- `GET /api/gold_options_analysis_sample` - 금 옵션 데이터 분석 (샘플 데이터)
- `GET /api/test_kis_api` - KIS API 연결 테스트

## 기능

1. **금 프리미엄 계산**: 해외 금 시세와 국내 금 시세를 비교하여 김치 프리미엄을 계산
2. **금 옵션 분석**: COT(Commitment of Traders) 데이터를 분석하여 매수/매도 신호 제공
3. **실시간 환율**: 한국수출입은행 API를 통한 실시간 환율 정보

## 주의사항

- `kis_api.py` 파일이 없는 경우 금 옵션 분석 기능의 일부가 제한될 수 있습니다.
- 샘플 데이터를 사용하여 기본적인 분석 기능은 항상 이용 가능합니다.
