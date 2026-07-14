"""
สร้าง Sentinel-2-lowcloud.html: Sentinel-2 median composite ของประเทศไทย
ตั้งแต่ 2026-01-01 จนถึงปัจจุบัน โดยคัดเฉพาะภาพที่ปลอดเมฆหรือมีเมฆรวมทั้งฉาก
ไม่เกิน 10% (CLOUDY_PIXEL_PERCENTAGE <= 10) แล้วยัง mask เมฆที่หลงเหลือระดับ
พิกเซลซ้ำอีกชั้นด้วย s2cloudless ก่อนทำ median บนพื้นหลัง Google Satellite

วิธีใช้ (working directory: D:\GeoAi, ใช้ venv ของโปรเจกต์นี้):
       D:\GeoAi\.venv\Scripts\python.exe generate_sentinel2_thailand_lowcloud.py
   (รันจากโฟลเดอร์ D:\GeoAi เพื่อให้ผลลัพธ์ Sentinel-2-lowcloud.html ถูกวางไว้ที่นี่)

หมายเหตุ: พื้นที่ที่มีเมฆหนาต่อเนื่อง (เช่น ภาคใต้/ภาคตะวันตกช่วงหน้าฝน) อาจไม่มี
ภาพผ่านเกณฑ์ <=10% เพียงพอ ทำให้เกิดช่องว่างข้อมูล (NoData) ในจุดนั้น ๆ ซึ่งเป็น
ผลที่ยอมรับตามที่ตกลงไว้ (ไม่ผ่อนเกณฑ์เมฆเพื่อลด NoData)
"""

import ee
import geemap

# ---------------- CONFIG ----------------
EE_PROJECT_ID = "ee-kittisapkao9"
START_DATE = "2026-01-01"
END_DATE = "2026-12-31"
MAX_SCENE_CLOUD_PERCENT = 10  # กรองทั้งฉาก: CLOUDY_PIXEL_PERCENTAGE <= 10
CLOUD_PROB_THRESHOLD = 40  # mask พิกเซลเมฆที่หลงเหลือในฉากที่ผ่านเกณฑ์ข้างต้น
OUTPUT_HTML = "Sentinel-2-lowcloud.html"

# ---------------- AUTH / INIT ----------------
ee.Authenticate()
ee.Initialize(project=EE_PROJECT_ID)

# ---------------- AOI: ขอบเขตประเทศไทย ----------------
countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
thailand = countries.filter(ee.Filter.eq("country_na", "Thailand"))
thailand_geom = thailand.geometry()

# ---------------- Sentinel-2 SR: กรองทั้งฉาก cloud <= 10% ----------------
s2_sr = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate(START_DATE, END_DATE)
    .filterBounds(thailand_geom)
    .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_SCENE_CLOUD_PERCENT))
    .select(["B2", "B3", "B4", "B8"])
)

s2_clouds = (
    ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
    .filterDate(START_DATE, END_DATE)
    .filterBounds(thailand_geom)
)

s2_joined = ee.Join.saveFirst("cloud_mask").apply(
    primary=s2_sr,
    secondary=s2_clouds,
    condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
)


def mask_clouds(img):
    img = ee.Image(img)
    cloud_prob = ee.Image(img.get("cloud_mask")).select("probability")
    is_clear = cloud_prob.lt(CLOUD_PROB_THRESHOLD)
    return img.updateMask(is_clear).divide(10000).copyProperties(
        img, ["system:time_start"]
    )


s2_clean = ee.ImageCollection(s2_joined).map(mask_clouds)

# ---------------- Median composite ----------------
composite = s2_clean.median().clip(thailand_geom)

vis_true_color = {
    "bands": ["B4", "B3", "B2"],
    "min": 0.0,
    "max": 0.3,
    "gamma": 1.3,
}

# ---------------- Build interactive map ----------------
Map = geemap.Map(center=[13.5, 101.0], zoom=6)
Map.add_tile_layer(
    url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    name="Google Satellite",
    attribution="Google",
)

Map.addLayer(
    composite,
    vis_true_color,
    f"Sentinel-2 Median {START_DATE} to present, cloud<={MAX_SCENE_CLOUD_PERCENT}%",
)
Map.addLayer(
    ee.Image().paint(thailand, 0, 2),
    {"palette": ["yellow"]},
    "Thailand boundary",
)

Map.centerObject(thailand, 6)
Map.add_layer_control()

Map.to_html(OUTPUT_HTML)
print(f"Saved: {OUTPUT_HTML}")
