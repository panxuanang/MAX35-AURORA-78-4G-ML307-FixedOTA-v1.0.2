# MAX35 AURORA 4G / ML307

Target hardware: **SpotPear ESP32S3-MAX35-TouchLCD-BCamera-Case-4G**.

This repository is a reproducible product overlay, not a frozen fork of Xiaozhi. GitHub Actions checks out the selected `78/xiaozhi-esp32` revision, downloads the SpotPear MAX35 vendor source package, positively identifies the MAX35 **ML307** board implementation, imports only the hardware layer, then adds the AURORA UI.

The Xiaozhi application, audio pipeline, protocol, MCP, OTA implementation, camera tool flow and 4G networking remain owned by the current 78 upstream stack; this product only fixes the OTA discovery endpoint.

## v1.0.2 correction

The previous v1.0.1 importer could mistake `main/boards/common` for the MAX35 4G board because that generic directory contains the shared ML307 network base. It does **not** contain the MAX35 LCD/camera/audio hardware, so the build stopped with `Vendor MAX35 4G board has no SpiLcdDisplay construction/subclass to attach AURORA UI`.

v1.0.2 fixes that selection logic. It now follows SpotPear's own MAX35-ML307 Kconfig/CMake mapping first, prefers the physical `sp-esp32-s3-lcd-3.5` hardware directory used by the known MAX35 project, rejects `main/boards/common`, and verifies the selected source has the real MAX35 display/camera hardware before attaching AURORA. The Xiaozhi application/network/MCP logic is still left upstream; the product change is the UI plus the fixed build profile/OTA endpoint.

The workflow is also manual-only in this release, so uploading the files will not create one automatic run and then another manual run.

## Hardware profile used by this build

- ESP32-S3, 16 MB flash
- 3.5 inch 480x320 landscape UI on the MAX35 ST7796 display
- ML307 Cat.1 4G network module
- Rear camera
- GC0308 DVP camera, YUV422/YUYV, 640x480 at 16 fps
- Camera rotation: 90 degrees (rear-camera setting)
- Touch hardware is preserved when initialized by the SpotPear board code
- AURORA does not require touch and does not add any touch-shutter flow
- ES8311 audio and the remaining MAX35 hardware are taken from the vendor board implementation

SpotPear notes that the SD card cannot be used while the 4G function is active. This project does not try to override that hardware limitation.

## Fixed private OTA/backend endpoint

This build is locked to the following Xiaozhi OTA/backend discovery endpoint:

```text
http://124.221.112.55:8002/xiaozhi/ota/
```

The address is written into `CONFIG_OTA_URL` at build time. In addition, this product overlay patches the current upstream `Ota::GetCheckVersionUrl()` so it always returns `CONFIG_OTA_URL` and does **not** allow a stale NVS `wifi/ota_url` value to override it. No Wi-Fi provisioning page or GitHub repository variable is required to select the backend.

The OTA endpoint is also used by the Xiaozhi stack to discover the server connection information returned by your backend.

## AURORA UI behavior

The visual design is independent from the older STELLAR project, but it keeps the useful conversation behavior requested for MAX35:

1. The home screen is shown while idle.
2. Entering a voice conversation automatically opens a dedicated DIALOG page.
3. User transcription is kept in the upper context area.
4. Assistant answers use true multiline wrapping.
5. If an answer is taller than the visible answer area, it stays at the beginning briefly and then scrolls slowly by the exact required pixel distance.
6. The UI waits until the long answer has finished scrolling before returning home.
7. Native Xiaozhi camera preview remains on the normal `Capture -> SetPreviewImage` path; the AURORA layer hides while the preview is displayed and returns afterward.

The project deliberately does **not** import the old STELLAR weather, Todo, custom MCP tools, or touch-confirmed shutter flow.

## Safety checks in the build

The importer refuses to build if it cannot find a real MAX35 ML307 vendor board. It will not silently fall back to the Wi-Fi MAX35 board.

Preflight also checks that:

- the imported board contains ML307 or DualNetwork integration;
- the custom board has its own unique 78 board identity;
- the camera uses the current `EspVideo` wrapper instead of the old IDF5-era wrapper;
- legacy `driver/adc.h` use is redirected to IDF6 `adc_oneshot` compatibility;
- `mcp_server.cc` has not been patched with a touch shutter or product-specific camera consent gate;
- long-answer wrapping and delayed readable scrolling are present;
- the final build has rear-camera 90-degree rotation and the ML307-friendly UART ISR setting.

## Repository layout

```text
.github/workflows/build-max35-4g.yml
scripts/find_source_root.py
scripts/import_max35_4g_to_78.py
scripts/preflight.py
overlay/main/display/aurora_max35/
  aurora_max35_display.h
  aurora_max35_display.cc
  ui_pages.h
  ui_home.cc
  ui_chat.cc
VERSION
MANIFEST.txt
UPLOAD_GUIDE_CN.txt
```

## Build on GitHub

1. Create an empty GitHub repository.
2. Upload **all** files from this package to the repository root. The hidden `.github/workflows/` directory is required.
3. Open **Actions**.
4. Select **Build MAX35 AURORA 4G ML307**.
5. Choose **Run workflow**. Leave `upstream_ref` as `main` unless you intentionally want to pin another 78 revision.
6. When the workflow finishes, download the artifact named:

```text
MAX35-AURORA-4G-ML307-Firmware
```

The main flashable file is:

```text
MAX35_AURORA_4G_ML307_<version>_merged-binary.bin
```

Flash address:

```text
0x0
```

## Recommended first flash

When changing from a different firmware branch, erase the ESP32-S3 flash before writing the merged binary so old NVS and partition data cannot interfere.

Example:

```bash
esptool.py --chip esp32s3 erase_flash
esptool.py --chip esp32s3 --baud 460800 write_flash 0x0 MAX35_AURORA_4G_ML307_<version>_merged-binary.bin
```

Use the serial port option required by your computer if it is not selected automatically.

## 4G behavior

This is not a Wi-Fi provisioning build. The selected SpotPear hardware board must contain real ML307 integration and the current 78 stack provides the ML307 networking implementation. On a normal boot you should expect the modem to be detected and then wait for cellular network readiness rather than depend on a `Xiaozhi-xxxx` Wi-Fi hotspot.

If the firmware boots but has no network, inspect the 115200 serial log for ML307 modem detection, SIM/ICCID reporting and network-ready messages before changing the UI.

## Camera assumption

This package intentionally fixes the camera to **GC0308** for deterministic builds. SpotPear documentation also describes OV5640 variants. If your physical 4G unit contains an OV5640, change the camera build configuration before flashing; a sensor mismatch is not a UI issue.

## UI tuning

Primary behavior constants are in:

```text
overlay/main/display/aurora_max35/aurora_max35_display.cc
```

Current values:

```cpp
kScrollDelayMs = 1600;
kScrollMsPerPixel = 78;
kReturnHomeDelayUs = 4500000;
kAfterScrollDelayUs = 2000000;
```

Visual layout is in:

```text
ui_home.cc
ui_chat.cc
```

Prefer changing those UI files instead of application, audio, networking, protocol or MCP code.

## Architecture

```text
78/xiaozhi-esp32
  Application / Audio / Protocol / MCP / OTA / ML307 / Camera tool
                         |
                         +---- native behavior preserved

SpotPear vendor source
  MAX35 4G pins / LCD / touch / ES8311 / power / DVP camera / ML307 wiring
                         |
                         +---- imported hardware board only

This repository
  AURORA display overlay + deterministic MAX35 4G build registration
```

Version: see `VERSION`.
