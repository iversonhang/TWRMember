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
        total_amount NUMERIC(10, 2) DEFAULT 0.0,
        status VARCHAR(20) DEFAULT 'Pending',
        order_date DATE DEFAULT CURRENT_DATE
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INT,
        item_name VARCHAR(100),
        size VARCHAR(10),
        price NUMERIC(10, 2),
        pickup_status VARCHAR(20) DEFAULT 'Uncollected'
    );
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        item_name VARCHAR(100) UNIQUE,
        price NUMERIC(10, 2),
        sizes VARCHAR(100),
        is_visible BOOLEAN DEFAULT TRUE
    );
    """
    run_query(create_tables_sql)

init_db()

# ==========================================
# 2. 自動生成編號邏輯
# ==========================================
def get_next_trial_code():
    query = "SELECT member_code FROM members WHERE member_code LIKE 'TRIAL-%'"
    df = run_query(query, fetch=True)
    if df.empty:
        return "TRIAL-0001"
    existing_nums = [int(code.split('-')[1]) for code in df['member_code'] if '-' in code]
    existing_nums.sort()
    target = 1
    for num in existing_nums:
        if num == target:
            target += 1
        elif num > target:
            break
    return f"TRIAL-{target:04d}"

def get_next_twr_code():
    query = "SELECT member_code FROM members WHERE member_code LIKE 'TWR%'"
    df = run_query(query, fetch=True)
    if df.empty:
        return "TWR00001"
    max_num = max([int(code.replace('TWR', '')) for code in df['member_code'] if 'TWR' in code] + [0])
    return f"TWR{max_num + 1:05d}"

# ==========================================
# 3. 側邊欄導覽與全域管理員登入
# ==========================================
st.sidebar.title("🏉 欖球會系統")
menu = st.sidebar.radio("選擇功能", ["📝 報名試堂 (公眾)", "👕 買隊衣 (會員購物車)", "🛠 管理員後台 (Admin)"])

st.sidebar.divider()
st.sidebar.subheader("🔒 管理員登入")
admin_password = st.sidebar.text_input("輸入 Admin 密碼", type="password")

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
                st.success("✅ 成功報名試堂！")
                st.info(f"📌 您的專屬編號為：**{temp_code}**")
            else:
                st.warning("⚠️ 請填寫姓名與電話。")

# ==========================================
# 5. 功能模組：買隊衣 (會員購物車)
# ==========================================
elif menu == "👕 買隊衣 (會員購物車)":
    st.title("購買隊衣 (購物車)")
    st.write("您可以同時選購多項商品，系統會自動加總總金額。")
    
    df_products = run_query("SELECT * FROM products WHERE is_visible = TRUE", fetch=True)
    
    if df_products.empty:
        st.warning("⚠ 目前沒有開放訂購的隊衣品項。")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []
            
        st.subheader("1. 確認會員身分")
        search_input = st.text_input("請輸入會員編號 或 登記電話")
        
        selected_member_code = None
        if search_input:
            res_mem = run_query("SELECT member_code, name, phone FROM members WHERE member_code = %s OR phone = %s", (search_input, search_input), fetch=True)
            if not res_mem.empty:
                if len(res_mem) > 1:
                    opts = [f"{r['name']} ({r['member_code']})" for _, r in res_mem.iterrows()]
                    chosen = st.selectbox("此電話有多位成員，請選擇：", opts)
                    selected_member_code = chosen.split("(")[-1].replace(")", "")
                else:
                    selected_member_code = res_mem.iloc[0]['member_code']
                    st.success(f"✅ 已識別會員: {res_mem.iloc[0]['name']} ({selected_member_code})")
            else:
                st.error("❌ 找不到此編號或電話。")
        
        st.divider()
        
        st.subheader("2. 選擇商品並加入購物車")
        with st.form("add_to_cart_form"):
            prod_name = st.selectbox("選擇商品", df_products['item_name'].tolist())
            p_row = df_products[df_products['item_name'] == prod_name].iloc[0]
            sizes = [s.strip() for s in str(p_row['sizes']).split(',')]
            price = float(p_row['price'])
            
            chosen_size = st.selectbox("選擇尺寸", sizes)
            add_btn = st.form_submit_button("🛒 加入購物車")
            
            if add_btn:
                st.session_state.cart.append({"item": prod_name, "size": chosen_size, "price": price})
                st.success(f"已加入: {prod_name} (尺寸: {chosen_size})")
        
        if st.session_state.cart:
            st.divider()
            st.subheader("3. 目前購物車明細")
            df_cart = pd.DataFrame(st.session_state.cart)
            st.dataframe(df_cart, hide_index=True)
            
            total_sum = float(df_cart['price'].sum())
            st.markdown(f"### 💰 總金額: **${total_sum:.2f}**")
            
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("🗑️ 清空購物車"):
                    st.session_state.cart = []
                    st.rerun()
            with col_c2:
                if st.button("✅ 確認送出訂單"):
                    if selected_member_code:
                        conn = get_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                "INSERT INTO orders (member_code, total_amount) VALUES (%s, %s) RETURNING id",
                                (selected_member_code, total_sum)
                            )
                            new_order_id = cur.fetchone()[0]
                            
                            for item in st.session_state.cart:
                                cur.execute(
                                    "INSERT INTO order_items (order_id, item_name, size, price) VALUES (%s, %s, %s, %s)",
                                    (new_order_id, item['item'], item['size'], float(item['price']))
                                )
                            conn.commit()
                            st.success(f"🎉 訂單已成功建立！訂單編號: #{new_order_id}，總金額: ${total_sum:.2f}。")
                            st.session_state.cart = []
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"結帳失敗: {e}")
                        finally:
                            cur.close()
                            conn.close()
                    else:
                        st.warning("⚠️ 請先在上方完成會員身分識別才能送出訂單。")

# ==========================================
# 6. 功能模組：管理員後台
# ==========================================
elif menu == "🛠 管理員後台 (Admin)":
    st.title("系統管理後台")
    
    if admin_password == "admin123":
        tab1, tab2, tab3, tab4 = st.tabs(["🔍 會員管理", "👕 隊衣商品設定", "📈 試堂名單", "📦 訂單與品項領取管理"])
        
        # --- Tab 1: 會員管理 ---
        with tab1:
            st.subheader("搜尋與管理")
            search_query = st.text_input("輸入編號、姓名或電話搜尋:")
            if search_query:
                df_m = run_query("SELECT * FROM members WHERE member_code ILIKE %s OR name ILIKE %s OR phone = %s", (f"%{search_query}%", f"%{search_query}%", search_query), fetch=True)
                if not df_m.empty:
                    st.dataframe(df_m, hide_index=True)
                    opts = [f"{r['name']} ({r['member_code']})" for _, r in df_m.iterrows()]
                    sel_opt = st.selectbox("🎯 選擇要編輯的成員", opts)
                    sel_code = sel_opt.split("(")[-1].split(")")[0]
                    t_row = df_m[df_m['member_code'] == sel_code].iloc[0]
                    
                    with st.form("update_member"):
                        st.write(f"正在編輯: **{t_row['name']}**")
                        new_status = st.selectbox("更改狀態", ["Trial", "Active", "Expired"], index=["Trial", "Active", "Expired"].index(t_row['status']) if t_row['status'] in ["Trial", "Active", "Expired"] else 0)
                        new_code = st.text_input("會員編號", value=t_row['member_code'])
                        if st.form_submit_button("💾 儲存"):
                            run_query("UPDATE members SET status = %s, member_code = %s WHERE id = %s", (new_status, new_code, int(t_row['id'])))
                            if t_row['member_code'] != new_code:
                                run_query("UPDATE orders SET member_code = %s WHERE member_code = %s", (new_code, t_row['member_code']))
                            st.success("更新成功！")
                            st.rerun()
                            
                    st.divider()
                    st.subheader(f"📦 該會員的歷史訂單紀錄 ({sel_code})")
                    
                    df_member_orders = run_query("""
                        SELECT o.id AS order_id, o.order_date, o.total_amount, o.status AS pay_status,
                               i.item_name, i.size, i.price, i.pickup_status
                        FROM orders o
                        LEFT JOIN order_items i ON o.id = i.order_id
                        WHERE o.member_code = %s
                        ORDER BY o.order_date DESC
                    """, (sel_code,), fetch=True)
                    
                    if not df_member_orders.empty:
                        st.dataframe(df_member_orders, hide_index=True)
                    else:
                        st.info("此會員目前尚無任何購物訂單紀錄。")
                        
                else:
                    st.warning("找不到此人。")
                    
            st.divider()
            st.write("📋 所有會員總表")
            df_all_m = run_query("SELECT * FROM members ORDER BY id DESC", fetch=True)
            if not df_all_m.empty:
                st.dataframe(df_all_m, hide_index=True)

        # --- Tab 2: 商品設定 ---
        with tab2:
            st.subheader("👕 隊衣商品與庫存預先定義")
            with st.form("add_prod"):
                n_name = st.text_input("商品名稱")
                n_price = st.number_input("價格", min_value=0.0)
                n_sizes = st.text_input("尺寸 (逗號分隔)")
                n_vis = st.checkbox("公開上架", value=True)
                if st.form_submit_button("新增"):
                    run_query("INSERT INTO products (item_name, price, sizes, is_visible) VALUES (%s, %s, %s, %s)", (n_name, n_price, n_sizes, n_vis))
                    st.success("新增成功！")
                    st.rerun()
            st.divider()
            df_p = run_query("SELECT * FROM products", fetch=True)
            if not df_p.empty:
                st.dataframe(df_p, hide_index=True)

        # --- Tab 3: 試堂名單 ---
        with tab3:
            st.subheader("即將到來的試堂")
            df_t = run_query("SELECT member_code, name, phone, trial_date FROM members WHERE status = 'Trial' ORDER BY trial_date ASC", fetch=True)
            if not df_t.empty:
                st.dataframe(df_t, hide_index=True)

        # --- Tab 4: 訂單與品項領取管理 ---
        with tab4:
            st.subheader("📦 訂單總覽與個別商品領取勾選")
            df_orders = run_query("""
                SELECT o.id, o.member_code, m.name AS member_name, o.total_amount, o.status, o.order_date 
                FROM orders o 
                LEFT JOIN members m ON o.member_code = m.member_code 
                ORDER BY o.order_date DESC
            """, fetch=True)
            
            if not df_orders.empty:
                for _, ord_row in df_orders.iterrows():
                    order_id = ord_row['id']
                    with st.expander(f"🛒 訂單 #{order_id} | 會員: {ord_row['member_name']} ({ord_row['member_code']}) | 金額: ${ord_row['total_amount']} | 付款: {ord_row['status']} | 日期: {ord_row['order_date']}"):
                        df_items = run_query("SELECT id, item_name, size, price, pickup_status FROM order_items WHERE order_id = %s", (int(order_id),), fetch=True)
                        
                        if not df_items.empty:
                            st.write("**📦 訂單商品明細與領取狀態：**")
                            for _, item_row in df_items.iterrows():
                                item_id = item_row['id']
                                current_pickup = item_row['pickup_status']
                                
                                c1, c2, c3 = st.columns([3, 2, 2])
                                c1.text(f"• {item_row['item_name']} (尺寸: {item_row['size']}) - ${item_row['price']}")
                                
                                new_item_pickup = c2.selectbox(
                                    "狀態", 
                                    ["Uncollected", "Collected"], 
                                    index=["Uncollected", "Collected"].index(current_pickup) if current_pickup in ["Uncollected", "Collected"] else 0,
                                    key=f"item_status_{item_id}"
                                )
                                
                                if c3.button("更新品項", key=f"btn_item_{item_id}"):
                                    run_query("UPDATE order_items SET pickup_status = %s WHERE id = %s", (new_item_pickup, int(item_id)))
                                    st.success(f"品項 #{item_id} 狀態已更新！")
                                    st.rerun()
                        
                        st.divider()
                        with st.form(f"order_manage_{order_id}"):
                            st.write("💳 管理整筆訂單付款狀態")
                            p_stat = st.selectbox("付款狀態", ["Pending", "Paid", "Cancelled"], index=["Pending", "Paid", "Cancelled"].index(ord_row['status']) if ord_row['status'] in ["Pending", "Paid", "Cancelled"] else 0)
                            if st.form_submit_button("更新付款狀態"):
                                run_query("UPDATE orders SET status = %s WHERE id = %s", (p_stat, int(order_id)))
                                st.success(f"訂單 #{order_id} 付款狀態更新成功！")
                                st.rerun()
            else:
                st.info("目前尚無任何訂單紀錄。")
    else:
        st.warning("⚠️ 請在左側欄輸入正確的管理員密碼以解鎖後台 (預設密碼: admin123)。")
