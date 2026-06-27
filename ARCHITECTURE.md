# 架构文档

## 架构概述

**静一静** 是一款基于 Python + tkinter/ttkbootstrap 的 Windows 桌面应用。采用单文件架构（`main.py`），所有核心逻辑集中在一个模块中，便于维护和打包。

应用架构遵循分层设计：
- **工具层**：日志、配置读写、语录管理
- **数据层**：JSON 数据持久化、统计记录
- **UI 层**：ttkbootstrap 多页面界面、锁屏窗口
- **核心功能层**：热键监听、托盘管理、进程守护、自启管理

---

## 模块划分

```
main.py
├── 工具层
│   ├── 路径常量（DATA_DIR, CONFIG_FILE, QUOTES_FILE 等）
│   ├── 日志函数 log()
│   ├── 配置读写（load_config, save_config）
│   ├── 语录读写（load_quotes, save_quotes）
│   └── 统计读写（load_stats, save_stats, load_hotkey_log 等）
├── 数据层
│   ├── 热键使用记录（record_hotkey_press, get_hotkey_stats）
│   ├── 喝水/休息记录（record_water_drink, record_rest）
│   ├── 连续打卡统计（get_streak_days）
│   ├── 本周峰值统计（get_weekly_peak）
│   ├── 图表生成（generate_weekly_chart）
│   └── CSV 导出（export_to_csv）
├── UI 层
│   ├── App 类（主应用）
│   │   ├── 首页（_build_home）
│   │   ├── 提醒中心（_build_focus）
│   │   ├── 语录库（_build_quotes）
│   │   ├── 统计页面（_build_stats）
│   │   └── 设置页面（_build_settings）
│   └── LockWindow 类（全屏锁屏窗口）
└── 核心功能层
    ├── WindowsHotkey 类（全局热键）
    ├── SingleInstance 类（单实例检测）
    ├── Watchdog 类（看门狗守护）
    └── AutoStartManager 类（开机自启）
```

---

## 核心类说明

### App（主应用类）

程序的入口和主控制器，负责：
- 初始化主窗口（ttkbootstrap Window）
- 构建侧边栏导航和五个内容页面
- 管理全局状态（配置、锁屏窗口、托盘图标）
- 协调喝水钟、休息钟的定时逻辑
- 处理热键回调和托盘交互

### LockWindow（锁屏窗口类）

全屏锁屏的实现，负责：
- 创建全屏、置顶、无边框的 Toplevel 窗口
- 显示语录和倒计时
- 处理 ESC 键强制退出（带阈值防抖）
- 喝水提醒时显示「喝了」按钮
- 倒计时结束后自动解锁，或记录「破防」日志

### WindowsHotkey（全局热键类）

使用 Windows 原生 `RegisterHotKey` API 实现全局热键：
- 创建隐藏窗口和消息循环线程
- 解析热键字符串（如 `alt+p`）为 mod_flags + vk_code
- 通过 `PeekMessageW` + `MsgWaitForMultipleObjects` 实现非阻塞消息循环
- 回调通过 `root.after(0, ...)` 派发到主线程
- 支持多实例（每个热键独立窗口类名）

### Watchdog（看门狗类）

进程守护机制：
- 独立守护线程，定期检查主进程（PID）是否存活
- 主进程退出后，等待 2 秒确保完全退出
- 通过进程名检查是否已有新实例在运行
- 使用 `subprocess.Popen` + `DETACHED_PROCESS` 重启程序

### SingleInstance（单实例检测类）

防止程序多开：
- 使用 `CreateMutexW` 创建 Windows 互斥锁
- 若互斥锁已存在（`ERROR_ALREADY_EXISTS`），则拒绝启动
- 启动失败时尝试激活已有窗口（`FindWindowW` + `SetForegroundWindow`）
- 程序退出时释放互斥锁

### AutoStartManager（开机自启管理类）

管理 Windows 开机自启：
- 操作注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- 自动处理 PyInstaller 单文件模式下 `sys.executable` 指向临时目录的问题
- 使用 `sys.argv[0]` 获取原始 exe 路径
- `is_enabled()` 仅检查键是否存在，不比较路径（支持 exe 移动或升级）

---

## 数据流说明

### 配置数据流

```
用户操作 UI
    ↓
save_config(cfg)  →  写入 DATA_DIR/jingyijing_config.json
    ↑
load_config()     ←  读取 JSON 文件（首次启动时创建默认配置）
    ↓
App.__init__() 读取配置初始化界面
```

### 提醒钟数据流

```
用户点击「开始」
    ↓
App._start_water() / _start_rest()
    ↓
每秒 tick 更新 UI 进度条和倒计时
    ↓
每 10 秒保存剩余秒数到配置（用于程序重启后恢复）
    ↓
倒计时结束 → 检查是否在工作时间内 → trigger_lock()
    ↓
锁屏结束 → 记录喝水/休息次数 → 刷新统计页面
```

### 统计图表数据流

```
用户点击「刷新图表」
    ↓
generate_weekly_chart()
    ↓
读取 jingyijing_hotkey_log.json
    ↓
按日期聚合 → matplotlib 生成柱状图
    ↓
保存到 DATA_DIR/weekly_chart.png
    ↓
PIL 加载图片显示到 Label 控件
```

---

## 配置文件结构

### jingyijing_config.json

```json
{
  "hotkey": "alt+p",
  "show_hotkey": "alt+o",
  "initial_lock": 30,
  "esc_threshold": 3,
  "theme": "cosmo",
  "quotes_allow_repeat": false,
  "quotes_last_date": "",
  "quotes_used": [],
  "auto_start": false,
  "watchdog": false,
  "lock_quote_font_size": 28,
  "lock_timer_font_size": 36,
  "window_width": 820,
  "window_height": 580,
  "water_interval": 45,
  "water_message": "喝口水吧",
  "rest_interval": 60,
  "rest_message": "休息一下吧",
  "water_enabled": true,
  "water_repeat": true,
  "rest_enabled": true,
  "rest_repeat": true,
  "work_start": "09:00",
  "work_end": "18:00",
  "lunch_start": "12:00",
  "lunch_end": "13:00",
  "rest_days": [],
  "water_last_time": "",
  "rest_last_time": "",
  "water_remaining_save": 0,
  "rest_remaining_save": 0,
  "water_lock_duration": 30,
  "rest_lock_duration": 180
}
```

### quotes.json

```json
{
  "quotes": [
    "静一静，深呼吸",
    "专注当下，效率倍增"
  ]
}
```

### jingyijing_stats.json

```json
{
  "sessions": 0,
  "total_minutes": 0,
  "today_minutes": 0,
  "today_date": ""
}
```

### jingyijing_hotkey_log.json

```json
{
  "records": [
    {"date": "2024-01-01", "time": "14:30:00"}
  ]
}
```

---

## 日志文件说明

| 文件 | 说明 |
|------|------|
| `静一静_破防日志.txt` | 记录 ESC 强制退出锁屏的事件 |
| `静一静_错误日志.txt` | 记录程序运行中的异常和错误 |

---

## 打包说明

### PyInstaller 单文件模式注意事项

本项目使用 PyInstaller `--onefile` 模式打包，有以下特殊处理：

1. **路径处理**：
   - 开发时：`__file__` 指向脚本目录
   - 打包后：`sys.executable` 指向临时解压目录，需用 `sys.argv[0]` 获取原始 exe 路径
   - 代码中通过 `getattr(sys, 'frozen', False)` 判断运行环境

2. **数据持久化目录**：
   - 所有配置文件、日志、数据均存放到 `%USERPROFILE%\AppData\Roaming\静一静\`
   - 避免 PyInstaller 每次解压后临时目录变化导致数据丢失

3. **依赖收集**：
   - `--collect-data ttkbootstrap`：打包主题文件
   - `--collect-data pystray`：打包托盘图标资源

4. **看门狗重启**：
   - 看门狗重启时使用 `sys.executable`
   - 单文件模式下 PyInstaller 引导程序会自动处理临时目录

5. **开机自启**：
   - 注册表写入的是 `sys.argv[0]` 路径
   - 确保 exe 文件不会移动位置，否则自启失效
