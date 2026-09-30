#include "aurora_max35_display.h"

#include "application.h"

#include <cstring>
#include <ctime>
#include <cstdio>
#include <utility>
#include <esp_log.h>
#include <esp_timer.h>

namespace {
constexpr const char* TAG = "AuroraMAX35";

constexpr uint32_t kIdle = 0x46D7C6;
constexpr uint32_t kListening = 0x55B8FF;
constexpr uint32_t kSpeaking = 0xF2C36B;
constexpr uint32_t kBusy = 0x8EA8FF;
constexpr uint32_t kError = 0xFF6B7A;

constexpr int kScrollDelayMs = 1600;
constexpr int kScrollMsPerPixel = 78;
constexpr int64_t kReturnHomeDelayUs = 4500000LL;
constexpr int64_t kAfterScrollDelayUs = 2000000LL;

bool IsConversing(DeviceState state) {
    return state == kDeviceStateConnecting ||
           state == kDeviceStateListening ||
           state == kDeviceStateSpeaking;
}

const char* StateText(DeviceState state) {
    switch (state) {
        case kDeviceStateStarting: return "小智启动中";
        case kDeviceStateWifiConfiguring: return "等待配网";
        case kDeviceStateIdle: return "小智待命中";
        case kDeviceStateConnecting: return "正在连接 AI";
        case kDeviceStateListening: return "正在聆听";
        case kDeviceStateSpeaking: return "正在回答";
        case kDeviceStateNotifying: return "消息提醒";
        case kDeviceStateUpgrading: return "系统升级中";
        case kDeviceStateActivating: return "设备激活中";
        case kDeviceStateAudioTesting: return "音频测试中";
        case kDeviceStateFatalError: return "系统异常";
        default: return "小智待命中";
    }
}

uint32_t StateColor(DeviceState state) {
    switch (state) {
        case kDeviceStateListening: return kListening;
        case kDeviceStateSpeaking: return kSpeaking;
        case kDeviceStateConnecting:
        case kDeviceStateStarting:
        case kDeviceStateActivating:
        case kDeviceStateUpgrading: return kBusy;
        case kDeviceStateFatalError: return kError;
        default: return kIdle;
    }
}

const char* StateOrbText(DeviceState state) {
    switch (state) {
        case kDeviceStateListening: return "IN";
        case kDeviceStateSpeaking: return "TX";
        case kDeviceStateConnecting: return "...";
        case kDeviceStateFatalError: return "!";
        default: return "AI";
    }
}

const char* Weekday(int day) {
    static const char* names[] = {
        "星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"
    };
    return (day >= 0 && day < 7) ? names[day] : "";
}
}  // namespace

void AuroraMax35Display::SetupUI() {
    // Build the normal 78/xiaozhi LCD tree first. Camera preview, notifications,
    // theme/font management and every upstream display feature therefore remain
    // available underneath the product UI overlay.
    LcdDisplay::SetupUI();
    EnsureProductUi();
}

bool AuroraMax35Display::EnsureProductUi() {
    if (ui_ready_) return true;

    DisplayLockGuard lock(this);
    if (!lock) return false;
    if (ui_ready_) return true;

    auto* screen = lv_screen_active();
    if (!screen) return false;

    aurora_max35::BuildHomeUi(screen, &home_);
    aurora_max35::BuildChatUi(screen, &chat_);

    page_ = Page::Home;
    conversation_active_ = false;
    preview_active_ = false;
    last_state_ = Application::GetInstance().GetDeviceState();
    ShowPageInternal(Page::Home);
    UpdateHomeInternal();
    ui_ready_ = true;

    ESP_LOGI(TAG, "AURORA UI attached: MAX35 4G / ML307 / current 78 stack");
    return true;
}

void AuroraMax35Display::ShowPageInternal(Page page) {
    if (!home_.root || !chat_.root) return;

    lv_obj_add_flag(home_.root, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(chat_.root, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t* target = (page == Page::Home) ? home_.root : chat_.root;
    if (target) {
        lv_obj_remove_flag(target, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(target);
    }

    page_ = page;
    if (page != Page::Chat) aurora_max35::ChatUiStopScroll(&chat_);
}

void AuroraMax35Display::SetCustomUiHidden(bool hidden) {
    if (!home_.root || !chat_.root) return;
    if (hidden) {
        lv_obj_add_flag(home_.root, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(chat_.root, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    ShowPageInternal(page_);
}

void AuroraMax35Display::UpdateHomeInternal() {
    if (!home_.root) return;

    std::time_t now = std::time(nullptr);
    std::tm tm{};
    localtime_r(&now, &tm);

    char time_text[16];
    char date_text[64];
    if (now > 1700000000) {
        std::snprintf(time_text, sizeof(time_text), "%02d:%02d", tm.tm_hour, tm.tm_min);
        std::snprintf(date_text, sizeof(date_text), "%d月%d日  %s",
                      tm.tm_mon + 1, tm.tm_mday, Weekday(tm.tm_wday));
    } else {
        std::snprintf(time_text, sizeof(time_text), "--:--");
        std::snprintf(date_text, sizeof(date_text), "时间同步中");
    }

    aurora_max35::HomeUiSetClock(&home_, time_text, date_text);
    aurora_max35::HomeUiSetState(
        &home_, StateText(last_state_), StateColor(last_state_), StateOrbText(last_state_));
}

void AuroraMax35Display::UpdateConversationState(DeviceState state) {
    if (page_ != Page::Chat) return;

    if (state == kDeviceStateListening) {
        aurora_max35::ChatUiSetState(&chat_, "我在听，请说话", kListening);
    } else if (state == kDeviceStateConnecting) {
        aurora_max35::ChatUiSetState(&chat_, "正在连接 AI", kBusy);
    } else if (state == kDeviceStateSpeaking) {
        aurora_max35::ChatUiSetState(&chat_, "小智正在回答", kSpeaking);
    } else if (state == kDeviceStateFatalError) {
        aurora_max35::ChatUiSetState(&chat_, "系统异常", kError);
    }
}

void AuroraMax35Display::SetStatus(const char* status) {
    LvglDisplay::SetStatus(status);
    if (!EnsureProductUi() || !status || !status[0]) return;

    DisplayLockGuard lock(this);
    if (!lock) return;
    if (page_ == Page::Home && home_.status) {
        lv_label_set_text(home_.status, status);
    }
}

void AuroraMax35Display::SetChatMessage(const char* role, const char* content) {
    // Preserve upstream subtitle/message behavior as well. Our layer is visual
    // presentation only; Application/Protocol/Audio/MCP behavior is untouched.
    LcdDisplay::SetChatMessage(role, content);

    if (!role || !content || !content[0]) return;
    if (!EnsureProductUi()) return;

    DisplayLockGuard lock(this);
    if (!lock) return;

    if (std::strcmp(role, "system") == 0) return;

    if (std::strcmp(role, "user") == 0) {
        conversation_active_ = true;
        return_home_us_ = 0;
        scroll_finish_us_ = 0;
        ShowPageInternal(Page::Chat);
        aurora_max35::ChatUiSetUser(&chat_, content);
        aurora_max35::ChatUiSetAnswer(&chat_, "我听到了，正在思考…");
        aurora_max35::ChatUiSetState(&chat_, "正在思考", kListening);
        return;
    }

    if (std::strcmp(role, "assistant") == 0) {
        conversation_active_ = true;
        return_home_us_ = 0;
        ShowPageInternal(Page::Chat);
        aurora_max35::ChatUiSetAnswer(&chat_, content);
        aurora_max35::ChatUiSetState(&chat_, "小智正在回答", kSpeaking);
        scroll_finish_us_ = aurora_max35::ChatUiStartReadableScroll(
            &chat_, kScrollDelayMs, kScrollMsPerPixel);
    }
}

void AuroraMax35Display::ClearChatMessages() {
    LcdDisplay::ClearChatMessages();
    if (!EnsureProductUi()) return;

    DisplayLockGuard lock(this);
    if (!lock) return;

    aurora_max35::ChatUiStopScroll(&chat_);
    aurora_max35::ChatUiSetUser(&chat_, "正在聆听…");
    aurora_max35::ChatUiSetAnswer(&chat_, "请说，我在听。");
    scroll_finish_us_ = 0;
    return_home_us_ = 0;
}

void AuroraMax35Display::SetPreviewImage(std::unique_ptr<LvglImage> image) {
    const bool has_image = static_cast<bool>(image);

    if (has_image && EnsureProductUi()) {
        DisplayLockGuard lock(this);
        if (lock) {
            preview_active_ = true;
            SetCustomUiHidden(true);
        }
    }

    // Keep current 78's proven Capture -> SetPreviewImage path. The custom
    // layer simply gets out of the way while the stock preview is visible.
    LcdDisplay::SetPreviewImage(std::move(image));

    if (!has_image && EnsureProductUi()) {
        DisplayLockGuard lock(this);
        if (lock) {
            preview_active_ = false;
            SetCustomUiHidden(false);
        }
    }
}

void AuroraMax35Display::UpdateStatusBar(bool update_all) {
    LvglDisplay::UpdateStatusBar(update_all);
    if (!EnsureProductUi()) return;

    const DeviceState state = Application::GetInstance().GetDeviceState();
    const int64_t now = esp_timer_get_time();

    DisplayLockGuard lock(this);
    if (!lock) return;

    if (state != last_state_) {
        if (!preview_active_ && state == kDeviceStateListening && page_ == Page::Home) {
            conversation_active_ = true;
            return_home_us_ = 0;
            scroll_finish_us_ = 0;
            ShowPageInternal(Page::Chat);
            aurora_max35::ChatUiSetUser(&chat_, "正在聆听…");
            aurora_max35::ChatUiSetAnswer(&chat_, "请说，我在听。");
        }

        UpdateConversationState(state);
        last_state_ = state;
    }

    if (!preview_active_ && page_ == Page::Home) {
        UpdateHomeInternal();
    }

    if (!preview_active_ && page_ == Page::Chat && conversation_active_) {
        if (state == kDeviceStateIdle) {
            if (scroll_finish_us_ > now) {
                return_home_us_ = scroll_finish_us_ + kAfterScrollDelayUs;
            } else if (return_home_us_ == 0) {
                return_home_us_ = now + kReturnHomeDelayUs;
            }
        } else if (IsConversing(state)) {
            return_home_us_ = 0;
        }

        if (return_home_us_ > 0 && now >= return_home_us_) {
            conversation_active_ = false;
            return_home_us_ = 0;
            scroll_finish_us_ = 0;
            ShowPageInternal(Page::Home);
            UpdateHomeInternal();
        }
    }
}
