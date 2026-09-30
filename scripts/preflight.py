#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: preflight.py <78-xiaozhi-root>")

root = Path(sys.argv[1]).resolve()
main = root / "main"
board = main / "boards" / "spotpear" / "max35-4g"
ui = main / "display" / "aurora_max35"

marker = root / ".max35_4g_vendor_board_path"
if not marker.exists():
    raise SystemExit("vendor board provenance marker missing")
selected_vendor = marker.read_text(encoding="utf-8", errors="ignore").strip().replace("\\", "/")
if "/main/boards/common" in selected_vendor or selected_vendor.endswith("/boards/common"):
    raise SystemExit("generic main/boards/common was selected instead of the real MAX35 hardware board")
if "sp-esp32-s3-lcd-3.5" not in selected_vendor.lower() and "max35" not in selected_vendor.lower():
    raise SystemExit(f"unexpected vendor board path: {selected_vendor}")
print("[OK] real MAX35 hardware folder selected:", selected_vendor)

required = [
    root / "scripts" / "build.py",
    main / "application.cc",
    main / "audio" / "audio_service.cc",
    main / "mcp_server.cc",
    main / "boards" / "common" / "ml307_board.h",
    ui / "aurora_max35_display.h",
    ui / "aurora_max35_display.cc",
    ui / "ui_pages.h",
    ui / "ui_home.cc",
    ui / "ui_chat.cc",
    board / "config.json",
]
for path in required:
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")
    print("[OK]", path.relative_to(root))

cfg = json.loads((board / "config.json").read_text(encoding="utf-8"))
if cfg.get("manufacturer") != "spotpear" or cfg.get("type") != "max35-4g" or cfg.get("target") != "esp32s3":
    raise SystemExit("invalid MAX35 4G board identity")
builds = cfg.get("builds") or []
if len(builds) != 1 or builds[0].get("name") != "max35-4g-ml307-gc0308":
    raise SystemExit("expected exactly one MAX35 4G ML307 GC0308 build variant")
opts = builds[0].get("sdkconfig_append") or []
joined = "\n".join(opts)
for token in (
    "CONFIG_BOARD_TYPE_SPOTPEAR_MAX35_4G=y",
    "CONFIG_ESP_VIDEO_ENABLE_DVP_VIDEO_DEVICE=y",
    "CONFIG_CAMERA_GC0308=y",
    "CONFIG_CAMERA_GC0308_AUTO_DETECT_DVP_INTERFACE_SENSOR=y",
    "CONFIG_CAMERA_GC0308_DVP_YUV422_YUYV_640X480_16FPS=y",
    "CONFIG_CAMERA_OV2640=n",
    "CONFIG_CAMERA_OV5640=n",
    "CONFIG_XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE=y",
    "CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90=y",
    "CONFIG_UART_ISR_IN_IRAM=y",
    'CONFIG_OTA_URL="http://124.221.112.55:8002/xiaozhi/ota/"',
):
    if token not in joined:
        raise SystemExit(f"missing MAX35 4G build option: {token}")
if "CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_270=y" in joined:
    raise SystemExit("front-camera 270-degree rotation leaked into 4G rear build")
print("[OK] rear camera is GC0308 + YUYV + 90-degree rotation")
print("[OK] modem UART ISR is configured for IRAM")
print("[OK] OTA/backend URL is fixed to http://124.221.112.55:8002/xiaozhi/ota/")

ota_cc = (main / "ota.cc").read_text(encoding="utf-8", errors="ignore")
fixed_fn = re.search(
    r"std::string\s+Ota::GetCheckVersionUrl\(\)\s*\{(?P<body>.*?)\n\}",
    ota_cc,
    re.S,
)
if not fixed_fn:
    raise SystemExit("Ota::GetCheckVersionUrl() missing after fixed-OTA patch")
body = fixed_fn.group("body")
if "return CONFIG_OTA_URL;" not in body:
    raise SystemExit("GetCheckVersionUrl does not return fixed CONFIG_OTA_URL")
if 'GetString("ota_url")' in body or 'Settings settings("wifi"' in body:
    raise SystemExit("NVS ota_url override still active in GetCheckVersionUrl")
print("[OK] stale NVS wifi/ota_url can no longer override the fixed 4G backend")

kconfig = (main / "Kconfig.projbuild").read_text(encoding="utf-8", errors="ignore")
if not re.search(r"(?m)^\s*config\s+BOARD_TYPE_SPOTPEAR_MAX35_4G\s*$", kconfig):
    raise SystemExit("MAX35 4G Kconfig board registration missing")
cmake = (main / "CMakeLists.txt").read_text(encoding="utf-8", errors="ignore")
if 'set(BOARD_DIR "spotpear/max35-4g")' not in cmake:
    raise SystemExit("MAX35 4G BOARD_DIR registration missing")
for src in ("aurora_max35_display.cc", "ui_home.cc", "ui_chat.cc"):
    if src not in cmake:
        raise SystemExit(f"AURORA CMake source missing: {src}")
print("[OK] current 78 build system knows MAX35 4G + AURORA UI")

board_sources = []
for path in board.rglob("*"):
    if path.is_file() and path.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp"}:
        board_sources.append((path, path.read_text(encoding="utf-8", errors="ignore")))
board_blob = "\n".join(text for _, text in board_sources)
board_low = board_blob.lower()
if "AuroraMax35Display" not in board_blob:
    raise SystemExit("vendor board display was not attached to AuroraMax35Display")

if not any(token in board_low for token in (
    "ml307board",
    "ml307_board",
    "dualnetworkboard",
    "dual_network_board",
)):
    raise SystemExit("imported MAX35 board is not ML307/DualNetwork based")
if not (
    ("ml307" in board_low and "tx" in board_low and "rx" in board_low)
    or re.search(r"Ml307Board\s*\(", board_blob)
    or re.search(r"DualNetworkBoard\s*\(", board_blob)
):
    raise SystemExit("ML307 UART pins/constructor were not found in imported MAX35 board")
print("[OK] imported board contains real ML307 network integration")

old_cam_include = re.compile(r'#[ \t]*include[ \t]*[<"](?:boards/common/)?esp32_camera\.h[>"]')
old_cam_ctor = re.compile(r"new\s+Esp32Camera\s*\(\s*video_config\s*\)")
old_cam_member = re.compile(r"\bEsp32Camera\s*\*\s*camera_\b")
dvp_sources = []
for path, text in board_sources:
    if not any(token in text for token in (
        "esp_video_init_config_t",
        "esp_video_init_dvp_config_t",
        "esp_video_init_sccb_config_t",
        "esp_cam_ctlr_dvp_pin_config_t",
    )):
        continue
    dvp_sources.append((path, text))
    if old_cam_include.search(text):
        raise SystemExit(f"old esp32_camera.h wrapper include remains: {path}")
    if old_cam_ctor.search(text):
        raise SystemExit(f"old Esp32Camera(video_config) remains: {path}")
    if old_cam_member.search(text):
        raise SystemExit(f"old Esp32Camera* camera_ remains: {path}")
    if '#include "esp_video.h"' not in text:
        raise SystemExit(f"DVP source does not include current esp_video.h: {path}")
if not dvp_sources:
    raise SystemExit("no MAX35 DVP camera source found after import")
dvp_blob = "\n".join(text for _, text in dvp_sources)
if "new EspVideo(video_config)" not in dvp_blob:
    raise SystemExit("MAX35 DVP source does not instantiate EspVideo(video_config)")
print("[OK] MAX35 camera uses current 78 EspVideo wrapper")

legacy_adc = re.compile(r'#[ \t]*include[ \t]*[<"](?:driver/adc\.h|driver/deprecated/driver/adc\.h)[>"]')
if legacy_adc.search(board_blob):
    raise SystemExit("legacy driver/adc.h remains in imported MAX35 board")
shim = board / "legacy_adc_compat.h"
if not shim.exists():
    raise SystemExit("MAX35 IDF6 ADC compatibility shim missing")
for token in ("adc_oneshot_new_unit", "adc_oneshot_config_channel", "adc_oneshot_read"):
    if token not in shim.read_text(encoding="utf-8", errors="ignore"):
        raise SystemExit(f"MAX35 ADC shim incomplete: {token}")
print("[OK] IDF6 ADC compatibility installed")

# Product UI must never replace the native MCP/camera flow with a touch shutter.
mcp = (main / "mcp_server.cc").read_text(encoding="utf-8", errors="ignore")
for forbidden in (
    "WaitForTouchShutter",
    "WaitForCameraConsent",
    "stellar_max35::RegisterProductTools",
    "aurora_max35::WaitForCameraConsent",
):
    if forbidden in mcp:
        raise SystemExit(f"unexpected product MCP/touch patch present: {forbidden}")
print("[OK] upstream MCP camera path is untouched")

chat = (ui / "ui_chat.cc").read_text(encoding="utf-8", errors="ignore")
for token in (
    "LV_LABEL_LONG_WRAP",
    "ChatUiStartReadableScroll",
    "lv_anim_set_delay",
    "lv_anim_set_duration",
):
    if token not in chat:
        raise SystemExit(f"long-answer UI behavior missing: {token}")
print("[OK] chat page wraps long answers and performs delayed readable scrolling")

print("[done] MAX35 AURORA 4G/ML307 preflight passed")
