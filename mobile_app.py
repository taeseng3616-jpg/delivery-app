import streamlit as st
import pandas as pd
import os
import csv
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="매출관리시스템", page_icon="💰")

# 파일 설정
FILE_WORK = "daily_log.csv"
FILE_BANK = "deposit_log.csv"
FILE_MAINT = "maintenance_log.csv"
FILE_GOAL = "goal.txt"

# --- 공통 함수 ---
def save_to_csv(file_name, data_list):
    if not os.path.exists(file_name):
        with open(file_name, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if file_name == FILE_WORK:
                writer.writerow(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리(km)", "메모"])
            elif file_name == FILE_BANK:
                writer.writerow(["입금날짜", "입금처", "입금액", "메모"])
            elif file_name == FILE_MAINT:
                writer.writerow(["날짜", "항목", "금액", "당시주행거리", "메모"])
    
    with open(file_name, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow(data_list)

def load_data(file_name):
    if os.path.exists(file_name):
        try:
            df = pd.read_csv(file_name)
            # [에러 방지 핵심 코드] 옛날 파일이라 컬럼이 없으면 자동으로 0 채우기
            if file_name == FILE_WORK and '배달건수' not in df.columns:
                df['배달건수'] = 0
            if file_name == FILE_WORK and '순수익' not in df.columns: # 혹시 몰라 추가
                df['순수익'] = 0
            return df.fillna(0) # 빈카이 있으면 0으로 채움
        except:
            return pd.DataFrame() # 파일이 깨졌으면 빈 걸로 시작
    return pd.DataFrame()

# 데이터 덮어쓰기 (수정/삭제용)
def rewrite_csv(file_name, df):
    df.to_csv(file_name, index=False, encoding="utf-8-sig")

# --- 사이드바 ---
st.sidebar.header("🎯 목표 관리")
try:
    with open(FILE_GOAL, "r") as f: goal = int(f.read().strip())
except: goal = 3000000

new_goal = st.sidebar.number_input("목표액 설정", value=goal, step=100000)
if st.sidebar.button("목표 수정"):
    with open(FILE_GOAL, "w") as f: f.write(str(new_goal))
    st.rerun()

df_work = load_data(FILE_WORK)
current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    # 날짜 처리 강화 (에러 방지)
    df_work['날짜'] = df_work['날짜'].astype(str)
    month_data = df_work[df_work['날짜'].str.contains(current_month, na=False)]
    
    if not month_data.empty:
        current_profit = month_data['순수익'].sum()
        current_count = month_data['배달건수'].sum()

progress = min(current_profit / new_goal, 1.0) if new_goal > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"수익: **{int(current_profit):,}원** ({progress*100:.1f}%)")
st.sidebar.write(f"배달: **{int(current_count)}건**")

# --- 메인 화면 ---
st.title("💰 매출관리시스템")

tab1, tab2, tab3, tab4 = st.tabs(["📝 매출입력", "🏦 입금관리", "🔧 지출/정비", "📊 통계"])

# [탭 1] 매출 입력 및 관리
with tab1:
    st.subheader("일일 매출 기록")
    with st.form("work_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        date = col1.date_input("날짜", datetime.now())
        count = col2.number_input("배달건수(건)", min_value=0, step=1)
        
        c1, c2 = st.columns(2)
        coupang = c1.number_input("쿠팡(원)", min_value=0, step=1000)
        baemin = c2.number_input("배민(원)", min_value=0, step=1000)
        
        c3, c4 = st.columns(2)
        expense = c3.number_input("지출(식대)", min_value=0, step=1000)
        distance = c4.text_input("주행거리(km)")
        
        memo = st.text_input("메모")
        
        if st.form_submit_button("저장하기"):
            total = coupang + baemin
            net = total - expense
            save_to_csv(FILE_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
            st.success("저장 완료!")
            st.rerun()

    st.write("---")
    
    # 수정/삭제 기능
    with st.expander("🗑️ 기록 수정 및 삭제 (여기를 클릭하세요)"):
        if not df_work.empty:
            # 라벨 만들 때 에러 안나게 안전장치 추가
            df_work['temp_label'] = df_work['날짜'].astype(str) + " | " + df_work['순수익'].astype(int).astype(str) + "원"
            
            selected_label = st.selectbox("삭제할 기록 선택", df_work['temp_label'].tolist()[::-1])
            
            if st.button("🗑️ 이 기록 삭제하기"):
                # 선택된 라벨과 일치하는 행 찾아서 삭제
                df_work = df_work[df_work['temp_label'] != selected_label]
                # 임시 라벨 컬럼 지우고 저장
                df_work = df_work.drop(columns=['temp_label'])
                rewrite_csv(FILE_WORK, df_work)
                st.success("삭제되었습니다.")
                st.rerun()
        else:
            st.write("삭제할 데이터가 없습니다.")

    if not df_work.empty:
        # 보여줄 컬럼만 선택 (에러 방지)
        cols = ['날짜', '순수익', '배달건수', '메모']
        safe_cols = [c for c in cols if c in df_work.columns]
        st.dataframe(df_work[safe_cols].sort_values(by="날짜", ascending=False).head(5), use_container_width=True)


# [탭 2] 입금 관리
with tab2:
    st.subheader("통장 입금 확인")
    with st.form("bank_form", clear_on_submit=True):
        date = st.date_input("입금일", datetime.now())
        col_s, col_a = st.columns([1, 2])
        source = col_s.selectbox("입금처", ["쿠팡", "배민", "기타"])
        amount = col_a.number_input("입금액(원)", min_value=0, step=10000)
        memo = st.text_input("메모")
        if st.form_submit_button("입금 저장"):
            save_to_csv(FILE_BANK, [date, source, amount, memo])
            st.success("저장 완료!")
            st.rerun()

    df_bank = load_data(FILE_BANK)
    with st.expander("🗑️ 입금 내역 삭제"):
        if not df_bank.empty:
            df_bank['temp_label'] = df_bank['입금날짜'].astype(str) + " | " + df_bank['입금액'].astype(int).astype(str) + "원"
            sel_bank = st.selectbox("삭제할 내역", df_bank['temp_label'].tolist()[::-1])
            if st.button("선택한 입금 삭제"):
                df_bank = df_bank[df_bank['temp_label'] != sel_bank]
                df_bank = df_bank.drop(columns=['temp_label'])
                rewrite_csv(FILE_BANK, df_bank)
                st.success("삭제되었습니다.")
                st.rerun()
                
    if not df_bank.empty:
        st.dataframe(df_bank.sort_values(by="입금날짜", ascending=False), use_container_width=True)


# [탭 3] 지출/정비
with tab3:
    st.subheader("차량 정비 및 지출")
    items = ["휘발유", "오일교환", "브레이크패드", "타이어", "구동벨트", "보험료", "기타"]
    with st.form("maint_form", clear_on_submit=True):
        date = st.date_input("날짜", datetime.now())
        item = st.selectbox("항목", items)
        cost = st.number_input("비용(원)", min_value=0, step=1000)
        km = st.text_input("현재 Km")
        memo = st.text_input("내용")
        if st.form_submit_button("기록 저장"):
            save_to_csv(FILE_MAINT, [date, item, cost, km, memo])
            st.success("저장 완료!")
            st.rerun()

    df_maint = load_data(FILE_MAINT)
    with st.expander("🗑️ 정비 기록 삭제"):
        if not df_maint.empty:
            df_maint['temp_label'] = df_maint['날짜'].astype(str) + " | " + df_maint['항목'] + " | " + df_maint['금액'].astype(int).astype(str)
            sel_maint = st.selectbox("삭제할 기록", df_maint['temp_label'].tolist()[::-1])
            if st.button("선택한 기록 삭제"):
                df_maint = df_maint[df_maint['temp_label'] != sel_maint]
                df_maint = df_maint.drop(columns=['temp_label'])
                rewrite_csv(FILE_MAINT, df_maint)
                st.success("삭제되었습니다.")
                st.rerun()

    if not df_maint.empty:
        st.dataframe(df_maint.sort_values(by="날짜", ascending=False), use_container_width=True)

# [탭 4] 통계
with tab4:
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        col_a, col_b = st.columns(2)
        col_a.metric("이번 달 총 순수익", f"{int(current_profit):,} 원")
        if '배달건수' in df_work.columns:
             col_b.metric("총 배달 건수", f"{int(current_count)} 건")
        
        st.write("📉 최근 14일 수입 추이")
        chart_data = df_work[['날짜', '순수익']].tail(14).set_index('날짜')
        st.bar_chart(chart_data)
    else:
        st.info("데이터가 없습니다.")