import streamlit as st
import psycopg2
import pandas as pd
from datetime import date
import time

st.set_page_config(page_title="欖球會管理系統", layout="wide", page_icon="🏉")

# ==========================================
# 1. 資料庫連線與初始化模組
# ==========================================
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def run_query(query, params=None, fetch=False):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if fetch:
            result = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(result, columns=cols)
            conn.commit()
            return df
        conn.commit()
    except Exception as e:
        st.error(f"資料庫錯誤: {e}")
        if fetch:
            return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()

def init_db():
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        member_code VARCHAR(50) UNIQUE,
        name VARCHAR(100),
        phone VARCHAR(20),
        status VARCHAR(20) DEFAULT 'Trial',
        trial_date DATE,
        join_date DATE
    );
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        member_code VARCHAR(50),
        item VARCHAR(100),
        size VARCHAR(10),
        status VARCHAR(20) DEFAULT 'Pending',
        order_date DATE DEFAULT CURRENT_DATE
    );
    """
    run_query(create_tables_sql)

init_db()

# ==========================================
# 2. 自動生成編號邏輯
# ==========================================
def get_next_trial_code():
    """尋找最小可用的 TRIAL 編號 (Reuse 機制)"""
    query = "SELECT member_code FROM members WHERE member_code LIKE 'TRIAL-%'"
    df = run_query(query, fetch=True)
    
    if df.empty:
        return "TRIAL-0001"
    
    existing_nums = []
    for code in df['member_code']:
        try:
            num = int(code.split('-')[1])
            existing_nums.append(num)
        except:
            pass
            
    existing_nums.sort()
    
    target = 1
    for num in existing_nums:
        if num == target:
            target += 1
        elif num > target:
            break
            
    return f"TRIAL-{target:04d}"

def get_next_twr_code():
    """尋找最大的 TWR 編號並 +1 (由 00001 開始)"""
    query = "SELECT member_code FROM members WHERE member_code LIKE 'TWR%'"
    df = run_query(query, fetch=True)
    
    if df.empty:
        return "TWR00001"
    
    max_num = 0
    for code in df['member_code']:
        try:
            num = int(code.replace('TWR', ''))
            if num > max_num:
                max_num = num
        except:
            pass
            
    next_num = max_num + 1
    return f"TWR{next_num:05d}"

# ==========================================
# 3. 側邊欄選單
# ==========================================
st.sidebar.title("🏉 欖球會系統")
menu = st.sidebar.radio("選擇功能", ["📝 報名試堂 (公眾)", "👕 買隊衣 (會員)", "🛠️ 管理員後台 (Admin)"])

# ==========================================
# 4. 功能模組：報名試堂
# ==========================================
if menu == "📝 報名試堂 (公眾)":
    st.title("報名欖球試堂")
    st.write("歡迎填寫以下資料報名試堂，報名後您將獲得一組專屬編號。")
    
    with st.form("trial_form"):
        name = st.text_input("球員姓名 (Name)")
        phone = st.text_input("聯絡電話 (Phone)")
        trial_date = st.date_input("選擇試堂日期", min_value=date.today())
        
        submitted = st.form_submit_button("提交報名")
        if submitted:
            if name and phone:
                temp_code = get_next_trial_code()
                
                run_query(
                    "INSERT INTO members (member_code, name, phone, status, trial_date) VALUES (%s, %s, %s, 'Trial', %s)", 
                    (temp_code, name, phone, trial_date)
                )
                st.success("✅ 成功報名試堂！我們會盡快與您聯絡。")
                st.info(f"📌 您的專屬編號為：**{temp_code}** (請記下此編號以便日後查詢或購買隊衣)")
            else:
                st.warning("⚠️ 請填寫姓名與電話。")

# ==========================================
# 5. 功能模組：買隊衣
# ==========================================
elif menu == "👕 買隊衣 (會員)":
    st.title("購買隊衣")
    st.write("正式會員或試堂學員皆可使用編號或登記電話下單。")
    
    if 'found_members' not in st.session_state:
        st.session_state.found_members = pd.DataFrame()
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""

    search_input = st.text_input("請輸入專屬編號 或 聯絡電話", value=st.session_state.search_term)
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("搜尋"):
            if search_input:
                search_sql = "SELECT id, member_code, name, phone, status FROM members WHERE member_code = %s OR phone = %s"
                result = run_query(search_sql, (search_input, search_input), fetch=True)
                
                if not result.empty:
                    st.session_state.found_members = result
                    st.session_state.search_term = search_input
                else:
                    st.error("❌ 找不到符合此編號或電話的會員，請重新確認。")
                    st.session_state.found_members = pd.DataFrame()
            else:
                st.warning("⚠️ 請輸入搜尋資料。")
    with col2:
        if not st.session_state.found_members.empty:
             st.success(f"✅ 找到 {len(st.session_state.found_members)} 位會員")

    st.divider()

    if not st.session_state.found_members.empty:
        with st.form("order_form"):
            st.subheader("填寫訂單")
            
            member_options = []
            for index, row in st.session_state.found_members.iterrows():
                member_options.append(f"{row['name']} ({row['member_code']})")
            
            selected_member_str = st.selectbox("選擇要購買隊衣的學員", member_options)
            selected_member_code = selected_member_str.split("(")[-1].replace(")", "")
            
            item = st.selectbox("選擇商品", ["2026 主場球衣", "2026 作客球衣", "訓練短褲"])
            size = st.selectbox("選擇尺寸", ["XS", "S", "M", "L", "XL"])
            
            submitted = st.form_submit_button("確認下單")
            
            if submitted:
                run_query(
                    "INSERT INTO orders (member_code, item, size) VALUES (%s, %s, %s)",
                    (selected_member_code, item, size)
                )
                st.success(f"✅ 訂單已收到！({selected_member_str}) 的 {item} ({size}) 訂購成功，請聯絡教練付款。")
                
                if st.button("完成並返回"):
                    st.session_state.found_members = pd.DataFrame()
                    st.session_state.search_term = ""
                    st.rerun()

# ==========================================
# 6. 功能模組：管理員後台
# ==========================================
elif menu == "🛠️ 管理員後台 (Admin)":
    st.title("系統管理後台")
    
    admin_password = st.sidebar.text_input("輸入 Admin 密碼", type="password")
    
    if admin_password == "admin123":
        tab1, tab2, tab3 = st.tabs(["🔍 會員管理 (更新狀態)", "📈 試堂名單", "📦 隊衣訂單"])
        
        # --- Tab 1: 會員管理 ---
        with tab1:
            st.subheader("搜尋與管理")
            search_query = st.text_input("輸入編號、姓名或電話搜尋:")
            
            if search_query:
                search_sql = "SELECT * FROM members WHERE member_code ILIKE %s OR name ILIKE %s OR phone = %s"
                df_members = run_query(search_sql, (f"%{search_query}%", f"%{search_query}%", search_query), fetch=True)
                
                if not df_members.empty:
                    st.success(f"🔍 找到 {len(df_members)} 筆符合的紀錄，請在下方選擇欲編輯的成員：")
                    st.dataframe(df_members, hide_index=True)
                    
                    st.divider()
                    
                    options = []
                    for _, r in df_members.iterrows():
                        options.append(f"{r['name']} ({r['member_code']}) - 電話: {r['phone']}")
                    
                    selected_option = st.selectbox("🎯 選擇要編輯的成員", options)
                    selected_code = selected_option.split("(")[-1].split(")")[0]
                    
                    target_row = df_members[df_members['member_code'] == selected_code].iloc[0]
                    
                    member_id = target_row['id']
                    current_status = target_row['status']
                    current_code = target_row['member_code']
                    trial_date_val = target_row['trial_date']
                    join_date_val = target_row['join_date']
                    
                    with st.form("update_member"):
                        st.markdown(f"### ✏️ 正在編輯: **{target_row['name']}**")
                        
                        time_col1, time_col2 = st.columns(2)
                        time_col1.info(f"📅 報名試堂日: {trial_date_val if pd.notna(trial_date_val) else '無紀錄'}")
                        time_col2.success(f"🎉 正式入會日: {join_date_val if pd.notna(join_date_val) else '尚未入會'}")
                        
                        st.divider()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            status_options = ["Trial", "Active", "Expired"]
                            new_status = st.selectbox(
                                "更改狀態 (繳費後轉為 Active)", 
                                status_options, 
                                index=status_options.index(current_status) if current_status in status_options else 0
                            )
                        
                        with col2:
                            suggested_code = current_code
                            if new_status == "Active" and current_status == "Trial" and current_code.startswith("TRIAL"):
                                suggested_code = get_next_twr_code()
                                
                            new_code = st.text_input("會員編號 (轉正式會員請設為 TWR 開頭)", value=suggested_code)
                            
                        if st.form_submit_button("💾 確認更新資料"):
                            try:
                                join_date_sql = ""
                                if new_status == "Active" and current_status != "Active" and pd.isna(join_date_val):
                                    join_date_sql = ", join_date = CURRENT_DATE"
                                    
                                update_sql = f"UPDATE members SET status = %s, member_code = %s {join_date_sql} WHERE id = %s"
                                run_query(update_sql, (new_status, new_code, int(member_id)))
                                
                                if current_code != new_code:
                                    run_query(
                                        "UPDATE orders SET member_code = %s WHERE member_code = %s", 
                                        (new_code, current_code)
                                    )
                                    
                                st.success(f"✅ 會員 {target_row['name']} 資料更新成功！")
                                if current_code != new_code:
                                    st.info(f"🔄 編號已從 {current_code} 變更為 {new_code}，歷史訂單已自動同步。 (原 {current_code} 已釋出供 Reuse)")
                                
                                time.sleep(1.5)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ 更新失敗：{e}")
                else:
                    st.warning("找不到此人。")
                    
            st.divider()
            st.write("📋 系統所有會員總表")
            df_all = run_query("SELECT * FROM members ORDER BY id DESC", fetch=True)
            if not df_all.empty:
                st.dataframe(df_all, hide_index=True)
            
        # --- Tab 2: 試堂名單 ---
        with tab2:
            st.subheader("即將到來的試堂")
            df_trials = run_query("SELECT member_code, name, phone, trial_date FROM members WHERE status = 'Trial' ORDER BY trial_date ASC", fetch=True)
            if not df_trials.empty:
                st.dataframe(df_trials, hide_index=True)
            else:
                st.write("目前沒有待處理的試堂名單。")
            
        # --- Tab 3: 隊衣訂單 ---
        with tab3:
            st.subheader("隊衣訂購紀錄")
            df_orders = run_query("SELECT * FROM orders ORDER BY order_date DESC", fetch=True)
            if not df_orders.empty:
                st.dataframe(df_orders, hide_index=True)
            
            with st.form("update_order"):
                order_id = st.number_input("輸入訂單 ID (id) 以更新狀態", min_value=1, step=1)
                order_status = st.selectbox("狀態", ["Pending", "Paid", "Delivered"])
                if st.form_submit_button("更新訂單"):
                    run_query("UPDATE orders SET status = %s WHERE id = %s", (order_status, int(order_id)))
                    st.success("✅ 訂單更新成功！")
                    st.rerun()
    else:
        st.info("請於左側欄輸入管理員密碼以解鎖後台 (預設測試密碼: admin123)。")
