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
    st.error(f"⚠️ 연결 실패! {e}")
    st.stop()

# 시트 이름 정의
SHEET_WORK = "매출기록"
SHEET_BANK = "입금기록"
SHEET_MAINT = "정비기록"
SHEET_GOAL = "목표설정"

# --- 데이터 로드 ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        # 데이터 없어도 헤더 생성
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

# --- 데이터 추가 (한 줄 저장) ---
def save_new_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    if not worksheet.get_all_values():
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    worksheet.append_row([str(x) for x in data_list])

# --- [핵심] 통째로 업데이트 (수정 반영용) ---
def update_entire_sheet(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear() # 싹 지우고
    # 다시 씀 (헤더 + 내용)
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

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

# ================= 메인 화면 =================
st.title("✅ 배달 CEO 장부 (Pro)")

# 사이드바 (목표)
st.sidebar.header("🏆 목표 현황")
goal_amount = get_goal()

df_work = load_data(SHEET_WORK)
current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    df_work['날짜'] = df_work['날짜'].astype(str)
    # 계산을 위해 숫자 변환
    for col in ['순수익', '배달건수']:
        if col in df_work.columns:
            df_work[col] = pd.to_numeric(df_work[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    month_data = df_work[df_work['날짜'].str.contains(current_month, na=False)]
    current_profit = month_data['순수익'].sum()
    current_count = month_data['배달건수'].sum()

progress = min(current_profit / goal_amount, 1.0) if goal_amount > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"💰 수익: **{int(current_profit):,}원**")
st.sidebar.write(f"🛵 배달: **{int(current_count)}건**")
new_goal = st.sidebar.number_input("목표 수정", value=goal_amount, step=100000)
if st.sidebar.button("목표 저장"):
    set_goal(new_goal)
    st.rerun()

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📝배달매출", "💰입금관리", "🛠️정비관리", "📊통계"])

# --- [탭 1] 배달 매출 ---
with tab1:
    # 1. 입력 폼
    with st.expander("✍️ 새 매출 입력하기 (접기/펴기)", expanded=True):
        with st.form("work_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            date = col1.date_input("날짜", datetime.now())
            count = col2.number_input("건수", min_value=0)
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
                save_new_entry(SHEET_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
                st.success("저장 완료!")
                st.rerun()

    st.write("---")
    
    # 2. [핵심] 엑셀처럼 수정/삭제 가능한 표
    st.subheader("📋 장부 수정 및 삭제")
    st.caption("💡 팁: 표의 숫자를 클릭해서 바로 고칠 수 있습니다. 수정 후 **[변경사항 저장]**을 꼭 누르세요!")
    
    if not df_work.empty:
        # num_rows="dynamic"을 넣어서 행 추가/삭제 가능하게 함
        edited_df = st.data_editor(
            df_work.sort_values(by="날짜", ascending=False),
            num_rows="dynamic",
            use_container_width=True,
            key="editor_work"
        )
        
        # 수정사항 저장 버튼
        if st.button("🔴 변경사항(수정/삭제) 구글 시트에 저장", type="primary"):
            with st.spinner("저장 중..."):
                update_entire_sheet(SHEET_WORK, edited_df)
            st.success("완벽하게 수정되었습니다!")
            st.rerun()
    else:
        st.info("데이터가 없습니다.")

# --- [탭 2] 입금 관리 ---
with tab2:
    with st.expander("✍️ 새 입금 입력하기", expanded=True):
        with st.form("bank_form", clear_on_submit=True):
            d = st.date_input("입금일", datetime.now())
            s = st.radio("입금처", ["쿠팡", "배민"], horizontal=True)
            a = st.number_input("금액", step=10000)
            m = st.text_input("메모")
            if st.form_submit_button("💾 입금 저장"):
                save_new_entry(SHEET_BANK, [d, s, a, m])
                st.rerun()

    st.subheader("📋 입금 내역 수정")
    df_bank = load_data(SHEET_BANK)
    if not df_bank.empty:
        # 수정 가능한 표
        edited_bank = st.data_editor(
            df_bank.sort_values(by="입금날짜", ascending=False),
            num_rows="dynamic",
            use_container_width=True,
            key="editor_bank"
        )
        if st.button("🔴 입금 변경사항 저장"):
            update_entire_sheet(SHEET_BANK, edited_bank)
            st.success("저장 완료!")
            st.rerun()

# --- [탭 3] 정비 관리 ---
with tab3:
    with st.expander("✍️ 새 정비 입력하기", expanded=True):
        with st.form("maint_form", clear_on_submit=True):
            d = st.date_input("날짜", datetime.now())
            i = st.selectbox("항목", ["휘발유", "오일교환", "타이어", "기타"])
            c = st.number_input("비용", step=1000)
            k = st.text_input("Km")
            m = st.text_input("내용")
            if st.form_submit_button("💾 정비 저장"):
                save_new_entry(SHEET_MAINT, [d, i, c, k, m])
                st.rerun()

    st.subheader("📋 정비 내역 수정")
    df_maint = load_data(SHEET_MAINT)
    if not df_maint.empty:
        # 수정 가능한 표
        edited_maint = st.data_editor(
            df_maint.sort_values(by="날짜", ascending=False),
            num_rows="dynamic",
            use_container_width=True,
            key="editor_maint"
        )
        if st.button("🔴 정비 변경사항 저장"):
            update_entire_sheet(SHEET_MAINT, edited_maint)
            st.success("저장 완료!")
            st.rerun()

# --- [탭 4] 통계 ---
with tab4:
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        c1, c2 = st.columns(2)
        c1.metric("이번 달 수익", f"{int(current_profit):,}원")
        c2.metric("이번 달 배달", f"{int(current_count)}건")
        st.bar_chart(df_work.set_index('날짜')['순수익'].tail(7))
    else:
        st.info("데이터가 없습니다.")
