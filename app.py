[import streamlit as st
import pandas as pd
# 假設使用 sqlite3 連結資料庫
# import sqlite3 

st.set_page_config(page_title="欖球會會員管理系統", layout="wide")

st.title("🏉 欖球會 Admin 管理後台")

# 模擬資料庫載入
@st.cache_data
def load_mock_data():
    return pd.DataFrame({
        "member_id": ["R001", "R002", "R003"],
        "name": ["Chan Tai Man", "Wong Siu Ming", "Lee Ka Ho"],
        "membership_status": ["Active", "Expired", "Pending"],
        "jersey_size": ["M", "L", "S"]
    })

if "df" not in st.session_state:
    st.session_state.df = load_mock_data()

st.subheader("🔍 搜尋與更新會員資料")

# 搜尋區塊
search_type = st.radio("搜尋方式", ["會員 ID", "會員姓名"], horizontal=True)
search_query = st.text_input(f"請輸入{search_type}")

if search_query:
    if search_type == "會員 ID":
        result = st.session_state.df[st.session_state.df["member_id"].str.contains(search_query, case=False)]
    else:
        result = st.session_state.df[st.session_state.df["name"].str.contains(search_query, case=False)]
    
    if not result.empty:
        st.write("### 搜尋結果")
        # 顯示找到的會員
        target_idx = result.index0]
        member = result.iloc[0]
        
        # 更新資料表單
        with st.form("update_form"):
            st.write(f"正在編輯: **{member['name']}** ({member['member_id']})")
            
            new_status = st.selectbox(
                "會員狀態 (Membership Status)", 
                ["Active", "Pending", "Expired"], 
                index=["Active", "Pending", "Expired"].index(member['membership_status'])
            )
            
            new_size = st.selectbox(
                "隊衣尺寸 (Jersey Size)", 
                ["S", "M", "L", "XL"], 
                index=["S", "M", "L", "XL"].index(member['jersey_size'])
            )
            
            submit_button = st.form_submit_button("更新資料 (Update)")
            
            if submit_button:
                # 實際應用中，此處會執行 SQL UPDATE 語法
                st.session_state.df.at[target_idx, 'membership_status'] = new_status
                st.session_state.df.at[target_idx, 'jersey_size'] = new_size
                st.success(f"✅ 成功更新會員 {member['member_id']} 的資料！")
                st.experimental_rerun()
    else:
        st.warning("找不到相符的會員紀錄")

st.divider()
st.subheader("📋 目前所有會員總表")
st.dataframe(st.session_state.df, use_container_width=True)
