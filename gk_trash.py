"""Thung rac (muc 52): giu lai lop / clip vua xoa trong phien lam viec de lay lai duoc.
Module doc lap, khong dung Undo/Redo. Hoat dong theo kieu "ngan chan" (intercept): EditorPage
goi trash.push(...) THAY VI xoa hang luon, va trash.restore_last() / dialog de lay lai.

Vi sao tach rieng Undo/Redo: Undo la "lam lai 1 buoc vua lam" (bao gom ca di chuyen, doi mau...),
con Thung rac la noi chua RIENG cac mon da XOA, xem duoc danh sach, lay lai mon cu tu lau ma
khong can bam Undo hang chuc lan di qua moi thay doi khac o giua. Hai thu bo tro nhau, khong
thay the nhau.
"""
import time

MAX_ITEMS = 200          # gioi han muc trong thung rac (tranh phinh bo nho vo han trong phien dai)


class TrashItem:
    """1 muc da xoa. kind: 'layer' hoac 'clip'. payload la du lieu can de khoi phuc, tuy kind:
    - 'layer': payload = (Layer, [(row, start, dur, src_off), ...])  -  giong dinh dang _clips_of()/
      _insert_layer() da co san trong gk_editor.py cua ong, nen khoi phuc chi can goi lai ham do.
    - 'clip': payload = (Layer, row, start, dur, src_off)  -  du de goi lai add_layer_clip()."""
    __slots__ = ("kind", "payload", "label", "ts")

    def __init__(self, kind, payload, label):
        self.kind, self.payload, self.label, self.ts = kind, payload, label, time.time()


class Trash:
    """Danh sach cac muc da xoa trong phien lam viec hien tai (khong luu ra dia: dong app la het,
    dung tinh than 'xoa nham lay lai duoc trong luc dang lam', khac voi Auto-save/Version la ban
    luu ra dia qua nhieu lan sua). Moi project (EditorPage) nen co 1 Trash rieng."""

    def __init__(self):
        self.items = []          # moi nhat o cuoi danh sach

    def push(self, kind, payload, label):
        self.items.append(TrashItem(kind, payload, label))
        del self.items[:-MAX_ITEMS]      # qua gioi han thi bo cac muc CU NHAT (dau danh sach)

    def peek_last(self):
        return self.items[-1] if self.items else None

    def pop_last(self):
        return self.items.pop() if self.items else None

    def pop(self, item):
        if item in self.items:
            self.items.remove(item)
            return item
        return None

    def clear(self):
        self.items.clear()

    def is_empty(self):
        return not self.items

    def __len__(self):
        return len(self.items)
