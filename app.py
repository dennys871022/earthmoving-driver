import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="現場派車系統", layout="centered")
st.title("📱 現場車籍查詢與派車")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1y3Qnlx9qFwV6S6pyFTsT4rlXP_Tb8qd9tNhRBTjBHao/edit"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"資料庫連線失敗：{e}")
    st.stop()

def load_sheet_data(sheet_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

df_drivers = load_sheet_data("drivers")

if df_drivers.empty:
    st.warning("車籍資料庫尚未建立。")
    st.stop()

if 'confirmed_plate' not in st.session_state:
    st.session_state['confirmed_plate'] = ""

all_fields = ["姓名", "身分證", "車頭車號", "車斗車號"]
if "order" in st.query_params:
    url_order = st.query_params["order"].split(",")
    if set(url_order) == set(all_fields):
        current_order = url_order
    else:
        current_order = all_fields
else:
    current_order = all_fields

with st.expander("⚙️ 個人化顯示順序設定"):
    st.caption("💡 提示：先將下方選項全部「打叉」清除，再依想要的順序重新點選。設定完成後請將此網頁「加入書籤」，即可永久保存專屬順序！")
    new_order = st.multiselect("設定預覽與個別複製的顯示順序：", options=all_fields, default=current_order)
    if len(new_order) == 4 and new_order != current_order:
        st.query_params["order"] = ",".join(new_order)
        st.rerun()

display_fields = new_order if len(new_order) == 4 else all_fields

search_term = st.text_input("輸入車號數字搜尋 (車頭或車斗)：")

def match_plate(plate_val, kw):
    if pd.isna(plate_val):
        return False
    plate_str = str(plate_val).upper().strip()
    if plate_str == kw:
        return True
    parts = plate_str.replace("-", " ").split()
    if kw in parts:
        return True
    return False

if search_term:
    keyword = search_term.strip().upper()
    
    condition = df_drivers['車頭車號'].apply(match_plate, kw=keyword) | \
                df_drivers['車斗車號'].apply(match_plate, kw=keyword)
    search_results = df_drivers[condition]
    
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

        plate = target_data['車頭車號']

        st.markdown("### 🔎 查詢結果確認")
        for field in display_fields:
            st.markdown(f"**{field}：** {target_data.get(field, '無資料')}")
        st.divider()

        if st.button("✅ 資訊無誤，確認車輛並記錄車次", use_container_width=True):
            tw_now = datetime.utcnow() + timedelta(hours=8)
            current_date_str = tw_now.strftime("%Y-%m-%d")
            current_time_str = tw_now.strftime("%H:%M:%S")
            note = ""
            
            df_logs = load_sheet_data("dispatch_logs")
            
            if not df_logs.empty and '日期' in df_logs.columns and '時間' in df_logs.columns:
                try:
                    df_logs['完整時間'] = pd.to_datetime(df_logs['日期'].astype(str) + ' ' + df_logs['時間'].astype(str))
                    last_time = df_logs['完整時間'].max()
                    if pd.notnull(last_time):
                        diff = (tw_now - last_time).total_seconds()
                        if diff < 60:
                            note = "1分鐘內連續查詢"
                except:
                    pass

            new_log = pd.DataFrame([{
                "日期": current_date_str,
                "時間": current_time_str,
                "車頭車號": plate,
                "出土分區": "未指定",
                "載運方量(m³)": 12.0,
                "備註": note
            }])
            
            try:
                if df_logs.empty:
                    updated_logs = new_log
                else:
                    updated_logs = pd.concat([df_logs, new_log], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, worksheet="dispatch_logs", data=updated_logs)
                
                st.session_state['confirmed_plate'] = plate
                st.success("車次紀錄已自動送出，個別複製功能已解鎖！")
            except Exception as e:
                st.error("寫入資料庫失敗。")

        if st.session_state.get('confirmed_plate') == plate:
            st.write("#### 📋 點擊下方各區塊右上角圖示即可個別複製")
            for field in display_fields:
                val = str(target_data.get(field, "無資料"))
                st.caption(field)
                st.code(val, language="text")
        else:
            st.info("⚠️ 請先點擊上方「✅ 資訊無誤，確認車輛並記錄車次」按鈕，解鎖複製功能。")
