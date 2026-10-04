import streamlit as st
import psycopg2
import pandas as pd
from datetime import date
import uuid

st.set_page_config(page_title="欖球會管理系統", layout="wide", page_icon="🏉")

# ==========================================
# 1. 資料庫連線與初始化模組
# ==========================================
def get_connection():
    """建立資料庫連線"""
    return psycopg2.connect(st.secrets["DB_URL"])

def run_query(query, params=None, fetch=False):
    """執行 SQL 語法，支援讀取與寫入"""
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
            return pd.DataFrame() # 防呆：發生錯誤時回傳空表格，避免網頁崩潰
    finally:
        cursor.close()
        conn.close()

def init_db():
    """初始化資料表，現在所有人員都在 members 表中"""
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        member_code VARCHAR(50) UNIQUE,
        name VARCHAR(100),
        phone VARCHAR(20),
        status VARCHAR(20) DEFAULT 'Trial', -- 預設為試堂 (Trial)
        trial_date DATE,                   -- 試堂日期
        join_date DATE                     -- 轉為正式會員的日期
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

# 執行初始化
init_db()

# 生成隨機短編號的輔助函數 (例如 T-1A2B)
def generate_short_code(prefix="T"):
    return f"{prefix}-{str(uuid.uuid4())[:4].upper()}"

# ==========================================
# 2. 側邊欄選單 (系統導覽)
# ==========================================
st.sidebar.title("🏉 欖球會系統")
menu = st.sidebar.radio("選擇功能", ["📝 報名試堂 (公眾)", "👕 買隊衣 (會員)", "🛠️ 管理員後台 (Admin)"])

# ==========================================
# 3. 功能模組：報名試堂 (直接進入 members 表)
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
                # 為試堂自動生成一個臨時編號
                temp_code = generate_short_code("TRIAL")
                
                # 直接寫入 members 表，狀態預設為 Trial
                run_query(
                    "INSERT INTO members (member_code, name, phone, status, trial_date) VALUES (%s, %s, %s, 'Trial', %s)", 
                    (temp_code, name, phone, trial_date)
                )
                st.success("✅ 成功報名試堂！我們會盡快與您聯絡。")
                st.info(f"📌 您的專屬編號為：**{temp_code}** (請記下此編號以便日後查詢或購買隊衣)")
            else:
                st.warning("⚠️ 請填寫姓名與電話。")

# ==========================================
# 4. 功能模組：買隊衣 (支援電話號碼搜尋與家庭多成員選擇)
# ==========================================
elif menu == "👕 買隊衣 (會員)":
    st.title("購買隊衣")
    st.write("正式會員或試堂學員皆可使用編號或登記電話下單。")
    
    # 建立兩個 session state 來管理搜尋狀態
    if 'found_members' not in st.session_state:
        st.session_state.found_members = pd.DataFrame()
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""

    # 第一步：搜尋會員
    search_input = st.text_input("請輸入專屬編號 或 聯絡電話", value=st.session_state.search_term)
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("搜尋"):
            if search_input:
                # 同時搜尋 member_code (完全符合) 或 phone (完全符合或包含)
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

    # 第二步：顯示訂購表單 (只有在找到會員後才顯示)
    if not st.session_state.found_members.empty:
        with st.form("order_form"):
            st.subheader("填寫訂單")
            
            # 準備下拉選單的選項 (顯示 姓名 + 編號)
            member_options = []
            for index, row in st.session_state.found_members.iterrows():
                member_options.append(f"{row['name']} ({row['member_code']})")
            
            # 如果有多個成員（例如同一個電話有多個小朋友），讓用戶選擇
            selected_member_str = st.selectbox("選擇要購買隊衣的學員", member_options)
            
            # 從選擇的字串中提取 member_code
            # 格式是 "Name (MEMBER_CODE)"，所以我們取括號內的內容
            selected_member_code = selected_member_str.split("(")[-1].replace(")", "")
            
            item = st.selectbox("選擇商品", ["2026 主場球衣", "2026 作客球衣", "訓練短褲"])
            size = st.selectbox("選擇尺寸", ["XS", "S", "M", "L", "XL"])
            
            submitted = st.form_submit_button("確認下單")
            
            if submitted:
                # 寫入訂單，使用剛剛提取出來的確切 member_code
                run_query(
                    "INSERT INTO orders (member_code, item, size) VALUES (%s, %s, %s)",
                    (selected_member_code, item, size)
                )
                st.success(f"✅ 訂單已收到！({selected_member_str}) 的 {item} ({size}) 訂購成功，請聯絡教練付款。")
                
                # 訂購完成後提供按鈕可以重新整理/清空畫面
                if st.button("完成並返回"):
                    st.session_state.found_members = pd.DataFrame()
                    st.session_state.search_term = ""
                    st.rerun()

# ==========================================
# 5. 功能模組：管理員後台
# ==========================================
elif menu == "🛠️ 管理員後台 (Admin)":
    st.title("系統管理後台")
    
    admin_password = st.sidebar.text_input("輸入 Admin 密碼", type="password")
    
    if admin_password == "admin123":
        tab1, tab2, tab3 = st.tabs(["🔍 會員管理 (更新狀態)", "📈 試堂名單", "📦 隊衣訂單"])
        
        # --- Tab 1: 會員管理 (更新狀態) ---
        with tab1:
            st.subheader("搜尋與管理")
            search_query = st.text_input("輸入編號或姓名搜尋:")
            
            if search_query:
                search_sql = "SELECT * FROM members WHERE member_code ILIKE %s OR name ILIKE %s"
                df_members = run_query(search_sql, (f"%{search_query}%", f"%{search_query}%"), fetch=True)
                
                if not df_members.empty:
                    st.dataframe(df_members, hide_index=True)
                    
                    member_id = df_members.iloc[0]['id']
                    current_status = df_members.iloc[0]['status']
                    current_code = df_members.iloc[0]['member_code']
                    
                    with st.form("update_member"):
                        st.write(f"正在管理: **{df_members.iloc[0]['name']}** ({current_code})")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # 更新狀態，包含 Trial 和 Active
                            status_options = ["Trial", "Active", "Expired"]
                            new_status = st.selectbox(
                                "更改狀態 (繳費後請轉為 Active)", 
                                status_options, 
                                index=status_options.index(current_status) if current_status in status_options else 0
                            )
                        
                        with col2:
                            # 允許管理員修改編號 (例如將 TRIAL-1234 改為正式的 R001)
                            new_code = st.text_input("更新會員編號 (選填)", value=current_code)
                            
                        if st.form_submit_button("確認更新"):
                            # 如果狀態變成 Active 且之前不是，記錄 join_date
                            join_date_sql = ""
                            if new_status == "Active" and current_status != "Active":
                                join_date_sql = ", join_date = CURRENT_DATE"
                                
                            try:
                                run_query(
                                    f"UPDATE members SET status = %s, member_code = %s {join_date_sql} WHERE id = %s", 
                                    (new_status, new_code, int(member_id))
                                )
                                st.success("✅ 資料更新成功！")
                                st.rerun()
                            except Exception as e:
                                st.error("❌ 更新失敗，可能是會員編號與其他人重複。")
                else:
                    st.warning("找不到此人。")
                    
            st.divider()
            st.write("📋 所有人名單 (包含試堂與正式會員)")
            st.dataframe(run_query("SELECT * FROM members ORDER BY id DESC", fetch=True), hide_index=True)
            
        # --- Tab 2: 試堂專屬視角 ---
        with tab2:
            st.subheader("即將到來的試堂")
            # 只顯示狀態為 Trial 的人
            df_trials = run_query("SELECT member_code, name, phone, trial_date FROM members WHERE status = 'Trial' ORDER BY trial_date ASC", fetch=True)
            if not df_trials.empty:
                st.dataframe(df_trials, hide_index=True)
            else:
                st.write("目前沒有待處理的試堂名單。")
            
        # --- Tab 3: 隊衣訂單 ---
        with tab3:
            st.subheader("隊衣訂購紀錄")
            df_orders = run_query("SELECT * FROM orders ORDER BY order_date DESC", fetch=True)
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
