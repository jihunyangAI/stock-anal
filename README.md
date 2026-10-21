# 주식 데이터 분석기

Yahoo Finance 시세를 조회하고 차트로 비교하는 Streamlit 앱입니다.

## 기능

- 종목코드와 기간(1개월, 3개월, 6개월, 1년)으로 시세를 조회합니다.
- 회사명, 현재가, 전일 대비 등락률, 일별 시세 테이블을 보여 줍니다.
- 종가 선차트와 캔들스틱 차트를 그립니다. 캔들스틱 아래에는 거래량 막대가 있습니다.
- 20일, 60일 이동평균선을 점선으로 켜고 끌 수 있습니다.
- 종목코드를 쉼표로 구분해 입력하면 시작일 종가를 0%로 맞춘 수익률을 한 차트에 비교합니다. 예: `005930.KS, 000660.KS`
- 사이드바 수익률 계산기에서 매수날짜와 매수금액을 넣으면 현재가치와 수익률을 계산합니다. 수익은 파란색, 손실은 빨간색입니다.

종목코드는 Yahoo Finance 형식입니다. 삼성전자 `005930.KS`, SK하이닉스 `000660.KS`, 애플 `AAPL`.

## 실행

Python 3.11 이상이 필요합니다. 이 저장소는 Python 3.14에서 확인했습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

macOS나 Linux에서는 가상환경 활성화 명령만 다릅니다.

```bash
source .venv/bin/activate
```

브라우저에서 `http://localhost:8501`을 엽니다.

## 콘솔 예시

`samsung_stock.py`는 종목 하나(기본값 `AAPL`)의 회사명, 현재가, 전일 대비 등락률과 최근 1개월 데이터 5행을 출력합니다.

```powershell
python samsung_stock.py
```

시세는 Yahoo Finance에서 가져오며, 투자 판단에 쓰지 마세요.
