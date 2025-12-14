import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="배달 CEO 장부", page_icon="🛵", layout="centered")

# --- 구글 시트 연결 ---
try:
    # st.secrets를 사용하거나, json 파일 경로를 직접 입력하세요.
    # 로컬 테스트 시에는 json 파일 경로를 사용하시는 것이 편할 수 있습니다.
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

# --- 데이터 로드 함수 (수정됨: 에러 방지용 강력 모드) ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        rows = worksheet.get_all_values()

        # 1. 각 시트별로 우리가 원하는 '정확한' 제목(헤더)을 미리 정해둡니다.
        if sheet_name == SHEET_WORK:
            required_cols = ["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"]
        elif sheet_name == SHEET_BANK:
            required_cols = ["입금날짜", "입금처", "입금액", "메모"]
        elif sheet_name == SHEET_MAINT:
            required_cols = ["날짜", "항목", "금액", "당시주행거리", "메모"]
        else:
            required_cols = []

        # 2. 시트에 데이터가 아예 없거나 제목줄만 있는 경우
        if len(rows) < 2:
            return pd.DataFrame(columns=required_cols)

        # 3. 데이터 부분만 가져오기 (첫 번째 줄은 제목일 테니 건너뜀)
        data = rows[1:]
        
        # 4. 데이터프레임 만들기
        df = pd.DataFrame(data)

        # [중요] 시트에서 가져온 데이터 칸 수가 우리가 원하는 칸 수랑 다를 때 에러 안 나게 처리
        # 데이터 칸이 모자라면? -> 빈 칸 채우기
        if df.shape[1] < len(required_cols):
            for i in range(len(required_cols) - df.shape[1]):
                df[len(df.columns)] = "" 
        
        # 데이터 칸이 넘치면? -> 필요한 만큼만 자르기
        df = df.iloc[:, :len(required_cols)]

        # 5. 강제로 우리가 정한 이름 붙이기 (이것 때문에 KeyError가 사라집니다)
        df.columns = required_cols
        
        return df

    except Exception as e:
        # 뭔가 문제가 생기면 빈 표라도 줘서 앱이 꺼지는 걸 막음
        st.error(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame()

# --- 데이터 추가 (한 줄 저장) ---
def save_new_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    # 시트가 비어있다면 헤더 추가
    if not worksheet.get_all_values():
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["날짜", "쿠팡수입", "배민수입", "총수입", "지출", "순수익", "배달건수", "주행거리", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["날짜", "항목", "금액", "당시주행거리", "메모"])
    
    # 데이터 추가
    worksheet.append_row([str(x) for x in data_list])

# --- [핵심] 통째로 업데이트 (수정/삭제 반영용) ---
def update_entire_sheet(sheet_name, df):
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear() # 기존 내용 삭제
    # DataFrame을 리스트로 변환하여 업데이트 (헤더 + 값)
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

# 사이드바 (목표 및 요약)
st.sidebar.header("🏆 목표 현황")
goal_amount = get_goal()

# 데이터 로드 (매번 최신 데이터를 불러옵니다)
df_work = load_data(SHEET_WORK)
df_bank = load_data(SHEET_BANK)
df_maint = load_data(SHEET_MAINT)

current_profit = 0
current_count = 0

if not df_work.empty:
    current_month = datetime.now().strftime("%Y-%m")
    df_work['날짜'] = df_work['날짜'].astype(str)
    
    # 계산을 위해 숫자 변환 (콤마 제거 등)
    for col in ['순수익', '배달건수']:
        if col in df_work.columns:
            df_work[col] = pd.to_numeric(df_work[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    month_data = df_work[df_work['날짜'].str.contains(current_month, na=False)]
    current_profit = month_data['순수익'].sum()
    current_count = month_data['배달건수'].sum()

# 사이드바 표시
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

# ================= [탭 1] 배달 매출 =================
with tab1:
    st.header("📝 오늘의 매출 입력")
    # 1. 입력 폼
    with st.container(border=True):
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
            
            submitted = st.form_submit_button("💾 입력 내용 저장하기", type="primary")
            
            if submitted:
                total = coupang + baemin
                net = total - expense
                save_new_entry(SHEET_WORK, [date, coupang, baemin, total, expense, net, count, distance, memo])
                st.success("✅ 저장되었습니다!")
                st.rerun()

    st.write("---")
    
    # 2. 리스트 및 수정/삭제
    st.subheader("📋 전체 내역 (수정/삭제)")
    st.caption("💡 **사용법**: 표의 내용을 클릭해 수정하거나, 행 왼쪽을 선택 후 `Delete` 키를 눌러 삭제하세요.")
    
    if not df_work.empty:
        # 최신 날짜가 위로 오도록 정렬
        sorted_df = df_work.sort_values(by="날짜", ascending=False)
        
        # 데이터 에디터 (수정/삭제 가능 모드)
        edited_df = st.data_editor(
            sorted_df,
            num_rows="dynamic",     # 행 추가/삭제 가능
            use_container_width=True,
            key="editor_work",
            hide_index=True
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("🔴 수정/삭제 반영", help="표에서 수정한 내용을 구글 시트에 저장합니다."):
                with st.spinner("구글 시트에 반영 중..."):
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
            d = col1.date_input("입금일", datetime.now())
            s = col2.selectbox("입금처", ["쿠팡", "배민", "기타"]) # 라디오 대신 셀렉트박스로 변경하여 공간 절약
            a = st.number_input("입금액", step=10000)
            m = st.text_input("메모")
            
            if st.form_submit_button("💾 입금 저장", type="primary"):
                save_new_entry(SHEET_BANK, [d, s, a, m])
                st.success("✅ 입금 내역 저장 완료!")
                st.rerun()

    st.write("---")

    st.subheader("📋 입금 전체 내역 (수정/삭제)")
    st.caption("💡 **사용법**: 표를 직접 수정하거나 행을 삭제한 뒤 아래 버튼을 누르세요.")

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
    with st.container(border=True):
        with st.form("maint_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            d = col1.date_input("날짜", datetime.now())
            i = col2.selectbox("항목", ["휘발유", "오일교환", "타이어", "브레이크", "기타"])
            
            c = st.number_input("비용(원)", step=1000)
            k = st.text_input("현재 주행거리(Km)")
            m = st.text_input("정비 내용/메모")
            
            if st.form_submit_button("💾 정비 기록 저장", type="primary"):
                save_new_entry(SHEET_MAINT, [d, i, c, k, m])
                st.success("✅ 정비 기록 저장 완료!")
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
    st.subheader("📊 매출 분석")
    if not df_work.empty:
        c1, c2 = st.columns(2)
        c1.metric("이번 달 총 순수익", f"{int(current_profit):,}원")
        c2.metric("이번 달 총 배달", f"{int(current_count)}건")
        
        st.write("### 📅 최근 7일 수익 변화")
        # 날짜별로 그룹화하여 그래프가 예쁘게 나오도록 처리
        chart_data = df_work.copy()
        chart_data['날짜'] = pd.to_datetime(chart_data['날짜'])
        daily_profit = chart_data.groupby('날짜')['순수익'].sum().tail(7)
        st.bar_chart(daily_profit)
    else:
        st.info("데이터가 충분하지 않습니다.")

