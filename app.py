import streamlit as st
import psycopg2
import pandas as pd
from datetime import date

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
            # 獲取欄位名稱並轉換為 Pandas DataFrame 方便 Streamlit 顯示
            cols = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(result, columns=cols)
            conn.commit()
            return df
        conn.commit()
    except Exception as e:
        st.error(f"資料庫錯誤: {e}")
    finally:
        cursor.close()
        conn.close()

def init_db():
    """若資料表不存在則自動建立 (Members, Trials, Orders)"""
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        member_code VARCHAR(50) UNIQUE,
        name VARCHAR(100),
        phone VARCHAR(20),
        status VARCHAR(20) DEFAULT 'Active',
        join_date DATE DEFAULT CURRENT_DATE
    );
    CREATE TABLE IF NOT EXISTS trials (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        phone VARCHAR(20),
        trial_date DATE,
        status VARCHAR(20) DEFAULT 'Pending'
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

# ==========================================
# 2. 側邊欄選單 (系統導覽)
# ==========================================
st.sidebar.title("🏉 欖球會系統")
menu = st.sidebar.radio("選擇功能", ["📝 報名試堂 (公眾)", "👕 買隊衣 (會員)", "🛠️ 管理員後台 (Admin)"])

# ==========================================
# 3. 功能模組：報名試堂
# ==========================================
if menu == "📝 報名試堂 (公眾)":
    st.title("報名欖球試堂")
    st.write("歡迎填寫以下資料報名試堂，我們的教練會盡快聯絡你。")
    
    with st.form("trial_form"):
        name = st.text_input("球員姓名 (Name)")
        phone = st.text_input("聯絡電話 (Phone)")
        trial_date = st.date_input("選擇試堂日期", min_value=date.today())
        
        submitted = st.form_submit_button("提交報名")
        if submitted:
            if name and phone:
                run_query(
                    "INSERT INTO trials (name, phone, trial_date) VALUES (%s, %s, %s)", 
                    (name, phone, trial_date)
                )
                st.success("✅ 成功報名試堂！我們會盡快與您聯絡。")
            else:
                st.warning("⚠️ 請填寫姓名與電話。")

# ==========================================
# 4. 功能模組：買隊衣
# ==========================================
elif menu == "👕 買隊衣 (會員)":
    st.title("會員專屬 - 購買隊衣")
    
    with st.form("order_form"):
        member_code = st.text_input("請輸入你的會員編號 (Member ID)")
        item = st.selectbox("選擇商品", ["2026 主場球衣", "2026 作客球衣", "訓練短褲"])
        size = st.selectbox("選擇尺寸", ["XS", "S", "M", "L", "XL"])
        
        submitted = st.form_submit_button("確認下單")
        if submitted:
            if member_code:
                run_query(
                    "INSERT INTO orders (member_code, item, size) VALUES (%s, %s, %s)",
                    (member_code, item, size)
                )
                st.success("✅ 訂單已收到！請聯絡教練付款。")
            else:
                st.warning("⚠️ 請輸入有效的會員編號。")

# ==========================================
# 5. 功能模組：管理員後台
# ==========================================
elif menu == "🛠️ 管理員後台 (Admin)":
    st.title("系統管理後台")
    
    # 簡單的 Admin 密碼保護 (可根據需求修改或省略)
    admin_password = st.sidebar.text_input("輸入 Admin 密碼", type="password")
    
    if admin_password == "admin123": # 建議未來改放進 secrets.toml 中
        tab1, tab2, tab3 = st.tabs(["🔍 搜尋與更新會員", "📋 試堂名單", "📦 隊衣訂單"])
        
        # --- Tab 1: 搜尋與更新會員 ---
        with tab1:
            st.subheader("搜尋會員資料")
            search_col, add_col = st.columns(2)
            
            with search_col:
                search_query = st.text_input("輸入會員編號或姓名搜尋:")
                if search_query:
                    search_sql = "SELECT * FROM members WHERE member_code ILIKE %s OR name ILIKE %s"
                    df_members = run_query(search_sql, (f"%{search_query}%", f"%{search_query}%"), fetch=True)
                    
                    if not df_members.empty:
                        st.dataframe(df_members, hide_index=True)
                        
                        # 顯示更新表單
                        member_id = df_members.iloc[0]['id']
                        current_status = df_members.iloc[0]['status']
                        
                        with st.form("update_member"):
                            st.write(f"正在更新: {df_members.iloc[0]['name']}")
                            new_status = st.selectbox("更改會籍狀態", ["Active", "Pending", "Expired"], index=["Active", "Pending", "Expired"].index(current_status))
                            if st.form_submit_button("更新狀態"):
                                run_query("UPDATE members SET status = %s WHERE id = %s", (new_status, int(member_id)))
                                st.success("✅ 狀態更新成功！")
                                st.rerun()
                    else:
                        st.warning("找不到此會員。")
                        
            with add_col:
                st.subheader("新增正式會員")
                with st.form("add_member_form"):
                    new_code = st.text_input("設定會員編號 (如: R001)")
                    new_name = st.text_input("會員姓名")
                    new_phone = st.text_input("聯絡電話")
                    if st.form_submit_button("新增會員"):
                        try:
                            run_query(
                                "INSERT INTO members (member_code, name, phone) VALUES (%s, %s, %s)",
                                (new_code, new_name, new_phone)
                            )
                            st.success(f"✅ 成功新增會員: {new_code}")
                        except Exception:
                            st.error("新增失敗，會員編號可能重複。")

            st.divider()
            st.write("所有會員名單")
            st.dataframe(run_query("SELECT * FROM members ORDER BY id DESC", fetch=True), hide_index=True)
            
        # --- Tab 2: 試堂名單 ---
        with tab2:
            st.subheader("最新試堂報名")
            df_trials = run_query("SELECT * FROM trials ORDER BY trial_date DESC", fetch=True)
            st.dataframe(df_trials, hide_index=True)
            
        # --- Tab 3: 隊衣訂單 ---
        with tab3:
            st.subheader("隊衣訂購紀錄")
            df_orders = run_query("SELECT * FROM orders ORDER BY order_date DESC", fetch=True)
            st.dataframe(df_orders, hide_index=True)
            
            # 更新訂單狀態
            st.write("更新派送狀態")
            with st.form("update_order"):
                order_id = st.number_input("輸入訂單 ID (id)", min_value=1, step=1)
                order_status = st.selectbox("狀態", ["Pending", "Paid", "Delivered"])
                if st.form_submit_button("更新訂單"):
                    run_query("UPDATE orders SET status = %s WHERE id = %s", (order_status, int(order_id)))
                    st.success("✅ 訂單更新成功！")
                    st.rerun()
    else:
        st.info("請於左側欄輸入管理員密碼以解鎖後台 (預設測試密碼: admin123)。")
