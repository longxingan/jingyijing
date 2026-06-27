#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静一静 (JingYiJing) v6
专注助手 - 番茄钟 + 锁屏冥想
"""

import os
import sys
import json
import time
import random
import threading
import ctypes
import subprocess
from ctypes import wintypes
from datetime import datetime, date, timedelta
from pathlib import Path

# ==================== 开机自启工具 ====================
class AutoStartManager:
    """Windows 开机自启管理器"""
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "JingYiJing"

    @classmethod
    def _get_exe_path(cls):
        """获取正确的 exe 路径（PyInstaller 单文件模式下 sys.executable 指向临时目录）"""
        if getattr(sys, 'frozen', False):
            # 打包后：用 sys.argv[0] 获取原始 exe 路径
            exe_path = os.path.abspath(sys.argv[0])
        else:
            exe_path = sys.executable
        # 路径含空格时加引号
        if ' ' in exe_path:
            return f'"{exe_path}"'
        return exe_path

    @classmethod
    def is_enabled(cls):
        """检查是否已设置开机自启（只检查键是否存在，不比较路径，支持 exe 移动或升级）"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, cls.APP_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    @classmethod
    def enable(cls):
        """设置开机自启"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, cls.APP_NAME, 0, winreg.REG_SZ, cls._get_exe_path())
            winreg.CloseKey(key)
            return True
        except Exception as e:
            log(f"设置开机自启失败: {e}")
            return False

    @classmethod
    def disable(cls):
        """取消开机自启"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, cls.APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            log(f"取消开机自启失败: {e}")
            return False


# ==================== 看门狗进程守护 ====================
# ==================== 单实例检测（防止多开） ====================
class SingleInstance:
    """Windows 互斥锁，确保只有一个实例运行"""
    MUTEX_NAME = "JingYiJing_SingleInstance_v9"

    def __init__(self):
        self._handle = None

    def lock(self):
        """尝试获取互斥锁，返回 True 表示成功（首个实例）"""
        try:
            # 使用 CreateMutexW 创建互斥锁
            self._handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
            err = ctypes.windll.kernel32.GetLastError()
            if err == 183:  # ERROR_ALREADY_EXISTS
                # 互斥锁已存在，说明已有实例在运行
                ctypes.windll.kernel32.CloseHandle(self._handle)
                self._handle = None
                return False
            return True
        except Exception:
            return True  # 出错时允许运行

    def unlock(self):
        """释放互斥锁"""
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


class Watchdog:
    """看门狗：监控主进程，崩溃时自动重启（仅监控当前 exe 进程）"""
    def __init__(self, check_interval=5):
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._parent_pid = os.getpid()
        # 用 sys.argv[0] 获取原始 exe 路径（PyInstaller 单文件模式下 sys.executable 指向临时目录）
        if getattr(sys, 'frozen', False):
            self._exe_path = os.path.abspath(sys.argv[0]).lower()
        else:
            self._exe_path = sys.executable.lower()

    def start(self):
        """启动看门狗"""
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        log("[看门狗] 已启动")

    def stop(self):
        """停止看门狗"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        log("[看门狗] 已停止")

    def _watch_loop(self):
        """监控循环"""
        import psutil
        while self._running:
            try:
                # 检查当前 PID 的进程是否存活
                if not psutil.pid_exists(self._parent_pid):
                    log("[看门狗] 主进程已退出，准备重启...")
                    # 重启前等待 2 秒，确保旧进程完全退出
                    time.sleep(2)
                    # 检查是否已有新实例在运行（通过互斥锁或进程名）
                    if not self._is_another_instance_running():
                        subprocess.Popen([sys.executable], shell=False,
                                         creationflags=subprocess.DETACHED_PROCESS)
                    break
            except Exception as e:
                log(f"[看门狗] 监控异常: {e}")
            time.sleep(self.check_interval)

    def _is_another_instance_running(self):
        """检查是否已有其他实例在运行"""
        try:
            import psutil
            current_pid = os.getpid()
            exe_name = os.path.basename(self._exe_path)
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['pid'] != current_pid and proc.info['name']:
                        if exe_name.lower() in proc.info['name'].lower():
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return False

import tkinter as tk

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    from ttkbootstrap.dialogs import Messagebox
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    import tkinter as ttk
    from tkinter import messagebox as Messagebox
    TTKBOOTSTRAP_AVAILABLE = False

try:
    import keyboard as keyboard_global
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

VERSION = "v9.0.9"

# ==================== Windows 原生热键 ====================
class WindowsHotkey:
    """使用 Windows RegisterHotKey API 注册全局热键（最可靠，无需管理员权限）"""
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    _counter = 0

    def __init__(self):
        WindowsHotkey._counter += 1
        self._instance_id = WindowsHotkey._counter
        self.hwnd = None
        self.hotkey_id = self._instance_id
        self._class_name = f"JingYiJingHotkeyWnd_{self._instance_id}"
        self._callback = None
        self._thread = None
        self._running = False
        self._ready = threading.Event()
        self._success = False

    def _parse_hotkey(self, hk_str):
        """解析热键字符串，返回 (mod_flags, vk_code)"""
        hk_str = hk_str.lower().strip()
        mod_flags = 0
        if "alt" in hk_str:
            mod_flags |= self.MOD_ALT
        if "ctrl" in hk_str or "control" in hk_str:
            mod_flags |= self.MOD_CONTROL
        if "shift" in hk_str:
            mod_flags |= self.MOD_SHIFT
        if "win" in hk_str or "cmd" in hk_str:
            mod_flags |= self.MOD_WIN

        key_part = hk_str.split("+")[-1].strip()

        if len(key_part) == 1 and key_part.isalpha():
            vk = ord(key_part.upper())
            return mod_flags, vk

        if len(key_part) == 1 and key_part.isdigit():
            vk = ord(key_part)
            return mod_flags, vk

        vk_map = {
            "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
            "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
            "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
            "space": 0x20, "enter": 0x0D, "return": 0x0D,
            "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
            "insert": 0x2D, "delete": 0x2E, "home": 0x24,
            "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "backspace": 0x08, "bs": 0x08,
        }
        vk = vk_map.get(key_part)
        if vk is None:
            raise ValueError(f"\u4E0D\u652F\u6301\u7684\u70ED\u952E: {hk_str}")
        return mod_flags, vk

    def start(self, hotkey_str, callback):
        """启动热键监听（同步等待注册完成）"""
        self._callback = callback
        self._running = True
        self._ready.clear()
        self._success = False
        self._thread = threading.Thread(target=self._message_loop, args=(hotkey_str,), daemon=True)
        self._thread.start()
        # 等待注册完成（最多 3 秒）
        self._ready.wait(timeout=3.0)
        if not self._success:
            raise RuntimeError(f"RegisterHotKey \u6CE8\u518C\u5931\u8D25: {hotkey_str}")

    def _message_loop(self, hotkey_str):
        """Windows 消息循环线程"""
        try:
            mod_flags, vk = self._parse_hotkey(hotkey_str)
        except ValueError as e:
            log(f"[WinHotkey] \u89E3\u6790\u70ED\u952E\u5931\u8D25: {e}")
            self._success = False
            self._ready.set()
            return

        try:
            # 定义窗口过程类型
            WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p
            )

            # 定义 WNDCLASS 结构体
            class WNDCLASS(ctypes.Structure):
                _fields_ = [
                    ("style", ctypes.c_uint),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p),
                    ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p),
                    ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", ctypes.c_wchar_p),
                    ("lpszClassName", ctypes.c_wchar_p),
                ]

            @WNDPROC
            def wnd_proc(hwnd, msg, w_param, l_param):
                if msg == 0x0312:  # WM_HOTKEY
                    if self._callback:
                        try:
                            self._callback()
                        except Exception as e:
                            log(f"[WinHotkey] \u56DE\u8C03\u5F02\u5E38: {e}")
                    return 0
                return ctypes.windll.user32.DefWindowProcW(hwnd, msg, w_param, l_param)

            h_instance = ctypes.windll.kernel32.GetModuleHandleW(None)

            wndclass = WNDCLASS()
            wndclass.lpfnWndProc = wnd_proc
            wndclass.hInstance = h_instance
            wndclass.lpszClassName = self._class_name

            if not ctypes.windll.user32.RegisterClassW(ctypes.byref(wndclass)):
                err = ctypes.GetLastError()
                log(f"[WinHotkey] RegisterClassW 失败: {self._class_name}, err={err}")
                self._success = False
                self._ready.set()
                return

            self.hwnd = ctypes.windll.user32.CreateWindowExW(
                0, self._class_name, "",
                0, 0, 0, 0, 0,
                None, None, h_instance, None
            )

            if not self.hwnd:
                log(f"[WinHotkey] CreateWindowExW \u5931\u8D50")
                self._success = False
                self._ready.set()
                return

            if not ctypes.windll.user32.RegisterHotKey(self.hwnd, self.hotkey_id, mod_flags, vk):
                err = ctypes.GetLastError()
                log(f"[WinHotkey] RegisterHotKey \u5931\u8D51: {hotkey_str}, error={err}")
                ctypes.windll.user32.DestroyWindow(self.hwnd)
                self.hwnd = None
                self._success = False
                self._ready.set()
                return

            log(f"[WinHotkey] \u70ED\u952E\u5DF2\u6CE8\u518C: {hotkey_str} (mod={mod_flags}, vk=0x{vk:02X})")
            self._success = True
            self._ready.set()

            # 消息循环
            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p),
                    ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint),
                    ("pt_x", ctypes.c_long),
                    ("pt_y", ctypes.c_long),
                ]

            while self._running:
                # PeekMessage + MsgWaitForMultipleObjects 避免阻塞
                msg_obj = MSG()
                ret = ctypes.windll.user32.PeekMessageW(ctypes.byref(msg_obj), None, 0, 0, 1)  # PM_REMOVE
                if ret:
                    if msg_obj.message == 0x0312 and msg_obj.wParam == self.hotkey_id:
                        pass  # 已在 wnd_proc 中处理
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg_obj))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg_obj))
                else:
                    # 没有消息时等待一小段时间
                    ctypes.windll.user32.MsgWaitForMultipleObjects(
                        0, None, False, 100, 0x0001  # QS_ALLINPUT
                    )

        except Exception as e:
            log(f"[WinHotkey] \u6D88\u606F\u5FAA\u73AF\u5F02\u5E38: {e}")
            self._success = False
            self._ready.set()
        finally:
            if self.hwnd:
                ctypes.windll.user32.UnregisterHotKey(self.hwnd, self.hotkey_id)
                ctypes.windll.user32.DestroyWindow(self.hwnd)
                self.hwnd = None
            log("[WinHotkey] \u6D88\u606F\u5FAA\u73AF\u5DF2\u9000\u51FA")

    def stop(self):
        """停止热键监听"""
        self._running = False
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, 0x0012, 0, 0)  # WM_QUIT
        if self._thread:
            self._thread.join(timeout=2.0)


# ==================== 路径 ====================
# 数据文件存到用户目录，避免 PyInstaller 单文件模式每次解压后丢失
if getattr(sys, 'frozen', False):
    # 打包后：exe 所在目录（用 sys.argv[0] 获取原始 exe 路径，sys.executable 在单文件模式下指向临时目录）
    EXE_DIR = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    # 开发时：脚本所在目录
    EXE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# 持久化数据目录（用户目录下，不会随 exe 解压丢失）
DATA_DIR = Path.home() / "AppData" / "Roaming" / "静一静"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = EXE_DIR  # 兼容旧代码中可能用到 BASE_DIR 的地方
CONFIG_FILE = DATA_DIR / "jingyijing_config.json"
QUOTES_FILE = DATA_DIR / "quotes.json"
LOG_FILE = DATA_DIR / "静一静_破防日志.txt"
ERR_LOG = DATA_DIR / "静一静_错误日志.txt"
STATS_FILE = DATA_DIR / "jingyijing_stats.json"
HOTKEY_LOG_FILE = DATA_DIR / "jingyijing_hotkey_log.json"
WATER_LOG_FILE = DATA_DIR / "jingyijing_water.json"
REST_LOG_FILE = DATA_DIR / "jingyijing_rest.json"

AVAILABLE_THEMES = [
    "darkly", "superhero", "cyborg", "vapor",
    "litera", "flatly", "journal", "lumen",
    "solar", "simplex", "cosmo", "minty", "pulse"
]

# 初始配置（仅用于首次创建文件）
INITIAL_CONFIG = {
    "hotkey": "alt+p",
    "show_hotkey": "alt+o",
    "initial_lock": 30,
    "esc_threshold": 3,
    "theme": "cosmo",
    "quotes_allow_repeat": False,
    "quotes_last_date": "",
    "quotes_used": [],
    "auto_start": False,
    "watchdog": False,
    "lock_quote_font_size": 28,
    "lock_timer_font_size": 36,
    "window_width": 820,
    "window_height": 580,
    "water_interval": 45,
    "water_message": "喝口水吧",
    "rest_interval": 60,
    "rest_message": "休息一下吧",
    "water_enabled": True,
    "water_repeat": True,
    "rest_enabled": True,
    "rest_repeat": True,
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
    "rest_lock_duration": 180,
}

# ==================== 工具函数 ====================
def log(msg: str):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def ensure_config_file():
    """确保配置文件存在，不存在则创建初始版本"""
    if not CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(INITIAL_CONFIG, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"创建配置文件失败: {e}")


def ensure_quotes_file():
    """确保语录文件存在，不存在则创建空数组"""
    if not QUOTES_FILE.exists():
        try:
            with open(QUOTES_FILE, "w", encoding="utf-8") as f:
                json.dump({"quotes": []}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"创建语录文件失败: {e}")


def load_config() -> dict:
    """加载配置 - 只读，不覆盖"""
    ensure_config_file()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 校验主题有效性
        if cfg.get("theme") not in AVAILABLE_THEMES:
            cfg["theme"] = "cosmo"
        return cfg
    except Exception as e:
        log(f"加载配置失败: {e}")
        return INITIAL_CONFIG.copy()


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"保存配置失败: {e}")


def load_quotes() -> list:
    """加载语录 - 只读，不自动创建默认内容"""
    ensure_quotes_file()
    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("quotes", [])
    except Exception as e:
        log(f"加载语录失败: {e}")
        return []


def save_quotes(quotes_list: list):
    try:
        with open(QUOTES_FILE, "w", encoding="utf-8") as f:
            json.dump({"quotes": quotes_list}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"保存语录失败: {e}")


def load_stats() -> dict:
    default = {"sessions": 0, "total_minutes": 0, "today_minutes": 0, "today_date": ""}
    try:
        if STATS_FILE.exists():
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_stats(stats: dict):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        log(f"保存统计失败: {e}")


def load_hotkey_log() -> dict:
    default = {"records": []}
    try:
        if HOTKEY_LOG_FILE.exists():
            with open(HOTKEY_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_hotkey_log(log_data: dict):
    try:
        with open(HOTKEY_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        log(f"保存热键记录失败: {e}")


def record_hotkey_press():
    data = load_hotkey_log()
    today = date.today().isoformat()
    data["records"].append({"date": today, "time": datetime.now().strftime("%H:%M:%S")})
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    data["records"] = [r for r in data["records"] if r["date"] >= cutoff]
    save_hotkey_log(data)


def get_hotkey_stats(days: int = 7) -> dict:
    data = load_hotkey_log()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    records = [r for r in data["records"] if r["date"] >= cutoff]
    daily = {}
    for r in records:
        d = r["date"]
        daily[d] = daily.get(d, 0) + 1
    return {"total": len(records), "daily": daily, "days": days}


def get_streak_days() -> dict:
    """获取连续打卡天数"""
    data = load_hotkey_log()
    if not data["records"]:
        return {"current": 0, "longest": 0, "last_date": None}

    # 按日期去重，获取有打卡记录的日期列表
    dates = sorted(set(r["date"] for r in data["records"]), reverse=True)

    # 计算当前连续天数
    current_streak = 0
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if today in dates or yesterday in dates:
        check_date = date.today()
        while check_date.isoformat() in dates:
            current_streak += 1
            check_date -= timedelta(days=1)

    # 计算最长连续天数
    longest_streak = 0
    current_longest = 0
    all_dates = sorted(set(r["date"] for r in data["records"]))
    for i, d in enumerate(all_dates):
        if i == 0:
            current_longest = 1
        else:
            prev = datetime.strptime(all_dates[i-1], "%Y-%m-%d").date()
            curr = datetime.strptime(d, "%Y-%m-%d").date()
            if (curr - prev).days == 1:
                current_longest += 1
            else:
                longest_streak = max(longest_streak, current_longest)
                current_longest = 1
    longest_streak = max(longest_streak, current_longest)

    return {
        "current": current_streak,
        "longest": longest_streak,
        "last_date": dates[0] if dates else None
    }


def get_weekly_peak() -> dict:
    """获取本周峰值数据"""
    data = load_hotkey_log()
    # 本周开始（周一）
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.isoformat()

    records = [r for r in data["records"] if r["date"] >= monday_str]

    # 按日期统计
    daily = {}
    for r in records:
        d = r["date"]
        daily[d] = daily.get(d, 0) + 1

    # 按小时段统计（找出最活跃的时段）
    hourly = {}
    for r in records:
        h = r["time"][:2]  # 取小时
        hourly[h] = hourly.get(h, 0) + 1

    peak_day = max(daily, key=daily.get) if daily else None
    peak_day_count = daily.get(peak_day, 0) if peak_day else 0
    peak_hour = max(hourly, key=hourly.get) if hourly else None
    peak_hour_count = hourly.get(peak_hour, 0) if peak_hour else 0

    return {
        "total_this_week": len(records),
        "peak_day": peak_day,
        "peak_day_count": peak_day_count,
        "peak_hour": peak_hour,
        "peak_hour_count": peak_hour_count,
        "daily": daily
    }


def generate_weekly_chart() -> str:
    """生成本周专注趋势图，返回图片文件路径"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        # 设置中文字体
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        matplotlib.rcParams['axes.unicode_minus'] = False

        data = load_hotkey_log()
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        monday_str = monday.isoformat()

        records = [r for r in data["records"] if r["date"] >= monday_str]

        # 按日期统计
        daily = {}
        for r in records:
            d = r["date"]
            daily[d] = daily.get(d, 0) + 1

        # 补齐本周所有日期
        week_dates = []
        week_counts = []
        for i in range(7):
            d = (monday + timedelta(days=i)).isoformat()
            week_dates.append(d)
            week_counts.append(daily.get(d, 0))

        # 中文标签
        weekday_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(weekday_labels, week_counts, color="#6C5CE7", alpha=0.8)
        ax.set_ylabel("锁屏次数", fontsize=12)
        ax.set_title("本周专注趋势", fontsize=14, fontweight="bold")
        ax.set_ylim(0, max(week_counts + [1]) * 1.2)

        # 在柱子上显示数值
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        chart_path = DATA_DIR / "weekly_chart.png"
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        return str(chart_path)
    except Exception as e:
        log(f"生成图表失败: {e}")
        return ""


def export_to_csv() -> str:
    """导出数据到CSV，返回文件路径"""
    import csv

    # 导出破防日志
    csv_path = DATA_DIR / "静一静_数据导出.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["类型", "日期", "时间", "备注"])

        # 热键记录
        hk_data = load_hotkey_log()
        for r in hk_data["records"]:
            writer.writerow(["强制锁屏", r["date"], r["time"], ""])

        # 喝水记录
        water_data = load_water_log()
        for r in water_data.get("records", []):
            writer.writerow(["喝水提醒", r["date"], r["time"], ""])

        # 休息记录
        rest_data = load_rest_log()
        for r in rest_data.get("records", []):
            writer.writerow(["休息提醒", r["date"], r["time"], ""])

    return str(csv_path)


def load_water_log() -> dict:
    default = {"records": []}
    try:
        if WATER_LOG_FILE.exists():
            with open(WATER_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_water_log(log_data: dict):
    try:
        with open(WATER_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"保存喝水记录失败: {e}")


def load_rest_log() -> dict:
    default = {"records": []}
    try:
        if REST_LOG_FILE.exists():
            with open(REST_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_rest_log(log_data: dict):
    try:
        with open(REST_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"保存休息记录失败: {e}")


def record_rest():
    data = load_rest_log()
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    data["records"].append({"date": today, "time": now})
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    data["records"] = [r for r in data["records"] if r["date"] >= cutoff]
    save_rest_log(data)


def get_today_rest_count() -> int:
    data = load_rest_log()
    today = date.today().isoformat()
    return sum(1 for r in data["records"] if r["date"] == today)


def record_water_drink():
    data = load_water_log()
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    data["records"].append({"date": today, "time": now})
    # 保留最近 365 天的记录
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    data["records"] = [r for r in data["records"] if r["date"] >= cutoff]
    save_water_log(data)


def get_today_water_count() -> int:
    data = load_water_log()
    today = date.today().isoformat()
    return sum(1 for r in data["records"] if r["date"] == today)


def get_daily_quote(quotes: list, cfg: dict) -> str:
    if not quotes:
        return "静一静"
    today = date.today().isoformat()
    allow_repeat = cfg.get("quotes_allow_repeat", False)
    if allow_repeat:
        return random.choice(quotes)
    if cfg.get("quotes_last_date") != today:
        cfg["quotes_last_date"] = today
        cfg["quotes_used"] = []
        save_config(cfg)
    used = cfg.get("quotes_used", [])
    available = [q for q in quotes if q not in used]
    if not available:
        cfg["quotes_used"] = []
        available = quotes
        save_config(cfg)
    quote = random.choice(available) if available else "静一静"
    used.append(quote)
    cfg["quotes_used"] = used
    save_config(cfg)
    return quote


# ==================== 锁屏窗口 ====================
class LockWindow:
    def __init__(self, app: "App", is_water_reminder=False, reminder_text=None, lock_duration=None):
        self.app = app
        self.cfg = app.cfg
        self.root = None
        self.remaining = lock_duration if lock_duration is not None else self.cfg.get("initial_lock", 30)
        self.esc_count = 0
        self.last_esc = 0
        self.timer_id = None
        self.quotes = load_quotes()
        self.is_water_reminder = is_water_reminder
        self.reminder_text = reminder_text
        if reminder_text:
            self.current_quote = reminder_text
        else:
            self.current_quote = get_daily_quote(self.quotes, self.cfg) if self.quotes else "静一静"

    def show(self):
        self.root = ttk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

        sw = self.root.winfo_screenwidth()

        container = ttk.Frame(self.root)
        container.place(relx=0.5, rely=0.5, anchor="center")

        card = ttk.Frame(container, padding=50)
        card.pack()

        sep = ttk.Separator(card, orient=HORIZONTAL, bootstyle="primary")
        sep.pack(fill=X, pady=(0, 30))

        quote_font_size = self.cfg.get("lock_quote_font_size", 28)
        timer_font_size = self.cfg.get("lock_timer_font_size", 36)

        self.quote_label = ttk.Label(
            card, text=self.current_quote,
            font=("Microsoft YaHei", quote_font_size, "bold"),
            wraplength=int(sw * 0.6), justify=CENTER,
        )
        self.quote_label.pack(pady=20)

        self.timer_label = ttk.Label(
            card, text=self._fmt(self.remaining),
            font=("Consolas", timer_font_size, "bold"),
            bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None,
        )
        self.timer_label.pack(pady=15)

        hint = f"\u6309 ESC {self.cfg.get('esc_threshold', 3)}\u6B21\u53EF\u5F3A\u5236\u9000\u51FA"
        self.hint_label = ttk.Label(card, text=hint, font=("Microsoft YaHei", 11))
        self.hint_label.pack(pady=5)

        sep2 = ttk.Separator(card, orient=HORIZONTAL)
        sep2.pack(fill=X, pady=(20, 0))

        # 喝水提醒按钮
        if self.is_water_reminder:
            btn_frame = ttk.Frame(card)
            btn_frame.pack(pady=(15, 0))
            ttk.Button(
                btn_frame, text="\u2713 \u559d\u4e86",
                command=self._on_drank,
                bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None,
                width=12
            ).pack()

        # 绑定 ESC 键 - 使用 KeyRelease 确保能捕获
        self.root.bind("<KeyRelease-Escape>", self._on_esc)
        self.root.bind("<Button-1>", lambda e: "break")
        self.root.bind("<Key>", lambda e: "break")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self._tick()

    def _fmt(self, s):
        m, s = divmod(s, 60)
        return f"{m:02d}:{s:02d}"

    def _tick(self):
        if self.root is None or not self.root.winfo_exists():
            return
        if self.remaining > 0:
            self.remaining -= 1
            self.timer_label.config(text=self._fmt(self.remaining))
            self.timer_id = self.root.after(1000, self._tick)
        else:
            self._unlock()

    def _on_esc(self, event=None):
        now = time.time()
        threshold = self.cfg.get("esc_threshold", 3)
        if now - self.last_esc > 2:
            self.esc_count = 0
        self.last_esc = now
        self.esc_count += 1
        if self.esc_count >= threshold:
            self._force_exit()
        else:
            r = threshold - self.esc_count
            self.hint_label.config(text=f"\u518D\u6309 {r} \u6B21 ESC \u5F3A\u5236\u9000\u51FA...")

    def _on_drank(self):
        record_water_drink()
        self._destroy()

    def _force_exit(self):
        self._write_log()
        self._destroy()

    def _unlock(self):
        self._destroy()

    def _destroy(self):
        if self.timer_id:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
        if self.root and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.app.on_unlock()

    def _write_log(self):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] \u7834\u9632\u4E86\uff01\u5269\u4F59 {self.remaining} \u79D2\n")
        except Exception:
            pass


# ==================== 主应用 ====================
class App:
    def __init__(self):
        self.cfg = load_config()
        self.root = None
        self.lock_window = None
        self.tray_icon = None
        self.hotkey_listener = None
        self.win_hotkey = None  # Windows 原生热键对象
        self.win_show_hotkey = None  # 显示窗口热键对象
        self.status_var = None
        self.current_tab = "home"

        self.water_running = False
        self.water_remaining = 0
        self.water_timer_id = None
        self.rest_running = False
        self.rest_remaining = 0
        self.rest_timer_id = None

        self.stats = load_stats()
        self.all_quotes = load_quotes()
        self.today_water_count = get_today_water_count()
        self.today_rest_count = get_today_rest_count()

        # 看门狗
        self._watchdog = None
        if self.cfg.get("watchdog", False):
            self._watchdog = Watchdog()
            self._watchdog.start()

    def run(self):
        theme = self.cfg.get("theme", "cosmo")
        w = self.cfg.get("window_width", 820)
        h = self.cfg.get("window_height", 580)
        if TTKBOOTSTRAP_AVAILABLE:
            self.root = ttk.Window(title=f"\u9759\u4E00\u9759 {VERSION}", themename=theme, resizable=(True, True))
        else:
            self.root = ttk.Tk()
            self.root.title(f"\u9759\u4E00\u9759 {VERSION}")
            self.root.resizable(True, True)

        self.root.geometry(f"{w}x{h}")
        try:
            self.root.iconbitmap(str(BASE_DIR / "icon.ico"))
        except Exception:
            pass

        self._build_layout()
        self._start_hotkey()
        self.root.after(500, self._auto_start_timers)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_layout(self):
        outer = ttk.Frame(self.root)
        outer.pack(fill=BOTH, expand=True)

        sidebar = ttk.Frame(outer, width=180)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        brand = ttk.Frame(sidebar)
        brand.pack(fill=X, pady=(20, 15))

        ttk.Label(brand, text="\u9759\u4E00\u9759", font=("Microsoft YaHei", 20, "bold")).pack()
        ttk.Label(brand, text="\u4E13\u6CE8\u52A9\u624B", font=("Microsoft YaHei", 10)).pack()

        ttk.Separator(sidebar, orient=HORIZONTAL).pack(fill=X, padx=15, pady=5)

        nav_items = [
            ("home", "\U0001F3E0  \u9996\u9875"),
            ("focus", "\u23F1  \u63D0\u9192"),
            ("quotes", "\u270D  \u8BED\u5F55"),
            ("stats", "\U0001F4CA  \u7EDF\u8BA1"),
            ("settings", "\u2699  \u8BBE\u7F6E"),
        ]

        self.nav_btns = {}
        for key, label in nav_items:
            btn = ttk.Button(sidebar, text=label, style="nav.TButton",
                             command=lambda k=key: self._switch_tab(k))
            btn.pack(fill=X, padx=10, pady=2)
            self.nav_btns[key] = btn

        ttk.Separator(sidebar, orient=HORIZONTAL).pack(fill=X, padx=15, pady=(20, 5))

        hk_frame = ttk.Frame(sidebar)
        hk_frame.pack(fill=X, padx=15)

        ttk.Label(hk_frame, text="\u5FEB\u6377\u952E", font=("Microsoft YaHei", 9)).pack(anchor=W)

        self.hk_display = ttk.Label(hk_frame, text=self.cfg.get("hotkey", "alt+p"), font=("Consolas", 11, "bold"))
        self.hk_display.pack(anchor=W)

        self.status_var = ttk.StringVar(value="\u5C31\u7EEA")
        status_bar = ttk.Label(sidebar, textvariable=self.status_var, font=("Microsoft YaHei", 9), anchor=W)
        status_bar.pack(side=BOTTOM, fill=X, padx=15, pady=10)

        content = ttk.Frame(outer, padding=20)
        content.pack(side=RIGHT, fill=BOTH, expand=True)

        self.content_frame = content

        self.tab_frames = {}
        for key, _ in nav_items:
            f = ttk.Frame(content)
            self.tab_frames[key] = f

        self._build_home(self.tab_frames["home"])
        self._build_focus(self.tab_frames["focus"])
        self._build_quotes(self.tab_frames["quotes"])
        self._build_stats(self.tab_frames["stats"])
        self._build_settings(self.tab_frames["settings"])

        self._switch_tab("home")

    def _switch_tab(self, key):
        # 取消之前的鼠标滚轮绑定
        if hasattr(self, '_stats_canvas') and self._stats_canvas:
            self._stats_canvas.unbind_all("<MouseWheel>")

        self.current_tab = key
        for k, f in self.tab_frames.items():
            f.pack_forget()
        self.tab_frames[key].pack(fill=BOTH, expand=True)
        if key == "home":
            self._refresh_home_stats()
        elif key == "stats":
            self._refresh_stats_display()
            # 重新绑定鼠标滚轮
            if hasattr(self, '_stats_canvas') and self._stats_canvas:
                def _on_mousewheel(event):
                    self._stats_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                self._stats_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _refresh_home_stats(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            water_count = get_today_water_count()
            rest_count = get_today_rest_count()
            streak = get_streak_days()
            if hasattr(self, "home_stat_labels"):
                self.home_stat_labels.get("home_reminder", None).config(text=f"{water_count + rest_count}\u6B21")
                self.home_stat_labels.get("home_water", None).config(text=f"{water_count}\u6B21")
                self.home_stat_labels.get("home_rest", None).config(text=f"{rest_count}\u6B21")
                self.home_stat_labels.get("home_streak", None).config(text=f"{streak['current']}\u5929")
        except Exception:
            pass

    def _refresh_stats_display(self):
        try:
            water_count = get_today_water_count()
            rest_count = get_today_rest_count()
            if hasattr(self, "stats_value_labels"):
                self.stats_value_labels.get("\u4ECA\u65E5\u559D\u6C34", None).config(text=str(water_count))
                self.stats_value_labels.get("\u4ECA\u65E5\u4F11\u606F", None).config(text=str(rest_count))

            # 刷新连续打卡
            streak = get_streak_days()
            if hasattr(self, "streak_value_labels"):
                self.streak_value_labels.get("\u8FDE\u7EED\u6253\u5361", None).config(text=f"{streak['current']} \u5929")
                self.streak_value_labels.get("\u6700\u957F\u8FDE\u7EED", None).config(text=f"{streak['longest']} \u5929")
                last_date = streak['last_date'] or "\u6682\u65E0"
                self.streak_value_labels.get("\u4E0A\u6B21\u6253\u5361", None).config(text=last_date)

            # 刷新本周峰值
            peak = get_weekly_peak()
            if hasattr(self, "peak_value_labels"):
                self.peak_value_labels.get("\u672C\u5468\u9501\u5C4F", None).config(text=f"{peak['total_this_week']} \u6B21")
                peak_day = peak['peak_day']
                if peak_day:
                    peak_day_str = f"{peak_day[5:7]}\u6708{peak_day[8:]}\u65E5"
                    self.peak_value_labels.get("\u6700\u6D3B\u8DC3\u65E5\u671F", None).config(
                        text=f"{peak_day_str} ({peak['peak_day_count']}\u6B21)")
                else:
                    self.peak_value_labels.get("\u6700\u6D3B\u8DC3\u65E5\u671F", None).config(text="\u6682\u65E0")
                peak_hour = peak['peak_hour']
                if peak_hour:
                    self.peak_value_labels.get("\u6700\u6D3B\u8DC3\u65F6\u6BB5", None).config(
                        text=f"{peak_hour}:00 ({peak['peak_hour_count']}\u6B21)")
                else:
                    self.peak_value_labels.get("\u6700\u6D3B\u8DC3\u65F6\u6BB5", None).config(text="\u6682\u65E0")
            
            # 刷新 Canvas 滚动区域
            if hasattr(self, '_stats_canvas') and self._stats_canvas:
                self._stats_canvas.update_idletasks()
                self._stats_canvas.configure(scrollregion=self._stats_canvas.bbox("all"))
        except Exception:
            pass

    # ------ \u9996\u9875 ------ 首页 ------
    def _build_home(self, parent):
        ttk.Label(parent, text="\u9996\u9875", font=("Microsoft YaHei", 18, "bold")).pack(anchor=NW, pady=(0, 15))

        card1 = ttk.Frame(parent, padding=20)
        card1.pack(fill=X, pady=(0, 12))

        ttk.Label(card1, text="\u5FEB\u6377\u64CD\u4F5C", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 12))

        btn_row = ttk.Frame(card1)
        btn_row.pack()

        self.lock_btn = ttk.Button(
            btn_row, text="\u25C9  \u7ACB\u5373\u9501\u5C4F",
            command=self.trigger_lock,
            bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None,
            width=16
        )
        self.lock_btn.pack(side=LEFT, padx=6)

        card3 = ttk.Frame(parent, padding=20)
        card3.pack(fill=X)

        ttk.Label(card3, text="\u4ECA\u65E5\u6982\u89C8", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 12))

        overview = ttk.Frame(card3)
        overview.pack()

        water_count = get_today_water_count()
        rest_count = get_today_rest_count()

        streak = get_streak_days()
        stat_data = [
            ("\u4ECA\u65E5\u63D0\u9192", f"{water_count + rest_count}\u6B21", "home_reminder"),
            ("\u4ECA\u65E5\u559D\u6C34", f"{water_count}\u6B21", "home_water"),
            ("\u4ECA\u65E5\u4F11\u606F", f"{rest_count}\u6B21", "home_rest"),
            ("\u8FDE\u7EED\u6253\u5361", f"{streak['current']}\u5929", "home_streak"),
        ]
        self.home_stat_labels = {}
        for label, value, key in stat_data:
            sf = ttk.Frame(overview)
            sf.pack(side=LEFT, padx=15)
            val_label = ttk.Label(sf, text=value, font=("Consolas", 20, "bold"))
            val_label.pack()
            self.home_stat_labels[key] = val_label
            ttk.Label(sf, text=label, font=("Microsoft YaHei", 9)).pack()

    # ------ 提醒中心 ------
    def _build_focus(self, parent):
        ttk.Label(parent, text="\u63D0\u9192\u4E2D\u5FC3", font=("Microsoft YaHei", 18, "bold")).pack(anchor=NW, pady=(0, 15))

        # ---- 第一行：工作时间设置 ----
        work_frame = ttk.Frame(parent, padding=10)
        work_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(work_frame, text="\u5DE5\u4F5C\u65F6\u95F4", font=("Microsoft YaHei", 12, "bold")).pack(side=LEFT)

        ttk.Label(work_frame, text="\u5F00\u59CB:").pack(side=LEFT, padx=(10, 2))
        self.work_start_var = ttk.StringVar(value=self.cfg.get("work_start", "09:00"))
        ttk.Entry(work_frame, textvariable=self.work_start_var, width=6).pack(side=LEFT)

        ttk.Label(work_frame, text="\u7ED3\u675F:").pack(side=LEFT, padx=(8, 2))
        self.work_end_var = ttk.StringVar(value=self.cfg.get("work_end", "18:00"))
        ttk.Entry(work_frame, textvariable=self.work_end_var, width=6).pack(side=LEFT)

        ttk.Label(work_frame, text="\u5348\u4F11\u5F00\u59CB:").pack(side=LEFT, padx=(8, 2))
        self.lunch_start_var = ttk.StringVar(value=self.cfg.get("lunch_start", "12:00"))
        ttk.Entry(work_frame, textvariable=self.lunch_start_var, width=6).pack(side=LEFT)

        ttk.Label(work_frame, text="\u5348\u4F11\u7ED3\u675F:").pack(side=LEFT, padx=(8, 2))
        self.lunch_end_var = ttk.StringVar(value=self.cfg.get("lunch_end", "13:00"))
        ttk.Entry(work_frame, textvariable=self.lunch_end_var, width=6).pack(side=LEFT)

        ttk.Label(work_frame, text="\u4F11\u606F\u65E5(0-6):").pack(side=LEFT, padx=(8, 2))
        self.rest_days_var = ttk.StringVar(value=",".join(map(str, self.cfg.get("rest_days", []))))
        ttk.Entry(work_frame, textvariable=self.rest_days_var, width=8).pack(side=LEFT)

        ttk.Button(work_frame, text="\u4FDD\u5B58\u65F6\u95F4",
                   command=self._save_reminder_params,
                   bootstyle="primary-outline" if TTKBOOTSTRAP_AVAILABLE else None).pack(side=LEFT, padx=10)

        # ---- 第二行：两个并排卡片 ----
        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill=BOTH, expand=True, pady=10)

        # 左侧：喝水钟
        water_card = ttk.Frame(cards_frame, padding=20)
        water_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        ttk.Label(water_card, text="\u559D\u6C34\u949F", font=("Microsoft YaHei", 14, "bold")).pack(anchor=NW, pady=(0, 10))

        self.water_enabled_var = ttk.BooleanVar(value=self.cfg.get("water_enabled", True))
        ttk.Checkbutton(water_card, text="\u542F\u7528", variable=self.water_enabled_var,
                        command=self._save_reminder_params).pack(anchor=NW)

        wf1 = ttk.Frame(water_card)
        wf1.pack(fill=X, pady=5)
        ttk.Label(wf1, text="\u95F4\u9694(\u5206):").pack(side=LEFT)
        self.water_interval_var = ttk.IntVar(value=self.cfg.get("water_interval", 45))
        ttk.Spinbox(wf1, from_=1, to=300, textvariable=self.water_interval_var, width=6).pack(side=LEFT, padx=3)

        wf1b = ttk.Frame(water_card)
        wf1b.pack(fill=X, pady=5)
        ttk.Label(wf1b, text="\u9501\u5C4F(\u79D2):").pack(side=LEFT)
        self.water_lock_var = ttk.IntVar(value=self.cfg.get("water_lock_duration", 30))
        ttk.Spinbox(wf1b, from_=5, to=600, textvariable=self.water_lock_var, width=6).pack(side=LEFT, padx=3)

        wf2 = ttk.Frame(water_card)
        wf2.pack(fill=X, pady=5)
        ttk.Label(wf2, text="\u63D0\u9192\u6587\u5B57:").pack(side=LEFT)
        self.water_message_var = ttk.StringVar(value=self.cfg.get("water_message", "\u559D\u53E3\u6C34\u5427"))
        ttk.Entry(wf2, textvariable=self.water_message_var, width=18).pack(side=LEFT, padx=3)

        self.water_repeat_var = ttk.BooleanVar(value=self.cfg.get("water_repeat", True))
        ttk.Checkbutton(water_card, text="\u91CD\u590D\u63D0\u9192", variable=self.water_repeat_var,
                        command=self._save_reminder_params).pack(anchor=NW)

        self.water_timer_label = ttk.Label(water_card, text="00:00", font=("Consolas", 36, "bold"),
                                           bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None)
        self.water_timer_label.pack(pady=10)

        self.water_progress = ttk.Progressbar(water_card, length=280, mode="determinate",
                                              bootstyle="info-striped" if TTKBOOTSTRAP_AVAILABLE else None)
        self.water_progress.pack(pady=5)

        self.water_status_label = ttk.Label(water_card, text="\u5DF2\u505C\u6B62", font=("Microsoft YaHei", 10))
        self.water_status_label.pack(pady=3)

        wf_btn = ttk.Frame(water_card)
        wf_btn.pack(pady=10)
        self.water_start_btn = ttk.Button(
            wf_btn, text="\u25B6  \u5F00\u59CB",
            command=self._toggle_water,
            bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None,
            width=12
        )
        self.water_start_btn.pack()

        # 右侧：休息钟
        rest_card = ttk.Frame(cards_frame, padding=20)
        rest_card.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 0))

        ttk.Label(rest_card, text="\u4F11\u606F\u949F", font=("Microsoft YaHei", 14, "bold")).pack(anchor=NW, pady=(0, 10))

        self.rest_enabled_var = ttk.BooleanVar(value=self.cfg.get("rest_enabled", True))
        ttk.Checkbutton(rest_card, text="\u542F\u7528", variable=self.rest_enabled_var,
                        command=self._save_reminder_params).pack(anchor=NW)

        rf1 = ttk.Frame(rest_card)
        rf1.pack(fill=X, pady=5)
        ttk.Label(rf1, text="\u95F4\u9694(\u5206):").pack(side=LEFT)
        self.rest_interval_var = ttk.IntVar(value=self.cfg.get("rest_interval", 60))
        ttk.Spinbox(rf1, from_=1, to=300, textvariable=self.rest_interval_var, width=6).pack(side=LEFT, padx=3)

        rf1b = ttk.Frame(rest_card)
        rf1b.pack(fill=X, pady=5)
        ttk.Label(rf1b, text="\u9501\u5C4F(\u79D2):").pack(side=LEFT)
        self.rest_lock_var = ttk.IntVar(value=self.cfg.get("rest_lock_duration", 180))
        ttk.Spinbox(rf1b, from_=5, to=600, textvariable=self.rest_lock_var, width=6).pack(side=LEFT, padx=3)

        rf2 = ttk.Frame(rest_card)
        rf2.pack(fill=X, pady=5)
        ttk.Label(rf2, text="\u63D0\u9192\u6587\u5B57:").pack(side=LEFT)
        self.rest_message_var = ttk.StringVar(value=self.cfg.get("rest_message", "\u4F11\u606F\u4E00\u4E0B\u5427"))
        ttk.Entry(rf2, textvariable=self.rest_message_var, width=18).pack(side=LEFT, padx=3)

        self.rest_repeat_var = ttk.BooleanVar(value=self.cfg.get("rest_repeat", True))
        ttk.Checkbutton(rest_card, text="\u91CD\u590D\u63D0\u9192", variable=self.rest_repeat_var,
                        command=self._save_reminder_params).pack(anchor=NW)

        self.rest_timer_label = ttk.Label(rest_card, text="00:00", font=("Consolas", 36, "bold"),
                                          bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None)
        self.rest_timer_label.pack(pady=10)

        self.rest_progress = ttk.Progressbar(rest_card, length=280, mode="determinate",
                                             bootstyle="success-striped" if TTKBOOTSTRAP_AVAILABLE else None)
        self.rest_progress.pack(pady=5)

        self.rest_status_label = ttk.Label(rest_card, text="\u5DF2\u505C\u6B62", font=("Microsoft YaHei", 10))
        self.rest_status_label.pack(pady=3)

        rf_btn = ttk.Frame(rest_card)
        rf_btn.pack(pady=10)
        self.rest_start_btn = ttk.Button(
            rf_btn, text="\u25B6  \u5F00\u59CB",
            command=self._toggle_rest,
            bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None,
            width=12
        )
        self.rest_start_btn.pack()

    def _save_reminder_params(self):
        self.cfg["work_start"] = self.work_start_var.get()
        self.cfg["work_end"] = self.work_end_var.get()
        self.cfg["lunch_start"] = self.lunch_start_var.get()
        self.cfg["lunch_end"] = self.lunch_end_var.get()
        try:
            rd = [int(x.strip()) for x in self.rest_days_var.get().split(",") if x.strip() != ""]
            self.cfg["rest_days"] = rd
        except Exception:
            self.cfg["rest_days"] = []
        self.cfg["water_enabled"] = self.water_enabled_var.get()
        self.cfg["water_repeat"] = self.water_repeat_var.get()
        self.cfg["water_interval"] = self.water_interval_var.get()
        self.cfg["water_message"] = self.water_message_var.get()
        self.cfg["water_lock_duration"] = self.water_lock_var.get()
        self.cfg["rest_enabled"] = self.rest_enabled_var.get()
        self.cfg["rest_repeat"] = self.rest_repeat_var.get()
        self.cfg["rest_interval"] = self.rest_interval_var.get()
        self.cfg["rest_message"] = self.rest_message_var.get()
        self.cfg["rest_lock_duration"] = self.rest_lock_var.get()
        self.cfg["watchdog"] = self.watchdog_var.get()
        self.cfg["auto_start"] = self.auto_start_var.get()
        save_config(self.cfg)
        if TTKBOOTSTRAP_AVAILABLE:
            Messagebox.show_info("\u53C2\u6570\u5DF2\u4FDD\u5B58", "\u6210\u529F")
        else:
            Messagebox.showinfo("\u6210\u529F", "\u53C2\u6570\u5DF2\u4FDD\u5B58")

    # ------ 语录 ------
    def _build_quotes(self, parent):
        ttk.Label(parent, text="\u8BED\u5F55\u5E93", font=("Microsoft YaHei", 18, "bold")).pack(anchor=NW, pady=(0, 15))

        opts = ttk.Frame(parent)
        opts.pack(fill=X, pady=(0, 10))

        self.quote_repeat_var = ttk.BooleanVar(value=self.cfg.get("quotes_allow_repeat", False))
        ttk.Checkbutton(
            opts, text="\u5141\u8BB8\u91CD\u590D\u663E\u793A",
            variable=self.quote_repeat_var,
            command=self._save_quote_settings
        ).pack(side=LEFT)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=True)

        ttk.Label(list_frame, text="\u7F16\u8F91\u8BED\u5F55 (\u6BCF\u884C\u4E00\u6761)", font=("Microsoft YaHei", 11)).pack(anchor=NW, pady=(0, 5))

        self.quote_text = ttk.Text(list_frame, height=14, wrap=WORD)
        self.quote_text.pack(fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.quote_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.quote_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.quote_text.yview)

        if self.all_quotes:
            self.quote_text.insert(END, "\n".join(self.all_quotes))

        btn_row = ttk.Frame(parent)
        btn_row.pack(pady=10)

        ttk.Button(btn_row, text="\u4FDD\u5B58\u8BED\u5F55",
                   command=self._save_quotes_from_ui,
                   bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None,
                   width=12).pack(side=LEFT, padx=5)

        ttk.Button(btn_row, text="\u6E05\u7A7A\u8BED\u5F55",
                   command=self._clear_quotes,
                   bootstyle="danger-outline" if TTKBOOTSTRAP_AVAILABLE else None,
                   width=12).pack(side=LEFT, padx=5)

    def _save_quote_settings(self):
        self.cfg["quotes_allow_repeat"] = self.quote_repeat_var.get()
        save_config(self.cfg)

    def _save_quotes_from_ui(self):
        text = self.quote_text.get("1.0", END).strip()
        quotes = [line.strip() for line in text.split("\n") if line.strip()]
        self.all_quotes = quotes
        save_quotes(quotes)
        if TTKBOOTSTRAP_AVAILABLE:
            Messagebox.show_info(f"\u5DF2\u4FDD\u5B58 {len(quotes)} \u6761\u8BED\u5F55", "\u6210\u529F")
        else:
            Messagebox.showinfo("\u6210\u529F", f"\u5DF2\u4FDD\u5B58 {len(quotes)} \u6761\u8BED\u5F55")

    def _clear_quotes(self):
        self.all_quotes = []
        self.quote_text.delete("1.0", END)
        save_quotes([])

    # ------ 统计 ------
    def _build_stats(self, parent):
        # 创建 Canvas + Scrollbar 实现滚动
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Canvas 大小变化时，更新 scrollable_frame 宽度
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 保存引用以便清理
        self._stats_canvas = canvas
        self._stats_scrollbar = scrollbar

        ttk.Label(scrollable_frame, text="\u7EDF\u8BA1", font=("Microsoft YaHei", 18, "bold")).pack(anchor=NW, pady=(0, 15))

        data_frame = ttk.Frame(scrollable_frame)
        data_frame.pack(pady=10, fill=X)

        water_count = get_today_water_count()
        rest_count = get_today_rest_count()

        cards_data = [
            ("\u4ECA\u65E5\u559D\u6C34", str(water_count), "\u6B21"),
            ("\u4ECA\u65E5\u4F11\u606F", str(rest_count), "\u6B21"),
        ]

        self.stats_value_labels = {}
        for title, value, unit in cards_data:
            c = ttk.Frame(data_frame, padding=20)
            c.pack(side=LEFT, padx=8, expand=True, fill=BOTH)
            val_label = ttk.Label(c, text=value, font=("Consolas", 36, "bold"))
            val_label.pack()
            self.stats_value_labels[title] = val_label
            ttk.Label(c, text=title, font=("Microsoft YaHei", 10)).pack()
            ttk.Label(c, text=unit, font=("Microsoft YaHei", 9)).pack()

        # 连续打卡卡片
        streak_frame = ttk.Frame(scrollable_frame, padding=15)
        streak_frame.pack(fill=X, pady=(10, 5))

        ttk.Label(streak_frame, text="\u8FDE\u7EED\u6253\u5361",
                  font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 8))

        streak = get_streak_days()
        streak_data = [
            ("\u8FDE\u7EED\u6253\u5361", f"{streak['current']} \u5929"),
            ("\u6700\u957F\u8FDE\u7EED", f"{streak['longest']} \u5929"),
            ("\u4E0A\u6B21\u6253\u5361", streak['last_date'] or "\u6682\u65E0"),
        ]

        streak_cards = ttk.Frame(streak_frame)
        streak_cards.pack(fill=X)

        self.streak_value_labels = {}
        for title, value in streak_data:
            c = ttk.Frame(streak_cards, padding=15)
            c.pack(side=LEFT, padx=8, expand=True, fill=BOTH)
            val_label = ttk.Label(c, text=value, font=("Consolas", 20, "bold"))
            val_label.pack()
            self.streak_value_labels[title] = val_label
            ttk.Label(c, text=title, font=("Microsoft YaHei", 9)).pack()

        # 本周峰值卡片
        peak_frame = ttk.Frame(scrollable_frame, padding=15)
        peak_frame.pack(fill=X, pady=(10, 5))

        ttk.Label(peak_frame, text="\u672C\u5468\u5CF0\u503C",
                  font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 8))

        peak = get_weekly_peak()
        peak_day_str = "\u6682\u65E0"
        if peak['peak_day']:
            peak_day_str = f"{peak['peak_day'][5:7]}\u6708{peak['peak_day'][8:]}\u65E5 ({peak['peak_day_count']}\u6B21)"
        peak_hour_str = "\u6682\u65E0"
        if peak['peak_hour']:
            peak_hour_str = f"{peak['peak_hour']}:00 ({peak['peak_hour_count']}\u6B21)"

        peak_data = [
            ("\u672C\u5468\u9501\u5C4F", f"{peak['total_this_week']} \u6B21"),
            ("\u6700\u6D3B\u8DC3\u65E5\u671F", peak_day_str),
            ("\u6700\u6D3B\u8DC3\u65F6\u6BB5", peak_hour_str),
        ]

        peak_cards = ttk.Frame(peak_frame)
        peak_cards.pack(fill=X)

        self.peak_value_labels = {}
        for title, value in peak_data:
            c = ttk.Frame(peak_cards, padding=15)
            c.pack(side=LEFT, padx=8, expand=True, fill=BOTH)
            val_label = ttk.Label(c, text=value, font=("Consolas", 16, "bold"))
            val_label.pack()
            self.peak_value_labels[title] = val_label
            ttk.Label(c, text=title, font=("Microsoft YaHei", 9)).pack()

        # 图表区域
        chart_frame = ttk.Frame(scrollable_frame, padding=15)
        chart_frame.pack(fill=X, pady=(10, 5))

        ttk.Label(chart_frame, text="\u672C\u5468\u4E13\u6CE8\u8D8B\u52BF",
                  font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 8))

        self.chart_label = ttk.Label(chart_frame, text="\u70B9\u51FB\u5237\u65B0\u56FE\u8868\u6309\u94AE\u67E5\u770B\u672C\u5468\u8D8B\u52BF")
        self.chart_label.pack()

        ttk.Button(
            chart_frame, text="\u5237\u65B0\u56FE\u8868",
            command=self._refresh_chart,
            bootstyle="primary-outline" if TTKBOOTSTRAP_AVAILABLE else None
        ).pack(pady=(8, 0))

        # 导出按钮
        export_frame = ttk.Frame(scrollable_frame, padding=15)
        export_frame.pack(fill=X, pady=(5, 10))

        ttk.Button(
            export_frame, text="\u5BFC\u51CACSV",
            command=self._export_csv,
            bootstyle="primary-outline" if TTKBOOTSTRAP_AVAILABLE else None
        ).pack()

        # 热键使用记录
        hk_frame = ttk.Frame(scrollable_frame, padding=15)
        hk_frame.pack(fill=BOTH, expand=True, pady=15)

        ttk.Label(hk_frame, text="\u5FEB\u6377\u952E\u4F7F\u7528\u8BB0\u5F55 (\u8FD17\u5929)",
                  font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 8))

        hk_data = get_hotkey_stats(7)

        daily_frame = ttk.Frame(hk_frame)
        daily_frame.pack(fill=X, pady=5)

        if hk_data["daily"]:
            for i in range(6, -1, -1):
                d = (date.today() - timedelta(days=i)).isoformat()
                count = hk_data["daily"].get(d, 0)
                day_label = d[5:]
                sf = ttk.Frame(daily_frame)
                sf.pack(side=LEFT, padx=5, expand=True)
                ttk.Label(sf, text=str(count), font=("Consolas", 18, "bold")).pack()
                ttk.Label(sf, text=day_label, font=("Microsoft YaHei", 9)).pack()
        else:
            ttk.Label(daily_frame, text="\u6682\u65E0\u8BB0\u5F55", font=("Microsoft YaHei", 11)).pack()

        ttk.Label(hk_frame, text=f"\u8FD17\u5929\u5408\u8BA1: {hk_data['total']} \u6B21",
                  font=("Microsoft YaHei", 11)).pack(anchor=W, pady=(5, 0))

        # 破防日志
        log_frame = ttk.Frame(scrollable_frame, padding=15)
        log_frame.pack(fill=BOTH, expand=True, pady=15)

        ttk.Label(log_frame, text="\u7834\u9632\u65E5\u5FD7", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 8))

        log_text = ttk.Text(log_frame, height=8, wrap=WORD)
        log_text.pack(fill=BOTH, expand=True)

        log_scrollbar = ttk.Scrollbar(log_text)
        log_scrollbar.pack(side=RIGHT, fill=Y)
        log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.config(command=log_text.yview)

        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                    log_text.insert(END, content if content else "\u6682\u65E0\u7834\u9632\u8BB0\u5F55")
            else:
                log_text.insert(END, "\u6682\u65E0\u7834\u9632\u8BB0\u5F55")
        except Exception:
            log_text.insert(END, "\u8BFB\u53D6\u65E5\u5FD7\u5931\u8D25")

        log_text.config(state=DISABLED)

        ttk.Button(
            log_frame, text="\u4E00\u952E\u6E05\u7A7A\u7834\u9632\u65E5\u5FD7",
            command=self._clear_log,
            bootstyle="danger-outline" if TTKBOOTSTRAP_AVAILABLE else None
        ).pack(pady=(8, 0))

    # ------ 设置 ------
    def _build_settings(self, parent):
        ttk.Label(parent, text="\u8BBE\u7F6E", font=("Microsoft YaHei", 18, "bold")).pack(anchor=NW, pady=(0, 15))

        set_main = ttk.Frame(parent)
        set_main.pack(fill=BOTH, expand=True)

        left = ttk.Frame(set_main)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

        theme_frame = ttk.Frame(left, padding=15)
        theme_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(theme_frame, text="\u4E3B\u9898\u8BBE\u7F6E", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 10))

        tr = ttk.Frame(theme_frame)
        tr.pack(fill=X)

        ttk.Label(tr, text="\u4E3B\u9898\u98CE\u683C:").pack(side=LEFT)

        self.theme_var = ttk.StringVar(value=self.cfg.get("theme", "cosmo"))
        theme_cb = ttk.Combobox(
            tr, textvariable=self.theme_var,
            values=AVAILABLE_THEMES, width=16, state="readonly"
        )
        theme_cb.pack(side=LEFT, padx=8)
        theme_cb.bind("<<ComboboxSelected>>", self._on_theme_change)

        ttk.Button(tr, text="\u5E94\u7528\u4E3B\u9898",
                   command=self._apply_theme,
                   bootstyle="primary-outline" if TTKBOOTSTRAP_AVAILABLE else None
                   ).pack(side=LEFT)

        hk_frame = ttk.Frame(left, padding=15)
        hk_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(hk_frame, text="\u5FEB\u6377\u952E", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 10))

        hkr = ttk.Frame(hk_frame)
        hkr.pack(fill=X)

        ttk.Label(hkr, text="\u5168\u5C40\u5FEB\u6377\u952E:").pack(side=LEFT)
        self.hk_var = ttk.StringVar(value=self.cfg.get("hotkey", "alt+p"))
        hk_entry = ttk.Entry(hkr, textvariable=self.hk_var, width=18)
        hk_entry.pack(side=LEFT, padx=8)

        shk_row = ttk.Frame(hk_frame)
        shk_row.pack(fill=X, pady=3)
        ttk.Label(shk_row, text="\u663E\u793A\u7A97\u53E3\u5FEB\u6377\u952E:").pack(side=LEFT)
        self.show_hotkey_var = ttk.StringVar(value=self.cfg.get("show_hotkey", "alt+o"))
        ttk.Entry(shk_row, textvariable=self.show_hotkey_var, width=15).pack(side=LEFT, padx=5)
        ttk.Button(hkr, text="\u4FEE\u6539",
                   command=self._change_hotkey,
                   bootstyle="primary-outline" if TTKBOOTSTRAP_AVAILABLE else None
                   ).pack(side=LEFT)

        ttk.Label(hk_frame, text="\u793A\u4F8B: alt+p, ctrl+shift+f1, alt+space",
                  font=("Microsoft YaHei", 9)).pack(anchor=W, pady=(4, 0))

        # 系统设置
        sys_frame = ttk.Frame(left, padding=15)
        sys_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(sys_frame, text="\u7CFB\u7EDF\u8BBE\u7F6E", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 10))

        # 开机自启
        auto_row = ttk.Frame(sys_frame)
        auto_row.pack(fill=X, pady=3)
        self.auto_start_var = ttk.BooleanVar(value=self.cfg.get("auto_start", False))
        ttk.Checkbutton(
            auto_row, text="\u5F00\u673A\u81EA\u52A8\u542F\u52A8",
            variable=self.auto_start_var,
            command=self._toggle_auto_start
        ).pack(side=LEFT)

        # 看门狗
        wd_row = ttk.Frame(sys_frame)
        wd_row.pack(fill=X, pady=3)
        self.watchdog_var = ttk.BooleanVar(value=self.cfg.get("watchdog", False))
        ttk.Checkbutton(
            wd_row, text="\u770B\u95E8\u72D7\u8FDB\u7A0B\u5B88\u62A4\uff08\u5D29\u6E83\u65F6\u81EA\u52A8\u91CD\u542F\uff09",
            variable=self.watchdog_var,
            command=self._toggle_watchdog
        ).pack(side=LEFT)

        right = ttk.Frame(set_main)
        right.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 0))

        lock_frame = ttk.Frame(right, padding=15)
        lock_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(lock_frame, text="\u9501\u5C4F\u8BBE\u7F6E", font=("Microsoft YaHei", 13, "bold")).pack(anchor=NW, pady=(0, 10))

        lr1 = ttk.Frame(lock_frame)
        lr1.pack(fill=X, pady=3)
        ttk.Label(lr1, text="\u521D\u59CB\u9501\u5C4F(\u79D2):").pack(side=LEFT)
        self.lock_var = ttk.IntVar(value=self.cfg.get("initial_lock", 30))
        ttk.Spinbox(lr1, from_=10, to=300, textvariable=self.lock_var, width=8).pack(side=LEFT, padx=5)

        lr2 = ttk.Frame(lock_frame)
        lr2.pack(fill=X, pady=3)
        ttk.Label(lr2, text="ESC\u9000\u51FA\u9608\u503C:").pack(side=LEFT)
        self.esc_var = ttk.IntVar(value=self.cfg.get("esc_threshold", 3))
        ttk.Spinbox(lr2, from_=1, to=10, textvariable=self.esc_var, width=8).pack(side=LEFT, padx=5)

        lr3 = ttk.Frame(lock_frame)
        lr3.pack(fill=X, pady=3)
        ttk.Label(lr3, text="\u8BED\u5F55\u5B57\u53F7:").pack(side=LEFT)
        self.lock_quote_font_var = ttk.IntVar(value=self.cfg.get("lock_quote_font_size", 28))
        ttk.Spinbox(lr3, from_=12, to=72, textvariable=self.lock_quote_font_var, width=6).pack(side=LEFT, padx=5)

        lr4 = ttk.Frame(lock_frame)
        lr4.pack(fill=X, pady=3)
        ttk.Label(lr4, text="\u8BA1\u65F6\u5B57\u53F7:").pack(side=LEFT)
        self.lock_timer_font_var = ttk.IntVar(value=self.cfg.get("lock_timer_font_size", 36))
        ttk.Spinbox(lr4, from_=12, to=72, textvariable=self.lock_timer_font_var, width=6).pack(side=LEFT, padx=5)

        save_btn_frame = ttk.Frame(right)
        save_btn_frame.pack(fill=X, pady=15)

        ttk.Button(
            save_btn_frame, text="\u4FDD\u5B58\u6240\u6709\u8BBE\u7F6E",
            command=self._save_all_settings,
            bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None,
            width=20
        ).pack()

    # ==================== 逻辑 ====================

    def _on_theme_change(self, event=None):
        self._apply_theme()

    def _apply_theme(self):
        if not TTKBOOTSTRAP_AVAILABLE:
            return
        theme = self.theme_var.get()
        try:
            self.root.style.theme_use(theme)
            self.cfg["theme"] = theme
            save_config(self.cfg)
            self.status_var.set(f"\u4E3B\u9898\u5DF2\u5207\u6362: {theme}")
        except Exception as e:
            log(f"\u5207\u6362\u4E3B\u9898\u5931\u8D25: {e}")

    def _change_hotkey(self):
        new_hk = self.hk_var.get().strip().lower()
        if not new_hk:
            return
        self.cfg["hotkey"] = new_hk
        self._stop_hotkey()
        self._start_hotkey()
        save_config(self.cfg)
        if hasattr(self, 'hk_display'):
            self.hk_display.config(text=new_hk)

    def _start_hotkey(self):
        """启动全局热键（Windows 原生 API 优先，最可靠）"""
        hk = self.cfg.get("hotkey", "alt+p")

        # 方案 A: Windows 原生 RegisterHotKey（最可靠，无需管理员权限）
        try:
            self.win_hotkey = WindowsHotkey()
            # 回调在子线程执行，必须用 root.after 派发到主线程
            self.win_hotkey.start(hk, lambda: self.root.after(0, self._on_hotkey_triggered))
            self.status_var.set(f"\u5FEB\u6377\u952E\u5DF2\u542F\u7528: {hk}")
            self._hotkey_type = "winapi"
            log(f"\u5FEB\u6377\u952E\u5DF2\u542F\u7528 (WinAPI): {hk}")
        except Exception as e:
            log(f"Windows \u539F\u751F\u70ED\u952E\u5931\u8D25: {e}")
            self._hotkey_type = None

        # \u663E\u793A\u7A97\u53E3\u70ED\u952E
        show_hk = self.cfg.get("show_hotkey", "alt+o")
        try:
            self.win_show_hotkey = WindowsHotkey()
            show_callback = lambda: self.root.after(0, self._show_window_from_hotkey)
            self.win_show_hotkey.start(show_hk, show_callback)
            log(f"\u663E\u793A\u7A97\u53E3\u70ED\u952E\u5DF2\u542F\u7528 (WinAPI): {show_hk}")
        except Exception as e:
            log(f"[\u663E\u793A\u70ED\u952E] \u6CE8\u518C\u5931\u8D25: {e}")
            self.win_show_hotkey = None

        # \u5982\u679C\u9501\u5C4F\u70ED\u952E\u5DF2\u6210\u529F\uFF0C\u65E0\u9700\u7EE7\u7EED fallback
        if getattr(self, '_hotkey_type', None) == "winapi":
            return

        # 方案 B: keyboard 库（需要管理员权限）
        if KEYBOARD_AVAILABLE:
            try:
                def on_hotkey():
                    try:
                        self.root.after(0, self._on_hotkey_triggered)
                    except Exception:
                        pass

                keyboard_global.add_hotkey(hk, on_hotkey, suppress=False)
                self.status_var.set(f"\u5FEB\u6377\u952E\u5DF2\u542F\u7528: {hk}")
                self._hotkey_type = "keyboard"
                log(f"\u5FEB\u6377\u952E\u5DF2\u542F\u7528 (keyboard): {hk}")
                return
            except Exception as e:
                log(f"keyboard \u5E93\u70ED\u952E\u5931\u8D25: {e}")

        self.status_var.set("\u70ED\u952E\u542F\u7528\u5931\u8D25")
    def _on_hotkey_triggered(self):
        """热键触发回调——Windows 原生热键直接调用，无需 after(0)"""
        log("[\u70ED\u952E] _on_hotkey_triggered \u88AB\u8C03\u7528")
        # 只有新建锁屏时才记录，累加时间不算新锁屏
        if self.lock_window is None or self.lock_window.root is None or not self.lock_window.root.winfo_exists():
            record_hotkey_press()
        self.trigger_lock()

    def _show_window_from_hotkey(self):
        """热键触发切换窗口显示/隐藏"""
        log("[热键] Alt+O 切换窗口")
        try:
            if self.root.state() == 'withdrawn' or not self.root.winfo_viewable():
                # 窗口被隐藏，显示它
                self._show_window()
            else:
                # 窗口可见，隐藏到托盘
                self._hide_to_tray()
        except Exception as e:
            log(f"[热键] 切换窗口异常: {e}")
    def _stop_hotkey(self):
        """停止热键（仅在退出或变更热键时调用）"""
        if self.win_hotkey:
            try:
                self.win_hotkey.stop()
            except Exception:
                pass
            self.win_hotkey = None
        if self.win_show_hotkey:
            try:
                self.win_show_hotkey.stop()
            except Exception:
                pass
            self.win_show_hotkey = None
        if getattr(self, '_hotkey_type', None) == "keyboard" and KEYBOARD_AVAILABLE:
            try:
                keyboard_global.unhook_all()
            except Exception:
                pass

    def trigger_lock(self, is_water_reminder=False, reminder_text=None, lock_duration=None):
        if self.lock_window is not None and self.lock_window.root is not None and self.lock_window.root.winfo_exists():
            # 锁屏已存在，增加 30 秒
            self.lock_window.remaining += 30
            self.lock_window.timer_label.config(text=self.lock_window._fmt(self.lock_window.remaining))
            self.status_var.set("\u9501\u5C4F\u65F6\u95F4 +30\u79D2")
        else:
            # 新建锁屏
            self.lock_window = LockWindow(self, is_water_reminder=is_water_reminder, reminder_text=reminder_text, lock_duration=lock_duration)
            self.lock_window.show()

    def on_unlock(self):
        self.lock_window = None
        self.today_water_count = get_today_water_count()
        self.today_rest_count = get_today_rest_count()
        self._refresh_home_stats()
        if self.current_tab == "stats":
            self._refresh_stats_display()

    def _toggle_water(self):
        if not self.water_running:
            self._start_water()
        else:
            self._stop_water()

    def _start_water(self):
        if not self.water_enabled_var.get():
            self.status_var.set("\u559D\u6C34\u949F\u672A\u542F\u7528")
            return
        interval = self.water_interval_var.get()
        if interval <= 0:
            return
        self.water_running = True
        self.water_remaining = interval * 60
        self.water_total = self.water_remaining
        self.water_start_btn.config(text="\u25A0  \u505C\u6B62", bootstyle="danger" if TTKBOOTSTRAP_AVAILABLE else None)
        self.water_status_label.config(text="\u8FD0\u884C\u4E2D")
        self._save_water_remaining()
        self._water_tick()

    def _stop_water(self):
        self.water_running = False
        if self.water_timer_id:
            try:
                self.root.after_cancel(self.water_timer_id)
            except Exception:
                pass
            self.water_timer_id = None
        self.water_start_btn.config(text="\u25B6  \u5F00\u59CB", bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None)
        self.water_status_label.config(text="\u5DF2\u505C\u6B62")
        self.water_timer_label.config(text="00:00")
        self.water_progress.config(value=0)

    def _water_tick(self):
        if not self.water_running:
            return

        if self.water_remaining > 0:
            self.water_remaining -= 1
            m, s = divmod(self.water_remaining, 60)
            self.water_timer_label.config(text=f"{m:02d}:{s:02d}")
            pct = (self.water_total - self.water_remaining) / self.water_total * 100
            self.water_progress.config(value=pct)

            if not self._is_work_time():
                self.status_var.set("\u975E\u5DE5\u4F5C\u65F6\u95F4\uFF0C\u6682\u505C\u63D0\u9192")
            else:
                self.status_var.set("\u559D\u6C34\u949F\u8FD0\u884C\u4E2D")

            # 每10秒保存一次剩余时间，避免频繁IO
            if self.water_remaining % 10 == 0:
                self._save_water_remaining()

            self.water_timer_id = self.root.after(1000, self._water_tick)
        else:
            self._water_trigger()

    def _water_trigger(self):
        if self._is_work_time():
            msg = self.water_message_var.get()
            lock_dur = self.water_lock_var.get()
            self.trigger_lock(is_water_reminder=True, reminder_text=msg, lock_duration=lock_dur)
        # 更新时间戳
        self.cfg["water_last_time"] = datetime.now().isoformat()
        save_config(self.cfg)
        if self.water_repeat_var.get():
            self.water_remaining = self.water_interval_var.get() * 60
            self.water_total = self.water_remaining
            self.water_progress.config(value=0)
            self._water_tick()
        else:
            self._stop_water()

    def _toggle_rest(self):
        if not self.rest_running:
            self._start_rest()
        else:
            self._stop_rest()

    def _start_rest(self):
        if not self.rest_enabled_var.get():
            self.status_var.set("\u4F11\u606F\u949F\u672A\u542F\u7528")
            return
        interval = self.rest_interval_var.get()
        if interval <= 0:
            return
        self.rest_running = True
        self.rest_remaining = interval * 60
        self.rest_total = self.rest_remaining
        self.rest_start_btn.config(text="\u25A0  \u505C\u6B62", bootstyle="danger" if TTKBOOTSTRAP_AVAILABLE else None)
        self.rest_status_label.config(text="\u8FD0\u884C\u4E2D")
        self._save_rest_remaining()
        self._rest_tick()

    def _stop_rest(self):
        self.rest_running = False
        if self.rest_timer_id:
            try:
                self.root.after_cancel(self.rest_timer_id)
            except Exception:
                pass
            self.rest_timer_id = None
        self.rest_start_btn.config(text="\u25B6  \u5F00\u59CB", bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None)
        self.rest_status_label.config(text="\u5DF2\u505C\u6B62")
        self.rest_timer_label.config(text="00:00")
        self.rest_progress.config(value=0)

    def _rest_tick(self):
        if not self.rest_running:
            return

        if self.rest_remaining > 0:
            self.rest_remaining -= 1
            m, s = divmod(self.rest_remaining, 60)
            self.rest_timer_label.config(text=f"{m:02d}:{s:02d}")
            pct = (self.rest_total - self.rest_remaining) / self.rest_total * 100
            self.rest_progress.config(value=pct)

            if not self._is_work_time():
                self.status_var.set("\u975E\u5DE5\u4F5C\u65F6\u95F4\uFF0C\u6682\u505C\u63D0\u9192")
            else:
                self.status_var.set("\u4F11\u606F\u949F\u8FD0\u884C\u4E2D")

            if self.rest_remaining % 10 == 0:
                self._save_rest_remaining()

            self.rest_timer_id = self.root.after(1000, self._rest_tick)
        else:
            self._rest_trigger()

    def _rest_trigger(self):
        if self._is_work_time():
            msg = self.rest_message_var.get()
            lock_dur = self.rest_lock_var.get()
            self.trigger_lock(reminder_text=msg, lock_duration=lock_dur)
            record_rest()
            self._refresh_home_stats()
            if self.current_tab == "stats":
                self._refresh_stats_display()
        # 更新时间戳
        self.cfg["rest_last_time"] = datetime.now().isoformat()
        save_config(self.cfg)
        if self.rest_repeat_var.get():
            self.rest_remaining = self.rest_interval_var.get() * 60
            self.rest_total = self.rest_remaining
            self.rest_progress.config(value=0)
            self._rest_tick()
        else:
            self._stop_rest()

    def _is_work_time(self) -> bool:
        now = datetime.now()
        weekday = now.weekday()
        rest_days = self.cfg.get("rest_days", [])
        if weekday in rest_days:
            return False

        try:
            current = now.strftime("%H:%M")
            work_start = self.cfg.get("work_start", "09:00")
            work_end = self.cfg.get("work_end", "18:00")
            lunch_start = self.cfg.get("lunch_start", "12:00")
            lunch_end = self.cfg.get("lunch_end", "13:00")

            if current < work_start or current > work_end:
                return False
            if lunch_start <= current <= lunch_end:
                return False
        except Exception:
            pass
        return True

    def _save_water_remaining(self):
        """保存喝水钟剩余秒数到配置"""
        self.cfg["water_remaining_save"] = self.water_remaining
        self.cfg["water_total_save"] = self.water_total
        save_config(self.cfg)

    def _save_rest_remaining(self):
        """保存休息钟剩余秒数到配置"""
        self.cfg["rest_remaining_save"] = self.rest_remaining
        self.cfg["rest_total_save"] = self.rest_total
        save_config(self.cfg)

    def _auto_start_timers(self):
        """程序启动后自动恢复并启动喝水钟和休息钟（基于剩余秒数，不依赖系统时间）"""

        # 喝水钟自动恢复
        if self.water_enabled_var.get():
            saved_remaining = self.cfg.get("water_remaining_save", 0)
            saved_total = self.cfg.get("water_total_save", 0)
            interval_sec = self.water_interval_var.get() * 60

            if saved_remaining > 0 and saved_total > 0:
                # 有保存的剩余时间，恢复继续
                self.water_remaining = saved_remaining
                self.water_total = saved_total if saved_total > 0 else interval_sec
                self.water_running = True
                pct = (self.water_total - self.water_remaining) / self.water_total * 100
                m, s = divmod(self.water_remaining, 60)
                self.water_timer_label.config(text=f"{m:02d}:{s:02d}")
                self.water_progress.config(value=pct)
                self.water_start_btn.config(text="\u25A0  \u505C\u6B62", bootstyle="danger" if TTKBOOTSTRAP_AVAILABLE else None)
                self.water_status_label.config(text="\u8FD0\u884C\u4E2D")
                self._water_tick()
                self.status_var.set("\u559D\u6C34\u949F\u5DF2\u81EA\u52A8\u6062\u590D\u8FD0\u884C")
            else:
                # 没有保存的状态，从头开始
                self._start_water()

        # 休息钟自动恢复
        if self.rest_enabled_var.get():
            saved_remaining = self.cfg.get("rest_remaining_save", 0)
            saved_total = self.cfg.get("rest_total_save", 0)
            interval_sec = self.rest_interval_var.get() * 60

            if saved_remaining > 0 and saved_total > 0:
                self.rest_remaining = saved_remaining
                self.rest_total = saved_total if saved_total > 0 else interval_sec
                self.rest_running = True
                pct = (self.rest_total - self.rest_remaining) / self.rest_total * 100
                m, s = divmod(self.rest_remaining, 60)
                self.rest_timer_label.config(text=f"{m:02d}:{s:02d}")
                self.rest_progress.config(value=pct)
                self.rest_start_btn.config(text="\u25A0  \u505C\u6B62", bootstyle="danger" if TTKBOOTSTRAP_AVAILABLE else None)
                self.rest_status_label.config(text="\u8FD0\u884C\u4E2D")
                self._rest_tick()
                self.status_var.set("\u4F11\u606F\u949F\u5DF2\u81EA\u52A8\u6062\u590D\u8FD0\u884C")
            else:
                self._start_rest()

    def _toggle_auto_start(self):
        """切换开机自启"""
        enabled = self.auto_start_var.get()
        if enabled:
            if AutoStartManager.enable():
                self.cfg["auto_start"] = True
                save_config(self.cfg)
                self.status_var.set("\u5F00\u673A\u81EA\u542F\u5DF2\u5F00\u542F")
            else:
                self.auto_start_var.set(False)
                self.status_var.set("\u5F00\u673A\u81EA\u542F\u8BBE\u7F6E\u5931\u8D25")
        else:
            if AutoStartManager.disable():
                self.cfg["auto_start"] = False
                save_config(self.cfg)
                self.status_var.set("\u5F00\u673A\u81EA\u542F\u5DF2\u5173\u95ED")
            else:
                self.auto_start_var.set(True)
                self.status_var.set("\u53D6\u6D88\u5F00\u673A\u81EA\u542F\u5931\u8D25")

    def _toggle_watchdog(self):
        """切换看门狗"""
        enabled = self.watchdog_var.get()
        if enabled:
            if not hasattr(self, '_watchdog'):
                self._watchdog = Watchdog()
            self._watchdog.start()
            self.cfg["watchdog"] = True
            save_config(self.cfg)
            self.status_var.set("\u770B\u95E8\u72D7\u5DF2\u5F00\u542F")
        else:
            if hasattr(self, '_watchdog'):
                self._watchdog.stop()
            self.cfg["watchdog"] = False
            save_config(self.cfg)
            self.status_var.set("\u770B\u95E8\u72D7\u5DF2\u5173\u95ED")

    def _save_all_settings(self):
        self.cfg["initial_lock"] = self.lock_var.get()
        self.cfg["esc_threshold"] = self.esc_var.get()
        self.cfg["lock_quote_font_size"] = self.lock_quote_font_var.get()
        self.cfg["lock_timer_font_size"] = self.lock_timer_font_var.get()
        self.cfg["watchdog"] = self.watchdog_var.get()
        self.cfg["auto_start"] = self.auto_start_var.get()
        self.cfg["show_hotkey"] = self.show_hotkey_var.get()
        save_config(self.cfg)

        if TTKBOOTSTRAP_AVAILABLE:
            Messagebox.show_info("\u8BBE\u7F6E\u5DF2\u4FDD\u5B58", "\u6210\u529F")
        else:
            Messagebox.showinfo("\u6210\u529F", "\u8BBE\u7F6E\u5DF2\u4FDD\u5B58")

    def _clear_log(self):
        try:
            open(LOG_FILE, "w", encoding="utf-8").close()
            if TTKBOOTSTRAP_AVAILABLE:
                Messagebox.show_info("\u65E5\u5FD7\u5DF2\u6E05\u7A7A", "\u6210\u529F")
            else:
                Messagebox.showinfo("\u6210\u529F", "\u65E5\u5FD7\u5DF2\u6E05\u7A7A")
        except Exception as e:
            log(f"\u6E05\u7A7A\u65E5\u5FD7\u5931\u8D25: {e}")

    def _refresh_chart(self):
        """刷新图表显示"""
        try:
            chart_path = generate_weekly_chart()
            if chart_path and Path(chart_path).exists():
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(chart_path)
                    # 缩放以适应界面
                    img = img.resize((640, 320), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.chart_label.config(image=photo, text="")
                    self.chart_label.image = photo  # 保持引用
                except Exception:
                    self.chart_label.config(text="\u56FE\u8868\u5DF2\u751F\u6210\uff0c\u4F46\u65E0\u6CD5\u663E\u793A\u56FE\u7247")
            else:
                self.chart_label.config(text="\u6682\u65E0\u6570\u636E\u6216 matplotlib \u672A\u5B89\u88C5")
        except Exception as e:
            log(f"\u5237\u65B0\u56FE\u8868\u5931\u8D25: {e}")
            self.chart_label.config(text=f"\u5237\u65B0\u56FE\u8868\u5931\u8D25: {e}")
        finally:
            # 图表加载后更新 Canvas 滚动区域
            if hasattr(self, '_stats_canvas') and self._stats_canvas:
                self._stats_canvas.update_idletasks()
                self._stats_canvas.configure(scrollregion=self._stats_canvas.bbox("all"))

    def _export_csv(self):
        """导出CSV数据"""
        try:
            path = export_to_csv()
            if TTKBOOTSTRAP_AVAILABLE:
                Messagebox.show_info(f"\u6570\u636E\u5DF2\u5BFC\u51FA\u5230: {path}", "\u5BFC\u51FA\u6210\u529F")
            else:
                Messagebox.showinfo("\u5BFC\u51FA\u6210\u529F", f"\u6570\u636E\u5DF2\u5BFC\u51FA\u5230: {path}")
        except Exception as e:
            log(f"\u5BFC\u51FACSV\u5931\u8D25: {e}")
            if TTKBOOTSTRAP_AVAILABLE:
                Messagebox.show_error(f"\u5BFC\u51FA\u5931\u8D25: {e}", "\u9519\u8BEF")
            else:
                Messagebox.showerror("\u9519\u8BEF", f"\u5BFC\u51FA\u5931\u8D25: {e}")

    # ---- 托盘 ----
    def _on_close(self):
        if PYSTRAY_AVAILABLE and PIL_AVAILABLE:
            try:
                self._hide_to_tray()
            except Exception as e:
                log(f"[托盘] 关闭时隐藏失败: {e}")
                self._stop_hotkey()
                self.root.destroy()
        else:
            self._stop_hotkey()
            self.root.destroy()

    def _create_tray_icon(self):
        if self.tray_icon:
            return
        try:
            # 创建简单图标：紫色圆形白色中心
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([2, 2, 62, 62], fill=(108, 92, 231, 255))
            d.ellipse([20, 20, 44, 44], fill=(255, 255, 255, 255))

            # pystray 回调必须接受 (icon, item) 参数，用 lambda 包装
            menu = pystray.Menu(
                pystray.MenuItem("显示", lambda icon, item: self._show_window()),
                pystray.MenuItem("锁屏", lambda icon, item: self.trigger_lock()),
                pystray.MenuItem("退出", lambda icon, item: self._quit())
            )
            self.tray_icon = pystray.Icon("jingyijing_v9", img, "静一静 v9", menu)
            self.tray_icon.on_double_click = lambda icon: self._show_window()
            
            # 在守护线程中运行托盘
            self._tray_thread = threading.Thread(target=self._run_tray, daemon=True)
            self._tray_thread.start()
            log("[托盘] 图标已创建")
        except Exception as e:
            import traceback
            log(f"[托盘] 创建异常: {type(e).__name__}: {e}")
            log(f"[托盘] 异常详情: {traceback.format_exc()}")
            raise

    def _run_tray(self):
        """托盘图标运行入口"""
        try:
            self.tray_icon.run()
        except Exception as e:
            import traceback
            log(f"[托盘] 运行异常: {type(e).__name__}: {e}")
            log(f"[托盘] 异常详情: {traceback.format_exc()}")
    def _show_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.status_var.set("窗口已显示")
        except Exception as e:
            log(f"[托盘] 显示窗口失败: {e}")

    def _hide_to_tray(self):
        """隐藏窗口到托盘"""
        try:
            self.root.withdraw()
            if not self.tray_icon:
                self._create_tray_icon()
            self.status_var.set("已最小化到托盘")
        except Exception as e:
            log(f"[托盘] 隐藏到托盘失败: {e}")

    def _quit(self, icon=None, item=None):
        self._stop_hotkey()
        self.root.after(0, self._do_quit)

    def _do_quit(self):
        if self._watchdog:
            self._watchdog.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)


# ==================== 入口 ====================
def main():
    # 单实例检测
    single = SingleInstance()
    if not single.lock():
        log("[启动] 检测到已有实例在运行，尝试激活现有窗口...")
        # 尝试找到现有窗口并激活
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, f"\u9759\u4E00\u9759 {VERSION}")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return

    try:
        app = App()
        app.run()
    finally:
        single.unlock()


if __name__ == "__main__":
    main()
