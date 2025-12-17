import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import time

# 1. 페이지 설정
st.set_page_config(page_title="배달통합장부", page_icon="🛵", layout="centered")

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

# ==========================================
# [로그인 기능] 단순화된 로그인 처리
# ==========================================
def login_screen():
    st.title("🛵 배달 CEO 장부 (공용)")
    st.write("본인의 아이디와 비밀번호를 사용하여 로그인하세요.")
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (닉네임)", placeholder="예: 라이더1")
        password = st.text_input("비밀번호", type="password", placeholder="비밀번호 설정")
        submit = st.form_submit_button("로그인 / 시작하기", type="primary")
        
        if submit:
            if user_id and password:
                # 세션에 사용자 정보 저장
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user_id
                st.session_state['password'] = password # 간단한 검증용 (실제론 DB가 필요하지만 시트로 대체)
                st.success(f"반갑습니다, {user_id}님!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("아이디와 비밀번호를 모두 입력해주세요.")

# 로그인이 안 되어 있으면 로그인 화면만 보여주고 중단
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_screen()
    st.stop()

# 로그인 된 사용자 ID
CURRENT_USER = st.session_state['user_id']
CURRENT_PW = st.session_state['password']


# --- 데이터 로드 함수 (수정됨: 사용자 ID 필터링) ---
def load_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        rows = worksheet.get_all_values()

        # [변경] 맨 앞에 '아이디', '비번' 컬럼 추가됨
        if sheet_name == SHEET_WORK:
            required_cols = ["아이디", "비번", "날짜", "쿠팡수입", "배민수입", "총수입", "순수익", "배달건수", "메모"]
        elif sheet_name == SHEET_BANK:
            required_cols = ["아이디", "비번", "입금날짜", "입금처", "입금액", "메모"]
        elif sheet_name == SHEET_MAINT:
            required_cols = ["아이디", "비번", "날짜", "항목", "금액", "당시주행거리", "메모"]
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
        
        # [핵심] 현재 로그인한 사용자의 데이터만 필터링해서 리턴!
        # 비밀번호까지 일치하는지 확인 (간단한 보안)
        my_data = df[(df['아이디'] == CURRENT_USER) & (df['비번'] == CURRENT_PW)]
        
        return my_data
    except Exception as e:
        return pd.DataFrame()

# --- 데이터 추가 (수정됨: 아이디/비번 자동 저장) ---
def save_new_entry(sheet_name, data_list):
    worksheet = sh.worksheet(sheet_name)
    
    # 헤더 정의
    if not worksheet.get_all_values():
        if sheet_name == SHEET_WORK:
            worksheet.append_row(["아이디", "비번", "날짜", "쿠팡수입", "배민수입", "총수입", "순수익", "배달건수", "메모"])
        elif sheet_name == SHEET_BANK:
            worksheet.append_row(["아이디", "비번", "입금날짜", "입금처", "입금액", "메모"])
        elif sheet_name == SHEET_MAINT:
            worksheet.append_row(["아이디", "비번", "날짜", "항목", "금액", "당시주행거리", "메모"])
    
    # [핵심] 데이터 앞에 내 아이디와 비번을 붙여서 저장
    full_data = [CURRENT_USER, CURRENT_PW] + data_list
    worksheet.append_row([str(x) for x in full_data])

# --- 업데이트 (수정됨: 내 데이터만 수정하고 남의 건 건드리지 않음) ---
def update_my_data(sheet_name, my_edited_df):
    worksheet = sh.worksheet(sheet_name)
    all_rows = worksheet.get_all_values()
    
    # 1. 헤더 가져오기
    if not all_rows: return # 데이터 없음
    header = all_rows[0]
    
    # 2. 전체 데이터 DataFrame으로 변환
    all_df = pd.DataFrame(all_rows[1:], columns=header)
    
    # 3. 내 데이터가 아닌 것들만 남기기 (남의 데이터 보존)
    others_df = all_df[all_df['아이디'] != CURRENT_USER]
    
    # 4. 내 수정된 데이터에 아이디/비번 다시 확실히 박아넣기 (수정 중 실수 방지)
    my_edited_df['아이디'] = CURRENT_USER
    my_edited_df['비번'] = CURRENT_PW
    
    # 5. 합치기 (남의 데이터 + 나의 수정된 데이터)
    final_df = pd.concat([others_df, my_edited_df], ignore_index=True)
    
    # 6. 구글 시트 클리어 후 재작성
    worksheet.clear()
    worksheet.update([final_df.columns.values.tolist()] + final_df.values.tolist())


# --- 목표 관리 (사용자별 목표 분리 필요 - 임시로 300 고정) ---
# 목표 기능은 사용자별로 저장하려면 로직이 복잡해져서 일단 공통 기본값 or 세션값으로 대체
def get_user_goal():
    # 목표 설정 시트는 공유하기 어려우므로, 일단 개인별 목표는 세션에만 유지하거나 기본값 사용
    if 'my_goal' not in st.session_state:
        st.session_state['my_goal'] = 3000000
    return st.session_state['my_goal']

def set_user_goal(amount):
    st.session_state['my_goal'] = amount


# --- 숫자 변환 도우미 ---
def safe_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# ================= 메인 화면 =================
col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title(f"🛵 {CURRENT_USER}님의 장부")
with col_logout:
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

# 사이드바
st.sidebar.header(f"👤 {CURRENT_USER}님 현황")
goal_amount = get_user_goal()

# 1. 데이터 로드 (내 것만 가져옴)
df_work = load_data(SHEET_WORK)
df_bank = load_data(SHEET_BANK)
df_maint = load_data(SHEET_MAINT)

# 2. 숫자 변환
if not df_work.empty:
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

new_goal = st.sidebar.number_input("목표 금액 (임시)", value=goal_amount, step=100000)
if st.sidebar.button("목표 설정"):
    set_user_goal(new_goal)
    st.rerun()

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📝배달매출", "💰입금관리", "🛠️정비관리", "📊통계"])

# ================= [탭 1] 배달 매출 =================
with tab1:
    st.header("📝 금일매출")
    with st.container(border=True):
        with st.form("work_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            date = col1.date_input("날짜", datetime.now(), format="YYYY-MM-DD")
            count = col2.number_input("건수", min_value=0)
            
            c1, c2 = st.columns(2)
            coupang = c1.number_input("쿠팡(원)", step=1000)
            baemin = c2.number_input("배민(원)", step=1000)
            
            memo = st.text_input("메모")
            
            if st.form_submit_button("💾 입력 내용 저장하기", type="primary"):
                total = coupang + baemin
                net = total 
                save_new_entry(SHEET_WORK, [date, coupang, baemin, total, net, count, memo])
                st.success("✅ 저장되었습니다!")
                time.sleep(0.5)
                st.rerun()

    st.write("---")
    st.subheader("📋 전체 내역 (수정/삭제)")
    st.caption("💡 다른 사용자의 데이터는 보이지 않습니다.")
    
    if not df_work.empty:
        df_view = df_work.copy()
        df_view['날짜_dt'] = pd.to_datetime(df_view['날짜'], errors='coerce')
        df_view['월'] = df_view['날짜_dt'].dt.strftime('%Y-%m')
        
        all_months = sorted(df_view['월'].dropna().unique().tolist(), reverse=True)
        
        if all_months:
            col_sel, _ = st.columns([1, 2])
            selected_month = col_sel.selectbox("📅 수정할 데이터의 '월(Month)'을 선택하세요", all_months)
            
            current_month_df = df_view[df_view['월'] == selected_month].drop(columns=['날짜_dt', '월'])
            # 화면에서 아이디, 비번 컬럼은 숨김 (굳이 볼 필요 없으므로)
            cols_to_hide = ['아이디', '비번']
            current_month_df = current_month_df.drop(columns=[c for c in cols_to_hide if c in current_month_df.columns])

            sorted_view = current_month_df.sort_values(by="날짜", ascending=False)
            
            edited_df = st.data_editor(
                sorted_view,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_work",
                hide_index=True
            )
            
            if st.button("🔴 매출 수정/삭제 반영"):
                with st.spinner("저장 중..."):
                    # 1. 내 전체 데이터 로드 (필터링되지 않은 원본 필요하지만 여기선 이미 필터링됨)
                    # -> update_my_data 함수에서 처리함
                    
                    # 2. 이번달 말고 다른달 데이터 보존 로직
                    # (현재 df_work는 '내 데이터' 전체임)
                    df_work['날짜_temp'] = pd.to_datetime(df_work['날짜'], errors='coerce')
                    df_work['월_temp'] = df_work['날짜_temp'].dt.strftime('%Y-%m')
                    
                    # 내 데이터 중 수정 안 한 달
                    my_data_keep = df_work[df_work['월_temp'] != selected_month].drop(columns=['날짜_temp', '월_temp'])
                    
                    # 내 데이터 합치기 (다른달 + 수정한 이번달)
                    # edited_df에는 아이디/비번이 없을 수 있으므로 update_my_data에서 처리
                    my_final_df = pd.concat([my_data_keep, edited_df], ignore_index=True)
                    
                    # 전체 업데이트 요청
                    update_my_data(SHEET_WORK, my_final_df)
                    
                st.success("완벽하게 수정되었습니다!")
                st.rerun()
        else:
            st.info("표시할 데이터가 없습니다.")
    else:
        st.info("저장된 매출 데이터가 없습니다.")

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
                st.success("✅ 저장 완료!")
                time.sleep(0.5)
                st.rerun()

    st.write("---")
    st.subheader("📋 입금 전체 내역 (수정/삭제)")

    if not df_bank.empty:
        df_bank_view = df_bank.copy()
        df_bank_view['날짜_dt'] = pd.to_datetime(df_bank_view['입금날짜'], errors='coerce')
        df_bank_view['월'] = df_bank_view['날짜_dt'].dt.strftime('%Y-%m')

        all_months_bank = sorted(df_bank_view['월'].dropna().unique().tolist(), reverse=True)

        if all_months_bank:
            col_sel_bank, _ = st.columns([1, 2])
            selected_month_bank = col_sel_bank.selectbox("📅 조회할 월 선택", all_months_bank, key="bank_month_select")

            current_month_bank_df = df_bank_view[df_bank_view['월'] == selected_month_bank].drop(columns=['날짜_dt', '월'])
            
            cols_to_hide = ['아이디', '비번']
            current_month_bank_df = current_month_bank_df.drop(columns=[c for c in cols_to_hide if c in current_month_bank_df.columns])
            
            sorted_bank_view = current_month_bank_df.sort_values(by="입금날짜", ascending=False)

            edited_bank = st.data_editor(
                sorted_bank_view,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_bank",
                hide_index=True
            )
            
            if st.button("🔴 입금 수정/삭제 반영"):
                with st.spinner("저장 중..."):
                    df_bank['날짜_temp'] = pd.to_datetime(df_bank['입금날짜'], errors='coerce')
                    df_bank['월_temp'] = df_bank['날짜_temp'].dt.strftime('%Y-%m')

                    my_data_keep = df_bank[df_bank['월_temp'] != selected_month_bank].drop(columns=['날짜_temp', '월_temp'])
                    my_final_df = pd.concat([my_data_keep, edited_bank], ignore_index=True)
                    
                    update_my_data(SHEET_BANK, my_final_df)

                st.success("저장 완료!")
                st.rerun()
        else:
            st.info("데이터가 없습니다.")
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
            final_item = st.text_input("✏️ 항목 이름 입력")
        else:
            final_item = selected_item
            
        c = st.number_input("비용(원)", step=1000)
        k = st.text_input("현재 주행거리(Km)")
        m = st.text_input("정비 내용/메모")
        
        if st.button("💾 정비 기록 저장", type="primary"):
            if not final_item:
                st.warning("항목을 입력해주세요!")
            else:
                save_new_entry(SHEET_MAINT, [d, final_item, c, k, m])
                st.success(f"✅ 저장 완료!")
                time.sleep(1)
                st.rerun()

    st.write("---")
    st.subheader("🚗 내 오토바이 정비 현황")
    st.caption("항목별 마지막 정비 기록입니다.")

    if not df_maint.empty:
        df_status = df_maint.sort_values(by="날짜", ascending=False).drop_duplicates(["항목"])
        df_status_view = df_status[["항목", "날짜", "당시주행거리", "메모"]]
        st.dataframe(df_status_view, hide_index=True, use_container_width=True)
    else:
        st.info("기록이 없습니다.")

    st.write("---")
    with st.expander("📋 정비 전체 기록 수정/삭제"):
        if not df_maint.empty:
            cols_to_hide = ['아이디', '비번']
            df_maint_view = df_maint.drop(columns=[c for c in cols_to_hide if c in df_maint.columns])
            
            sorted_maint = df_maint_view.sort_values(by="날짜", ascending=False)
            edited_maint = st.data_editor(
                sorted_maint,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_maint",
                hide_index=True
            )
            
            if st.button("🔴 정비 수정/삭제 반영"):
                update_my_data(SHEET_MAINT, edited_maint)
                st.success("저장 완료!")
                st.rerun()
        else:
            st.info("기록이 없습니다.")

# ================= [탭 4] 통계 =================
with tab4:
    if not df_work.empty:
        df_stat = df_work.copy()
        df_stat['날짜'] = pd.to_datetime(df_stat['날짜'], errors='coerce')
        df_stat = df_stat.dropna(subset=['날짜'])
        
        if not df_stat.empty:
            df_stat['년'] = df_stat['날짜'].dt.year
            df_stat['월'] = df_stat['날짜'].dt.strftime('%Y-%m')
            
            st.subheader("📊 월별 상세 분석 (Monthly)")
            unique_months = sorted(df_stat['월'].unique().tolist(), reverse=True)
            
            if unique_months:
                selected_month = st.selectbox("조회할 월 선택", unique_months)
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
                st.info("데이터가 없습니다.")

            st.write("---")

            st.subheader("📅 연간 매출 분석 (Yearly)")
            unique_years = sorted(df_stat['년'].unique(), reverse=True)
            if unique_years:
                selected_year = st.selectbox("조회할 년도 선택", unique_years)
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
                    st.info("데이터가 없습니다.")
            else:
                st.info("데이터가 없습니다.")

        else:
             st.info("날짜 데이터가 충분하지 않습니다.")
    else:
        st.info("데이터가 없습니다.")
