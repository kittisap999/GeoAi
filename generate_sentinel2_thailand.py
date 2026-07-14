"""
สร้าง Sentinel-2.html: Sentinel-2 cloud-free median composite ของประเทศไทย
ปี 2026 (ตลอดทั้งปี ตามข้อมูลที่มี ณ วันที่รัน) บนพื้นหลัง Google Satellite

วิธีใช้ (working directory: D:\GeoAi, ใช้ venv ของโปรเจกต์นี้):
       D:\GeoAi\.venv\Scripts\python.exe generate_sentinel2_thailand.py
   (รันจากโฟลเดอร์ D:\GeoAi เพื่อให้ผลลัพธ์ Sentinel-2.html ถูกวางไว้ที่นี่)
   ครั้งแรกจะมี prompt ให้ login + วาง verification code -> cache token ไว้
   ใช้ครั้งถัดไปโดยไม่ต้อง login ซ้ำ
   ไฟล์ Sentinel-2.html เปิดด้วย browser ได้เลย (ต้องต่อ internet เพราะ tile
   โหลดสดจาก Earth Engine + Google server)

หมายเหตุ: ถ้ารันก่อนสิ้นปี 2026 จะได้ median จากข้อมูลที่มีถึงวันที่รันเท่านั้น
(ไม่ใช่ทั้งปีจริง) เดือนที่ยังไม่ถึงจะไม่มีภาพ ต้องรันซ้ำภายหลังเพื่อให้ครอบคลุม
ทั้งปีจริง ๆ
"""

import ee
import geemap

# ---------------- CONFIG ----------------
EE_PROJECT_ID = "ee-kittisapkao9"
START_DATE = "2026-01-01"
END_DATE = "2026-12-31"
CLOUD_PROB_THRESHOLD = 40  # % ความน่าจะเป็นเมฆที่จะถูก mask ทิ้ง (ต่ำ = เข้มงวดกว่า)
OUTPUT_HTML = "Sentinel-2.html"

# ---------------- AUTH / INIT ----------------
ee.Authenticate()
ee.Initialize(project=EE_PROJECT_ID)

# ---------------- AOI: ขอบเขตประเทศไทย ----------------
countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
thailand = countries.filter(ee.Filter.eq("country_na", "Thailand"))
thailand_geom = thailand.geometry()

# ---------------- Sentinel-2 SR + cloud probability ----------------
s2_sr = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate(START_DATE, END_DATE)
    .filterBounds(thailand_geom)
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
# หมายเหตุ: geemap.add_basemap("SATELLITE") เวอร์ชันนี้ resolve ไปที่ Esri World
# Imagery ไม่ใช่ Google จึงดึง tile ของ Google Satellite ตรง ๆ แทน (endpoint
# XYZ ที่ใช้กันทั่วไปในเครื่องมือ GIS อื่น ๆ เช่น QGIS "Google Satellite")
Map = geemap.Map(center=[13.5, 101.0], zoom=6)
Map.add_tile_layer(
    url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    name="Google Satellite",
    attribution="Google",
)

Map.addLayer(
    composite,
    vis_true_color,
    f"Sentinel-2 Median {START_DATE[:4]} (Thailand, cloud-free)",
)
Map.addLayer(
    ee.Image().paint(thailand, 0, 2),
    {"palette": ["yellow"]},
    "ขอบเขตประเทศไทย",
)

Map.centerObject(thailand, 6)
Map.add_layer_control()

Map.to_html(OUTPUT_HTML)
print(f"Saved: {OUTPUT_HTML}")
