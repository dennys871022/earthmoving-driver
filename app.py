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

        plate = target_data['車頭車號']

        st.markdown("### 🔎 查詢結果確認")
        st.markdown(f"**姓名：** {target_data.get('姓名', '無資料')}")
        st.markdown(f"**車頭車號：** {target_data.get('車頭車號', '無資料')}")
        st.markdown(f"**車斗車號：** {target_data.get('車斗車號', '無資料')}")
        st.markdown(f"**身分證：** {target_data.get('身分證', '無資料')}")
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
                st.success("車次紀錄已自動送出，一鍵複製功能已解鎖！")
            except Exception as e:
                st.error("寫入資料庫失敗。")

        if st.session_state.get('confirmed_plate') == plate:
            st.write("#### 📋 點擊下方區塊右上角圖示即可一鍵複製全部資料")
            
            copy_text = f"姓名：{target_data.get('姓名', '無資料')}\n"
            copy_text += f"身分證：{target_data.get('身分證', '無資料')}\n"
            copy_text += f"車頭車號：{target_data.get('車頭車號', '無資料')}\n"
            copy_text += f"車斗車號：{target_data.get('車斗車號', '無資料')}"
            
            st.code(copy_text, language="text")
        else:
            st.info("⚠️ 請先點擊上方「✅ 資訊無誤，確認車輛並記錄車次」按鈕，解鎖複製功能。")
