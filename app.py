import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="現場派車系統", layout="centered")

# 強制覆蓋外觀：全面常駐顯示並加入「複製」文字
st.markdown("""
    <style>
    /* 鎖定複製按鈕，強制常駐顯示並調整為長方形按鈕 */
    div[data-testid="stCodeBlock"] button,
    button[title="Copy to clipboard"],
    button[aria-label="Copy to clipboard"] {
        opacity: 1 !important;
        visibility: visible !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: #FF4B4B !important;
        border: 1px solid #FF4B4B !important;
        padding: 6px 12px !important;
        border-radius: 6px !important;
        width: auto !important;
        height: 32px !important;
        right: 8px !important;
        top: 8px !important;
        transform: scale(1) !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    /* 使用偽元素強制在按鈕內補上「複製」文字 */
    div[data-testid="stCodeBlock"] button::after,
    button[title="Copy to clipboard"]::after,
    button[aria-label="Copy to clipboard"]::after {
        content: "複製" !important;
        color: white !important;
        font-size: 14px !important;
        font-weight: bold !important;
        margin-left: 6px !important;
        white-space: nowrap !important;
    }
    
    /* 調整內建圖示為白色 */
    div[data-testid="stCodeBlock"] button svg,
    button[title="Copy to clipboard"] svg,
    button[aria-label="Copy to clipboard"] svg {
        fill: white !important;
        stroke: white !important;
        color: white !important;
        width: 16px !important;
        height: 16px !important;
    }
    
    /* 點擊與懸停視覺回饋 */
    div[data-testid="stCodeBlock"] button:hover {
        background-color: #D43F3F !important;
        border-color: #D43F3F !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📱 現場車籍查詢與派車")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1y3Qnlx9qFwV6S6pyFTsT4rlXP_Tb8qd9tNhRBTjBHao/edit"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"資料庫連線失敗：{e}")
    st.stop()

def load_drivers_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="drivers", ttl=1800)
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

def safe_append_row(worksheet_name, data_dict):
    try:
        worksheet = conn.client.open_by_url(SHEET_URL).worksheet(worksheet_name)
        headers = worksheet.row_values(1)
        row_data = [str(data_dict.get(h, "")) for h in headers]
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        try:
            df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
            df = df.dropna(how='all')
            new_row = pd.DataFrame([data_dict])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=updated_df)
            return True
        except Exception as e2:
            st.error(f"寫入失敗：{e2}")
            return False

df_drivers = load_drivers_data()

if 'confirmed_plate' not in st.session_state:
    st.session_state['confirmed_plate'] = ""
if 'last_submit_time' not in st.session_state:
    st.session_state['last_submit_time'] = None

all_fields = ["姓名", "身分證", "車頭車號", "車斗車號"]

if "order" in st.query_params:
    url_order = st.query_params["order"].split(",")
    current_order = url_order if set(url_order) == set(all_fields) else all_fields
else:
    current_order = all_fields

with st.expander("⚙️ 個人化顯示順序設定"):
    st.caption("💡 提示：設定完成後將網頁加入書籤即可保存順序。")
    new_order = st.multiselect("設定預覽與個別複製的顯示順序：", options=all_fields, default=current_order)
    if len(new_order) == 4 and new_order != current_order:
        st.query_params["order"] = ",".join(new_order)
        st.rerun()

display_fields = new_order if len(new_order) == 4 else all_fields

default_search = st.query_params.get("search", "")
search_term = st.text_input("輸入車號數字搜尋 (車頭或車斗)：", value=default_search)

def match_plate(plate_val, kw):
    if pd.isna(plate_val):
        return False
    plate_str = str(plate_val).upper().strip().replace(" ", "")
    kw = kw.replace(" ", "")
    if plate_str == kw:
        return True
    parts = plate_str.replace("-", " ").split()
    return kw in parts

if search_term:
    keyword = search_term.strip().upper()
    
    if st.query_params.get("search") != keyword:
        st.query_params["search"] = keyword
    
    if df_drivers.empty:
        search_results = pd.DataFrame()
    else:
        condition = df_drivers['車頭車號'].apply(match_plate, kw=keyword) | \
                    df_drivers['車斗車號'].apply(match_plate, kw=keyword)
        search_results = df_drivers[condition]
    
    if search_results.empty:
        st.warning("查無符合資料。您可以在此直接新增臨時車籍：")
        with st.form("add_driver_form"):
            st.write("### ➕ 新增現場車籍資料")
            new_head = st.text_input("車頭車號 (必填，例如 999-GU)", value=keyword)
            new_tail = st.text_input("車斗車號 (必填)")
            new_name = st.text_input("司機姓名 (必填)")
            new_id = st.text_input("身分證 (必填)")
            
            if st.form_submit_button("寫入資料庫並繼續派車", use_container_width=True):
                norm_head = new_head.strip().upper().replace(" ", "")
                norm_tail = new_tail.strip().upper().replace(" ", "")
                norm_name = new_name.strip()
                norm_id = new_id.strip().upper().replace(" ", "")
                
                if not norm_head or not norm_tail or not norm_name or not norm_id:
                    st.error("所有欄位皆為必填，請檢查是否有遺漏。")
                elif "-" not in norm_head or "-" not in norm_tail:
                    st.error("車牌格式錯誤：車頭與車斗車號中間必須包含「-」符號。")
                else:
                    existing_plates = []
                    if not df_drivers.empty and '車頭車號' in df_drivers.columns:
                        existing_plates = df_drivers['車頭車號'].astype(str).str.upper().str.replace(" ", "").tolist()
                    
                    if norm_head in existing_plates:
                        st.error(f"❌ 錯誤：車號 {norm_head} 已經存在於資料庫中。")
                    else:
                        new_driver_data = {
                            "姓名": norm_name,
                            "身分證": norm_id,
                            "車頭車號": norm_head,
                            "車斗車號": norm_tail
                        }
                        if safe_append_row("drivers", new_driver_data):
                            st.success("✅ 新增成功！")
                            st.rerun()
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
            
            if st.session_state['last_submit_time'] is not None:
                diff = (tw_now - st.session_state['last_submit_time']).total_seconds()
                if diff < 60:
                    note = "1分鐘內連續查詢"

            new_log_data = {
                "日期": current_date_str,
                "時間": current_time_str,
                "車頭車號": plate,
                "出土分區": "未指定",
                "載運方量(m³)": 12.0,
                "備註": note
            }
            
            if safe_append_row("dispatch_logs", new_log_data):
                st.session_state['confirmed_plate'] = plate
                st.session_state['last_submit_time'] = tw_now
                st.success("車次紀錄已安全送出，個別複製功能已解鎖！")

        if st.session_state.get('confirmed_plate') == plate:
            st.markdown("#### 📋 點擊下方區塊右側的紅色按鈕即可複製：")
            for field in display_fields:
                val = str(target_data.get(field, "無資料"))
                st.caption(field)
                st.code(val, language="text")
        else:
            st.info("⚠️ 請先點擊上方「✅ 資訊無誤，確認車輛並記錄車次」按鈕，解鎖複製功能。")
