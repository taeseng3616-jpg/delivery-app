import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# 1. 페이지 설정 (넓은 화면 모드 적용)
st.set_page_config(page_title="매출관리시스템", page_icon="💰", layout="wide")

# --- 구글 시트 연결 설정 ---
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    # [주의] 본인의 구글 시트 주소로 꼭 확인하세요! (URL 방식이 가장 확실함)
    # 아래 주소는 예시이므로, 본인의 시트 주소가 코드에 잘 들어있는지 확인해주세요.
    # 만약 에러가 나면 기존에 잘 되던 방식(open_by_url 등)을 그대로 쓰셔도 됩니다.
    url = "https://docs.google.com/spreadsheets/d/1vNdErX9sW6N5ulvfr-ndcrGmutxwiuvfe2og87AOEnI/edit?gid=0#gid=0" # 여기에 본인 주소 넣으셨죠?
    # 혹시 주소 넣는 게 번거로우시면 아래처럼 이름으로 찾기도 가능합니다.
    sh = gc.open("매출장부_DB") 
except Exception:
    # 에러 발생 시 주소 방식으로 재시도 (안전장치)
    try:
        # 여기에 아까 복사해둔 긴 주소를 넣어두면 안전합니다.
        url = "https://docs.google.com/spreadsheets/d/..." 
        sh = gc.open_by_url(url)
    except Exception as e:
        st.error(f"구글 시트 연결 실패! 설정을 확인해주세요.\n{e}")
        st.stop()

# 시트 이름 정의
SHEET_WORK = "매출기록"
SHEET_BANK = "입금기록"
SHEET_MAINT = "정비기록"
SHEET_GOAL = "목표설정"

# --- 함수 모음 ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def save_new_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    if not worksheet.get_all_values():
        # 헤더 생성
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    
    # 데이터 추가 (문자열 변환)
    worksheet.append_row([str(x) for x in data_list])

# [핵심] 엑셀처럼 수정한 데이터 통째로 업데이트하기
def update_entire_sheet(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear() # 기존 내용 싹 지우고
    # 헤더와 데이터 다시 쓰기
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

# 데이터 로드 및 통계
df_work = load_data(SHEET_WORK)
current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    df_work['날짜'] = df_work['날짜'].astype(str)
    # 숫자 변환 (콤마 제거)
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

# [탭 1] 간편 입력 (모바일용)
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

# [탭 2] 장부 관리 (PC 스타일 - 엑셀처럼 수정!)
with tab2:
    st.subheader("📋 전체 장부 (클릭해서 수정 가능)")
    st.info("💡 팁: 표 안의 숫자를 클릭해서 바로 고칠 수 있습니다. 수정 후 **[변경사항 저장]** 버튼을 꼭 눌러주세요!")
    
    if not df_work.empty:
        # 엑셀 같은 편집기 표시 (num_rows="dynamic"을 주면 행 추가/삭제도 가능)
        edited_df = st.data_editor(
            df_work.sort_values(by="날짜", ascending=False),
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_work"
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        if col_btn1.button("🔴 변경사항 저장"):
            with st.spinner("구글 시트에 반영 중..."):
                # 다시 문자열로 변환해서 저장 (안전성 확보)
                update_entire_sheet(SHEET_WORK, edited_df)
            st.success("완벽하게 수정되었습니다!")
            st.rerun()
    else:
        st.write("아직 데이터가 없습니다.")

# [탭 3] 입금 및 정비 (간소화)
with tab3:
    col_bank, col_maint = st.columns(2)
    
    with col_bank:
        st.subheader("🏦 입금 기록")
        with st.form("bank_add"):
            d = st.date_input("입금일")
            s = st.selectbox("입금처", ["쿠팡", "배민"])
            a = st.number_input("금액", step=10000)
            if st.form_submit_button("입금 추가"):
                save_new_entry(SHEET_BANK, [d, s, a, ""])
                st.rerun()
        
        # 입금 데이터 편집기
        df_bank = load_data(SHEET_BANK)
        if not df_bank.empty:
            edit_bank = st.data_editor(df_bank, num_rows="dynamic", key="edit_bank")
            if st.button("입금 수정 저장"):
                update_entire_sheet(SHEET_BANK, edit_bank)
                st.success("저장 완료")
                st.rerun()

    with col_maint:
        st.subheader("🔧 정비 기록")
        with st.form("maint_add"):
            d = st.date_input("정비일")
            i = st.selectbox("항목", ["오일", "타이어", "기타"])
            c = st.number_input("비용", step=1000)
            k = st.text_input("Km")
            if st.form_submit_button("정비 추가"):
                save_new_entry(SHEET_MAINT, [d, i, c, k, ""])
                st.rerun()
                
        # 정비 데이터 편집기
        df_maint = load_data(SHEET_MAINT)
        if not df_maint.empty:
            edit_maint = st.data_editor(df_maint, num_rows="dynamic", key="edit_maint")
            if st.button("정비 수정 저장"):
                update_entire_sheet(SHEET_MAINT, edit_maint)
                st.success("저장 완료")
                st.rerun()

# [탭 4] 통계
with tab4:
    st.subheader("📊 매출 분석 리포트")
    if not df_work.empty:
        total_p = df_work['순수익'].sum()
        st.metric("누적 총 순수익", f"{int(total_p):,} 원")
        
        st.write("📉 일별 순수익 추이")
        chart_df = df_work.copy()
        chart_df = chart_df.set_index("날짜").sort_index()
        st.line_chart(chart_df['순수익'])

