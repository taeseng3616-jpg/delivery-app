import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="매출관리시스템", page_icon="💰", layout="wide")

# --- 구글 시트 연결 설정 ---
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    # 님의 구글 시트 주소 (변경 없음)
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

# --- 데이터 로드 함수 ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 빈 표라도 보여주기 위한 처리
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

def update_entire_sheet(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# 목표 관리
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
st.sidebar.title("사장님 메뉴")
goal = get_goal()
new_goal = st.sidebar.number_input("월 목표액", value=goal, step=100000)
if st.sidebar.button("목표 저장"):
    set_goal(new_goal)
    st.rerun()

# 데이터 로드
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
    current_profit = month_data['순수익'].sum()
    current_count = month_data['배달건수'].sum()

progress = min(current_profit / new_goal, 1.0) if new_goal > 0 else 0
st.sidebar.progress(progress)
st.sidebar.info(f"💰 이번달: **{int(current_profit):,}원**\n🛵 배달: **{int(current_count)}건**")

# --- 메인 화면 ---
st.title("💰 통합 매출관리시스템 (Pro)")

tab1, tab2, tab3, tab4 = st.tabs(["📝 간편입력", "📋 장부관리(수정/삭제)", "🏦 입금/정비", "📊 통계"])

# [탭 1] 간편 입력
with tab1:
    st.subheader("오늘의 매출 입력")
    with st.form("input_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        date = col1.date_input("날짜", datetime.now())
        count = col2.number_input("건수", min_value=0)
        c1, c2 = st.columns(2)
        coupang = c1.number_input("쿠팡수입", step=1000)
        baemin = c2.number_input("배민수입", step=1000)
        c3, c4 = st.columns(2)
        expense = c3.number_input("지출", step=1000)
        distance = c4.text_input("주행거리")
        memo = st.text_input("메모")
        
        if st.form_submit_button("저장하기 💾"):
            total = coupang + baemin
            net = total - expense
            save_new_entry(SHEET_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
            st.success("저장되었습니다!")
            st.rerun()

# [탭 2] 장부 관리 (삭제 기능 추가!)
with tab2:
    st.subheader("📋 전체 장부 (수정/삭제)")
    
    # 1. 엑셀처럼 수정하는 표
    st.write("👇 **내용 수정**: 표를 클릭해서 숫자를 고치고 [변경사항 저장]을 누르세요.")
    edited_df = st.data_editor(
        df_work.sort_values(by="날짜", ascending=False) if not df_work.empty else df_work,
        num_rows="dynamic", 
        use_container_width=True,
        key="editor_work"
    )
    if st.button("🔴 변경사항 저장 (수정 반영)", type="primary"):
        with st.spinner("저장 중..."):
            update_entire_sheet(SHEET_WORK, edited_df)
        st.success("수정되었습니다!")
        st.rerun()

    st.write("---")

    # 2. [NEW] 확실한 삭제 기능 (드롭다운 방식)
    st.subheader("🗑️ 간편 삭제")
    with st.expander("여기를 눌러서 삭제할 기록을 선택하세요", expanded=True):
        if not df_work.empty:
            # 삭제 목록 만들기 (날짜 | 금액)
            df_work['del_label'] = df_work['날짜'].astype(str) + " | 순수익: " + df_work['순수익'].astype(str) + "원"
            del_list = df_work['del_label'].tolist()[::-1] # 최신순
            
            selected_del = st.selectbox("삭제할 항목 선택", del_list)
            
            if st.button("❌ 선택한 항목 삭제하기"):
                # 선택한 라벨을 제외한 나머지 데이터만 남김
                new_df = df_work[df_work['del_label'] != selected_del].drop(columns=['del_label'])
                with st.spinner("삭제 중..."):
                    update_entire_sheet(SHEET_WORK, new_df)
                st.success("삭제 완료!")
                st.rerun()
        else:
            st.write("삭제할 데이터가 없습니다.")

# [탭 3] 입금/정비
with tab3:
    col_bank, col_maint = st.columns(2)
    
    with col_bank:
        st.subheader("🏦 입금 관리")
        with st.form("bank_add"):
            d = st.date_input("입금일")
            s = st.selectbox("입금처", ["쿠팡", "배민"])
            a = st.number_input("금액", step=10000)
            if st.form_submit_button("입금 추가"):
                save_new_entry(SHEET_BANK, [d, s, a, ""])
                st.rerun()
        
        # 입금 삭제/수정
        df_bank = load_data(SHEET_BANK)
        with st.expander("입금 내역 수정/삭제"):
            if not df_bank.empty:
                edit_bank = st.data_editor(df_bank, num_rows="dynamic")
                if st.button("입금 변경사항 저장"):
                    update_entire_sheet(SHEET_BANK, edit_bank)
                    st.rerun()

    with col_maint:
        st.subheader("🔧 정비 관리")
        with st.form("maint_add"):
            d = st.date_input("정비일")
            i = st.selectbox("항목", ["오일", "타이어", "기타"])
            c = st.number_input("비용", step=1000)
            k = st.text_input("Km")
            if st.form_submit_button("정비 추가"):
                save_new_entry(SHEET_MAINT, [d, i, c, k, ""])
                st.rerun()
                
        # 정비 삭제/수정
        df_maint = load_data(SHEET_MAINT)
        with st.expander("정비 내역 수정/삭제"):
            if not df_maint.empty:
                edit_maint = st.data_editor(df_maint, num_rows="dynamic")
                if st.button("정비 변경사항 저장"):
                    update_entire_sheet(SHEET_MAINT, edit_maint)
                    st.rerun()

# [탭 4] 통계
with tab4:
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        total_p = df_work['순수익'].sum()
        st.metric("누적 총 순수익", f"{int(total_p):,} 원")
        chart_df = df_work.copy()
        chart_df = chart_df.set_index("날짜").sort_index()
        st.line_chart(chart_df['순수익'])
    else:
        st.info("데이터가 없습니다.")
