import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="배달 CEO 장부", page_icon="🛵", layout="centered")

# --- 구글 시트 연결 ---
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    # 사장님 시트 주소
    url = "https://docs.google.com/spreadsheets/d/1vNdErX9sW6N5ulvfr-ndcrGmutxwiuvfe2og87AOEnI"
    sh = gc.open_by_url(url)
except Exception as e:
    st.error(f"⚠️ 구글 시트 연결 실패! 잠시 후 새로고침 해주세요.\n{e}")
    st.stop()

# 시트 이름 정의
SHEET_WORK = "매출기록"
SHEET_BANK = "입금기록"
SHEET_MAINT = "정비기록"
SHEET_GOAL = "목표설정"

# --- 데이터 로드 (무조건 표 보이게) ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 데이터가 없어도 헤더(제목줄)는 무조건 만듦
        if df.empty:
            if sheet_name == SHEET_WORK:
                return pd.DataFrame(columns=["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
            elif sheet_name == SHEET_BANK:
                return pd.DataFrame(columns=["입금날짜", "입금처", "입금액", "메모"])
            elif sheet_name == SHEET_MAINT:
                return pd.DataFrame(columns=["날짜", "항목", "금액", "당시주행거리", "메모"])
        return df
    except:
        return pd.DataFrame()

# --- 저장 함수 ---
def save_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    if not worksheet.get_all_values(): # 헤더 없으면 생성
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    worksheet.append_row([str(x) for x in data_list])

# --- 삭제 함수 ---
def delete_entry(sheet_name, row_index):
    worksheet = sh.worksheet(sheet_name)
    worksheet.delete_rows(row_index + 2) # 구글시트 행 번호 보정

# --- 목표 관리 ---
def get_goal():
    try:
        worksheet = sh.worksheet(SHEET_GOAL)
        val = worksheet.acell('A1').value
        return int(val) if val else 3000000
    except: return 3000000

def set_goal(amount):
    try:
        worksheet = sh.worksheet(SHEET_GOAL)
        worksheet.update('A1', str(amount))
    except: pass

# --- 사이드바 ---
st.sidebar.header("🏆 목표 관리")
goal_amount = get_goal()

df_work = load_data(SHEET_WORK)
current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    df_work['날짜'] = df_work['날짜'].astype(str)
    for col in ['순수익', '배달건수']:
        if col in df_work.columns:
            df_work[col] = pd.to_numeric(df_work[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    month_data = df_work[df_work['날짜'].str.contains(current_month, na=False)]
    if not month_data.empty:
        current_profit = month_data['순수익'].sum()
        current_count = month_data['배달건수'].sum()

progress = min(current_profit / goal_amount, 1.0) if goal_amount > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"💰 수익: **{int(current_profit):,}원** ({progress*100:.1f}%)")
st.sidebar.write(f"🛵 배달: **{int(current_count)}건**")

new_goal = st.sidebar.number_input("목표 수정", value=goal_amount, step=100000)
if st.sidebar.button("목표 저장"):
    set_goal(new_goal)
    st.sidebar.success("저장됨")
    st.rerun()

# --- 메인 화면 ---
st.title("🛵 배달 CEO 장부")

tab1, tab2, tab3, tab4 = st.tabs(["📝배달매출", "💰입금관리", "🛠️정비관리", "📊통계"])

# [탭 1] 배달 매출 (입력 + 리스트 + 삭제)
with tab1:
    # 1. 입력 폼
    st.subheader("✍️ 오늘 매출 입력")
    with st.form("work_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        date = col1.date_input("날짜", datetime.now())
        count = col2.number_input("건수(건)", min_value=0)
        c1, c2 = st.columns(2)
        coupang = c1.number_input("쿠팡(원)", step=1000)
        baemin = c2.number_input("배민(원)", step=1000)
        c3, c4 = st.columns(2)
        expense = c3.number_input("지출(원)", step=1000)
        distance = c4.text_input("거리(km)")
        memo = st.text_input("메모")
        
        if st.form_submit_button("💾 저장하기"):
            total = coupang + baemin
            net = total - expense
            save_entry(SHEET_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
            st.success("저장 완료!")
            st.rerun()

    st.write("---") # 구분선

    # 2. 이력 리스트 (여기가 빠졌었습니다!)
    st.subheader("📋 입력된 장부 목록")
    if not df_work.empty:
        # 보기 좋게 최신순 정렬
        df_display = df_work.sort_values(by="날짜", ascending=False)
        # 테이블 보여주기
        st.dataframe(df_display, use_container_width=True)
        
        # 3. 삭제/수정 기능
        st.caption("▼ 내용을 지우고 싶으면 아래에서 날짜를 선택하고 삭제 버튼을 누르세요.")
        with st.expander("🗑️ 기록 삭제하기 (여기를 누르세요)"):
            # 선택하기 편하게 라벨 생성
            df_work['label'] = df_work['날짜'].astype(str) + " | 수익: " + df_work['순수익'].astype(str) + "원"
            del_list = df_work['label'].tolist()[::-1] # 최신순
            
            selected_del = st.selectbox("삭제할 항목 선택", del_list, key="del_work_box")
            
            if st.button("❌ 삭제하기", key="btn_del_work"):
                # 선택된 항목 삭제
                idx = df_work[df_work['label'] == selected_del].index[0]
                delete_entry(SHEET_WORK, idx)
                st.success("삭제되었습니다.")
                st.rerun()
    else:
        st.info("아직 입력된 데이터가 없습니다.")

# [탭 2] 입금 관리 (입력 + 리스트 + 삭제)
with tab2:
    st.subheader("✍️ 입금 기록")
    with st.form("bank_form", clear_on_submit=True):
        d = st.date_input("입금일", datetime.now())
        s = st.radio("입금처", ["쿠팡", "배민"], horizontal=True)
        a = st.number_input("금액", step=10000)
        m = st.text_input("메모")
        if st.form_submit_button("💾 입금 저장"):
            save_entry(SHEET_BANK, [d, s, a, m])
            st.rerun()

    st.write("---")
    
    st.subheader("📋 입금 내역")
    df_bank = load_data(SHEET_BANK)
    if not df_bank.empty:
        st.dataframe(df_bank.sort_values(by="입금날짜", ascending=False), use_container_width=True)
        
        with st.expander("🗑️ 입금 삭제하기"):
            df_bank['label'] = df_bank['입금날짜'].astype(str) + " | " + df_bank['입금액'].astype(str) + "원"
            sel_bank = st.selectbox("삭제할 입금", df_bank['label'].tolist()[::-1], key="del_bank_box")
            if st.button("❌ 삭제하기", key="btn_del_bank"):
                idx = df_bank[df_bank['label'] == sel_bank].index[0]
                delete_entry(SHEET_BANK, idx)
                st.rerun()

# [탭 3] 정비 관리 (입력 + 리스트 + 삭제)
with tab3:
    st.subheader("✍️ 정비 기록")
    with st.form("maint_form", clear_on_submit=True):
        d = st.date_input("날짜", datetime.now())
        i = st.selectbox("항목", ["휘발유", "오일교환", "타이어", "기타"])
        c = st.number_input("비용", step=1000)
        k = st.text_input("Km")
        m = st.text_input("내용")
        if st.form_submit_button("💾 정비 저장"):
            save_entry(SHEET_MAINT, [d, i, c, k, m])
            st.rerun()

    st.write("---")

    st.subheader("📋 정비 내역")
    df_maint = load_data(SHEET_MAINT)
    if not df_maint.empty:
        st.dataframe(df_maint.sort_values(by="날짜", ascending=False), use_container_width=True)
        
        with st.expander("🗑️ 정비 삭제하기"):
            df_maint['label'] = df_maint['날짜'].astype(str) + " | " + df_maint['항목']
            sel_maint = st.selectbox("삭제할 정비", df_maint['label'].tolist()[::-1], key="del_maint_box")
            if st.button("❌ 삭제하기", key="btn_del_maint"):
                idx = df_maint[df_maint['label'] == sel_maint].index[0]
                delete_entry(SHEET_MAINT, idx)
                st.rerun()

# [탭 4] 통계
with tab4:
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        col_a, col_b = st.columns(2)
        col_a.metric("이번 달 수익", f"{int(current_profit):,} 원")
        col_b.metric("이번 달 배달", f"{int(current_count)} 건")
        
        st.write("📉 최근 7일 수익 그래프")
        chart_data = df_work.tail(7).copy()
        chart_data.set_index('날짜', inplace=True)
        st.bar_chart(chart_data['순수익'])
    else:
        st.info("데이터가 없습니다.")
