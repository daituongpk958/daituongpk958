import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
import time
from database import Database

# --- PAGE CONFIG & CUSTOM CSS ---
st.set_page_config(
    page_title="Hệ Thống Quản Lý Đất Đai",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Bảng màu chuyên nghiệp */
    :root {
        --primary-bg: #f8fafc;
        --card-bg: #ffffff;
        --text-color: #1e293b;
        --border-color: #e2e8f0;
        --accent-blue: #2563eb;
        --accent-green: #16a34a;
        --accent-header: #f1f5f9;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* Giao diện chung */
    .stApp { background-color: var(--primary-bg); color: var(--text-color); }
    
    /* Customize Tabs */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 10px; 
        background-color: var(--card-bg); 
        padding: 10px 15px 0 15px;
        border-radius: 10px 10px 0 0;
        border-bottom: 2px solid var(--border-color);
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; font-weight: 600; font-size: 16px;
        color: #475569; border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] { color: var(--accent-blue); border-bottom-color: var(--accent-blue); }
    
    /* Cards and Containers */
    div.stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color); }
    
    /* Section Headers */
    .section-header {
        background-color: var(--accent-header);
        padding: 12px 20px;
        border-left: 5px solid var(--accent-blue);
        border-radius: 0 8px 8px 0;
        margin: 25px 0 15px 0;
        font-weight: 700;
        color: var(--text-color);
        font-size: 1.1em;
        box-shadow: var(--shadow-sm);
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.2s;
        border: 1px solid var(--border-color);
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: var(--shadow-md);
        border-color: var(--accent-blue); color: var(--accent-blue);
    }
    
    /* Specific Button Styles */
    .btn-save>div>button { background-color: var(--accent-blue); color: white; border: none; }
    .btn-save>div>button:hover { background-color: #1d4ed8; color: white; }
    
    /* Metrics */
    div[data-testid="stMetricValue"] { color: var(--accent-blue); font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- UTILS ---
def validate_sovaoso(text):
    if not text: return True
    return bool(re.match(r"^(CS|CH|H|CT|CN)\d+$", text, re.IGNORECASE))

def validate_date(text):
    if not text: return True
    for fmt in ["%d/%m/%Y", "%m/%Y", "%Y"]:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False

def validate_mavach(text) :
    if not text: return True
    return bool(re.match(r"^\d{13}$", text))

# --- SESSION STATE INITIALIZATION ---
init_states = {
    'db': None, 'connected': False, 'editing_data': None, 'current_ids': None,
    'user_info': {'user': '', 'commune': ''}, 'search_results': pd.DataFrame(),
    'stats': None
}
for key, val in init_states.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- SIDEBAR: CONNECTION & CONFIG ---
with st.sidebar:
    st.image("https://img.icons8.com/color/200/000000/map-marker--v1.png", width=120)
    st.markdown("## ⚙️ Cấu Hình Hệ Thống")
    
    with st.expander("🔌 Kết nối SQL & Đăng nhập Hệ thống", expanded=not st.session_state.connected):
        st.markdown("**1. Cấu hình Cơ sở dữ liệu**")
        sc1, sc2 = st.columns([2, 1])
        server_ip = sc1.text_input("Server IP", value="192.168.1.112")
        server_port = sc2.text_input("Port", value="1433")
        database = st.text_input("Database", value="master")
        use_sql_auth = st.checkbox("Sử dụng SQL Auth", value=True)
        
        if use_sql_auth:
            c1, c2 = st.columns(2)
            db_user = c1.text_input("SQL User", value="kimdongtd")
            db_pass = c2.text_input("SQL Password", value="23091993@@", type="password")
        else:
            db_user, db_pass = None, None
            st.caption("ℹ️ Windows Authentication")
            
        st.divider()
        st.markdown("**2. Tài khoản Đăng nhập Hệ thống**")
        app_user = st.text_input("Tên đăng nhập (Username)", placeholder="Nhập tên đăng nhập...")
        app_pass = st.text_input("Mật khẩu (Password)", type="password", placeholder="Nhập mật khẩu...")
        
        if st.button("🔄 KẾT NỐI & ĐĂNG NHẬP", use_container_width=True):
            if not app_user or not app_pass:
                st.error("Vui lòng nhập Tên đăng nhập và Mật khẩu Hệ thống!")
            else:
                # Format IP,PORT for SQL Server driver compatibility
                server_str = f"{server_ip},{server_port}"
                db = Database(server_str, database, db_user, db_pass)
                success, msg = db.connect()
                
                if success:
                    # Authenticate App User
                    auth_success, auth_msg, user_info = db.authenticate_user(app_user, app_pass)
                    if auth_success:
                        st.session_state.db = db
                        st.session_state.connected = True
                        st.session_state.user_info = {
                            'user': user_info.get('fullname', app_user),
                            'username': app_user,
                            # Save initial commune from DB, user can override later
                            'commune': user_info.get('commune', ''),
                            'can_input': user_info.get('can_input', 1),
                            'can_edit': user_info.get('can_edit', 1)
                        }
                        st.rerun()
                    else:
                        st.error(f"Xác thực thất bại: {auth_msg}")
                        db.close()
                else:
                    st.error(f"Lỗi SQL: {msg}")
    
    if st.session_state.connected:
        st.success("🟢 Trạng thái: Đã kết nối")
        st.divider()
        st.markdown("### 👤 Phiên Làm Việc")
        
        # Lấy danh sách xã từ DB để gợi ý
        communes = st.session_state.db.get_communes()
        
        st.session_state.user_info['user'] = st.text_input("Người thực hiện:", value=st.session_state.user_info.get('user', ''))
        
        if communes:
            current_commune = st.session_state.user_info['commune']
            idx = communes.index(current_commune) if current_commune in communes else 0
            st.session_state.user_info['commune'] = st.selectbox("Xã/Phường:", communes, index=idx)
        else:
            st.session_state.user_info['commune'] = st.text_input("Xã/Phường:", value=st.session_state.user_info.get('commune', ''))
            
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.db.close()
            for key in ['db', 'connected', 'editing_data', 'current_ids', 'stats']:
                st.session_state[key] = init_states[key]
            st.rerun()

# --- MAIN APPLICATION ---
if not st.session_state.connected:
    st.title("🏛️ Hệ Thống Quản Lý Đất Đai")
    st.info("👋 Xin chào! Vui lòng cấu hình kết nối SQL Server ở thanh bên trái (Sidebar) để bắt đầu sử dụng hệ thống.")
    st.stop()

st.title("🏛️ Hệ Thống Quản Lý CSDL Đất Đai")

tab1, tab2, tab3 = st.tabs(["📝 CHỈNH SỬA HỒ SƠ", "💰 NVTC & HCQ", "📊 BÁO CÁO THỐNG KÊ"])

# ==============================================================================
# TAB 1: EDITING INTERFACE
# ==============================================================================
with tab1:
    st.markdown("### 🔍 1. Tra cứu Hồ sơ")
    
    with st.container():
        sc1, sc2, sc3 = st.columns([2, 5, 2])
        with sc1:
            search_type = st.selectbox("Tìm kiếm theo:", ["Tất cả", "Mã GCN", "Số tờ / Số thửa", "Tên chủ"])
        with sc2:
            search_term = st.text_input("Nhập từ khóa tìm kiếm (Mã GCN, Số tờ, Tên...):", placeholder="Ví dụ: CS1234, 15, Nguyễn Văn A...")
        with sc3:
            st.write(" ")
            st.write(" ")
            if st.button("🔎 TÌM KIẾM", use_container_width=True):
                with st.spinner("Đang truy vấn..."):
                    st.session_state.search_results = st.session_state.db.search_gcn(search_term)
    
    if not st.session_state.search_results.empty:
        st.markdown(f"**Kết quả: Tìm thấy `{len(st.session_state.search_results)}` hồ sơ.**")
        st.dataframe(
            st.session_state.search_results, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "MAGCN": st.column_config.TextColumn("Mã GCN", width="medium"),
                "SOHIEUTO": st.column_config.TextColumn("Tờ"),
                "SOHIEUTHUA": st.column_config.TextColumn("Thửa"),
                "TENCHU": st.column_config.TextColumn("Tên Chủ", width="large"),
                "DIACHITHUADAT": st.column_config.TextColumn("Địa chỉ thửa", width="large"),
                "DIENTICH": st.column_config.NumberColumn("Diện tích (m2)", format="%.1f")
            }
        )
        
        load_col1, load_col2 = st.columns([3, 1])
        with load_col1:
            selected_magcn = st.selectbox("📌 Chọn mã hồ sơ (MAGCN) để tải lên Form:", st.session_state.search_results['MAGCN'].unique())
        with load_col2:
            st.write(" ")
            st.write(" ")
            if st.button("📂 TẢI DỮ LIỆU", use_container_width=True, type="primary"):
                # Lấy mathuadat tương ứng
                mathuadat = st.session_state.search_results[st.session_state.search_results['MAGCN'] == selected_magcn]['MATHUADAT'].iloc[0]
                with st.spinner("Đang tải chi tiết hồ sơ..."):
                    st.session_state.editing_data = st.session_state.db.load_gcn_data(selected_magcn, mathuadat)
                    st.session_state.current_ids = {'MAGCN': selected_magcn, 'MATHUADAT': mathuadat}
                st.toast(f"Đã tải xong hồ sơ {selected_magcn}", icon="✅")
                st.rerun()

    st.divider()
    
    # --- FORM NHẬP LIỆU ---
    if st.session_state.editing_data:
        data = st.session_state.editing_data
        st.markdown(f"### 📝 2. Chi tiết hồ sơ: `{st.session_state.current_ids['MAGCN']}`")
        
        # --- PDF BROWSER (Tuỳ chọn hiển thị file quét) ---
        link_path = data.get('HOSOQUET_LINK', '')
        if link_path:
            with st.expander(f"📂 Tệp hồ sơ đính kèm (Đường dẫn: {link_path})", expanded=False):
                if os.path.exists(link_path):
                    if os.path.isdir(link_path):
                        pdfs = [f for f in os.listdir(link_path) if f.lower().endswith('.pdf')]
                        if pdfs:
                            pdf_sel = st.selectbox("Chọn file PDF:", pdfs)
                            if st.button("📄 Mở File PDF này"):
                                os.startfile(os.path.join(link_path, pdf_sel))
                        else:
                            st.warning("Thư mục trống hoặc không có file PDF.")
                    else:
                        if st.button("📄 Mở File"):
                            os.startfile(link_path)
                else:
                    st.error("Đường dẫn file quét không tồn tại trên máy trạm này.")

        # =========================================
        #             START OF MAIN FORM
        # =========================================
        with st.form("main_edit_form", border=False):
            # --- I. THỬA ĐẤT ---
            st.markdown('<div class="section-header">I. THÔNG TIN THỬA ĐẤT</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            data['THUDAT']['SOHIEUTO'] = c1.text_input("1. Số tờ:", value=data['THUDAT'].get('SOHIEUTO', ''))
            data['THUDAT']['SOHIEUTHUA'] = c2.text_input("2. Số thửa:", value=data['THUDAT'].get('SOHIEUTHUA', ''))
            data['THUDAT']['DIENTICH'] = c3.number_input("3. Diện tích (m²):", value=float(data['THUDAT'].get('DIENTICH') or 0.0), format="%.2f", step=1.0)
            data['THUDAT']['DIENTICHPHAPLY'] = c4.number_input("4. DT Pháp lý (m²):", value=float(data['THUDAT'].get('DIENTICHPHAPLY') or 0.0), format="%.2f", step=1.0)
            
            c5, c6 = st.columns([2, 1])
            data['THUDAT']['DIACHITHUADAT'] = c5.text_input("5. Địa chỉ thửa đất:", value=data['THUDAT'].get('DIACHITHUADAT', ''))
            data['THUDAT']['NGUONGOCHINHTHANH'] = c6.text_input("6. Nguồn gốc hình thành:", value=data['THUDAT'].get('NGUONGOCHINHTHANH', ''))
            
            # --- II. LOẠI ĐẤT ---
            st.markdown('<div class="section-header">II. THÔNG TIN LOẠI ĐẤT ĐĂNG KÝ</div>', unsafe_allow_html=True)
            df_dk = pd.DataFrame(data['DANGKY'])
            cols_dk = ["LOAIDAT", "DIENTICH", "NGUONGOC", "THOIHANSUDUNG", "SUDUNGCHUNG"]
            
            if df_dk.empty:
                df_dk = pd.DataFrame(columns=cols_dk)
            else:
                for c in cols_dk:
                    if c not in df_dk.columns: df_dk[c] = ""
                df_dk = df_dk[cols_dk]
            
            st.caption("Chỉnh sửa trực tiếp trên bảng. Thêm hàng mới phía dưới cùng.")
            edited_dk = st.data_editor(
                df_dk, 
                num_rows="dynamic", 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "LOAIDAT": st.column_config.TextColumn("Mục đích SD (Mã)", required=True),
                    "DIENTICH": st.column_config.NumberColumn("Diện tích (m²)", format="%.2f"),
                    "NGUONGOC": st.column_config.TextColumn("Nguồn gốc sử dụng"),
                    "THOIHANSUDUNG": st.column_config.TextColumn("Thời hạn SD"),
                    "SUDUNGCHUNG": st.column_config.SelectboxColumn("SD Chung (0=Riêng)", options=[0, 1])
                }
            )

            # --- III. CHỦ SỬ DỤNG ---
            st.markdown('<div class="section-header">III. THÔNG TIN CHỦ SỬ DỤNG</div>', unsafe_allow_html=True)
            owners = data.get('CHUSUDUNG', [])
            if not owners: owners.append({}) # Đảm bảo có ít nhất 1 chủ
            
            # Chỉ hiển thị tối đa 2 chủ trên giao diện web cho gọn (có thể mở rộng)
            for idx in range(2): 
                if idx >= len(owners):
                    st.markdown(f"**👤 Chủ sử dụng {idx+1} (Chưa nhập)**")
                    if not st.checkbox(f"Kích hoạt nhập thông tin Chủ {idx+1}", key=f"add_owner_{idx}"): 
                        continue
                    owners.append({})
                else:
                    st.markdown(f"**👤 Chủ sử dụng {idx+1}**")
                
                # Layout thông tin chủ
                oc1, oc2, oc3 = st.columns([2, 1, 1])
                owners[idx]['TENCHU'] = oc1.text_input(f"Họ và tên", value=owners[idx].get('TENCHU', ''), key=f"ten_{idx}")
                owners[idx]['NAMSINH'] = oc2.number_input(f"Năm sinh", value=int(owners[idx].get('NAMSINH') or 0), step=1, key=f"ns_{idx}")
                
                gt_val = owners[idx].get('GIOITINH', '')
                gt_idx = ["", "Nam", "Nữ"].index(gt_val) if gt_val in ["", "Nam", "Nữ"] else 0
                owners[idx]['GIOITINH'] = oc3.selectbox(f"Giới tính", ["", "Nam", "Nữ"], index=gt_idx, key=f"gt_{idx}")
                
                oc4, oc5, oc6 = st.columns([1, 1, 2])
                hob_val = owners[idx].get('HOONGBA', '')
                hob_idx = ["", "Ông", "Bà", "Hộ ông", "Hộ bà", "Tổ chức"].index(hob_val) if hob_val in ["", "Ông", "Bà", "Hộ ông", "Hộ bà", "Tổ chức"] else 0
                owners[idx]['HOONGBA'] = oc4.selectbox(f"Danh xưng", ["", "Ông", "Bà", "Hộ ông", "Hộ bà", "Tổ chức"], index=hob_idx, key=f"hob_{idx}")
                
                lgt_val = owners[idx].get('LOAIGIAYTO', '')
                lgt_idx = ["", "CCCD", "CMND", "Hộ chiếu", "Mã ĐT", "Khác"].index(lgt_val) if lgt_val in ["", "CCCD", "CMND", "Hộ chiếu", "Mã ĐT", "Khác"] else 0
                owners[idx]['LOAIGIAYTO'] = oc5.selectbox(f"Loại giấy tờ", ["", "CCCD", "CMND", "Hộ chiếu", "Mã ĐT", "Khác"], index=lgt_idx, key=f"lgt_{idx}")
                
                owners[idx]['SOGIAYTO'] = oc6.text_input(f"Số giấy tờ", value=owners[idx].get('SOGIAYTO', ''), key=f"sgt_{idx}")
                
                oc7, oc8 = st.columns([1, 2])
                owners[idx]['NGAYCAP'] = oc7.text_input(f"Ngày cấp (dd/mm/yyyy)", value=owners[idx].get('NGAYCAP', ''), key=f"nc_{idx}")
                owners[idx]['NOICAP'] = oc8.text_input(f"Nơi cấp", value=owners[idx].get('NOICAP', ''), key=f"loc_{idx}")
                
                owners[idx]['DIACHI'] = st.text_input(f"Địa chỉ thường trú", value=owners[idx].get('DIACHI', ''), key=f"dc_{idx}")
                st.write("") # space

            # --- IV. GCN ---
            st.markdown('<div class="section-header">IV. THÔNG TIN GIẤY CHỨNG NHẬN</div>', unsafe_allow_html=True)
            gcn = data['GIAYCHUNGNHAN']
            
            g1, g2, g3 = st.columns(3)
            gcn['SOPHATHANH'] = g1.text_input("1. Số phát hành (Số seri):", value=gcn.get('SOPHATHANH', ''))
            
            svs = g2.text_input("2. Số vào sổ:", value=gcn.get('SOVAOSO', ''), help="Các tiền tố hợp lệ: CS, CH, H, CT, CN")
            if not validate_sovaoso(svs): st.warning("⚠️ Cảnh báo: Định dạng Số vào sổ có thể chưa chuẩn.")
            gcn['SOVAOSO'] = svs
            
            ngay_gcn = g3.text_input("3. Ngày cấp GCN:", value=gcn.get('NGAYCAPGCN', ''), help="Định dạng: dd/mm/yyyy")
            if not validate_date(ngay_gcn): st.warning("⚠️ Cảnh báo: Sai định dạng ngày.")
            gcn['NGAYCAPGCN'] = ngay_gcn

            g4, g5, g6 = st.columns(3)
            mv = g4.text_input("4. Mã vạch:", value=gcn.get('MAVACH', ''))
            if not validate_mavach(mv): st.warning("⚠️ Cảnh báo: Mã vạch GCN thường chứa đúng 13 chữ số.")
            gcn['MAVACH'] = mv
            
            hsg_val = gcn.get('SOHOSOGOC', '')
            if mv and len(mv) >= 6 and not hsg_val: 
                hsg_val = mv[-6:] # Auto-fill rule from PyQt app
            gcn['SOHOSOGOC'] = g5.text_input("5. Số hồ sơ gốc:", value=hsg_val)
            gcn['TENNGUOIKY'] = g6.text_input("6. Người ký GCN:", value=gcn.get('TENNGUOIKY', ''))
            
            gcn['CANCUPHAPLY'] = st.text_input("7. Căn cứ pháp lý:", value=gcn.get('CANCUPHAPLY', ''))
            gcn['GHICHU'] = st.text_area("8. Ghi chú chung:", value=gcn.get('GHICHU', ''), height=80)

            st.write(" ")
            
            # --- ACTION BAR ---
            st.markdown('<div class="btn-save">', unsafe_allow_html=True)
            if st.form_submit_button("LƯU KIỂM TRA & CẬP NHẬT DỮ LIỆU", use_container_width=True):
                # Basic validation
                if not owners[0].get('TENCHU'):
                    st.error("❌ Lỗi: Tên chủ sử dụng đầu tiên không được để trống!")
                elif not st.session_state.user_info.get('user'):
                    st.error("❌ Lỗi: Vui lòng cấu hình Người thực hiện ở Sidebar!")
                else:
                    # Gom dữ liệu để lưu
                    save_pkg = {
                        'THUDAT': data['THUDAT'],
                        'DANGKY': edited_dk.to_dict('records'),
                        'CHUSUDUNG': owners,
                        'GIAYCHUNGNHAN': gcn,
                        'USER_INFO': st.session_state.user_info,
                        'HOSOQUET_LINK': link_path
                    }
                    with st.spinner("Đang lưu dữ liệu vào CSDL..."):
                        success, msg = st.session_state.db.save_data(save_pkg, st.session_state.current_ids)
                        
                    if success:
                        st.success(f"🎉 {msg}")
                        st.balloons()
                    else:
                        st.error(f"❌ Lỗi khi lưu vào SQL Server: {msg}")
            st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 2: NVTC & HCQ
# ==============================================================================
with tab2:
    if not st.session_state.editing_data:
        st.warning("⚠️ Yêu cầu: Vui lòng tra cứu và chọn một hồ sơ ở Tab CHỈNH SỬA HỒ SƠ trước để quản lý Phụ lục.")
    else:
        mth = st.session_state.current_ids['MATHUADAT']
        st.info(f"📍 Đang thao tác trên Phụ lục của Mã Thửa Đất: **`{mth}`**")
        
        nv_col, hc_col = st.columns(2)
        
        # --- NGHĨA VỤ TÀI CHÍNH ---
        with nv_col:
            st.markdown('<div class="section-header" style="margin-top:0;">💰 NGHĨA VỤ TÀI CHÍNH</div>', unsafe_allow_html=True)
            nvtc_data = st.session_state.db.load_nvtc(mth)
            df_nvtc = pd.DataFrame(nvtc_data)
            cols_nvtc = ["LOAINGHIAVUTAICHINH", "TIENNGHIAVUTAICHINH", "SOTIENDANOP", "GIAYNOPTIEN", "NOIRAGIAYNOPTIEN", "ISKHOA"]
            
            for c in cols_nvtc:
                if c not in df_nvtc.columns: df_nvtc[c] = ""
            if len(df_nvtc) == 0: df_nvtc = pd.DataFrame(columns=cols_nvtc)
            
            edited_nvtc = st.data_editor(
                df_nvtc[cols_nvtc], 
                num_rows="dynamic", key="nvtc_editor", 
                use_container_width=True, hide_index=True,
                column_config={
                    "LOAINGHIAVUTAICHINH": st.column_config.SelectboxColumn("Loại NVTC", options=["Tiền sử dụng đất", "Thuế TNCN", "Lệ phí trước bạ", "Nghĩa vụ khác"]),
                    "TIENNGHIAVUTAICHINH": st.column_config.NumberColumn("Tiền NVTC (VNĐ)", format="%d"),
                    "SOTIENDANOP": st.column_config.NumberColumn("Đã nộp (VNĐ)", format="%d"),
                    "GIAYNOPTIEN": "Giấy nộp tiền",
                    "NOIRAGIAYNOPTIEN": "Nơi ra giấy",
                    "ISKHOA": st.column_config.CheckboxColumn("Khóa")
                }
            )
            if st.button("💾 CẬP NHẬT NVTC", use_container_width=True):
                with st.spinner("Đang lưu NVTC..."):
                    succ, msg = st.session_state.db.save_nvtc(mth, edited_nvtc.to_dict('records'))
                if succ: 
                    st.toast("Cập nhật NVTC thành công!", icon="✅")
                else: 
                    st.error(f"Lỗi: {msg}")

        # --- HẠN CHẾ QUYỀN ---
        with hc_col:
            st.markdown('<div class="section-header" style="margin-top:0;">⚖️ HẠN CHẾ QUYỀN</div>', unsafe_allow_html=True)
            hcq_data = st.session_state.db.load_hcq(mth)
            df_hcq = pd.DataFrame(hcq_data)
            cols_hcq = ["LOAIHANCHE", "DIENTICHHANCHE", "NOIDUNGHANCHE", "ISKHOA"]
            
            for c in cols_hcq:
                if c not in df_hcq.columns: df_hcq[c] = ""
            if len(df_hcq) == 0: df_hcq = pd.DataFrame(columns=cols_hcq)

            edited_hcq = st.data_editor(
                df_hcq[cols_hcq], 
                num_rows="dynamic", key="hcq_editor", 
                use_container_width=True, hide_index=True,
                column_config={
                    "LOAIHANCHE": st.column_config.TextColumn("Loại hạn chế"),
                    "DIENTICHHANCHE": st.column_config.NumberColumn("Diện tích (m²)", format="%.2f"),
                    "NOIDUNGHANCHE": st.column_config.TextColumn("Nội dung"),
                    "ISKHOA": st.column_config.CheckboxColumn("Khóa")
                }
            )
            if st.button("💾 CẬP NHẬT HẠN CHẾ QUYỀN", use_container_width=True):
                with st.spinner("Đang lưu HCQ..."):
                    succ, msg = st.session_state.db.save_hcq(mth, edited_hcq.to_dict('records'))
                if succ: 
                    st.toast("Cập nhật HCQ thành công!", icon="✅")
                else: 
                    st.error(f"Lỗi: {msg}")


# ==============================================================================
# TAB 3: DASHBOARD STATS
# ==============================================================================
with tab3:
    st.markdown("### 📊 Dashboard Báo Cáo & Thống Kê")
    st.caption("Tổng hợp dữ liệu từ hệ thống. Bấm cập nhật để lấy dữ liệu mới nhất.")
    
    if st.button("🔄 TẢI MỚI DỮ LIỆU THỐNG KÊ", type="primary"):
        with st.spinner("Đang tổng hợp dữ liệu từ SQL Server..."):
            st.session_state.stats = st.session_state.db.get_stats()
            st.toast("Đã cập nhật số liệu!", icon="📊")

    if 'stats' in st.session_state and st.session_state.stats:
        stats = st.session_state.stats
        
        # High level metrics
        c1, c2, c3 = st.columns(3)
        c1.metric(label="📄 Tổng số Giấy chứng nhận (GCN)", value=f"{stats['total_gcn']:,}")
        c2.metric(label="🌍 Tổng diện tích quản lý (m²)", value=f"{stats['total_area']:,.2f}")
        c3.metric(label="🏘️ Số lượng xã/phường tham gia", value=len(stats['by_commune']))
        
        st.divider()
        
        # Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("**1. Số lượng hồ sơ theo Xã/Phường**")
            if not stats['by_commune'].empty:
                df_com = stats['by_commune'].set_index('TENXATHUCHIEN')
                st.bar_chart(df_com, color="#2563eb", height=350)
            else:
                st.info("Chưa có dữ liệu theo xã.")
                
        with chart_col2:
            st.markdown("**2. Hiệu suất nhập liệu theo Người dùng**")
            if not stats['by_user'].empty:
                df_usr = stats['by_user'].set_index('TENNGUOITHUCHIEN')
                st.bar_chart(df_usr, color="#16a34a", height=350)
            else:
                st.info("Chưa có dữ liệu người dùng.")
    else:
        st.info("👆 Bấm vào nút 'TẢI MỚI DỮ LIỆU THỐNG KÊ' phía trên để xem báo cáo.")
