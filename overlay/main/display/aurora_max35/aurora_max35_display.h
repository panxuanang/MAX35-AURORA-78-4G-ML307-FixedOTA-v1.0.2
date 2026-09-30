#pragma once

#include "device_state.h"
#include "display/lcd_display.h"
#include "ui_pages.h"

#include <cstdint>
#include <memory>

class AuroraMax35Display : public SpiLcdDisplay {
public:
    using SpiLcdDisplay::SpiLcdDisplay;

    void SetupUI() override;
    void SetStatus(const char* status) override;
    void SetChatMessage(const char* role, const char* content) override;
    void ClearChatMessages() override;
    void SetPreviewImage(std::unique_ptr<LvglImage> image) override;
    void UpdateStatusBar(bool update_all = false) override;

private:
    enum class Page { Home, Chat };

    aurora_max35::HomeUi home_;
    aurora_max35::ChatUi chat_;
    Page page_ = Page::Home;
    DeviceState last_state_ = kDeviceStateUnknown;
    bool ui_ready_ = false;
    bool conversation_active_ = false;
    bool preview_active_ = false;
    int64_t scroll_finish_us_ = 0;
    int64_t return_home_us_ = 0;

    bool EnsureProductUi();
    void ShowPageInternal(Page page);
    void SetCustomUiHidden(bool hidden);
    void UpdateHomeInternal();
    void UpdateConversationState(DeviceState state);
};
