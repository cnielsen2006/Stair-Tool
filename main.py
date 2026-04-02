import ctypes
import sys

from app import App

MUTEX_NAME = "StairCalculator_SingleInstance_Mutex"
WINDOW_TITLE = "Stair Calculator — IBC/IRC"


def _bring_existing_to_front():
    """Find the existing window and bring it to the foreground."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        SW_RESTORE = 9
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)


if __name__ == "__main__":
    # Try to create a named mutex — if it already exists, another instance is running
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        _bring_existing_to_front()
        sys.exit(0)

    try:
        App().run()
    finally:
        kernel32.ReleaseMutex(mutex)
        kernel32.CloseHandle(mutex)
