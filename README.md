# GoLike Helper - Auto Captcha Solver

App Android giup tu dong chup man hinh va click captcha, khong can root.

## Tinh nang
- HTTP Server tai port 7788
- Chup man hinh real-time (MediaProjection)
- Tu dong click/swipe (Accessibility Service)
- Ket hop voi Python bot + Gemini AI

## API Endpoints

| Method | Path        | Body / Mo ta                          |
|--------|-------------|---------------------------------------|
| GET    | /ping       | Kiem tra server dang chay             |
| POST   | /screenshot | Tra ve anh base64 JPEG                |
| POST   | /tap        | `{"x":100,"y":200}` - click 1 diem   |
| POST   | /click      | `[{"x":1,"y":2},...]` - click nhieu  |
| POST   | /swipe      | `{"x1","y1","x2","y2","duration"}`   |

## Build APK tren GitHub (khong can PC)

1. **Fork hoac tao repo moi** tren GitHub
2. **Upload toan bo folder nay** len repo
3. Vao tab **Actions** → chon workflow → **Run workflow**
4. Sau ~5 phut, vao **Releases** de tai APK

## Cai dat va setup (1 lan duy nhat)

1. Cai APK vao dien thoai
2. Mo app → nhan **"Cap quyen Overlay"** → bat quyen
3. Nhan **"Cap quyen Accessibility"** → tim GoLike Helper → bat
4. Nhan **"KHOI DONG SERVER"** → dong y chup man hinh
5. Chay Python bot binh thuong

## Ket noi voi Python bot

```python
import requests, base64

BASE = "http://localhost:7788"  # tren cung thiet bi
# Hoac "http://IP_DIEN_THOAI:7788" neu bot chay tren may tinh

# Ping kiem tra
r = requests.get(f"{BASE}/ping")
print(r.json())  # {"status":"ok"}

# Chup man hinh
r = requests.post(f"{BASE}/screenshot")
img_b64 = r.json()["image"]
with open("screen.jpg","wb") as f:
    f.write(base64.b64decode(img_b64))

# Click tai toa do
requests.post(f"{BASE}/tap", json={"x": 540, "y": 960})

# Click nhieu diem
requests.post(f"{BASE}/click", json=[
    {"x": 100, "y": 200, "delay": 500},
    {"x": 300, "y": 400, "delay": 300},
])
```

## Yeu cau he thong
- Android 8.0+ (API 26)
- Khong can root
