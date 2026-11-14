# GK KeyFL

Trình chỉnh sửa **key frame** nhẹ viết bằng Python + **PySide6 (Qt6)**: nhiều panel kéo thả, timeline, đồ thị nội suy, theme, mẫu dự án và hệ thống plugin.

> Phiên bản hiện tại: `1.0.0` · © GrayKazu

## Tính năng

- **Editor nhiều panel dock** (Lớp, Thuộc tính, Dự án, Timeline, Đồ thị, Lệnh): kéo thả, tách cửa sổ, lưu/xoá bố cục (Workspace).
- **Lớp**: hình vuông, văn bản, hình ảnh, video, âm thanh; nhân đôi lớp, đặt lại vị trí/xoay/tỉ lệ.
- **Key frame**: thêm/xoá key, nhảy key trước/sau, tự động key, lặp (cyclic / ping-pong).
- **Kiểu nội suy**: tuyến tính, hold, ease, back, bounce, elastic, cyclic, noise, bezier tuỳ chỉnh; plugin có thể thêm kiểu mới.
- **Tách nền** (matte) và **Vector Editor** (cắt vùng ảnh thành lớp mới).
- **Video / âm thanh** qua ffmpeg.
- **Trang chủ**: dự án gần đây kèm ảnh xem trước, tìm kiếm, sắp xếp, đổi tên / xoá / hiện trong thư mục, bắt đầu từ mẫu.
- **Mẫu dự án**: Trống, Tiêu đề Pop-in, Lower third, Logo reveal, Trình chiếu 3 cảnh.
- **Theme**: nhiều theme có sẵn, plugin có thể thêm theme mới.
- **Tài khoản** (đăng nhập / chế độ khách), **Kiểm tra cập nhật**, **Kiểm tra hệ thống**.
- **Plugin** bằng Python (xem bên dưới).

## Yêu cầu

- Python 3.8 trở lên
- PySide6
- numpy (dùng cho tách nền / cắt vector)
- ffmpeg trong `PATH` hoặc đóng gói kèm (cho video / âm thanh / xuất file)
- psutil *(tuỳ chọn)*: hiện CPU/RAM ở thanh trạng thái

```bash
pip install PySide6 numpy psutil
```

Trên Linux (Wayland) cảnh báo `This plugin supports grabbing the mouse only for popup windows` là bình thường, không phải lỗi.

## Chạy

```bash
python3 gk_keyfl_ui.py
```

Luồng màn hình: **Đăng nhập → Trang chủ → Editor**.

Phím tắt ở trang chủ: `Ctrl+N` dự án mới · `Ctrl+O` mở dự án · `Ctrl+F` tìm dự án.

## Cấu trúc mã nguồn

| File | Vai trò |
| --- | --- |
| `gk_keyfl_ui.py` | Điểm vào ứng dụng, chuyển màn hình |
| `gk_pages.py` | Màn hình Đăng nhập + Trang chủ |
| `gk_editor.py` | Trang Editor, menu, lệnh, sự kiện |
| `gk_panels.py`, `gk_timeline.py` | Các panel và timeline |
| `gk_model.py` | Hằng số, nội suy, mô hình `Layer` / `Key` |
| `gk_theme.py` | Theme, phông chữ |
| `gk_plugins.py` | Hệ thống plugin |
| `gk_recent.py` | Danh sách dự án gần đây + thumbnail |
| `gk_templates.py` | Mẫu dự án |
| `gk_dialogs.py`, `gk_diag.py`, `gk_update.py` | Tài khoản, kiểm tra hệ thống, cập nhật |
| `gk_matte_ui.py`, `gk_matting.py` | Tách nền |
| `gk_vector.py`, `gk_vector_ui.py` | Vector Editor |
| `gk_media.py`, `gk_ffmpeg.py` | Video / âm thanh |
| `gk_settings.py`, `gk_prefs.py`, `gk_prefs_ui.py` | Cài đặt và tuỳ chọn |
| `extras_pack.py` | Plugin mẫu |

Dự án được lưu dạng JSON với đuôi `.gkproj`.

## Lệnh trong panel Lệnh

```
help | play | pause | seek <giây> | add <shape|text|image|video|audio> | del
ratio <16:9|9:16|1:1|4:5> | theme <tên> | save | load
```

Plugin có thể thêm lệnh riêng; gõ `help` để xem.

## Plugin

Plugin là một tệp `.py` (hoặc `.gkplugin`) đặt trong thư mục `Plugin` của Assets. Mở nhanh bằng menu **Plugin → Mở thư mục Plugin**, rồi **Plugin → Tải lại plugin**.

Lần đầu mỗi plugin phải được người dùng cho phép (nhớ theo mã băm SHA-256; sửa tệp thì hỏi lại). Plugin chạy với toàn quyền như chính ứng dụng, chỉ cho phép plugin từ nguồn bạn tin.

Tệp cần có hàm `register(api)` và (tuỳ chọn) biến `PLUGIN`:

```python
PLUGIN = {"name": "Demo", "version": "1.0", "author": "Bạn", "desc": "Mô tả ngắn"}

def register(api):
    api.add_command("hello", lambda args: api.log("Xin chào " + " ".join(args)))
    api.add_tool_action("Đếm số lớp", lambda: api.log(str(len(api.layers()))))
    api.on("layer_added", lambda L: api.log("Đã thêm lớp " + L.name))
```

**API chính**: `add_action`, `add_command`, `add_panel`, `add_tool_action`, `add_shortcut`, `add_ease`, `add_layer_kind`, `add_theme`, `on`, `layers`, `selected`, `add_layer`, `key`, `value`, `seek`, `play`, `pause`, `refresh`, `get` / `put` (lưu dữ liệu riêng của plugin), `log`.

**Sự kiện**: `seek`, `play`, `pause`, `layer_added`, `layer_removed`, `layer_selected`, `keys_changed`, `project_new`, `project_loaded`, `project_saved`, `theme_changed`.

Xem `extras_pack.py` để biết ví dụ đầy đủ (kiểu nội suy mới, lớp Hình tròn / Thanh tiến trình, theme Dracula, phím tắt).

## Kiểm tra cập nhật

Ứng dụng gọi `<máy chủ đăng nhập>/api/keyfl/version` (đổi bằng biến môi trường `GK_UPDATE_URL`). Máy chủ trả về JSON:

```json
{ "version": "1.1.0", "url": "https://...", "notes": "Ghi chú bản mới" }
```

Đoạn mã tuyến này cho Cloudflare Worker nằm trong `gkkeyfl_version_route.js`.

## Ghi chú cho người phát triển

Dự án từng có hai nhánh: bản **Qt5 / PyQt5** (nhiều tính năng) và bản **Qt6 / PySide6** (giao diện mới). Nhánh hiện tại là Qt6, đã gộp tính năng từ Qt5. Khi chép code cũ sang, chú ý các khác biệt:

- `pyqtSignal` → `Signal`, `exec_()` → `exec()`
- `QShortcut`, `QAction` nằm trong `QtGui`
- `QWheelEvent.pos()` → `position()`; `delta()` → `angleDelta().y()`
- `memoryview.setsize()` không còn, bỏ đi
