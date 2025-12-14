import streamlit as st
import pandas as pd
import os
import csv
from datetime import datetime

# 1. 페이지 설정 (모바일 최적화)
st.set_page_config(page_title="배달 CEO 장부", page_icon="🛵", layout="centered")

# 파일 이름 설정
FILE_WORK = "daily_log.csv"
FILE_BANK = "deposit_log.csv"
FILE_MAINT = "maintenance_log.csv"
FILE_GOAL = "goal.txt"

# --- 초기화 함수 ---
def init_files():
    if not os.path.exists(FILE_WORK):
        with open(FILE_WORK, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "주행거리(km)", "메모"])
    if not os.path.exists(FILE_BANK):
        with open(FILE_BANK, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["입금날짜", "입금처", "입금액", "메모"])
    if not os.path.exists(FILE_MAINT):
        with open(FILE_MAINT, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["날짜", "항목", "금액", "당시주행거리", "메모"])
    if not os.path.exists(FILE_GOAL):
        with open(FILE_GOAL, "w") as f: f.write("3000000")

init_files()

# --- 데이터 로드 함수 ---
def load_data(file_name):
    if os.path.exists(file_name):
        return pd.read_csv(file_name)
    return pd.DataFrame()

# --- 저장 함수들 ---
def save_to_csv(file_name, data_list):
    with open(file_name, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(data_list)

# --- 사이드바: 목표 설정 및 현황 ---
st.sidebar.header("🏆 목표 관리")
try:
    with open(FILE_GOAL, "r") as f:
        goal_amount = int(f.read().strip())
except:
    goal_amount = 3000000

# 이번 달 수익 계산
df_work = load_data(FILE_WORK)
current_profit = 0
if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    # 날짜 컬럼을 문자열로 변환 후 필터링
    df_work['날짜'] = df_work['날짜'].astype(str)
    month_data = df_work[df_work['날짜'].str.startswith(current_month)]
    current_profit = month_data['순수익'].sum() if not month_data.empty else 0

# 목표 달성률 표시
progress = min(current_profit / goal_amount, 1.0) if goal_amount > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"현재: **{current_profit:,}원** ({progress*100:.1f}%)")
st.sidebar.write(f"목표: {goal_amount:,}원")

# 목표 수정 기능
new_goal = st.sidebar.number_input("목표 금액 수정", value=goal_amount, step=100000)
if st.sidebar.button("목표 저장"):
    with open(FILE_GOAL, "w") as f:
        f.write(str(new_goal))
    st.sidebar.success("목표가 수정되었습니다!")
    st.rerun()

# --- 메인 화면 탭 구성 ---
st.title("🛵 배달 CEO 통합 관리")
tab1, tab2, tab3, tab4 = st.tabs(["📝일별장부", "💰입금관리", "🛠️정비관리", "📊통계"])

# [탭 1] 일별 장부
with tab1:
    st.subheader("오늘 매출 입력")
    with st.form("work_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        date = col1.date_input("날짜", datetime.now())
        distance = col2.text_input("주행거리(km)")
        
        c1, c2, c3 = st.columns(3)
        coupang = c1.number_input("쿠팡(원)", min_value=0, step=1000)
        baemin = c2.number_input("배민(원)", min_value=0, step=1000)
        expense = c3.number_input("지출(원)", min_value=0, step=1000)
        
        memo = st.text_input("메모")
        
        submitted = st.form_submit_button("저장하기")
        if submitted:
            total = coupang + baemin
            net = total - expense
            save_to_csv(FILE_WORK, [date, coupang, baemin, total, expense, net, distance, memo])
            st.success("저장 완료!")
            st.rerun()
    
    st.divider()
    st.subheader("📋 최근 기록 (삭제 가능)")
    if not df_work.empty:
        # 최신순 정렬
        df_display = df_work.sort_values(by="날짜", ascending=False)
        st.dataframe(df_display, use_container_width=True)
        
        # 삭제 기능
        delete_date = st.selectbox("삭제할 날짜 선택", df_display['날짜'].unique())
        if st.button("선택한 날짜 기록 삭제"):
            df_work = df_work[df_work['날짜'] != delete_date]
            df_work.to_csv(FILE_WORK, index=False, encoding="utf-8-sig")
            st.warning(f"{delete_date} 기록이 삭제되었습니다.")
            st.rerun()

# [탭 2] 입금 관리
with tab2:
    st.subheader("통장 입금 기록")
    with st.form("bank_form", clear_on_submit=True):
        b_date = st.date_input("입금일", datetime.now())
        b_source = st.radio("입금처", ["쿠팡", "배민"], horizontal=True)
        b_amount = st.number_input("입금액", min_value=0, step=10000)
        b_memo = st.text_input("메모")
        
        if st.form_submit_button("입금 저장"):
            save_to_csv(FILE_BANK, [b_date, b_source, b_amount, b_memo])
            st.success("입금 기록 저장됨")
            st.rerun()
            
    df_bank = load_data(FILE_BANK)
    if not df_bank.empty:
        st.dataframe(df_bank.sort_values(by="입금날짜", ascending=False), use_container_width=True)

# [탭 3] 정비 관리
with tab3:
    st.subheader("차량 정비 기록")
    with st.form("maint_form", clear_on_submit=True):
        m_date = st.date_input("날짜", datetime.now())
        m_item = st.selectbox("항목", ["휘발유", "오일교환", "브레이크패드", "타이어", "기타"])
        m_cost = st.number_input("비용", min_value=0, step=1000)
        m_km = st.text_input("현재 Km")
        m_memo = st.text_input("내용")
        
        if st.form_submit_button("정비 저장"):
            save_to_csv(FILE_MAINT, [m_date, m_item, m_cost, m_km, m_memo])
            st.success("정비 기록 저장됨")
            st.rerun()

    df_maint = load_data(FILE_MAINT)
    if not df_maint.empty:
        st.dataframe(df_maint.sort_values(by="날짜", ascending=False), use_container_width=True)

# [탭 4] 통계
with tab4:
    st.subheader("📊 최근 7일 순수익")
    if not df_work.empty:
        # 최근 7일 데이터 추출
        chart_data = df_work.tail(7).copy()
        chart_data.set_index('날짜', inplace=True)
        st.bar_chart(chart_data['순수익'])
        
        st.metric(label="이번 달 총 순수익", value=f"{current_profit:,} 원")
    else:
        st.info("데이터가 없습니다.")
        
    st.divider()
    
    # 엑셀 다운로드 (CSV)
    with open(FILE_WORK, "rb") as f:
        st.download_button("💾 엑셀(CSV)로 다운로드", f, file_name="매출장부.csv", mime="text/csv")
