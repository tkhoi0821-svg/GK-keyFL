"""Mau du an co san. Moi mau dung API cua editor (new_layer, Layer.set...) de dung lop + key frame.
Don vi: pos0/pos1 trai-phai/tren-duoi trong khoang +-100 (200 = ca khung); scl la phan tram; thoi gian tinh bang giay."""

TEMPLATES = [
    ("blank", "Trống", "Canvas trống, một hình vuông"),
    ("title", "Tiêu đề Pop-in", "Chữ nảy ra kèm thanh nhấn"),
    ("lower", "Lower third", "Thanh tên trượt vào góc dưới"),
    ("logo", "Logo reveal", "Hình xoay và bung ra"),
    ("slides", "Trình chiếu 3 cảnh", "Ba cảnh nối tiếp, mờ dần vào"),
]


def _keys(L, ch, pairs, ease=None):
    """Dat cac key (t, v) cho kenh ch; ease la kieu noi suy cua doan dau tien."""
    for t, v in pairs:
        L.set(ch, t, v, True)
    if ease:
        for k in L.kf[ch]:
            if abs(k.t - round(pairs[0][0], 2)) < 0.05:
                k.e = ease


def _clear(ed):
    for L in list(ed.stage.layers):
        if L.kind != "bg":
            ed.select_layer(L)
            ed.delete_layer()


def apply(ed, key):
    if key == "blank":
        return
    _clear(ed)
    if key == "title":
        bar = ed.new_layer("Hình vuông", start=0, dur=6)
        bar.name, bar.color = "Thanh nhấn", "#7a2bff"
        bar.base.update(pos1=-6.0, scl0=250.0, scl1=7.0)
        _keys(bar, "scl0", [(1.0, 0.0), (1.7, 250.0)], "ease_out")
        t = ed.new_layer("Văn bản", start=0, dur=6)
        t.name, t.text = "Tiêu đề", "Tiêu đề của bạn"
        t.base["pos1"] = 8.0
        for ch in ("scl0", "scl1"):
            _keys(t, ch, [(0.4, 0.0), (1.1, 100.0)], "back")
        _keys(t, "op", [(0.4, 0.0), (0.8, 100.0)])
    elif key == "lower":
        bar = ed.new_layer("Hình vuông", start=0, dur=6)
        bar.name, bar.color = "Thanh tên", "#7a2bff"
        bar.base.update(pos0=-40.0, pos1=-64.0, scl0=420.0, scl1=26.0)
        _keys(bar, "pos0", [(0.2, -160.0), (0.9, -40.0)], "ease_out")
        t = ed.new_layer("Văn bản", start=0, dur=6)
        t.name, t.text = "Tên · Chức danh", "Tên · Chức danh"
        t.base.update(pos0=-40.0, pos1=-64.0)
        _keys(t, "op", [(0.7, 0.0), (1.1, 100.0)])
    elif key == "logo":
        s = ed.new_layer("Hình vuông", start=0, dur=6)
        s.name, s.color = "Logo", "#7a2bff"
        _keys(s, "scl0", [(0.0, 0.0), (1.2, 100.0)], "elastic")
        _keys(s, "scl1", [(0.0, 0.0), (1.2, 100.0)], "elastic")
        _keys(s, "rot2", [(0.0, -180.0), (1.2, 0.0)], "ease_out")
        t = ed.new_layer("Văn bản", start=0, dur=6)
        t.name, t.text = "Thương hiệu", "THƯƠNG HIỆU"
        t.base["pos1"] = -38.0
        _keys(t, "op", [(1.2, 0.0), (1.8, 100.0)])
    elif key == "slides":
        for i, col in enumerate(("#7a2bff", "#e0457b", "#2f8fe0")):
            s = ed.new_layer("Hình vuông", start=i * 4.0, dur=4.0)
            s.name, s.color = "Cảnh %d" % (i + 1), col
            s.base.update(scl0=700.0, scl1=420.0)
            _keys(s, "op", [(i * 4.0, 0.0), (i * 4.0 + 0.6, 100.0)])
    ed.select_layer(None)
    ed.seek(0)
    ed.log("Đã tạo từ mẫu: " + dict((k, n) for k, n, _ in TEMPLATES)[key])
