import json
import os

STORAGE_FILE = "data.json"

# Đọc dữ liệu từ file
def load_data():
    if not os.path.exists(STORAGE_FILE):
        return {}  # Trả về dict rỗng nếu file không tồn tại
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # Nếu có lỗi đọc dữ liệu, trả về dict rỗng

# Lưu dữ liệu vào file
def save_data(data: dict):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Lấy giá trị từ dữ liệu lưu trữ
def get(key, default=None):
    data = load_data()
    return data.get(key, default)

# Cập nhật hoặc thêm giá trị vào dữ liệu
def set(key, value):
    data = load_data()
    data[key] = value
    save_data(data)

# Xóa key trong dữ liệu
def delete(key):
    data = load_data()
    if key in data:
        del data[key]
        save_data(data)