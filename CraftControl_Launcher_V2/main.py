"""
CraftControl v2.0
=================
Щоб додати нову мову — просто скопіюй будь-який файл з langs/
і заміни значення у словнику T. Програма підхопить автоматично.
"""

import sys
import os
import json
import importlib
import subprocess
import urllib.request
import urllib.parse
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTabWidget, QListWidget,
    QListWidgetItem, QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QSplitter, QFrame, QGridLayout, QScrollArea, QDialog, QFormLayout,
    QCheckBox, QSpinBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QToolBar, QStatusBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSize
from PyQt6.QtGui import (
    QColor, QFont, QAction, QDesktopServices, QTextCursor, QPalette
)

# ═══════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════
APP_VERSION  = "2.0.0"
APP_NAME     = "CraftControl"
BASE_DIR     = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
LANGS_DIR    = BASE_DIR / "langs"
CONFIG_FILE  = Path.home() / ".craftcontrol" / "config.json"
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════
#  LANGUAGE SYSTEM
#  Додати мову = скинути файл у langs/ і перезапустити
# ═══════════════════════════════════════════════════════
_LANGS: dict[str, dict] = {}   # code -> {name, T}
_current_T: dict = {}

def _load_langs():
    LANGS_DIR.mkdir(exist_ok=True)
    _LANGS.clear()
    for f in sorted(LANGS_DIR.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            code = getattr(mod, "LANG_CODE", f.stem)
            name = getattr(mod, "LANG_NAME", f.stem)
            t    = getattr(mod, "T", {})
            _LANGS[code] = {"name": name, "T": t}
        except Exception as e:
            print(f"[LANG] Не вдалося завантажити {f}: {e}")

def _apply_lang(code: str):
    global _current_T
    if code in _LANGS:
        _current_T = _LANGS[code]["T"]
    elif _LANGS:
        _current_T = next(iter(_LANGS.values()))["T"]
    else:
        _current_T = {}

def tr(key: str, *fallback) -> str:
    return _current_T.get(key, fallback[0] if fallback else key)

_load_langs()

# ═══════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════
_DEFAULT_CFG = {
    "servers":    [],
    "java_path":  "java",
    "playit_path":"",
    "lang":       "uk",
    "theme":      "dark",
    "accent":     "green",
    "font_size":  12,
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in _DEFAULT_CFG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(_DEFAULT_CFG)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════
ACCENTS = {
    "green":  {"main": "#00cc44", "glow": "rgba(0,204,68,0.12)"},
    "blue":   {"main": "#4ab4ff", "glow": "rgba(74,180,255,0.12)"},
    "purple": {"main": "#b060ff", "glow": "rgba(176,96,255,0.12)"},
    "orange": {"main": "#ff8c00", "glow": "rgba(255,140,0,0.12)"},
}

THEMES = {
    "dark": {
        "bg":  "#0d0f14", "bg2": "#111318", "bg3": "#090b0f",
        "border": "#1e2430",
        "text": "#aab4c4", "text2": "#556677",
        "yellow": "#ffaa00", "red": "#ff4444",
    },
    "light": {
        "bg":  "#f0f2f5", "bg2": "#ffffff", "bg3": "#e4e8ef",
        "border": "#c8d0dc",
        "text": "#1a2030", "text2": "#6677aa",
        "yellow": "#cc8800", "red": "#dd2222",
    },
}

def build_stylesheet(theme: str, accent: str, font_size: int) -> str:
    D  = THEMES.get(theme, THEMES["dark"])
    AC = ACCENTS.get(accent, ACCENTS["green"])
    A  = AC["main"]
    AG = AC["glow"]
    fs = font_size

    return f"""
QMainWindow, QWidget {{
    background-color: {D['bg']};
    color: {D['text']};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: {fs}px;
}}
QTabWidget::pane {{
    border: 1px solid {D['border']};
    background: {D['bg']};
}}
QTabBar::tab {{
    background: {D['bg2']};
    color: {D['text2']};
    padding: 8px 18px;
    border: 1px solid {D['border']};
    border-bottom: none;
    margin-right: 2px;
    font-size: {fs}px;
}}
QTabBar::tab:selected {{
    background: {D['bg']};
    color: {A};
    border-top: 2px solid {A};
}}
QTabBar::tab:hover {{ color: {D['text']}; }}
QPushButton {{
    background-color: {D['bg2']};
    color: {D['text']};
    border: 1px solid {D['border']};
    border-radius: 6px;
    padding: 7px 16px;
    font-family: 'Consolas', monospace;
    font-size: {fs}px;
}}
QPushButton:hover {{ background-color: {D['bg3']}; border-color: {D['text2']}; }}
QPushButton:pressed {{ background-color: {D['bg3']}; }}
QPushButton#btn_accent {{
    border-color: {A}; color: {A};
}}
QPushButton#btn_accent:hover {{ background-color: {AG}; }}
QPushButton#btn_red {{
    border-color: {D['red']}; color: {D['red']};
}}
QPushButton#btn_red:hover {{ background-color: rgba(255,68,68,0.1); }}
QPushButton#btn_blue {{
    border-color: #4ab4ff; color: #4ab4ff;
}}
QPushButton#btn_blue:hover {{ background-color: rgba(74,180,255,0.1); }}
QPushButton#btn_yellow {{
    border-color: {D['yellow']}; color: {D['yellow']};
}}
QPushButton#btn_yellow:hover {{ background-color: rgba(255,170,0,0.1); }}
QLineEdit, QTextEdit, QComboBox, QSpinBox {{
    background-color: {D['bg3']};
    color: {D['text']};
    border: 1px solid {D['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-family: 'Consolas', monospace;
    font-size: {fs}px;
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {A}; }}
QComboBox QAbstractItemView {{
    background-color: {D['bg2']};
    color: {D['text']};
    border: 1px solid {D['border']};
    selection-background-color: {AG};
    font-size: {fs}px;
}}
QComboBox::drop-down {{ border: none; }}
QListWidget {{
    background-color: {D['bg3']};
    border: 1px solid {D['border']};
    border-radius: 8px;
    outline: none;
    font-size: {fs}px;
}}
QListWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {D['border']}; }}
QListWidget::item:selected {{ background-color: {AG}; color: {A}; }}
QListWidget::item:hover {{ background-color: rgba(255,255,255,0.03); }}
QTableWidget {{
    background-color: {D['bg3']};
    border: 1px solid {D['border']};
    border-radius: 8px;
    gridline-color: {D['border']};
    outline: none;
    font-size: {fs}px;
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QTableWidget::item:selected {{ background-color: {AG}; color: {A}; }}
QHeaderView::section {{
    background-color: {D['bg2']};
    color: {D['text2']};
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid {D['border']};
    font-size: {max(fs-2,9)}px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QProgressBar {{
    background-color: {D['bg3']};
    border: 1px solid {D['border']};
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {A}; border-radius: 3px; }}
QScrollBar:vertical {{
    background: {D['bg2']}; width: 8px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {D['border']}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QGroupBox {{
    border: 1px solid {D['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    color: {D['text2']};
    font-size: {max(fs-2,9)}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px; padding: 0 6px;
    color: {D['text2']};
}}
QStatusBar {{
    background-color: {D['bg2']};
    color: {D['text2']};
    border-top: 1px solid {D['border']};
    font-size: {max(fs-1,10)}px;
}}
QToolBar {{
    background-color: {D['bg2']};
    border-bottom: 1px solid {D['border']};
    spacing: 4px; padding: 4px 8px;
}}
QSplitter::handle {{ background-color: {D['border']}; width: 1px; }}
QCheckBox {{ font-size: {fs}px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {D['border']};
    border-radius: 3px;
    background: {D['bg3']};
}}
QCheckBox::indicator:checked {{ background: {A}; border-color: {A}; }}
QLabel#sec {{ color: {D['text2']}; font-size: {max(fs-2,9)}px; text-transform: uppercase; letter-spacing: 1px; }}
QLabel#val_accent {{ color: {A}; font-weight: bold; }}
QLabel#val_red {{ color: {D['red']}; }}
QLabel#val_yellow {{ color: {D['yellow']}; }}
QLabel#hint {{ color: {D['text2']}; font-size: {max(fs-2,9)}px; font-style: italic; }}
"""

# ═══════════════════════════════════════════════════════
#  THREADS
# ═══════════════════════════════════════════════════════
class DownloadThread(QThread):
    progress = pyqtSignal(int)
    done     = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url, dest):
        super().__init__()
        self.url = url; self.dest = dest

    def run(self):
        try:
            def rep(c, b, t):
                if t > 0: self.progress.emit(min(int(c*b*100/t), 100))
            urllib.request.urlretrieve(self.url, self.dest, reporthook=rep)
            self.done.emit(self.dest)
        except Exception as e:
            self.error.emit(str(e))


class KernelFetchThread(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def __init__(self, ktype): super().__init__(); self.ktype = ktype

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "CraftControl/2.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    def run(self):
        try:
            results = []
            kt = self.ktype

            if kt == "Paper":
                data = self._get("https://api.papermc.io/v2/projects/paper")
                for v in reversed(data.get("versions", [])[-12:]):
                    try:
                        builds = self._get(f"https://api.papermc.io/v2/projects/paper/versions/{v}/builds")
                        bl = builds.get("builds", [])
                        if not bl: continue
                        b = bl[-1]
                        bnum = b["build"]
                        fname = b["downloads"]["application"]["name"]
                        url = (f"https://api.papermc.io/v2/projects/paper"
                               f"/versions/{v}/builds/{bnum}/downloads/{fname}")
                        results.append({"name": f"Paper {v} (build {bnum})", "url": url, "version": v, "fname": fname})
                    except Exception:
                        pass

            elif kt == "Purpur":
                data = self._get("https://api.purpurmc.org/v2/purpur")
                for v in reversed(data.get("versions", [])[-12:]):
                    try:
                        vdata = self._get(f"https://api.purpurmc.org/v2/purpur/{v}")
                        build = vdata.get("builds", {}).get("latest", "")
                        if not build: continue
                        url = f"https://api.purpurmc.org/v2/purpur/{v}/{build}/download"
                        results.append({"name": f"Purpur {v} (build {build})", "url": url, "version": v, "fname": f"purpur-{v}.jar"})
                    except Exception:
                        pass

            elif kt == "Fabric":
                games = self._get("https://meta.fabricmc.net/v2/versions/game")
                stable = [x["version"] for x in games if x.get("stable")][:10]
                loaders = self._get("https://meta.fabricmc.net/v2/versions/loader")
                loader_v = loaders[0]["version"] if loaders else ""
                installers = self._get("https://meta.fabricmc.net/v2/versions/installer")
                inst_v = installers[0]["version"] if installers else ""
                for v in stable:
                    url = (f"https://meta.fabricmc.net/v2/versions/loader"
                           f"/{v}/{loader_v}/{inst_v}/server/jar")
                    results.append({"name": f"Fabric {v}", "url": url, "version": v, "fname": f"fabric-server-{v}.jar"})

            elif kt == "Vanilla":
                data = self._get("https://launchermeta.mojang.com/mc/game/version_manifest.json")
                for vinfo in data["versions"]:
                    if vinfo["type"] != "release": continue
                    vdata = self._get(vinfo["url"])
                    dl = vdata.get("downloads", {}).get("server", {})
                    if dl.get("url"):
                        v = vinfo["id"]
                        results.append({"name": f"Vanilla {v}", "url": dl["url"], "version": v, "fname": f"vanilla-{v}.jar"})
                    if len(results) >= 12: break

            elif kt == "Forge":
                data = self._get("https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json")
                for mc_ver in sorted(data.keys(), reverse=True)[:10]:
                    builds = data[mc_ver]
                    if not builds: continue
                    latest = builds[-1]
                    forge_ver = f"{mc_ver}-{latest}"
                    url = (f"https://files.minecraftforge.net/net/minecraftforge/forge"
                           f"/{forge_ver}/forge-{forge_ver}-installer.jar")
                    results.append({"name": f"Forge {forge_ver}", "url": url, "version": mc_ver,
                                    "fname": f"forge-{forge_ver}-installer.jar",
                                    "note": "Installer — запусти для встановлення сервера"})

            elif kt == "NeoForge":
                data = self._get("https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge")
                versions = data.get("versions", [])
                for v in reversed(versions[-15:]):
                    url = (f"https://maven.neoforged.net/releases/net/neoforged/neoforge"
                           f"/{v}/neoforge-{v}-installer.jar")
                    results.append({"name": f"NeoForge {v}", "url": url, "version": v,
                                    "fname": f"neoforge-{v}-installer.jar",
                                    "note": "Installer"})

            self.result.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ModSearchThread(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def __init__(self, query, source, mod_type):
        super().__init__()
        self.query = query; self.source = source; self.mod_type = mod_type

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "CraftControl/2.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    def run(self):
        try:
            results = []
            q = urllib.parse.quote(self.query)

            if self.source == "Modrinth":
                facets = []
                if self.mod_type == "Плагін / Plugin":
                    facets = [["project_type:plugin"]]
                elif self.mod_type == "Мод / Mod":
                    facets = [["project_type:mod"]]
                elif self.mod_type == "Датапак / Datapack":
                    facets = [["project_type:datapack"]]
                elif self.mod_type == "Шейдер / Shader":
                    facets = [["project_type:shader"]]
                elif self.mod_type == "Ресурспак / Resourcepack":
                    facets = [["project_type:resourcepack"]]

                facets_param = ""
                if facets:
                    import json as _j
                    facets_param = "&facets=" + urllib.parse.quote(_j.dumps(facets))

                url = f"https://api.modrinth.com/v2/search?query={q}&limit=25{facets_param}"
                data = self._get(url)
                for hit in data.get("hits", []):
                    results.append({
                        "name":        hit.get("title", ""),
                        "description": hit.get("description", ""),
                        "downloads":   hit.get("downloads", 0),
                        "slug":        hit.get("slug", ""),
                        "project_id":  hit.get("project_id", ""),
                        "source":      "Modrinth",
                        "type":        hit.get("project_type", ""),
                    })

            elif self.source == "Hangar (Paper)":
                url = f"https://hangar.papermc.io/api/v1/projects?q={q}&limit=25"
                data = self._get(url)
                for p in data.get("result", []):
                    results.append({
                        "name":        p.get("name", ""),
                        "description": p.get("description", ""),
                        "downloads":   p.get("stats", {}).get("downloads", 0),
                        "slug":        p.get("namespace", {}).get("slug", ""),
                        "project_id":  p.get("namespace", {}).get("slug", ""),
                        "source":      "Hangar",
                        "type":        "plugin",
                    })

            self.result.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ModDownloadThread(QThread):
    progress = pyqtSignal(int)
    done     = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, project, dest_dir):
        super().__init__()
        self.project = project; self.dest_dir = dest_dir

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "CraftControl/2.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    def run(self):
        try:
            p = self.project
            dl_url = None
            fname  = None

            if p["source"] == "Modrinth":
                pid = p["project_id"]
                versions = self._get(f"https://api.modrinth.com/v2/project/{pid}/version")
                if not versions:
                    self.error.emit("Немає версій для завантаження")
                    return
                ver = versions[0]
                files = ver.get("files", [])
                if not files:
                    self.error.emit("Немає файлів у версії")
                    return
                primary = next((f for f in files if f.get("primary")), files[0])
                dl_url = primary["url"]
                fname  = primary["filename"]

            elif p["source"] == "Hangar":
                slug = p["project_id"]
                data = self._get(f"https://hangar.papermc.io/api/v1/projects/{slug}/latestrelease")
                # fallback: just link to page
                dl_url = f"https://hangar.papermc.io/{slug}"
                fname  = f"{slug}.jar"

            if not dl_url:
                self.error.emit("Не вдалося знайти посилання на завантаження")
                return

            dest = os.path.join(self.dest_dir, fname)
            def rep(c, b, t):
                if t > 0: self.progress.emit(min(int(c*b*100/t), 100))
            urllib.request.urlretrieve(dl_url, dest, reporthook=rep)
            self.done.emit(dest)
        except Exception as e:
            self.error.emit(str(e))


class ServerProcess(QThread):
    log_line    = pyqtSignal(str, str)
    stopped     = pyqtSignal()
    player_list = pyqtSignal(list)

    def __init__(self, java, jar_path, ram_mb, server_dir):
        super().__init__()
        self.java = java; self.jar_path = jar_path
        self.ram_mb = ram_mb; self.server_dir = server_dir
        self._proc = None; self._running = False

    def run(self):
        self._running = True
        cmd = [self.java, f"-Xmx{self.ram_mb}M", f"-Xms{self.ram_mb//2}M",
               "-jar", self.jar_path, "--nogui"]
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=self.server_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, text=True, bufsize=1,
                encoding="utf-8", errors="replace"
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                if not line: continue
                lvl = "INFO"
                ll  = line.lower()
                if "warn" in ll: lvl = "WARN"
                elif "error" in ll or "exception" in ll or "fatal" in ll: lvl = "ERROR"
                self.log_line.emit(lvl, line)
                # parse player join/leave for live list
                if " joined the game" in line:
                    nick = line.split()[-4] if len(line.split()) >= 4 else ""
                    if nick: self.player_list.emit([("join", nick)])
                elif " left the game" in line:
                    nick = line.split()[-4] if len(line.split()) >= 4 else ""
                    if nick: self.player_list.emit([("leave", nick)])
            self._proc.wait()
        except FileNotFoundError:
            self.log_line.emit("ERROR", f"Java не знайдено: {self.java}")
        except Exception as e:
            self.log_line.emit("ERROR", str(e))
        finally:
            self._running = False
            self.stopped.emit()

    def send_command(self, cmd):
        if self._proc and self._proc.stdin:
            try: self._proc.stdin.write(cmd + "\n"); self._proc.stdin.flush()
            except Exception: pass

    def stop(self):
        self.send_command("stop")
        if self._proc:
            try: self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired: self._proc.kill()


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════
def now(): return datetime.now().strftime("%H:%M:%S")

def sec_label(text: str) -> QLabel:
    l = QLabel(text); l.setObjectName("sec"); return l

def hint_label(text: str) -> QLabel:
    l = QLabel(text); l.setObjectName("hint"); l.setWordWrap(True); return l

def mkbtn(text, obj_name="") -> QPushButton:
    b = QPushButton(text)
    if obj_name: b.setObjectName(obj_name)
    return b

def input_dialog(parent, prompt: str) -> tuple[str, bool]:
    dlg = QDialog(parent); dlg.setWindowTitle(tr("dlg_input")); dlg.setFixedWidth(360)
    l = QVBoxLayout(dlg); l.addWidget(QLabel(prompt))
    inp = QLineEdit(); l.addWidget(inp)
    row = QHBoxLayout()
    ok = mkbtn(tr("dlg_ok"), "btn_accent"); ok.clicked.connect(dlg.accept)
    ca = mkbtn(tr("dlg_cancel"));           ca.clicked.connect(dlg.reject)
    row.addWidget(ok); row.addWidget(ca); l.addLayout(row)
    res = dlg.exec()
    return inp.text(), res == QDialog.DialogCode.Accepted


# ═══════════════════════════════════════════════════════
#  CONSOLE TAB
# ═══════════════════════════════════════════════════════
class ConsoleTab(QWidget):
    def __init__(self, server_ref, cfg):
        super().__init__()
        self.server_ref = server_ref; self.cfg = cfg
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)

        self.box = QTextEdit(); self.box.setReadOnly(True)
        self.box.setFont(QFont("Consolas", cfg.get("font_size", 12)))
        lay.addWidget(self.box)

        row = QHBoxLayout()
        self.inp = QLineEdit(); self.inp.setPlaceholderText(tr("console_placeholder"))
        self.inp.returnPressed.connect(self.send)
        row.addWidget(self.inp)
        send_btn = mkbtn(tr("console_send"), "btn_accent"); send_btn.clicked.connect(self.send)
        clr_btn  = mkbtn(tr("console_clear"));              clr_btn.clicked.connect(self.clear)
        row.addWidget(send_btn); row.addWidget(clr_btn)
        lay.addLayout(row)
        self.log("SYS", tr("app_ready"))

    def log(self, level: str, msg: str):
        cfg = self.cfg; theme = cfg.get("theme","dark"); accent = cfg.get("accent","green")
        D  = THEMES.get(theme, THEMES["dark"])
        A  = ACCENTS.get(accent, ACCENTS["green"])["main"]
        colors = {"INFO": A, "WARN": D["yellow"], "ERROR": D["red"],
                  "CMD": "#4ab4ff", "SYS": D["text2"]}
        c = colors.get(level, D["text"])
        html = (f'<span style="color:{D["text2"]}">{now()}</span> '
                f'<span style="color:{c}">[{level}]</span> '
                f'<span style="color:{D["text"]}">{msg}</span>')
        self.box.append(html)
        self.box.moveCursor(QTextCursor.MoveOperation.End)

    def send(self):
        cmd = self.inp.text().strip()
        if not cmd: return
        self.log("CMD", f"> {cmd}"); self.inp.clear()
        proc = self.server_ref.get("process")
        if proc and proc._running: proc.send_command(cmd)
        else: self.log("WARN", tr("console_server_offline"))

    def clear(self): self.box.clear()


# ═══════════════════════════════════════════════════════
#  SERVERS TAB
# ═══════════════════════════════════════════════════════
class ServersTab(QWidget):
    def __init__(self, cfg, server_ref, console):
        super().__init__()
        self.cfg = cfg; self.server_ref = server_ref; self.console = console
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        sp  = QSplitter(Qt.Orientation.Horizontal)

        # LEFT — server list
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(10,10,6,10)
        ll.addWidget(sec_label(tr("servers_title")))
        self.srv_list = QListWidget(); self.srv_list.currentRowChanged.connect(self._on_sel)
        ll.addWidget(self.srv_list)
        br = QHBoxLayout()
        add_b = mkbtn(tr("servers_add"), "btn_accent"); add_b.clicked.connect(self.add_srv)
        del_b = mkbtn(tr("servers_del"),  "btn_red");   del_b.clicked.connect(self.del_srv)
        br.addWidget(add_b); br.addWidget(del_b); ll.addLayout(br)

        # RIGHT — settings
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(6,10,10,10)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner  = QWidget(); il = QVBoxLayout(inner); il.setSpacing(10)

        rl.addWidget(sec_label(tr("servers_settings")))

        form = QFormLayout(); form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.f_name = QLineEdit()
        self.f_jar  = QLineEdit()
        self.f_dir  = QLineEdit()
        self.f_ram  = QSpinBox(); self.f_ram.setRange(256,65536); self.f_ram.setValue(1024); self.f_ram.setSuffix(" MB")
        self.f_java = QLineEdit(); self.f_java.setPlaceholderText("java")
        self.f_port = QSpinBox(); self.f_port.setRange(1024,65535); self.f_port.setValue(25565)

        bj = mkbtn("📁",); bj.setFixedWidth(34); bj.clicked.connect(self._browse_jar)
        jr = QHBoxLayout(); jr.addWidget(self.f_jar); jr.addWidget(bj)
        jw = QWidget(); jw.setLayout(jr)

        bd = mkbtn("📁"); bd.setFixedWidth(34); bd.clicked.connect(self._browse_dir)
        dr = QHBoxLayout(); dr.addWidget(self.f_dir); dr.addWidget(bd)
        dw = QWidget(); dw.setLayout(dr)

        form.addRow(tr("servers_name"), self.f_name)
        form.addRow(tr("servers_jar"),  jw)
        form.addRow(tr("servers_dir"),  dw)
        form.addRow(tr("servers_ram"),  self.f_ram)
        form.addRow(tr("servers_java"), self.f_java)
        form.addRow(tr("servers_port"), self.f_port)
        il.addLayout(form)

        eula_row = QHBoxLayout()
        self.eula_chk = QCheckBox(tr("servers_eula"))
        eula_btn = mkbtn(tr("servers_eula_btn")); eula_btn.clicked.connect(self._create_eula)
        eula_row.addWidget(self.eula_chk); eula_row.addWidget(eula_btn); eula_row.addStretch()
        il.addLayout(eula_row)

        # RCON group
        rcon_g = QGroupBox(tr("servers_rcon_group")); rcon_l = QFormLayout(rcon_g)
        self.f_rcon_host = QLineEdit(); self.f_rcon_host.setPlaceholderText("127.0.0.1")
        self.f_rcon_port = QSpinBox(); self.f_rcon_port.setRange(1,65535); self.f_rcon_port.setValue(25575)
        self.f_rcon_pass = QLineEdit(); self.f_rcon_pass.setEchoMode(QLineEdit.EchoMode.Password)
        rcon_l.addRow(tr("servers_rcon_host"), self.f_rcon_host)
        rcon_l.addRow(tr("servers_rcon_port"), self.f_rcon_port)
        rcon_l.addRow(tr("servers_rcon_pass"), self.f_rcon_pass)
        rcon_l.addRow("", hint_label(tr("servers_rcon_hint")))
        il.addWidget(rcon_g)

        # Custom API group
        api_g = QGroupBox(tr("servers_api_group")); api_l = QFormLayout(api_g)
        self.f_api_url = QLineEdit(); self.f_api_url.setPlaceholderText("http://localhost:8080")
        self.f_api_key = QLineEdit(); self.f_api_key.setPlaceholderText("your-api-key")
        api_l.addRow(tr("servers_api_url"), self.f_api_url)
        api_l.addRow(tr("servers_api_key"), self.f_api_key)
        api_l.addRow("", hint_label(tr("servers_api_hint")))
        il.addWidget(api_g)

        save_b = mkbtn(tr("servers_save"), "btn_accent"); save_b.clicked.connect(self._save)
        il.addWidget(save_b)

        run_row = QHBoxLayout()
        self.start_b = mkbtn(tr("servers_start"), "btn_accent"); self.start_b.clicked.connect(self._start)
        self.stop_b  = mkbtn(tr("servers_stop"),  "btn_red");    self.stop_b.clicked.connect(self._stop)
        self.stop_b.setEnabled(False)
        run_row.addWidget(self.start_b); run_row.addWidget(self.stop_b)
        il.addLayout(run_row)
        il.addStretch()

        scroll.setWidget(inner); rl.addWidget(scroll)
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([200,600])
        lay.addWidget(sp)
        self._refresh()

    def _refresh(self):
        self.srv_list.clear()
        for s in self.cfg.get("servers", []):
            self.srv_list.addItem(f"🖥  {s['name']}")

    def _on_sel(self, idx):
        srvs = self.cfg.get("servers", [])
        if 0 <= idx < len(srvs):
            s = srvs[idx]
            self.f_name.setText(s.get("name",""))
            self.f_jar.setText(s.get("jar",""))
            self.f_dir.setText(s.get("dir",""))
            self.f_ram.setValue(s.get("ram",1024))
            self.f_java.setText(s.get("java",""))
            self.f_port.setValue(s.get("port",25565))
            self.f_rcon_host.setText(s.get("rcon_host","127.0.0.1"))
            self.f_rcon_port.setValue(s.get("rcon_port",25575))
            self.f_rcon_pass.setText(s.get("rcon_pass",""))
            self.f_api_url.setText(s.get("api_url",""))
            self.f_api_key.setText(s.get("api_key",""))
            self.server_ref["current_idx"] = idx

    def add_srv(self):
        name, ok = input_dialog(self, tr("servers_new_name"))
        if ok and name:
            self.cfg.setdefault("servers",[]).append({
                "name": name, "jar":"","dir":"","ram":1024,"java":"java","port":25565,
                "rcon_host":"127.0.0.1","rcon_port":25575,"rcon_pass":"",
                "api_url":"","api_key":"","players":[]
            })
            save_config(self.cfg); self._refresh()
            self.srv_list.setCurrentRow(len(self.cfg["servers"])-1)

    def del_srv(self):
        idx = self.srv_list.currentRow()
        if idx < 0: return
        r = QMessageBox.question(self, tr("dlg_confirm"), tr("servers_del_confirm"))
        if r == QMessageBox.StandardButton.Yes:
            self.cfg["servers"].pop(idx); save_config(self.cfg); self._refresh()

    def _save(self):
        idx = self.srv_list.currentRow()
        if idx < 0: return
        s = self.cfg["servers"][idx]
        s.update({
            "name": self.f_name.text(), "jar": self.f_jar.text(),
            "dir":  self.f_dir.text(),  "ram": self.f_ram.value(),
            "java": self.f_java.text() or "java", "port": self.f_port.value(),
            "rcon_host": self.f_rcon_host.text(), "rcon_port": self.f_rcon_port.value(),
            "rcon_pass": self.f_rcon_pass.text(),
            "api_url": self.f_api_url.text(), "api_key": self.f_api_key.text(),
        })
        save_config(self.cfg); self._refresh(); self.srv_list.setCurrentRow(idx)
        self.console.log("INFO", f"{tr('servers_saved')} {s['name']}")

    def _browse_jar(self):
        f, _ = QFileDialog.getOpenFileName(self, "JAR", "", "JAR (*.jar)")
        if f: self.f_jar.setText(f); self.f_dir.setText(self.f_dir.text() or str(Path(f).parent))

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("servers_dir"))
        if d: self.f_dir.setText(d)

    def _create_eula(self):
        d = self.f_dir.text().strip()
        if not d: QMessageBox.warning(self, tr("dlg_warning"), tr("servers_no_dir")); return
        (Path(d)/"eula.txt").write_text("eula=true\n")
        self.console.log("INFO", f"{tr('servers_eula_done')} {d}/eula.txt")

    def _start(self):
        idx = self.srv_list.currentRow()
        if idx < 0: QMessageBox.warning(self, tr("dlg_warning"), tr("servers_select")); return
        s = self.cfg["servers"][idx]
        if not s.get("jar") or not Path(s["jar"]).exists():
            QMessageBox.warning(self, tr("dlg_error"), tr("servers_no_jar")); return
        sdir = s.get("dir") or str(Path(s["jar"]).parent)
        proc = ServerProcess(s.get("java","java"), s["jar"], s.get("ram",1024), sdir)
        proc.log_line.connect(self.console.log)
        proc.stopped.connect(self._on_stopped)
        proc.start()
        self.server_ref["process"] = proc
        self.start_b.setEnabled(False); self.stop_b.setEnabled(True)
        self.console.log("INFO", f"{tr('servers_starting')} '{s['name']}'...")

    def _stop(self):
        proc = self.server_ref.get("process")
        if proc: proc.stop()
        self.stop_b.setEnabled(False)

    def _on_stopped(self):
        self.start_b.setEnabled(True); self.stop_b.setEnabled(False)
        self.console.log("WARN", tr("servers_stopped"))


# ═══════════════════════════════════════════════════════
#  PLAYERS TAB — live list from process stdout
# ═══════════════════════════════════════════════════════
class PlayersTab(QWidget):
    def __init__(self, cfg, server_ref, console):
        super().__init__()
        self.cfg = cfg; self.server_ref = server_ref; self.console = console
        self._online: set[str] = set()
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)

        top = QHBoxLayout()
        self.nick_inp = QLineEdit(); self.nick_inp.setPlaceholderText(tr("players_nick"))
        self.rank_cb  = QComboBox(); self.rank_cb.addItems(["Гравець","VIP","Модератор","Адмін"])
        self.rank_cb.setFixedWidth(120)
        add_b = mkbtn(tr("players_add"), "btn_accent"); add_b.clicked.connect(self._add)
        ref_b = mkbtn(tr("players_refresh")); ref_b.clicked.connect(self._refresh_table)
        top.addWidget(self.nick_inp); top.addWidget(self.rank_cb)
        top.addWidget(add_b); top.addWidget(ref_b)
        lay.addLayout(top)

        self.online_lbl = QLabel("🟢 Онлайн: 0")
        self.online_lbl.setObjectName("val_accent")
        lay.addWidget(self.online_lbl)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            tr("players_nick"), tr("players_rank"),
            tr("players_status"), tr("players_ip"), tr("players_actions")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(4, 220); self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self.table)

        bot = QHBoxLayout()
        for label, obj, slot in [
            (tr("players_kick"), "btn_yellow", lambda: self._action("kick")),
            (tr("players_ban"),  "btn_red",    lambda: self._action("ban")),
            (tr("players_op"),   "btn_blue",   lambda: self._action("op")),
            (tr("players_tp"),   "",           lambda: self._action("tp")),
        ]:
            b = mkbtn(label, obj); b.clicked.connect(slot); bot.addWidget(b)
        bot.addStretch(); lay.addLayout(bot)

        self._load()

    def _load(self):
        idx = self.server_ref.get("current_idx", -1)
        srvs = self.cfg.get("servers", [])
        self._players = srvs[idx].get("players", []) if 0 <= idx < len(srvs) else []
        self._refresh_table()

    def on_player_event(self, events: list):
        """Called from ServerProcess.player_list signal"""
        for event, nick in events:
            if event == "join":
                self._online.add(nick)
                # mark in players list if exists
                for p in self._players:
                    if p["nick"].lower() == nick.lower():
                        p["status"] = tr("players_online"); break
                else:
                    self._players.append({"nick": nick, "rank": "Гравець",
                                          "status": tr("players_online"), "ip": "—"})
                self._save()
            elif event == "leave":
                self._online.discard(nick)
                for p in self._players:
                    if p["nick"].lower() == nick.lower():
                        p["status"] = tr("players_offline"); break
                self._save()
        self._refresh_table()

    def _refresh_table(self):
        # Also sync online status from _online set
        for p in self._players:
            if p["nick"] in self._online:
                p["status"] = tr("players_online")
        online_count = sum(1 for p in self._players if p.get("status") == tr("players_online"))
        self.online_lbl.setText(f"🟢 Онлайн: {online_count} / {len(self._players)}")

        self.table.setRowCount(0)
        for p in self._players:
            r = self.table.rowCount(); self.table.insertRow(r)
            ni = QTableWidgetItem(p["nick"]); self.table.setItem(r, 0, ni)
            rank = p.get("rank","Гравець")
            ri = QTableWidgetItem(rank)
            rc = {"Адмін":"#ff4444","Модератор":"#4ab4ff","VIP":"#ffaa00"}.get(rank)
            if rc: ri.setForeground(QColor(rc))
            self.table.setItem(r, 1, ri)
            st = p.get("status", tr("players_offline"))
            si = QTableWidgetItem(st)
            si.setForeground(QColor("#00cc44") if st == tr("players_online") else QColor("#556677"))
            self.table.setItem(r, 2, si)
            self.table.setItem(r, 3, QTableWidgetItem(p.get("ip","—")))
            self.table.setItem(r, 4, QTableWidgetItem(""))

    def _add(self):
        nick = self.nick_inp.text().strip()
        if not nick: return
        self._players.append({"nick":nick,"rank":self.rank_cb.currentText(),"status":tr("players_offline"),"ip":"—"})
        self._save(); self.nick_inp.clear(); self._refresh_table()
        self.console.log("INFO", f"{tr('players_added')} {nick}")

    def _save(self):
        idx = self.server_ref.get("current_idx",-1)
        srvs = self.cfg.get("servers",[])
        if 0 <= idx < len(srvs):
            srvs[idx]["players"] = self._players; save_config(self.cfg)

    def _action(self, act):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._players): return
        nick = self._players[row]["nick"]
        cmds = {"kick":f"kick {nick}","ban":f"ban {nick}","op":f"op {nick}","tp":f"tp {nick} 0 64 0"}
        cmd  = cmds.get(act,"")
        proc = self.server_ref.get("process")
        if proc and proc._running:
            proc.send_command(cmd); self.console.log("CMD", f"> {cmd}")
        else:
            self.console.log("WARN", f"{tr('players_server_offline')} /{cmd}")
        if act == "ban":
            nick_lower = nick.lower()
            self._online.discard(nick)
            self._players = [p for p in self._players if p["nick"].lower() != nick_lower]
            self._save(); self._refresh_table()


# ═══════════════════════════════════════════════════════
#  KERNELS + MODS TAB
# ═══════════════════════════════════════════════════════
class KernelsTab(QWidget):
    def __init__(self, console, cfg):
        super().__init__()
        self.console = console; self.cfg = cfg
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)

        tabs = QTabWidget()
        tabs.addTab(self._build_kernels(), "⬇ Ядра")
        tabs.addTab(self._build_mods(),    "🧩 Моди / Плагіни")
        lay.addWidget(tabs)

    # ── Kernels sub-tab ───────────────────────────────
    def _build_kernels(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)

        top = QHBoxLayout()
        self.k_type = QComboBox()
        self.k_type.addItems(["Paper","Purpur","Fabric","Vanilla","Forge","NeoForge"])
        top.addWidget(QLabel(tr("kernels_type"))); top.addWidget(self.k_type)
        fetch_b = mkbtn(tr("kernels_fetch"), "btn_blue"); fetch_b.clicked.connect(self._fetch)
        top.addWidget(fetch_b); top.addStretch(); lay.addLayout(top)

        self.k_list = QListWidget(); lay.addWidget(self.k_list)
        self.k_note = QLabel(""); self.k_note.setObjectName("hint"); lay.addWidget(self.k_note)

        dest_row = QHBoxLayout()
        self.k_dest = QLineEdit(); self.k_dest.setPlaceholderText(tr("kernels_dest"))
        br = mkbtn(tr("kernels_browse")); br.clicked.connect(self._browse_dest)
        dest_row.addWidget(self.k_dest); dest_row.addWidget(br); lay.addLayout(dest_row)

        self.k_prog = QProgressBar(); self.k_prog.setVisible(False); lay.addWidget(self.k_prog)
        self.k_status = QLabel(""); lay.addWidget(self.k_status)

        dl_b = mkbtn(tr("kernels_download"), "btn_accent"); dl_b.clicked.connect(self._download)
        lay.addWidget(dl_b)
        self._kernels = []
        return w

    def _fetch(self):
        kt = self.k_type.currentText()
        self.k_list.clear(); self.k_list.addItem(tr("kernels_fetching"))
        self.console.log("INFO", f"{tr('kernels_fetch_start')} {kt}")
        t = KernelFetchThread(kt); t.result.connect(self._on_kernels)
        t.error.connect(lambda e: self._on_fetch_err(e)); t.start(); self._ft = t

    def _on_kernels(self, kernels):
        self._kernels = kernels; self.k_list.clear()
        for k in kernels: self.k_list.addItem(k["name"])
        if kernels: self.k_list.setCurrentRow(0); self.console.log("INFO", f"{tr('kernels_found')} {len(kernels)}")
        else: self.k_list.addItem(tr("kernels_none"))
        self._update_note()

    def _update_note(self):
        idx = self.k_list.currentRow()
        if 0 <= idx < len(self._kernels):
            note = self._kernels[idx].get("note","")
            self.k_note.setText(f"ℹ {note}" if note else "")
        else:
            self.k_note.setText("")

    def _on_fetch_err(self, e):
        self.k_list.clear(); self.k_list.addItem(f"❌ {e}")
        self.console.log("ERROR", f"{tr('kernels_fetch_error')} {e}")

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, tr("kernels_browse"))
        if d: self.k_dest.setText(d)

    def _download(self):
        idx = self.k_list.currentRow()
        if idx < 0 or idx >= len(self._kernels):
            QMessageBox.warning(self, tr("dlg_warning"), tr("kernels_select")); return
        dest_dir = self.k_dest.text().strip()
        if not dest_dir:
            QMessageBox.warning(self, tr("dlg_warning"), tr("kernels_no_dest")); return
        k = self._kernels[idx]
        dest = os.path.join(dest_dir, k.get("fname", k["name"].replace(" ","_")+".jar"))
        self.k_prog.setVisible(True); self.k_prog.setValue(0)
        self.k_status.setText(tr("kernels_downloading"))
        self.console.log("INFO", f"↓ {k['name']}")
        self._dl = DownloadThread(k["url"], dest)
        self._dl.progress.connect(self.k_prog.setValue)
        self._dl.done.connect(lambda p: (self.k_status.setText(f"✅ {tr('kernels_saved')} {p}"),
                                          self.console.log("INFO", f"{tr('kernels_saved')} {p}")))
        self._dl.error.connect(lambda e: (self.k_status.setText(f"❌ {e}"),
                                           self.console.log("ERROR", f"{tr('kernels_error')} {e}")))
        self._dl.start()

    # ── Mods sub-tab ──────────────────────────────────
    def _build_mods(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(10,10,10,10); lay.setSpacing(8)

        top = QHBoxLayout()
        self.m_query = QLineEdit(); self.m_query.setPlaceholderText(tr("mods_search_ph"))
        self.m_query.returnPressed.connect(self._search)
        top.addWidget(self.m_query)

        self.m_source = QComboBox(); self.m_source.addItems(["Modrinth","Hangar (Paper)"])
        self.m_source.setFixedWidth(150)
        top.addWidget(QLabel(tr("mods_source"))); top.addWidget(self.m_source)

        self.m_type = QComboBox()
        self.m_type.addItems(["Всі","Плагін / Plugin","Мод / Mod","Датапак / Datapack","Шейдер / Shader","Ресурспак / Resourcepack"])
        self.m_type.setFixedWidth(200)
        top.addWidget(QLabel(tr("mods_type"))); top.addWidget(self.m_type)

        srch_b = mkbtn(tr("mods_search_btn"), "btn_blue"); srch_b.clicked.connect(self._search)
        top.addWidget(srch_b); lay.addLayout(top)

        self.m_status = QLabel(""); lay.addWidget(self.m_status)
        self.m_list   = QListWidget(); self.m_list.currentRowChanged.connect(self._on_mod_sel)
        lay.addWidget(self.m_list)

        self.m_desc = QLabel(""); self.m_desc.setWordWrap(True)
        self.m_desc.setObjectName("hint"); lay.addWidget(self.m_desc)

        dest_row = QHBoxLayout()
        self.m_dest = QLineEdit(); self.m_dest.setPlaceholderText(tr("mods_server_dir"))
        br2 = mkbtn(tr("mods_open_folder")); br2.clicked.connect(self._browse_mods_dir)
        dest_row.addWidget(QLabel(tr("mods_server_dir"))); dest_row.addWidget(self.m_dest); dest_row.addWidget(br2)
        lay.addLayout(dest_row)

        self.m_prog = QProgressBar(); self.m_prog.setVisible(False); lay.addWidget(self.m_prog)
        self.m_inst_status = QLabel(""); lay.addWidget(self.m_inst_status)

        inst_b = mkbtn(tr("mods_install"), "btn_accent"); inst_b.clicked.connect(self._install_mod)
        lay.addWidget(inst_b)
        self._mods = []
        return w

    def _search(self):
        q = self.m_query.text().strip()
        if not q: return
        self.m_list.clear(); self.m_list.addItem(tr("mods_searching"))
        self.m_status.setText(tr("mods_searching"))
        t = ModSearchThread(q, self.m_source.currentText(), self.m_type.currentText())
        t.result.connect(self._on_mods); t.error.connect(self._on_mod_err); t.start(); self._mt = t

    def _on_mods(self, mods):
        self._mods = mods; self.m_list.clear()
        if not mods: self.m_list.addItem(tr("mods_no_results")); self.m_status.setText(tr("mods_no_results")); return
        self.m_status.setText(f"{tr('mods_results')} {len(mods)}")
        for m in mods:
            dl = m.get("downloads",0)
            self.m_list.addItem(f"{m['name']}  [{m['type']}]  ↓{dl:,}")

    def _on_mod_sel(self, idx):
        if 0 <= idx < len(self._mods):
            m = self._mods[idx]
            self.m_desc.setText(f"{m.get('description','')}  |  Source: {m.get('source','')}  slug: {m.get('slug','')}")

    def _on_mod_err(self, e):
        self.m_list.clear(); self.m_list.addItem(f"❌ {e}")
        self.m_status.setText(f"❌ {e}")

    def _browse_mods_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("mods_server_dir"))
        if d: self.m_dest.setText(d)

    def _install_mod(self):
        idx = self.m_list.currentRow()
        if idx < 0 or idx >= len(self._mods):
            QMessageBox.warning(self, tr("dlg_warning"), tr("mods_select")); return
        dest_dir = self.m_dest.text().strip()
        if not dest_dir:
            QMessageBox.warning(self, tr("dlg_warning"), tr("mods_no_dir")); return

        m    = self._mods[idx]
        mtype = m.get("type","mod")
        # choose subfolder
        subfolder_map = {
            "plugin": "plugins", "mod": "mods",
            "datapack": "datapacks", "shader": "shaderpacks",
            "resourcepack": "resourcepacks",
        }
        subfolder = subfolder_map.get(mtype.lower(), "mods")
        final_dir = os.path.join(dest_dir, subfolder)
        os.makedirs(final_dir, exist_ok=True)

        self.m_prog.setVisible(True); self.m_prog.setValue(0)
        self.m_inst_status.setText(tr("mods_installing"))
        self.console.log("INFO", f"↓ {m['name']} → {subfolder}/")
        self._mdl = ModDownloadThread(m, final_dir)
        self._mdl.progress.connect(self.m_prog.setValue)
        self._mdl.done.connect(lambda p: (
            self.m_inst_status.setText(f"✅ {tr('mods_installed')} {p}"),
            self.console.log("INFO", f"{tr('mods_installed')} {p}")
        ))
        self._mdl.error.connect(lambda e: (
            self.m_inst_status.setText(f"❌ {e}"),
            self.console.log("ERROR", f"{tr('mods_error')} {e}")
        ))
        self._mdl.start()


# ═══════════════════════════════════════════════════════
#  PROPERTIES TAB
# ═══════════════════════════════════════════════════════
class PropertiesTab(QWidget):
    def __init__(self, cfg, server_ref, console):
        super().__init__()
        self.cfg = cfg; self.server_ref = server_ref; self.console = console
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10)
        top = QHBoxLayout()
        lb = mkbtn(tr("props_load"), "btn_blue"); lb.clicked.connect(self._load)
        sb = mkbtn(tr("props_save"), "btn_accent"); sb.clicked.connect(self._save)
        top.addWidget(lb); top.addWidget(sb); top.addStretch(); lay.addLayout(top)
        self.ed = QTextEdit(); self.ed.setFont(QFont("Consolas", self.cfg.get("font_size",12)))
        self.ed.setPlaceholderText("# server.properties\nserver-port=25565\nmax-players=20\ngamemode=survival\n...")
        lay.addWidget(self.ed); self._path = None

    def _load(self):
        idx  = self.server_ref.get("current_idx",-1)
        srvs = self.cfg.get("servers",[])
        sdir = srvs[idx].get("dir","") if 0 <= idx < len(srvs) else ""
        f, _ = QFileDialog.getOpenFileName(self,"server.properties",sdir,"Properties (*.properties);;All (*)")
        if f:
            self._path = f; self.ed.setPlainText(Path(f).read_text(encoding="utf-8",errors="replace"))
            self.console.log("INFO", f"{tr('props_loaded')} {f}")

    def _save(self):
        if not self._path:
            f, _ = QFileDialog.getSaveFileName(self,"Save","server.properties","Properties (*.properties)")
            if not f: return; self._path = f
        Path(self._path).write_text(self.ed.toPlainText(), encoding="utf-8")
        self.console.log("INFO", f"{tr('props_saved')} {self._path}")


# ═══════════════════════════════════════════════════════
#  WIKI TAB  (articles from website — no add button)
# ═══════════════════════════════════════════════════════
class WikiTab(QWidget):
    ARTICLES = [
        {"title":"Встановлення сервера","content":"""# Встановлення Minecraft сервера

## Крок 1: Java
Встановіть Java 21+ з adoptium.net або oracle.com

## Крок 2: Завантажте ядро
Вкладка "Ядра" → оберіть Paper/Purpur → Завантажити список → вибрати версію → вказати папку → Завантажити

## Крок 3: Додайте сервер
Вкладка "Сервери" → "+ Додати" → назва.
Вкажіть JAR файл та директорію.

## Крок 4: EULA
Натисніть "Створити eula.txt" (eula=true)

## Крок 5: Запуск
▶ Запустити!
"""},
        {"title":"Налаштування Playit.gg","content":"""# Playit.gg — тунель без port-forwarding

## Що це?
Playit.gg дозволяє грати без налаштування роутера.

## Встановлення
1. Скачайте playit.exe з playit.gg
2. Запустіть → отримайте безкоштовну адресу
3. Налаштуйте порт у server.properties
"""},
        {"title":"Оптимізація TPS","content":"""# Оптимізація продуктивності

## TPS — що це?
Ticks Per Second. Норма = 20. При < 15 — лаги.

## paper-world-defaults.yml
  max-auto-save-chunks-per-tick: 8
  prevent-moving-into-unloaded-chunks: true

## server.properties
  view-distance=8
  simulation-distance=6

## Рекомендовані плагіни
- Spark, ClearLag, FarmLimiter
"""},
        {"title":"LuckPerms — права","content":"""# Система прав з LuckPerms

## Основні команди
  /lp group default permission set essentials.spawn true
  /lp user Steve rank set vip
  /lp editor
"""},
        {"title":"Резервне копіювання","content":"""# Бекап сервера

## Що бекапити?
- world/, world_nether/, world_the_end/
- plugins/ (конфіги)
- server.properties, ops.json, whitelist.json
"""},
        {"title":"Встановлення плагінів","content":"""# Встановлення плагінів

## Джерела
- hangar.papermc.io
- modrinth.com
- spigotmc.org/resources

## Встановлення
1. Скачайте .jar
2. Помістіть у plugins/
3. /reload confirm або перезапуск
"""},
        {"title":"Forge та NeoForge","content":"""# Forge / NeoForge моддінг сервер

## Forge
1. Завантаж installer через вкладку "Ядра"
2. Запусти: java -jar forge-...-installer.jar --installServer
3. Запусти отриманий run.bat / run.sh

## NeoForge
Аналогічно. NeoForge = форк Forge з активнішою розробкою.
Рекомендовано для нових модів (1.20.1+)
"""},
    ]

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        sp  = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(10,10,6,10)
        ll.addWidget(sec_label(tr("wiki_articles")))
        self.art_list = QListWidget(); self.art_list.currentRowChanged.connect(self._show)
        ll.addWidget(self.art_list)
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(6,10,10,10)
        self.title_lbl = QLabel(""); self.title_lbl.setStyleSheet("font-size:15px;font-weight:bold;")
        rl.addWidget(self.title_lbl)
        self.content   = QTextEdit(); self.content.setReadOnly(True)
        self.content.setFont(QFont("Consolas",12)); rl.addWidget(self.content)
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([200,600]); lay.addWidget(sp)
        self._articles = list(self.ARTICLES); self._refresh()
        if self._articles: self.art_list.setCurrentRow(0)

    def _refresh(self):
        self.art_list.clear()
        for a in self._articles: self.art_list.addItem(a["title"])

    def _show(self, idx):
        if 0 <= idx < len(self._articles):
            a = self._articles[idx]
            self.title_lbl.setText(a["title"]); self.content.setPlainText(a["content"])


# ═══════════════════════════════════════════════════════
#  SETTINGS TAB
# ═══════════════════════════════════════════════════════
class SettingsTab(QWidget):
    apply_theme = pyqtSignal()   # tell MainWindow to rebuild stylesheet

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(12)

        # ── UI group ──────────────────────────────────
        ui_g = QGroupBox(tr("settings_ui_group")); ui_l = QFormLayout(ui_g); ui_l.setSpacing(8)

        # Language
        self.lang_cb = QComboBox()
        for code, info in _LANGS.items():
            self.lang_cb.addItem(info["name"], code)
        cur_lang = self.cfg.get("lang","uk")
        for i in range(self.lang_cb.count()):
            if self.lang_cb.itemData(i) == cur_lang:
                self.lang_cb.setCurrentIndex(i); break
        ui_l.addRow(tr("settings_lang"), self.lang_cb)

        # Theme
        self.theme_cb = QComboBox()
        self.theme_cb.addItem(tr("settings_theme_dark"), "dark")
        self.theme_cb.addItem(tr("settings_theme_light"), "light")
        if self.cfg.get("theme","dark") == "light": self.theme_cb.setCurrentIndex(1)
        ui_l.addRow(tr("settings_theme"), self.theme_cb)

        # Accent
        self.accent_cb = QComboBox()
        for key, lbl in [("green",tr("settings_accent_green")),("blue",tr("settings_accent_blue")),
                          ("purple",tr("settings_accent_purple")),("orange",tr("settings_accent_orange"))]:
            self.accent_cb.addItem(lbl, key)
        cur_acc = self.cfg.get("accent","green")
        for i in range(self.accent_cb.count()):
            if self.accent_cb.itemData(i) == cur_acc:
                self.accent_cb.setCurrentIndex(i); break
        ui_l.addRow(tr("settings_accent"), self.accent_cb)

        # Font size
        self.font_spin = QSpinBox(); self.font_spin.setRange(9,20); self.font_spin.setValue(self.cfg.get("font_size",12))
        ui_l.addRow(tr("settings_font_size"), self.font_spin)
        lay.addWidget(ui_g)

        # ── Java group ────────────────────────────────
        java_g = QGroupBox(tr("settings_java_group")); java_l = QFormLayout(java_g); java_l.setSpacing(8)
        self.java_inp = QLineEdit(); self.java_inp.setText(self.cfg.get("java_path","java"))
        jb = mkbtn(tr("settings_java_browse")); jb.setFixedWidth(34)
        jb.clicked.connect(self._browse_java)
        jr = QHBoxLayout(); jr.addWidget(self.java_inp); jr.addWidget(jb)
        jw = QWidget(); jw.setLayout(jr)
        java_l.addRow(tr("settings_java_path"), jw)
        det_b = mkbtn(tr("settings_java_detect")); det_b.clicked.connect(self._detect_java)
        java_l.addRow("", det_b)
        lay.addWidget(java_g)

        # ── Playit group ──────────────────────────────
        pl_g = QGroupBox(tr("settings_playit_group")); pl_l = QFormLayout(pl_g); pl_l.setSpacing(8)
        self.playit_inp = QLineEdit(); self.playit_inp.setText(self.cfg.get("playit_path",""))
        pb = mkbtn(tr("settings_playit_browse")); pb.setFixedWidth(34); pb.clicked.connect(self._browse_playit)
        pr = QHBoxLayout(); pr.addWidget(self.playit_inp); pr.addWidget(pb)
        pw = QWidget(); pw.setLayout(pr)
        pl_l.addRow(tr("settings_playit_path"), pw)
        plr = QHBoxLayout()
        launch_b = mkbtn(tr("settings_playit_launch"),"btn_accent"); launch_b.clicked.connect(self._launch_playit)
        site_b   = mkbtn(tr("settings_playit_site")); site_b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://playit.gg")))
        plr.addWidget(launch_b); plr.addWidget(site_b); plr.addStretch()
        pl_l.addRow("", plr)
        lay.addWidget(pl_g)

        save_b = mkbtn(tr("settings_save"), "btn_accent"); save_b.clicked.connect(self._save)
        self.save_lbl = QLabel(""); lay.addWidget(save_b); lay.addWidget(self.save_lbl)
        lay.addStretch()

    def _browse_java(self):
        f, _ = QFileDialog.getOpenFileName(self,"Java","","Executable (*.exe);;All (*)")
        if f: self.java_inp.setText(f)

    def _detect_java(self):
        try:
            out = subprocess.check_output(["java","-version"], stderr=subprocess.STDOUT, text=True)
            self.java_inp.setText("java"); self.save_lbl.setText(f"✅ {out.splitlines()[0]}")
        except Exception as e:
            self.save_lbl.setText(f"❌ {e}")

    def _browse_playit(self):
        f, _ = QFileDialog.getOpenFileName(self,"playit.exe","","Executable (*.exe);;All (*)")
        if f: self.playit_inp.setText(f)

    def _launch_playit(self):
        p = self.playit_inp.text().strip()
        if p and Path(p).exists():
            subprocess.Popen([p])
        else:
            QDesktopServices.openUrl(QUrl("https://playit.gg/download"))

    def _save(self):
        self.cfg["lang"]       = self.lang_cb.currentData()
        self.cfg["theme"]      = self.theme_cb.currentData()
        self.cfg["accent"]     = self.accent_cb.currentData()
        self.cfg["font_size"]  = self.font_spin.value()
        self.cfg["java_path"]  = self.java_inp.text()
        self.cfg["playit_path"]= self.playit_inp.text()
        save_config(self.cfg)
        _apply_lang(self.cfg["lang"])
        self.save_lbl.setText(f"✅ {tr('settings_saved')}")
        self.apply_theme.emit()


# ═══════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg        = load_config()
        self.server_ref = {"process": None, "current_idx": -1}
        _apply_lang(self.cfg.get("lang","uk"))

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100, 720); self.resize(1240, 800)
        self._apply_stylesheet()

        # Build tabs
        self.console_tab  = ConsoleTab(self.server_ref, self.cfg)
        self.servers_tab  = ServersTab(self.cfg, self.server_ref, self.console_tab)
        self.players_tab  = PlayersTab(self.cfg, self.server_ref, self.console_tab)
        self.kernels_tab  = KernelsTab(self.console_tab, self.cfg)
        self.props_tab    = PropertiesTab(self.cfg, self.server_ref, self.console_tab)
        self.wiki_tab     = WikiTab()
        self.settings_tab = SettingsTab(self.cfg)
        self.settings_tab.apply_theme.connect(self._apply_stylesheet)

        # Wire player events from server process
        # We hook into ServersTab's start to also connect player_list signal
        orig_start = self.servers_tab._start
        def patched_start():
            orig_start()
            proc = self.server_ref.get("process")
            if proc:
                proc.player_list.connect(self.players_tab.on_player_event)
        self.servers_tab._start = patched_start

        self.tabs = QTabWidget()
        for tab, label in [
            (self.console_tab,  tr("tab_console")),
            (self.servers_tab,  tr("tab_servers")),
            (self.players_tab,  tr("tab_players")),
            (self.kernels_tab,  tr("tab_kernels")),
            (self.props_tab,    tr("tab_props")),
            (self.wiki_tab,     tr("tab_wiki")),
            (self.settings_tab, tr("tab_settings")),
        ]:
            self.tabs.addTab(tab, label)
        self.setCentralWidget(self.tabs)

        # Toolbar
        tb = QToolBar(); tb.setMovable(False); self.addToolBar(tb)
        self.srv_lbl = QLabel(f"  {tr('status_offline')}  ")
        tb.addWidget(self.srv_lbl); tb.addSeparator()
        for label, fn in [
            (tr("toolbar_open_dir"), self._open_dir),
            (tr("toolbar_playit"),   lambda: QDesktopServices.openUrl(QUrl("https://playit.gg"))),
            (tr("toolbar_papermc"),  lambda: QDesktopServices.openUrl(QUrl("https://papermc.io"))),
        ]:
            a = QAction(label, self); a.triggered.connect(fn); tb.addAction(a)

        # Status bar
        self.sb = QStatusBar(); self.setStatusBar(self.sb)
        self.sb.showMessage(f"{APP_NAME} v{APP_VERSION}  |  {CONFIG_FILE}")

        # Timer
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(2000)

    def _apply_stylesheet(self):
        self.setStyleSheet(build_stylesheet(
            self.cfg.get("theme","dark"),
            self.cfg.get("accent","green"),
            self.cfg.get("font_size",12)
        ))

    def _tick(self):
        proc = self.server_ref.get("process")
        if proc and proc._running:
            self.srv_lbl.setText(f"  {tr('status_online')}  ")
            self.srv_lbl.setStyleSheet(f"color:{ACCENTS[self.cfg.get('accent','green')]['main']};font-size:12px")
        else:
            self.srv_lbl.setText(f"  {tr('status_offline')}  ")
            self.srv_lbl.setStyleSheet(f"color:{THEMES[self.cfg.get('theme','dark')]['text2']};font-size:12px")

    def _open_dir(self):
        idx  = self.server_ref.get("current_idx",-1)
        srvs = self.cfg.get("servers",[])
        if 0 <= idx < len(srvs):
            d = srvs[idx].get("dir","")
            if d and Path(d).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(d)); return
        QMessageBox.information(self, tr("dlg_warning"), tr("no_dir"))

    def closeEvent(self, e):
        proc = self.server_ref.get("process")
        if proc and proc._running:
            r = QMessageBox.question(self, tr("dlg_confirm"), tr("dlg_exit"))
            if r == QMessageBox.StandardButton.Yes: proc.stop(); e.accept()
            else: e.ignore()
        else:
            e.accept()


# ═══════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
