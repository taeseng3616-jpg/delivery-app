import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import time

# 1. 페이지 설정
st.set_page_config(page_title="매출현황", page_icon="🛵", layout="centered")

# --- 구글 시트 연결 ---
try:
    gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
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

# --- 데이터 로드 함수 (수정됨: 지출, 주행거리 제거) ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        rows = worksheet.get_all_values()

        if sheet_name == SHEET_WORK:
            # [변경] 지출, 주행거리 삭제됨
            required_cols = ["날짜", "쿠팡수입", "배민수입", "총수입", "순수익", "배달건수", "메모"]
        elif sheet_name == SHEET_BANK:
            required_cols = ["입금날짜", "입금처", "입금액", "메모"]
        elif sheet_name == SHEET_MAINT:
            required_cols = ["날짜", "항목", "금액", "당시주행거리", "메모"]
        else:
            required_cols = []

        if len(rows) < 2:
            return pd.DataFrame(columns=required_cols)

        data = rows[1:]
        df = pd.DataFrame(data)

        if df.shape[1] < len(required_cols):
            for i in range(len(required_cols) - df.shape[1]):
                df[len(df.columns)] = "" 
        df = df.iloc[:, :len(required_cols)]
        df.columns = required_cols
        return df
    except Exception as e:
        return pd.DataFrame()

# --- 데이터 추가 (수정됨: 지출, 주행거리 저장 제외) ---
def save_new_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    if not worksheet.get_all_values():
        if sheet_name == SHEET_WORK:
            # [변경] 헤더도 변경
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "순수익", "배달건수", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    worksheet.append_row([str(x) for x in data_list])

# --- 업데이트 ---
def update_entire_sheet(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear()
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

# --- 숫자 변환 도우미 ---
def safe_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# ================= 메인 화면 =================
st.title("매출현황")

# 사이드바
st.sidebar.header("🏆 목표 현황")
goal_amount = get_goal()

# 1. 데이터 로드
df_work = load_data(SHEET_WORK)
df_bank = load_data(SHEET_BANK)
df_maint = load_data(SHEET_MAINT)

# 2. 숫자 변환 (수정됨: 지출 컬럼 제외)
if not df_work.empty:
    # '지출' 제거됨
    for col in ['쿠팡수입', '배민수입', '총수입', '순수익', '배달건수']:
        if col in df_work.columns:
            df_work[col] = safe_numeric(df_work[col])

if not df_bank.empty:
    for col in ['입금액']:
        if col in df_bank.columns:
            df_bank[col] = safe_numeric(df_bank[col])

if not df_maint.empty:
    for col in ['금액']:
        if col in df_maint.columns:
            df_maint[col] = safe_numeric(df_maint[col])

# 3. 요약 계산
current_profit = 0
current_count = 0
if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    month_data = df_work[df_work['날짜'].astype(str).str.contains(current_month, na=False)]
    current_profit = month_data['순수익'].sum()
    current_count = month_data['배달건수'].sum()

progress = min(current_profit / goal_amount, 1.0) if goal_amount > 0 else 0
st.sidebar.progress(progress)
st.sidebar.write(f"💰 이번 달 수익: **{int(current_profit):,}원**")
st.sidebar.write(f"🛵 이번 달 배달: **{int(current_count)}건**")

new_goal = st.sidebar.number_input("목표 금액 수정", value=goal_amount, step=100000)
if st.sidebar.button("목표 저장"):
    set_goal(new_goal)
    st.rerun()

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📝배달매출", "💰입금관리", "🛠️정비관리", "📊통계"])

# ================= [탭 1] 배달 매출 (수정됨: 지출/거리 삭제) =================
with tab1:
    # [변경] 타이틀 변경
    st.header("📝 금일매출")
    with st.container(border=True):
        with st.form("work_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            date = col1.date_input("날짜", datetime.now(), format="YYYY-MM-DD")
            count = col2.number_input("건수", min_value=0)
            
            c1, c2 = st.columns(2)
            coupang = c1.number_input("쿠팡(원)", step=1000)
            baemin = c2.number_input("배민(원)", step=1000)
            
            # [변경] 지출, 거리 입력란 삭제됨
            memo = st.text_input("메모")
            
            if st.form_submit_button("💾 입력 내용 저장하기", type="primary"):
                total = coupang + baemin
                # [변경] 지출이 없으므로 순수익 = 총수입
                net = total 
                # [변경] 저장 리스트에서 expense, distance 삭제
                save_new_entry(SHEET_WORK, [date, coupang, baemin, total, net, count, memo])
                st.success("✅ 저장되었습니다!")
                time.sleep(0.5)
                st.rerun()

    st.write("---")
    st.subheader("📋 전체 내역 (수정/삭제)")
    
    if not df_work.empty:
        sorted_df = df_work.sort_values(by="날짜", ascending=False)
        edited_df = st.data_editor(
            sorted_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_work",
            hide_index=True
        )
        if st.button("🔴 매출 수정/삭제 반영"):
            with st.spinner("저장 중..."):
                update_entire_sheet(SHEET_WORK, edited_df)
            st.success("완벽하게 수정되었습니다!")
            st.rerun()
    else:
        st.info("아직 저장된 매출 데이터가 없습니다.")

# ================= [탭 2] 입금 관리 =================
with tab2:
    st.header("💰 입금 내역 입력")
    with st.container(border=True):
        with st.form("bank_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            d = col1.date_input("입금일", datetime.now(), format="YYYY-MM-DD")
            s = col2.selectbox("입금처", ["쿠팡", "배민", "기타"])
            a = st.number_input("입금액", step=10000)
            m = st.text_input("메모")
            
            if st.form_submit_button("💾 입금 저장", type="primary"):
                save_new_entry(SHEET_BANK, [d, s, a, m])
                st.success("✅ 입금 내역 저장 완료!")
                time.sleep(0.5)
                st.rerun()

    st.write("---")
    st.subheader("📋 입금 전체 내역 (수정/삭제)")

    if not df_bank.empty:
        sorted_bank = df_bank.sort_values(by="입금날짜", ascending=False)
        edited_bank = st.data_editor(
            sorted_bank,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_bank",
            hide_index=True
        )
        
        if st.button("🔴 입금 수정/삭제 반영"):
            update_entire_sheet(SHEET_BANK, edited_bank)
            st.success("저장 완료!")
            st.rerun()
    else:
        st.info("입금 내역이 없습니다.")

# ================= [탭 3] 정비 관리 =================
with tab3:
    st.header("🛠️ 오토바이 정비 입력")
    
    maint_items = [
        "휘발유", "오일교환", "미션오일", "브레이크(앞)", "브레이크(뒤)", 
        "에어필터", "구동벨트", "웨이트롤러", "배터리", "점화플러그", 
        "브레이크오일", "냉각수", "구동계", "타이어(앞)", "타이어(뒤)", 
        "보험료", "백미러"
    ]

    with st.container(border=True):
        col1, col2 = st.columns(2)
        d = col1.date_input("날짜", datetime.now(), format="YYYY-MM-DD")
        
        selected_item = col2.selectbox("정비 항목", maint_items + ["직접 입력"])
        
        if selected_item == "직접 입력":
            final_item = st.text_input("✏️ 항목 이름을 직접 입력하세요")
        else:
            final_item = selected_item
            
        c = st.number_input("비용(원)", step=1000)
        k = st.text_input("현재 주행거리(Km)")
        m = st.text_input("정비 내용/메모")
        
        if st.button("💾 정비 기록 저장", type="primary"):
            if not final_item:
                st.warning("⚠️ 항목을 입력해주세요!")
            else:
                save_new_entry(SHEET_MAINT, [d, final_item, c, k, m])
                st.success(f"✅ [{final_item}] 정비 기록 저장 완료!")
                time.sleep(1)
                st.rerun()

    st.write("---")
    st.subheader("📋 정비 전체 내역 (수정/삭제)")
    
    if not df_maint.empty:
        sorted_maint = df_maint.sort_values(by="날짜", ascending=False)
        edited_maint = st.data_editor(
            sorted_maint,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_maint",
            hide_index=True
        )
        
        if st.button("🔴 정비 수정/삭제 반영"):
            update_entire_sheet(SHEET_MAINT, edited_maint)
            st.success("저장 완료!")
            st.rerun()
    else:
        st.info("정비 기록이 없습니다.")

# ================= [탭 4] 통계 =================
with tab4:
    if not df_work.empty:
        df_stat = df_work.copy()
        df_stat['날짜'] = pd.to_datetime(df_stat['날짜'], errors='coerce')
        df_stat = df_stat.dropna(subset=['날짜'])
        
        if not df_stat.empty:
            df_stat['년'] = df_stat['날짜'].dt.year
            df_stat['월'] = df_stat['날짜'].dt.strftime('%Y-%m')
            
            # 1. [월별 분석] (상단)
            st.subheader("📊 월별 상세 분석 (Monthly)")
            unique_months = sorted(df_stat['월'].unique().tolist(), reverse=True)
            
            if unique_months:
                selected_month = st.selectbox("조회할 월을 선택하세요", unique_months)
                month_data = df_stat[df_stat['월'] == selected_month]

                stat_profit = month_data['순수익'].sum()
                stat_count = month_data['배달건수'].sum()

                m1, m2 = st.columns(2)
                m1.metric(f"{selected_month} 총 순수익", f"{int(stat_profit):,}원")
                m2.metric(f"{selected_month} 총 배달", f"{int(stat_count)}건")

                st.write(f"###### 📈 {selected_month} 일별 수익 변화")
                month_data['일'] = month_data['날짜'].dt.strftime('%d일')
                daily_chart = month_data.groupby('일')['순수익'].sum()
                st.bar_chart(daily_chart)
            else:
                st.info("월별 데이터가 없습니다.")

            st.write("---")

            # 2. [연간 분석] (하단)
            st.subheader("📅 연간 매출 분석 (Yearly)")
            unique_years = sorted(df_stat['년'].unique(), reverse=True)
            if unique_years:
                selected_year = st.selectbox("조회할 년도를 선택하세요", unique_years)
                year_data = df_stat[df_stat['년'] == selected_year]
                
                if not year_data.empty:
                    total_profit_year = year_data['순수익'].sum()
                    total_count_year = year_data['배달건수'].sum()
                    
                    c1, c2 = st.columns(2)
                    c1.metric(f"{selected_year}년 총 순수익", f"{int(total_profit_year):,}원")
                    c2.metric(f"{selected_year}년 총 배달", f"{int(total_count_year):,}건")
                    
                    year_data['월_숫자'] = year_data['날짜'].dt.month
                    monthly_chart = year_data.groupby('월_숫자')['순수익'].sum()
                    st.bar_chart(monthly_chart)
                else:
                    st.info("선택한 년도의 데이터가 없습니다.")
            else:
                st.info("연도별 데이터가 없습니다.")

        else:
             st.info("통계에 사용할 날짜 데이터가 충분하지 않습니다.")
    else:
        st.info("데이터가 없습니다.")
