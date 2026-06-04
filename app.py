import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="現場派車系統", layout="centered")
st.title("📱 現場車籍查詢與派車")

# 建立試算表連線
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"資料庫連線失敗，請檢查 Secrets 設定：{e}")
    st.stop()

def load_sheet_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

df_drivers = load_sheet_data("車籍資料")
df_zones = load_sheet_data("圖資基準")

if df_drivers.empty or df_zones.empty:
    st.warning("雲端資料庫尚未建立完成，請先由後台管理端上傳車籍與圖資基準。")
    st.stop()

zone_list = df_zones["分區代號"].tolist() if "分區代號" in df_zones.columns else []
vehicle_list = df_drivers["車頭車號"].dropna().unique().tolist() if "車頭車號" in df_drivers.columns else []

tab_search, tab_log = st.tabs(["🔍 快速查詢車籍", "📝 登錄出土紀錄"])

with tab_search:
    search_term = st.text_input("輸入車號數字搜尋 (車頭或車斗)：")
    
    if search_term:
        mask = df_drivers.apply(lambda row: row.astype(str).str.replace(r'\s+', '', regex=True).str.upper().str.contains(search_term.upper().replace(" ", "")), axis=1).any(axis=1)
        search_results = df_drivers[mask]
        
        if search_results.empty:
            st.warning("查無符合資料")
        else:
            if len(search_results) > 1:
                options = search_results.apply(lambda x: f"{x['車頭車號']} ({x['姓名']})", axis=1).tolist()
                selected_option = st.selectbox("找到多筆，請選擇：", options=options)
                selected_idx = options.index(selected_option)
                target_data = search_results.iloc[selected_idx]
            else:
                target_data = search_results.iloc[0]

            st.write("#### 📋 點擊灰色區塊直接複製")
            display_fields = ["姓名", "身分證", "車頭車號", "車斗車號"]
            
            for field in display_fields:
                val = str(target_data.get(field, "無資料"))
                st.caption(field)
                st.code(val, language="text")

with tab_log:
    with st.form("dispatch_form"):
        t_date = st.date_input("派車日期", date.today())
        t_plate = st.selectbox("載運車頭車號", options=["請選擇"] + vehicle_list)
        t_zone = st.selectbox("來源分區", options=["請選擇"] + zone_list)
        
        default_vol = 0.0
        if t_plate != "請選擇":
            match_row = df_drivers[df_drivers["車頭車號"] == t_plate]
            if not match_row.empty and "標準載重(m³)" in match_row.columns:
                try:
                    default_vol = float(match_row["標準載重(m³)"].iloc[0])
                except:
                    pass
            
        t_vol = st.number_input("實際載運方量 (m³)", value=default_vol, min_value=0.0, step=1.0)
        t_note = st.text_input("備註")
        
        submit_btn = st.form_submit_button("➕ 登錄紀錄")
        
        if submit_btn:
            if t_plate == "請選擇" or t_zone == "請選擇":
                st.error("請完整選擇車號與來源分區！")
            else:
                new_log = pd.DataFrame([{
                    "日期": str(t_date), "車頭車號": t_plate, "出土分區": t_zone, 
                    "載運方量(m³)": t_vol, "備註": t_note
                }])
                
                try:
                    current_logs = load_sheet_data("出土紀錄")
                    updated_logs = pd.concat([current_logs, new_log], ignore_index=True)
                    conn.update(worksheet="出土紀錄", data=updated_logs)
                    st.success(f"紀錄成功：{t_plate} 從 {t_zone} 載運 {t_vol} m³")
                except Exception as e:
                    st.error(f"寫入資料庫失敗：{e}")
