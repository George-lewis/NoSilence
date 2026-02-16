import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog
from urllib.parse import parse_qs, urlparse

import pystray
import pythoncom
import spotipy
import spotipy.exceptions
from PIL import Image, ImageDraw
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
from pystray import MenuItem as item
from rich.console import Console
from rich.traceback import install
from spotipy.oauth2 import SpotifyOAuth

install()
console = Console()

# Global variables
VERSION = "0.2.0"
CLIENT_ID: str = ""
CLIENT_SECRET: str = ""
sp: spotipy.Spotify = None  # type: ignore

# Windows API for detecting open menus
user32 = ctypes.windll.user32


def is_menu_open():
    # #32768 is the standard class name for a Windows context menu
    return user32.FindWindowW("#32768", None) != 0


# ==========================================================
# PATHS
# ==========================================================

if getattr(sys, "frozen", False):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    exe_dir = os.path.dirname(sys.executable)

    # Try next to the .exe first, then the bundle dir
    SECRETS_PATH = os.path.join(exe_dir, "secrets.json")
    if not os.path.exists(SECRETS_PATH):
        # Fallback for development if running from dist/ but secrets.json is in root
        alt_path = os.path.join(os.path.dirname(exe_dir), "secrets.json")
        if os.path.exists(alt_path):
            SECRETS_PATH = alt_path
        else:
            SECRETS_PATH = os.path.join(bundle_dir, "secrets.json")

    CONFIG_FILE = os.path.join(exe_dir, "config.json")
    # For Spotify token cache, keep it next to the exe
    CACHE_PATH = os.path.join(exe_dir, ".cache")
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(application_path)
    SECRETS_PATH = os.path.join(project_root, "secrets.json")
    CONFIG_FILE = os.path.join(project_root, "config.json")
    CACHE_PATH = os.path.join(project_root, ".cache")

# ==========================================================
# CONFIGURATION
# ==========================================================


def load_secrets():
    global CLIENT_ID, CLIENT_SECRET
    try:
        with open(SECRETS_PATH, "r") as f:
            secrets = json.load(f)
            CLIENT_ID = secrets["CLIENT_ID"]
            CLIENT_SECRET = secrets["CLIENT_SECRET"]
    except Exception as e:
        error_msg = f"Failed to load secrets.json at {SECRETS_PATH}.\n\nError: {e}"
        console.log(f"[red]{error_msg}[/red]")

        # Show a GUI error message if possible
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Initialization Error", error_msg)
        root.destroy()

        sys.exit(1)


load_secrets()

REDIRECT_URI = "https://127.0.0.1:8888"

SILENCE_THRESHOLD = 0.001

# Default silence timeout (seconds)
SILENCE_TIMEOUT = 30

# Default polling interval (seconds)
POLLING_INTERVAL = 1

SPOTIFY_VOLUME_PERCENT = 100
SYSTEM_VOLUME_PERCENT = 25
CHANGE_SPOTIFY_VOLUME = True
CHANGE_SYSTEM_VOLUME = True

SPOTIFY_DEVICE_NAME = None

FALLBACK_DJ_URI = "spotify:playlist:37i9dQZF1EYkqdzj48dyYq"
FALLBACK_PLAYLIST_URI = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"

# Preset timeout options (seconds)
TIMEOUT_OPTIONS = [10, 30, 60, 120, 300]

# Preset polling interval options (seconds)
POLLING_OPTIONS = [0.5, 1, 2, 5, 10]

# Preset threshold options
THRESHOLD_OPTIONS = [
    ("0.1%", 0.001),
    ("0.5%", 0.005),
    ("1.0%", 0.01),
    ("2.0%", 0.02),
]

# Preset volume options
VOLUME_OPTIONS = [10, 25, 20, 30, 40, 50, 60, 70, 80, 90, 100]


# ==========================================================
# CONFIG PERSISTENCE
# ==========================================================
def load_config():
    global SPOTIFY_DEVICE_NAME, SILENCE_TIMEOUT, SILENCE_THRESHOLD
    global SPOTIFY_VOLUME_PERCENT, SYSTEM_VOLUME_PERCENT, POLLING_INTERVAL
    global CHANGE_SPOTIFY_VOLUME, CHANGE_SYSTEM_VOLUME
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                SPOTIFY_DEVICE_NAME = cfg.get("spotify_device", SPOTIFY_DEVICE_NAME)
                SILENCE_TIMEOUT = cfg.get("silence_timeout", SILENCE_TIMEOUT)
                SILENCE_THRESHOLD = cfg.get("silence_threshold", SILENCE_THRESHOLD)
                SPOTIFY_VOLUME_PERCENT = cfg.get(
                    "spotify_volume_percent", SPOTIFY_VOLUME_PERCENT
                )
                SYSTEM_VOLUME_PERCENT = cfg.get(
                    "system_volume_percent", SYSTEM_VOLUME_PERCENT
                )
                POLLING_INTERVAL = cfg.get("polling_interval", POLLING_INTERVAL)
                CHANGE_SPOTIFY_VOLUME = cfg.get(
                    "change_spotify_volume", CHANGE_SPOTIFY_VOLUME
                )
                CHANGE_SYSTEM_VOLUME = cfg.get(
                    "change_system_volume", CHANGE_SYSTEM_VOLUME
                )
        except Exception as e:
            console.log(f"[yellow]Failed to load config:[/yellow] {e}")


def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(
                {
                    "spotify_device": SPOTIFY_DEVICE_NAME,
                    "silence_timeout": SILENCE_TIMEOUT,
                    "silence_threshold": SILENCE_THRESHOLD,
                    "spotify_volume_percent": SPOTIFY_VOLUME_PERCENT,
                    "system_volume_percent": SYSTEM_VOLUME_PERCENT,
                    "polling_interval": POLLING_INTERVAL,
                    "change_spotify_volume": CHANGE_SPOTIFY_VOLUME,
                    "change_system_volume": CHANGE_SYSTEM_VOLUME,
                },
                f,
                indent=2,
            )
    except Exception as e:
        console.log(f"[yellow]Failed to save config:[/yellow] {e}")


# ==========================================================
# SPOTIFY AUTH
# ==========================================================

scope = "user-modify-playback-state,user-read-playback-state"


def get_auth_code_from_user():
    console.log("[blue]Waiting for Spotify redirect...[/blue]")
    console.log(
        "[yellow]Please copy the FULL URL from your browser after logging in and "
        "paste it below.[/yellow]"
    )

    # Use a tkinter dialog for manual input
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    manual_url = simpledialog.askstring(
        "Spotify Authentication",
        "Paste the FULL redirect URL here (starting with https://127.0.0.1:8888/...):",
        parent=root,
    )
    root.destroy()

    if manual_url:
        try:
            parsed_url = urlparse(manual_url)
            params = parse_qs(parsed_url.query)
            if "code" in params:
                return params["code"][0]
        except Exception:
            pass
    return None


def init_spotify():
    global sp
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=scope,
        open_browser=False,
        cache_path=CACHE_PATH,
    )

    # Check if we already have a valid token
    token_info = None
    try:
        token_info = auth_manager.get_cached_token()
    except Exception:
        pass

    if not token_info:
        auth_url = auth_manager.get_authorize_url()
        console.log("[blue]Opening browser for Spotify authentication...[/blue]")
        webbrowser.open(auth_url)

        code = get_auth_code_from_user()
        if code:
            auth_manager.get_access_token(code)
            console.log("[green]Successfully authenticated with Spotify.[/green]")
        else:
            raise RuntimeError("Authentication cancelled or failed.")

    sp = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=15)


def safe_sp_call(func, *args, retries=3, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "name resolution" in str(e).lower() or "max retries" in str(e).lower():
                console.log(
                    f"[yellow]Network error detected ({attempt+1}/{retries}):[/yellow]"
                    f" {e}"
                )
                time.sleep(delay * (attempt + 1))
            else:
                raise e  # Re-raise other exceptions
    raise RuntimeError("Spotify call failed after retries due to network issues")


# ==========================================================
# STATE
# ==========================================================

last_sound_time = time.time()
running = True
paused = False
timeout_lock = threading.Lock()
threshold_lock = threading.Lock()
paused_lock = threading.Lock()
countdown_text = "Monitoring..."
tray_icon = None


# ==========================================================
# AUDIO MONITORING
# ==========================================================


def is_audio_playing():
    sessions = AudioUtilities.GetAllSessions()

    for session in sessions:
        if not session.Process:
            continue

        try:
            meter = session._ctl.QueryInterface(IAudioMeterInformation)
            peak = meter.GetPeakValue()

            with threshold_lock:
                threshold = SILENCE_THRESHOLD

            if peak > threshold:
                return True

        except Exception:
            continue

    return False


# ==========================================================
# SYSTEM VOLUME CONTROL
# ==========================================================


def set_system_volume(percent):
    devices = AudioUtilities.GetSpeakers()

    volume = devices.EndpointVolume

    scalar = max(0.0, min(1.0, percent / 100.0))

    volume.SetMute(0, None)
    volume.SetMasterVolumeLevelScalar(scalar, None)


# ==========================================================
# SPOTIFY DEVICE & VOLUME
# ==========================================================


def get_device_id_by_name(device_name):
    devices = safe_sp_call(sp.devices)
    if not devices:
        return None

    for device in devices["devices"]:
        if device["name"] == device_name:
            return device["id"]

    return None


def set_spotify_volume(device_id):
    safe_sp_call(sp.volume, SPOTIFY_VOLUME_PERCENT, device_id=device_id)


# ==========================================================
# PLAYBACK LOGIC
# ==========================================================


def resume_spotify():
    try:
        device_id = get_device_id_by_name(SPOTIFY_DEVICE_NAME)

        if not device_id:
            console.log(f"[yellow]Device '{SPOTIFY_DEVICE_NAME}' not found.[/yellow]")
            return

        if CHANGE_SYSTEM_VOLUME:
            set_system_volume(SYSTEM_VOLUME_PERCENT)

        playback = safe_sp_call(sp.current_playback)

        if playback and playback.get("is_playing"):
            return

        try:
            safe_sp_call(sp.start_playback, device_id=device_id)
            console.log("[green]Resumed previous playback.[/green]")

        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404:
                console.log("[blue]No resume context. Attempting DJ...[/blue]")

                try:
                    safe_sp_call(
                        sp.start_playback,
                        device_id=device_id,
                        context_uri=FALLBACK_DJ_URI,
                    )
                    console.log("[green]Started Spotify DJ.[/green]")

                except spotipy.exceptions.SpotifyException:
                    console.log(
                        "[yellow]DJ unavailable. Starting fallback playlist.[/yellow]"
                    )

                    safe_sp_call(
                        sp.start_playback,
                        device_id=device_id,
                        context_uri=FALLBACK_PLAYLIST_URI,
                    )
                    console.log("[green]Started fallback playlist.[/green]")
            else:
                raise

        if CHANGE_SPOTIFY_VOLUME:
            set_spotify_volume(device_id)

    except Exception as e:
        console.log(f"[red]Playback error:[/red] {e}")


# ==========================================================
# MONITOR LOOP
# ==========================================================


def monitor_loop():
    global last_sound_time, countdown_text

    pythoncom.CoInitialize()

    while running:
        try:
            with paused_lock:
                is_paused = paused

            if is_paused:
                new_text = "Paused"
                # Reset last_sound_time so it doesn't immediately resume upon unpausing
                last_sound_time = time.time()
            elif is_audio_playing():
                last_sound_time = time.time()
                new_text = "Monitoring..."
            else:
                with timeout_lock:
                    timeout_value = SILENCE_TIMEOUT

                remaining_time = timeout_value - (time.time() - last_sound_time)

                if remaining_time > 0:
                    new_text = f"Resuming in {int(remaining_time)}s"
                else:
                    new_text = "Resuming now..."
                    resume_spotify()
                    last_sound_time = time.time()

            if new_text != countdown_text:
                countdown_text = new_text
                if tray_icon:
                    tray_icon.title = f"NoSilence - {countdown_text}"
                    # Only update the menu if it's not currently open to avoid
                    # breaking it
                    if not is_menu_open():
                        tray_icon.update_menu()

        except Exception as e:
            console.log(f"[red]Monitor error:[/red] {e}")

        time.sleep(POLLING_INTERVAL)


# ==========================================================
# TRAY MENU
# ==========================================================


def set_timeout(seconds):
    global SILENCE_TIMEOUT
    with timeout_lock:
        SILENCE_TIMEOUT = seconds
    save_config()
    console.log(f"Silence timeout set to [cyan]{seconds}[/cyan] seconds")


def set_custom_timeout(icon, item):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    custom_timeout = simpledialog.askinteger(
        "Custom Silence Timeout",
        "Enter silence timeout in seconds:",
        parent=root,
        minvalue=1,
        maxvalue=9999,
    )
    if custom_timeout is not None:
        set_timeout(custom_timeout)
    root.destroy()


def create_timeout_menu():
    def get_items():
        menu_items = []
        menu_items.append(
            item(lambda i: f"Current: {SILENCE_TIMEOUT}s", None, enabled=False)
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        for seconds in TIMEOUT_OPTIONS:

            def make_action(s):
                def action(icon, item):
                    set_timeout(s)

                return action

            def make_checked(s):
                def checked(item):
                    return SILENCE_TIMEOUT == s

                return checked

            menu_items.append(
                item(
                    f"{seconds} seconds",
                    make_action(seconds),
                    checked=make_checked(seconds),
                )
            )
        # Add "Other..." option
        menu_items.append(item("Other...", set_custom_timeout))
        return menu_items

    return pystray.Menu(get_items)


def set_polling_interval(seconds):
    global POLLING_INTERVAL
    POLLING_INTERVAL = seconds
    save_config()
    console.log(f"Polling interval set to [cyan]{seconds}[/cyan] seconds")


def set_custom_polling_interval(icon, item):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    custom_interval = simpledialog.askfloat(
        "Custom Polling Interval",
        "Enter polling interval in seconds:",
        parent=root,
        minvalue=0.1,
        maxvalue=60.0,
    )
    if custom_interval is not None:
        set_polling_interval(custom_interval)
    root.destroy()


def create_polling_interval_menu():
    def get_items():
        menu_items = []
        menu_items.append(
            item(lambda i: f"Current: {POLLING_INTERVAL}s", None, enabled=False)
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        for seconds in POLLING_OPTIONS:

            def make_action(s):
                def action(icon, item):
                    set_polling_interval(s)

                return action

            def make_checked(s):
                def checked(item):
                    return POLLING_INTERVAL == s

                return checked

            menu_items.append(
                item(
                    f"{seconds}s",
                    make_action(seconds),
                    checked=make_checked(seconds),
                    radio=True,
                )
            )
        # Add "Other..." option
        menu_items.append(item("Other...", set_custom_polling_interval))
        return menu_items

    return pystray.Menu(get_items)


def set_threshold(threshold):
    global SILENCE_THRESHOLD
    with threshold_lock:
        SILENCE_THRESHOLD = threshold
    save_config()
    console.log(f"Silence threshold set to [cyan]{threshold * 100:.1f}%[/cyan]")


def set_custom_threshold(icon, item):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    custom_threshold = simpledialog.askfloat(
        "Custom Silence Threshold",
        "Enter silence threshold (e.g., 0.001 to 1.0):",
        parent=root,
        minvalue=0.0,
        maxvalue=1.0,
    )
    if custom_threshold is not None:
        set_threshold(custom_threshold)
    root.destroy()


def create_threshold_menu():
    def get_items():
        menu_items = []
        menu_items.append(
            item(
                lambda i: f"Current: {SILENCE_THRESHOLD * 100:.1f}%",
                None,
                enabled=False,
            )
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        for name, threshold in THRESHOLD_OPTIONS:

            def make_action(t):
                def action(icon, item):
                    set_threshold(t)

                return action

            def make_checked(t):
                def checked(item):
                    return SILENCE_THRESHOLD == t

                return checked

            menu_items.append(
                item(
                    name,
                    make_action(threshold),
                    checked=make_checked(threshold),
                    radio=True,
                )
            )
        # Add "Other..." option
        menu_items.append(item("Other...", set_custom_threshold))
        return menu_items

    return pystray.Menu(get_items)


def set_spotify_volume_config(percent):
    global SPOTIFY_VOLUME_PERCENT
    SPOTIFY_VOLUME_PERCENT = percent
    save_config()
    console.log(f"Spotify volume set to [cyan]{percent}%[/cyan]")


def set_custom_spotify_volume(icon, item):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    custom_volume = simpledialog.askinteger(
        "Custom Spotify Volume",
        "Enter Spotify volume percentage (0-100):",
        parent=root,
        minvalue=0,
        maxvalue=100,
    )
    if custom_volume is not None:
        set_spotify_volume_config(custom_volume)
    root.destroy()


def create_spotify_volume_menu():
    def get_items():
        menu_items = []
        menu_items.append(
            item(lambda i: f"Current: {SPOTIFY_VOLUME_PERCENT}%", None, enabled=False)
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        for percent in VOLUME_OPTIONS:

            def make_action(p):
                def action(icon, item):
                    set_spotify_volume_config(p)

                return action

            def make_checked(p):
                def checked(item):
                    return SPOTIFY_VOLUME_PERCENT == p

                return checked

            menu_items.append(
                item(
                    f"{percent}%",
                    make_action(percent),
                    checked=make_checked(percent),
                    radio=True,
                )
            )
        # Add "Other..." option
        menu_items.append(item("Other...", set_custom_spotify_volume))
        return menu_items

    return pystray.Menu(get_items)


def set_system_volume_config(percent):
    global SYSTEM_VOLUME_PERCENT
    SYSTEM_VOLUME_PERCENT = percent
    save_config()
    console.log(f"System volume set to [cyan]{percent}%[/cyan]")


def set_custom_system_volume(icon, item):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    custom_volume = simpledialog.askinteger(
        "Custom System Volume",
        "Enter system volume percentage (0-100):",
        parent=root,
        minvalue=0,
        maxvalue=100,
    )
    if custom_volume is not None:
        set_system_volume_config(custom_volume)
    root.destroy()


def create_system_volume_menu():
    def get_items():
        menu_items = []
        menu_items.append(
            item(lambda i: f"Current: {SYSTEM_VOLUME_PERCENT}%", None, enabled=False)
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        for percent in VOLUME_OPTIONS:

            def make_action(p):
                def action(icon, item):
                    set_system_volume_config(p)

                return action

            def make_checked(p):
                def checked(item):
                    return SYSTEM_VOLUME_PERCENT == p

                return checked

            menu_items.append(
                item(
                    f"{percent}%",
                    make_action(percent),
                    checked=make_checked(percent),
                    radio=True,
                )
            )
        # Add "Other..." option
        menu_items.append(item("Other...", set_custom_system_volume))
        return menu_items

    return pystray.Menu(get_items)


def set_device(device_name):
    global SPOTIFY_DEVICE_NAME
    SPOTIFY_DEVICE_NAME = device_name
    save_config()
    console.log(f"Spotify device set to [cyan]{device_name}[/cyan]")


def create_device_menu():
    def get_items():
        global SPOTIFY_DEVICE_NAME
        menu_items = []
        try:
            devices = safe_sp_call(sp.devices)
            if not devices:
                raise RuntimeError("Could not fetch devices.")

            available_devices = devices.get("devices", [])

            if not SPOTIFY_DEVICE_NAME and available_devices:
                SPOTIFY_DEVICE_NAME = available_devices[0]["name"]
                save_config()
                console.log(
                    f"Defaulting Spotify device to [cyan]{SPOTIFY_DEVICE_NAME}[/cyan]"
                )

            for device in available_devices:
                device_name = device.get("name")

                def make_action(d):
                    def action(icon, item):
                        set_device(d)

                    return action

                def make_checked(d):
                    def checked(item):
                        return SPOTIFY_DEVICE_NAME == d

                    return checked

                menu_items.append(
                    item(
                        device_name,
                        make_action(device_name),
                        checked=make_checked(device_name),
                        radio=True,
                    )
                )
        except (RuntimeError, Exception) as e:
            console.log(f"[red]Failed to fetch devices:[/red] {e}")
            menu_items.append(item("Error fetching devices", None, enabled=False))
        return menu_items

    return pystray.Menu(get_items)


def toggle_pause(icon, item):
    global paused
    with paused_lock:
        paused = not paused
    console.log(f"Program [cyan]{'paused' if paused else 'resumed'}[/cyan]")


def toggle_change_spotify_volume(icon, item):
    global CHANGE_SPOTIFY_VOLUME
    CHANGE_SPOTIFY_VOLUME = not CHANGE_SPOTIFY_VOLUME
    save_config()
    console.log(
        f"Spotify volume control [cyan]{'enabled' if CHANGE_SPOTIFY_VOLUME else 'disabled'}[/cyan]"
    )


def toggle_change_system_volume(icon, item):
    global CHANGE_SYSTEM_VOLUME
    CHANGE_SYSTEM_VOLUME = not CHANGE_SYSTEM_VOLUME
    save_config()
    console.log(
        f"System volume control [cyan]{'enabled' if CHANGE_SYSTEM_VOLUME else 'disabled'}[/cyan]"
    )


def create_menu(icon=None):
    def get_items():
        return [
            item(lambda item_obj: countdown_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(lambda i: "Resume" if paused else "Pause", toggle_pause),
            item(
                "Change Spotify Volume",
                toggle_change_spotify_volume,
                checked=lambda i: CHANGE_SPOTIFY_VOLUME,
            ),
            item(
                "Change System Volume",
                toggle_change_system_volume,
                checked=lambda i: CHANGE_SYSTEM_VOLUME,
            ),
            item("Devices", create_device_menu()),
            item("Silence Timeout", create_timeout_menu()),
            item("Polling Interval", create_polling_interval_menu()),
            item("Silence Threshold", create_threshold_menu()),
            item("Spotify Volume", create_spotify_volume_menu()),
            item("System Volume", create_system_volume_menu()),
            pystray.Menu.SEPARATOR,
            item(f"Version: {VERSION}", None, enabled=False),
            item("Quit", on_exit),
        ]

    return pystray.Menu(get_items)


def setup_tray():
    icon = pystray.Icon("NoSilence", create_icon(), "NoSilence")
    icon.menu = create_menu(icon)
    return icon


def create_icon():
    img = Image.new("RGB", (64, 64), (30, 215, 96))
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 48, 48), fill="black")
    return img


def on_exit(icon, item):
    global running
    running = False
    icon.stop()


# ==========================================================
# SPOTIFY AUTH CHECK
# ==========================================================
def check_spotify_auth():
    try:
        user = safe_sp_call(sp.current_user)
        if user:
            console.log(
                f"[bold green]Authenticated as {user['display_name']}[/bold green]"
            )
        else:
            raise RuntimeError("Could not authenticate.")
    except (spotipy.exceptions.SpotifyException, RuntimeError) as e:
        console.log(f"[red]Spotify authentication failed:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.log(f"[red]Unexpected error during Spotify auth:[/red] {e}")
        sys.exit(1)


# ==========================================================
# MAIN
# ==========================================================


def main():
    global tray_icon
    console.print(f"[bold green]NoSilence v{VERSION}[/bold green]")
    # Load config first
    load_config()

    # Initialize Spotify
    try:
        init_spotify()
        check_spotify_auth()
    except Exception as e:
        console.log(f"[bold red]Initialization failed:[/bold red] {e}")
        # Only retry if it's a network error, not an auth failure
        if "Authentication" in str(e):
            sys.exit(1)

        console.log("[blue]Retrying in 10 seconds...[/blue]")
        time.sleep(10)
        try:
            init_spotify()
            check_spotify_auth()
        except Exception as e2:
            console.log(f"[bold red]Final initialization failed:[/bold red] {e2}")
            sys.exit(1)

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

    tray_icon = setup_tray()
    tray_icon.run()


if __name__ == "__main__":
    main()
