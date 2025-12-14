import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="매출관리시스템", page_icon="💰")

# --- 구글 시트 연결 설정 (Secrets 사용) ---
# 주의: Streamlit Secrets에 [gcp_service_account] 정보가 있어야 함
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1vNdErX9sW6N5ulvfr-ndcrGmutxwiuvfe2og87AOEnI/edit?gid=0#gid=0")
except Exception as e:
    st.error(f"구글 시트 연결 실패! Secrets 설정을 확인하세요.\n에러내용: {e}")
    st.stop()

# 시트 이름 정의 (엑셀 하단 탭 이름과 같아야 함)
SHEET_WORK = "매출기록"
SHEET_BANK = "입금기록"
SHEET_MAINT = "정비기록"
SHEET_GOAL = "목표설정"

# --- 공통 함수: 구글 시트 읽기/쓰기 ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def save_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    # 헤더(제목)가 없으면 생성
    if not worksheet.get_all_values():
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    
    # 데이터 추가 (모든 데이터를 문자열로 변환하여 저장)
    worksheet.append_row([str(x) for x in data_list])

# 데이터 삭제 함수 (행 번호로 삭제)
def delete_entry(sheet_name, row_index):
    worksheet = sh.worksheet(sheet_name)
    worksheet.delete_rows(row_index + 2) # 헤더(1줄)+0부터시작하는인덱스 보정

# 목표 불러오기/저장하기
def get_goal():
    try:
        worksheet = sh.worksheet(SHEET_GOAL)
        val = worksheet.acell('A1').value
        return int(val) if val else 3000000
    except:
        return 3000000

def set_goal(amount):
    try:
        worksheet = sh.worksheet(SHEET_GOAL)
        worksheet.update('A1', str(amount))
    except:
        pass

# --- 사이드바 ---
st.sidebar.header("🎯 목표 관리")
goal = get_goal()
new_goal = st.sidebar.number_input("목표액 설정", value=goal, step=100000)

if st.sidebar.button("목표 수정"):
    set_goal(new_goal)
    st.success("수정 완료!")
    st.rerun()

# 달성률 계산
df_work = load_data(SHEET_WORK)
current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    df_work['날짜'] = df_work['날짜'].astype(str)
    # 쉼표(,) 제거 후 숫자 변환 처리
    df_work['순수익'] = pd.to_numeric(df_work['순수익'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df_work['배달건수'] = pd.to_numeric(df_work['배달건수'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    month_data = df_work[df_work['날짜'].str.contains(current_month, na=False)]
    if not month_data.empty:
        current_profit = month_data['순수익'].sum()
        current_count = month_data['배달건수'].sum()

progress = min(current_profit / new_goal, 1.0) if new_goal > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"수익: **{int(current_profit):,}원** ({progress*100:.1f}%)")
st.sidebar.write(f"배달: **{int(current_count)}건**")

# --- 메인 화면 ---
st.title("💰 매출관리시스템 (Cloud)")

tab1, tab2, tab3, tab4 = st.tabs(["📝 매출입력", "🏦 입금관리", "🔧 지출/정비", "📊 통계"])

# [탭 1] 매출 입력
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
            save_entry(SHEET_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
            st.success("저장 완료!")
            st.rerun()

    st.write("---")
    with st.expander("🗑️ 기록 삭제"):
        if not df_work.empty:
            df_work['label'] = df_work['날짜'].astype(str) + " | " + df_work['순수익'].astype(str) + "원"
            del_list = df_work['label'].tolist()[::-1]
            selected = st.selectbox("삭제할 항목", del_list)
            
            if st.button("선택한 항목 삭제"):
                idx = df_work[df_work['label'] == selected].index[0]
                delete_entry(SHEET_WORK, idx)
                st.success("삭제되었습니다.")
                st.rerun()

    if not df_work.empty:
        st.dataframe(df_work.sort_values(by="날짜", ascending=False).head(5), use_container_width=True)

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
            save_entry(SHEET_BANK, [date, source, amount, memo])
            st.success("저장 완료!")
            st.rerun()

    df_bank = load_data(SHEET_BANK)
    with st.expander("🗑️ 입금 삭제"):
        if not df_bank.empty:
            df_bank['label'] = df_bank['입금날짜'].astype(str) + " | " + df_bank['입금액'].astype(str) + "원"
            sel_bank = st.selectbox("삭제", df_bank['label'].tolist()[::-1])
            if st.button("입금 삭제"):
                idx = df_bank[df_bank['label'] == sel_bank].index[0]
                delete_entry(SHEET_BANK, idx)
                st.rerun()
                
    if not df_bank.empty:
        st.dataframe(df_bank.sort_values(by="입금날짜", ascending=False), use_container_width=True)

# [탭 3] 정비 관리
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
            save_entry(SHEET_MAINT, [date, item, cost, km, memo])
            st.success("저장 완료!")
            st.rerun()

    df_maint = load_data(SHEET_MAINT)
    with st.expander("🗑️ 정비 삭제"):
        if not df_maint.empty:
            df_maint['label'] = df_maint['날짜'].astype(str) + " | " + df_maint['항목']
            sel_maint = st.selectbox("삭제", df_maint['label'].tolist()[::-1])
            if st.button("정비 삭제"):
                idx = df_maint[df_maint['label'] == sel_maint].index[0]
                delete_entry(SHEET_MAINT, idx)
                st.rerun()

    if not df_maint.empty:
        st.dataframe(df_maint.sort_values(by="날짜", ascending=False), use_container_width=True)

# [탭 4] 통계
with tab4:
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        col_a, col_b = st.columns(2)
        col_a.metric("이번 달 총 순수익", f"{int(current_profit):,} 원")
        col_b.metric("총 배달 건수", f"{int(current_count)} 건")
        
        st.write("📉 최근 14일 수입 추이")
        chart_data = df_work[['날짜', '순수익']].tail(14).set_index('날짜')
        st.bar_chart(chart_data)
    else:
        st.info("데이터가 없습니다.")

