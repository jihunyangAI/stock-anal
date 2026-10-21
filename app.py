from datetime import date

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

PERIODS = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
}
# 화면에 보이는 구간보다 길게 받아 20일·60일 이동평균이 앞부분부터 맞게 계산되게 한다.
MA_SOURCE_PERIOD = {
    "1mo": "6mo",
    "3mo": "1y",
    "6mo": "1y",
    "1y": "2y",
}
DISPLAY_OFFSET = {
    "1mo": pd.DateOffset(months=1),
    "3mo": pd.DateOffset(months=3),
    "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
}

st.set_page_config(page_title="주식 데이터 분석기", layout="wide")
st.title("주식 데이터 분석기")


def format_price(value: float, currency: str) -> str:
    if currency == "KRW":
        return f"{value:,.0f} {currency}"
    if currency:
        return f"{value:,.2f} {currency}"
    return f"{value:,.2f}"


def parse_symbols(text: str) -> list[str]:
    symbols = []
    seen = set()
    for part in text.split(","):
        symbol = part.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _daily_close(history: pd.DataFrame) -> pd.Series:
    close = history["Close"].dropna().copy()
    close.index = pd.to_datetime(close.index.date)
    return close[~close.index.duplicated(keep="last")].sort_index()


def fetch_comparison(symbols: list[str], period: str) -> dict:
    closes = {}
    names = {}
    for symbol in symbols:
        not_found = f"'{symbol}' 종목의 데이터를 찾지 못했습니다. 종목코드를 확인해 주세요."
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            history = ticker.history(period=period)
            close = _daily_close(history) if not history.empty and "Close" in history else pd.Series(dtype=float)
        except Exception as exc:
            raise ValueError(not_found) from exc
        if close.empty:
            raise ValueError(not_found)
        closes[symbol] = close
        names[symbol] = info.get("longName") or info.get("shortName") or symbol

    start = max(series.index.min() for series in closes.values())
    compared = []
    for symbol, close in closes.items():
        window = close.loc[close.index >= start]
        if window.empty:
            raise ValueError(f"'{symbol}' 종목의 비교 기간 데이터가 없습니다.")
        compared.append(
            {
                "symbol": symbol,
                "name": names[symbol],
                "returns": (window / window.iloc[0] - 1) * 100,
            }
        )
    return {
        "mode": "compare",
        "period": period,
        "start": pd.Timestamp(start).strftime("%Y-%m-%d"),
        "series": compared,
    }


def fetch_quotes(text: str, period: str) -> dict:
    symbols = parse_symbols(text)
    if not symbols:
        raise ValueError("종목코드를 입력해 주세요.")
    if len(symbols) == 1:
        result = fetch_stock(symbols[0], period)
        result["mode"] = "single"
        return result
    return fetch_comparison(symbols, period)


def fetch_stock(symbol: str, period: str) -> dict:
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("종목코드를 입력해 주세요.")

    not_found = f"'{symbol}' 종목의 데이터를 찾지 못했습니다. 종목코드를 확인해 주세요."
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        fast = ticker.fast_info
        history = ticker.history(period=MA_SOURCE_PERIOD[period]).dropna(subset=["Close"])
        history = history.sort_index()
        history["MA20"] = history["Close"].rolling(20).mean()
        history["MA60"] = history["Close"].rolling(60).mean()
        visible_start = history.index.max() - DISPLAY_OFFSET[period]
        history = history.loc[history.index >= visible_start]
        price = fast.last_price
        previous_close = fast.previous_close
        currency = fast.currency or ""
    except Exception as exc:
        raise ValueError(not_found) from exc

    if history.empty or price is None or previous_close in (None, 0):
        raise ValueError(not_found)

    return {
        "symbol": symbol,
        "period": period,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "price": float(price),
        "currency": currency,
        "change_rate": (float(price) - float(previous_close)) / float(previous_close) * 100,
        "history": history,
    }


UP_COLOR = "#1570ef"
DOWN_COLOR = "#d92d20"
MA20_COLOR = "#f97316"
MA60_COLOR = "#16a34a"
COMPARE_COLORS = (
    "#2563eb",
    "#f97316",
    "#16a34a",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#ca8a04",
    "#db2777",
)
MA_LINES = (
    ("MA20", "20일", MA20_COLOR),
    ("MA60", "60일", MA60_COLOR),
)


def _format_price_value(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}"


def _style_price_chart(figure: go.Figure, title: str, currency: str) -> go.Figure:
    figure.update_layout(
        title=title,
        xaxis_title="날짜",
        yaxis_title="가격",
        hovermode="closest",
        height=480,
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
    )
    figure.update_xaxes(tickformat="%Y-%m-%d", hoverformat="%Y-%m-%d")
    figure.update_yaxes(tickformat=",.0f" if currency == "KRW" else ",.2f")
    return figure


def _moving_average_traces(
    frame: pd.DataFrame,
    currency: str,
    show_ma20: bool,
    show_ma60: bool,
) -> list[go.Scatter]:
    enabled = {"MA20": show_ma20, "MA60": show_ma60}
    digits = 0 if currency == "KRW" else 2
    traces = []
    for column, name, color in MA_LINES:
        if not enabled[column] or column not in frame:
            continue
        series = frame[column].dropna()
        if series.empty:
            continue
        traces.append(
            go.Scatter(
                x=series.index.strftime("%Y-%m-%d"),
                y=series.to_numpy(),
                mode="lines",
                name=name,
                line={"color": color, "width": 2, "dash": "dash"},
                customdata=[_format_price_value(value, digits) for value in series],
                hovertemplate=f"날짜: %{{x}}<br>{name} 이동평균: %{{customdata}}<extra></extra>",
            )
        )
    return traces


def build_price_chart(
    history: pd.DataFrame,
    company_name: str,
    currency: str,
    show_ma20: bool,
    show_ma60: bool,
) -> go.Figure:
    frame = history.sort_index()
    digits = 0 if currency == "KRW" else 2
    figure = go.Figure(
        data=[
            go.Scatter(
                x=frame.index.strftime("%Y-%m-%d"),
                y=frame["Close"],
                mode="lines",
                name="종가",
                customdata=frame["Close"].map(lambda value: _format_price_value(value, digits)),
                hovertemplate="날짜: %{x}<br>가격: %{customdata}<extra></extra>",
            ),
            *_moving_average_traces(frame, currency, show_ma20, show_ma60),
        ]
    )
    figure = _style_price_chart(figure, f"{company_name}주가추이", currency)
    figure.update_layout(
        showlegend=show_ma20 or show_ma60,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    return figure


def build_candlestick_chart(
    history: pd.DataFrame,
    company_name: str,
    currency: str,
    show_ma20: bool,
    show_ma60: bool,
) -> go.Figure:
    frame = history.sort_index()
    dates = frame.index.strftime("%Y-%m-%d")
    digits = 0 if currency == "KRW" else 2
    price_format = ",.0f" if currency == "KRW" else ",.2f"
    prices = [
        [
            _format_price_value(row.Open, digits),
            _format_price_value(row.High, digits),
            _format_price_value(row.Low, digits),
            _format_price_value(row.Close, digits),
        ]
        for row in frame.itertuples()
    ]
    volume_colors = [
        UP_COLOR if close >= open_price else DOWN_COLOR
        for open_price, close in zip(frame["Open"], frame["Close"])
    ]
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
    )
    figure.add_trace(
        go.Candlestick(
            x=dates,
            open=frame["Open"],
            high=frame["High"],
            low=frame["Low"],
            close=frame["Close"],
            increasing_line_color=UP_COLOR,
            increasing_fillcolor=UP_COLOR,
            decreasing_line_color=DOWN_COLOR,
            decreasing_fillcolor=DOWN_COLOR,
            customdata=prices,
            hovertemplate=(
                "날짜: %{x}<br>"
                "시가: %{customdata[0]}<br>"
                "고가: %{customdata[1]}<br>"
                "저가: %{customdata[2]}<br>"
                "종가: %{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    for trace in _moving_average_traces(frame, currency, show_ma20, show_ma60):
        figure.add_trace(trace, row=1, col=1)
    figure.add_trace(
        go.Bar(
            x=dates,
            y=frame["Volume"],
            marker_color=volume_colors,
            customdata=frame["Volume"].map(lambda value: f"{value:,.0f}"),
            hovertemplate="날짜: %{x}<br>거래량: %{customdata}<extra></extra>",
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    figure.update_layout(
        title=f"{company_name}주가추이",
        hovermode="closest",
        height=680,
        showlegend=show_ma20 or show_ma60,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 1, "xanchor": "right"},
        margin={"l": 16, "r": 24, "t": 64, "b": 48},
    )
    figure.update_xaxes(rangeslider_visible=False)
    figure.update_xaxes(automargin=True)
    figure.update_yaxes(automargin=True)
    figure.update_xaxes(
        tickformat="%Y-%m-%d",
        hoverformat="%Y-%m-%d",
        title_text="날짜",
        row=2,
        col=1,
    )
    figure.update_yaxes(title_text="가격", tickformat=price_format, title_standoff=12, row=1, col=1)
    figure.update_yaxes(title_text="거래량", tickformat=",.0f", title_standoff=12, row=2, col=1)
    return figure


def build_comparison_chart(result: dict) -> go.Figure:
    figure = go.Figure()
    for index, item in enumerate(result["series"]):
        returns = item["returns"]
        color = COMPARE_COLORS[index % len(COMPARE_COLORS)]
        figure.add_trace(
            go.Scatter(
                x=returns.index.strftime("%Y-%m-%d"),
                y=returns.to_numpy(),
                mode="lines",
                name=item["name"],
                line={"color": color, "width": 2.4},
                customdata=[f"{item['name']}: {value:+.2f}%" for value in returns],
                hovertemplate="날짜: %{x}<br>%{customdata}<extra></extra>",
            )
        )
    figure.update_layout(
        title="시작일 기준 수익률",
        xaxis_title="날짜",
        yaxis_title="수익률 (%)",
        hovermode="x unified",
        height=560,
        margin={"l": 16, "r": 24, "t": 72, "b": 48},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    figure.update_xaxes(tickformat="%Y-%m-%d", hoverformat="%Y-%m-%d", automargin=True)
    figure.update_yaxes(ticksuffix="%", automargin=True)
    return figure


def buy_close_on(history: pd.DataFrame, buy_date: date) -> tuple[pd.Timestamp, float]:
    close = _daily_close(history)
    target = pd.Timestamp(buy_date)
    later = close.loc[close.index >= target]
    used = later.index[0] if not later.empty else close.index[-1]
    return used, float(close.loc[used])


def _pnl_color(rate: float) -> str:
    # 계산기: 수익은 파랑, 손실은 빨강
    if rate > 0:
        return UP_COLOR
    if rate < 0:
        return DOWN_COLOR
    return "#475467"


def _colored_value(label: str, text: str, color: str) -> None:
    st.caption(label)
    st.markdown(
        (
            f"<p style='color:{color};font-size:1.35rem;font-weight:700;"
            f"margin:0 0 0.75rem 0'>{text}</p>"
        ),
        unsafe_allow_html=True,
    )


def render_return_calculator(result: dict | None) -> None:
    with st.sidebar:
        st.header("수익률 계산기")
        if result is None:
            st.caption("종목을 조회하면 매수일 기준 현재가치와 수익률을 계산합니다.")
            return
        if result.get("mode") == "compare":
            st.caption("종목을 하나만 조회하면 매수금액의 현재가치와 수익률을 계산합니다.")
            return

        close = _daily_close(result["history"])
        if close.empty or result["price"] <= 0:
            st.caption("계산에 쓸 주가 데이터가 없습니다.")
            return

        first = close.index.min().date()
        last = close.index.max().date()
        date_key = f"buy_date_{result['symbol']}_{result['period']}"
        selected = st.session_state.get(date_key)
        if not isinstance(selected, date) or selected < first or selected > last:
            st.session_state[date_key] = first
        buy_date = st.date_input("매수날짜", min_value=first, max_value=last, key=date_key)

        currency = result["currency"] or ""
        amount_key = f"buy_amount_{currency or 'NONE'}"
        if amount_key not in st.session_state:
            st.session_state[amount_key] = 1_000_000.0 if currency == "KRW" else 1_000.0
        buy_amount = st.number_input(
            "매수금액",
            min_value=0.0,
            step=100_000.0 if currency == "KRW" else 100.0,
            format="%.0f" if currency == "KRW" else "%.2f",
            key=amount_key,
        )

        used, buy_close = buy_close_on(result["history"], buy_date)
        st.caption(f"{result['name']}")
        if used.date() != buy_date:
            st.caption(f"휴장일이라 {used:%Y-%m-%d} 종가로 계산합니다.")
        st.caption(f"매수가 {format_price(buy_close, currency)}")

        if buy_amount <= 0 or buy_close <= 0:
            st.caption("매수금액을 입력하면 현재가치와 수익률을 계산합니다.")
            return

        current_value = buy_amount * (result["price"] / buy_close)
        rate = (current_value / buy_amount - 1) * 100
        color = _pnl_color(rate)
        _colored_value("현재가치", format_price(current_value, currency), color)
        _colored_value("수익률", f"{rate:+.2f}%", color)


def to_history_table(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    frame = frame.sort_index(ascending=False)
    frame.index = frame.index.strftime("%Y-%m-%d")
    frame.index.name = "날짜"
    frame = frame.rename(
        columns={
            "Open": "시가",
            "High": "고가",
            "Low": "저가",
            "Close": "종가",
            "Volume": "거래량",
        }
    )
    return frame.reset_index()


if "result" not in st.session_state:
    st.session_state.result = None
if "error" not in st.session_state:
    st.session_state.error = None

with st.form("stock_query"):
    ticker_col, period_col = st.columns([2, 1])
    symbol = ticker_col.text_input(
        "종목코드",
        value="005930.KS",
        help="여러 종목은 쉼표로 구분합니다. 예: 005930.KS, 000660.KS",
    )
    period_label = period_col.selectbox("기간", list(PERIODS))
    st.caption("비교할 종목은 쉼표로 구분합니다. 예: 005930.KS, 000660.KS")
    submitted = st.form_submit_button("데이터조회", type="primary")

if submitted:
    try:
        with st.spinner("데이터를 가져오는 중입니다."):
            st.session_state.result = fetch_quotes(symbol, PERIODS[period_label])
            st.session_state.error = None
    except Exception as exc:
        st.session_state.result = None
        st.session_state.error = str(exc)

render_return_calculator(st.session_state.result)

if st.session_state.error:
    st.error(st.session_state.error)
elif st.session_state.result is None:
    st.info("종목코드와 기간을 선택한 뒤 데이터조회를 눌러 주세요.")
else:
    result = st.session_state.result
    if result.get("mode") == "compare":
        st.success("종목 비교 데이터 조회가 완료되었습니다.")
        st.caption(f"시작일 {result['start']} 종가를 0%로 맞췄습니다.")
        st.plotly_chart(build_comparison_chart(result), width="stretch", theme=None)
        summary = pd.DataFrame(
            {
                "종목명": [item["name"] for item in result["series"]],
                "종목코드": [item["symbol"] for item in result["series"]],
                "시작일 대비 수익률": [f"{item['returns'].iloc[-1]:+.2f}%" for item in result["series"]],
            }
        )
        st.dataframe(summary, width="stretch", hide_index=True)
        st.stop()

    period_name = next(label for label, code in PERIODS.items() if code == result["period"])
    change_rate = result["change_rate"]
    # 국내 시세 관례: 상승은 빨강, 하락은 파랑
    if change_rate > 0:
        change_color = DOWN_COLOR
    elif change_rate < 0:
        change_color = UP_COLOR
    else:
        change_color = "#475467"

    st.success(f"{result['symbol']} 데이터 조회가 완료되었습니다.")

    name_col, price_col, change_col = st.columns(3)
    with name_col:
        with st.container(border=True):
            st.caption("회사명")
            st.markdown(f"**{result['name']}**")
    with price_col:
        with st.container(border=True):
            st.caption("현재가")
            st.markdown(f"**{format_price(result['price'], result['currency'])}**")
    with change_col:
        with st.container(border=True):
            st.caption("전일 대비 등락률")
            st.markdown(
                (
                    f"<p style='color:{change_color};font-size:1.6rem;"
                    f"font-weight:700;margin:0'>{change_rate:+.2f}%</p>"
                ),
                unsafe_allow_html=True,
            )

    ma20_col, ma60_col, _ = st.columns([1, 1, 3])
    show_ma20 = ma20_col.checkbox("20일 이동평균", value=True)
    show_ma60 = ma60_col.checkbox("60일 이동평균", value=True)

    line_tab, candle_tab = st.tabs(["선챠트", "캔들스틱 챠트"])
    with line_tab:
        st.plotly_chart(
            build_price_chart(
                result["history"],
                result["name"],
                result["currency"],
                show_ma20,
                show_ma60,
            ),
            width="stretch",
            theme=None,
        )
    with candle_tab:
        st.plotly_chart(
            build_candlestick_chart(
                result["history"],
                result["name"],
                result["currency"],
                show_ma20,
                show_ma60,
            ),
            width="stretch",
            theme=None,
        )

    table = to_history_table(result["history"])
    digits = 0 if result["currency"] == "KRW" else 2
    for column in ("시가", "고가", "저가", "종가"):
        table[column] = table[column].map(lambda value: f"{value:,.{digits}f}")
    table["거래량"] = table["거래량"].map(lambda value: f"{value:,.0f}")
    st.subheader("역사적 데이터")
    st.caption(f"{period_name} · {len(table)}개 거래일")
    st.dataframe(table, width="stretch", hide_index=True)
