"""
CraftControl v2.1.0
====================
Щоб додати мову — скинь .py у папку langs/
Обов'язкові змінні: LANG_CODE, LANG_NAME, T = {...}

ЗАБОРОНЕНІ мови: ru, be (захист від пропаганди)
"""

import sys, os, json, importlib, importlib.util
import subprocess, re, shutil, threading
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTabWidget, QListWidget,
    QComboBox, QProgressBar, QFileDialog, QMessageBox, QSplitter,
    QScrollArea, QDialog, QFormLayout, QCheckBox, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QToolBar, QStatusBar,
    QStackedWidget, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QAction, QDesktopServices, QTextCursor,
    QPainter, QPen, QBrush, QPainterPath,
)

# ═══════════════════════════════════════════════════════════════
#  PATHS & VERSION
# ═══════════════════════════════════════════════════════════════
APP_VERSION = "2.1.0"
APP_NAME    = "CraftControl"
BASE_DIR    = (Path(sys.executable).parent
               if getattr(sys, "frozen", False) else Path(__file__).parent)
LANGS_DIR   = BASE_DIR / "langs"
CONFIG_FILE = Path.home() / ".craftcontrol" / "config.json"
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Заборонені коди мов
BLOCKED_LANGS = {"ru", "be", "russian", "беларуская"}

# ═══════════════════════════════════════════════════════════════
#  LANGUAGE SYSTEM
#  Додати мову = кинути .py у langs/
#  Якщо мов немає — програма показує ключі замість тексту
# ═══════════════════════════════════════════════════════════════
_LANGS: dict[str, dict] = {}
_T:     dict[str, str]  = {}

# Ці назви треба вписати у файл перекладу як значення T["..."]
REQUIRED_KEYS = """
app_ready            console_send         console_clear        console_server_offline
tab_console          tab_servers          tab_players          tab_kernels
tab_java             tab_props            tab_wiki             tab_settings
servers_title        servers_add          servers_del          servers_save
servers_start        servers_stop         servers_name         servers_jar
servers_dir          servers_ram          servers_java         servers_port
servers_eula         servers_eula_btn     servers_new_name     servers_del_confirm
servers_eula_done    servers_saved        servers_no_jar       servers_starting
servers_stopped      servers_select       servers_no_dir       servers_rcon_group
servers_rcon_host    servers_rcon_port    servers_rcon_pass    servers_api_group
servers_api_url      servers_api_key      servers_api_hint
players_nick         players_add          players_rank         players_status
players_ip           players_actions      players_kick         players_ban
players_op           players_tp           players_online       players_offline
players_refresh      players_added        players_server_offline
players_joined       players_left         players_online_label  in_db
kernels_type         kernels_filter       kernels_filter_ph     kernels_fetch
kernels_fetch_start  kernels_fetching     kernels_found        kernels_none
kernels_dest         kernels_download     kernels_saved        kernels_select
kernels_no_dest      kernels_fetch_error  tab_kernels_kern     tab_kernels_mods
mods_search_ph       mods_search_btn      mods_source          mods_type
mods_server_dir      mods_install         mods_installing      mods_installed
mods_select          mods_no_dir          mods_searching       mods_no_results
mods_results         hangar_browser       hangar_opened
java_tab_title       java_tab_hint        java_version_label   java_fetch
java_fetching        java_found           java_none            java_dest
java_dest_ph         java_download        java_select          java_no_dest
java_install_note    java_scan_title      java_scan_select     java_scan_tip
props_load           props_save           props_loaded         props_saved
props_text_mode      props_gui_mode
wiki_articles        wiki_link_text       wiki_url
settings_ui_group    settings_lang        settings_theme       settings_theme_dark
settings_theme_light settings_accent      settings_accent_green settings_accent_blue
settings_accent_purple settings_accent_orange settings_font_size settings_java_group
settings_java_path   settings_java_detect settings_save        settings_saved
settings_playit_group settings_playit_path settings_playit_launch settings_playit_site
monitor_tab          monitor_cpu          monitor_ram          monitor_tps
monitor_players      monitor_no_server    backup_tab           backup_dir
backup_browse        backup_run           backup_running       backup_done
backup_error         backup_no_dir        backup_auto          backup_interval
status_online        status_offline       toolbar_open_dir     toolbar_playit
toolbar_papermc      dlg_ok               dlg_cancel           dlg_confirm
dlg_exit             no_dir
""".split()

def _load_langs():
    LANGS_DIR.mkdir(exist_ok=True)
    _LANGS.clear()
    for f in sorted(LANGS_DIR.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            code = getattr(mod, "LANG_CODE", f.stem).lower().strip()
            name = getattr(mod, "LANG_NAME", f.stem)
            if code in BLOCKED_LANGS or any(b in name.lower() for b in ("русский","рус","russian","беларус")):
                print(f"[LANG] BLOCKED: {name} ({code})")
                continue
            t = getattr(mod, "T", {})
            _LANGS[code] = {"name": name, "T": t}
            print(f"[LANG] OK: {name} ({code}) — {len(t)} keys")
        except Exception as e:
            print(f"[LANG] Error {f.name}: {e}")

def _apply_lang(code: str):
    global _T
    entry = _LANGS.get(code) or (next(iter(_LANGS.values())) if _LANGS else None)
    _T = entry["T"] if entry else {}

def tr(key: str, *fallback) -> str:
    if key in _T: return _T[key]
    if fallback:  return fallback[0]
    return key  # якщо мов немає — повертаємо сам ключ

_load_langs()

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
_DEF = {"servers":[],"java_path":"java","playit_path":"",
        "lang":"uk","theme":"dark","accent":"green","font_size":12}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            c = json.loads(CONFIG_FILE.read_text("utf-8"))
            for k,v in _DEF.items(): c.setdefault(k,v)
            return c
        except: pass
    return dict(_DEF)

def save_config(c: dict):
    CONFIG_FILE.write_text(json.dumps(c,indent=2,ensure_ascii=False),"utf-8")

# ═══════════════════════════════════════════════════════════════
#  THEME
# ═══════════════════════════════════════════════════════════════
ACCENTS = {
    "green":  ("#00cc44","rgba(0,204,68,.14)"),
    "blue":   ("#4ab4ff","rgba(74,180,255,.14)"),
    "purple": ("#b060ff","rgba(176,96,255,.14)"),
    "orange": ("#ff8c00","rgba(255,140,0,.14)"),
}
THEMES = {
    "dark":  {"bg":"#0d0f14","bg2":"#111318","bg3":"#090b0f","brd":"#1e2430",
              "txt":"#aab4c4","txt2":"#556677","yel":"#ffaa00","red":"#ff4444"},
    "light": {"bg":"#f0f2f5","bg2":"#ffffff","bg3":"#e8eaef","brd":"#c8d0dc",
              "txt":"#1a2030","txt2":"#6677aa","yel":"#cc8800","red":"#dd2222"},
}

def build_css(theme="dark", accent="green", fs=12) -> str:
    D = THEMES.get(theme, THEMES["dark"])
    A, AG = ACCENTS.get(accent, ACCENTS["green"])
    return f"""
* {{font-family:'Consolas','Courier New',monospace;font-size:{fs}px;}}
QMainWindow,QWidget{{background:{D['bg']};color:{D['txt']};}}
QTabWidget::pane{{border:1px solid {D['brd']};background:{D['bg']};}}
QTabBar::tab{{background:{D['bg2']};color:{D['txt2']};padding:8px 18px;
    border:1px solid {D['brd']};border-bottom:none;margin-right:2px;}}
QTabBar::tab:selected{{background:{D['bg']};color:{A};border-top:2px solid {A};}}
QTabBar::tab:hover{{color:{D['txt']};}}
QPushButton{{background:{D['bg2']};color:{D['txt']};border:1px solid {D['brd']};
    border-radius:6px;padding:7px 16px;}}
QPushButton:hover{{background:{D['bg3']};border-color:{D['txt2']};}}
QPushButton#pa{{border-color:{A};color:{A};}}
QPushButton#pa:hover{{background:{AG};}}
QPushButton#pr{{border-color:{D['red']};color:{D['red']};}}
QPushButton#pr:hover{{background:rgba(255,68,68,.1);}}
QPushButton#pb{{border-color:#4ab4ff;color:#4ab4ff;}}
QPushButton#pb:hover{{background:rgba(74,180,255,.1);}}
QPushButton#py{{border-color:{D['yel']};color:{D['yel']};}}
QPushButton#py:hover{{background:rgba(255,170,0,.1);}}
QLineEdit,QTextEdit,QComboBox,QSpinBox{{background:{D['bg3']};color:{D['txt']};
    border:1px solid {D['brd']};border-radius:6px;padding:6px 10px;}}
QLineEdit:focus,QTextEdit:focus{{border-color:{A};}}
QComboBox{{padding:6px 30px 6px 10px;}}
QComboBox::drop-down{{border:none;width:20px;}}
QComboBox QAbstractItemView{{background:{D['bg2']};color:{D['txt']};
    border:1px solid {D['brd']};selection-background-color:{AG};outline:none;}}
QListWidget{{background:{D['bg3']};border:1px solid {D['brd']};
    border-radius:8px;outline:none;}}
QListWidget::item{{padding:8px 12px;border-bottom:1px solid {D['brd']};}}
QListWidget::item:selected{{background:{AG};color:{A};}}
QListWidget::item:hover{{background:rgba(255,255,255,.03);}}
QTableWidget{{background:{D['bg3']};border:1px solid {D['brd']};
    border-radius:8px;gridline-color:{D['brd']};outline:none;}}
QTableWidget::item{{padding:6px 10px;border:none;}}
QTableWidget::item:selected{{background:{AG};color:{A};}}
QHeaderView::section{{background:{D['bg2']};color:{D['txt2']};padding:6px 10px;
    border:none;border-bottom:1px solid {D['brd']};
    font-size:{max(fs-2,9)}px;text-transform:uppercase;letter-spacing:1px;}}
QProgressBar{{background:{D['bg3']};border:1px solid {D['brd']};border-radius:4px;
    height:8px;text-align:center;color:transparent;}}
QProgressBar::chunk{{background:{A};border-radius:3px;}}
QScrollBar:vertical{{background:{D['bg2']};width:8px;border:none;}}
QScrollBar::handle:vertical{{background:{D['brd']};border-radius:4px;min-height:20px;}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
QGroupBox{{border:1px solid {D['brd']};border-radius:8px;margin-top:12px;
    padding-top:8px;color:{D['txt2']};font-size:{max(fs-2,9)}px;}}
QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 6px;color:{D['txt2']};}}
QStatusBar{{background:{D['bg2']};color:{D['txt2']};border-top:1px solid {D['brd']};}}
QToolBar{{background:{D['bg2']};border-bottom:1px solid {D['brd']};
    spacing:4px;padding:4px 8px;}}
QSplitter::handle{{background:{D['brd']};width:1px;}}
QCheckBox::indicator{{width:14px;height:14px;border:1px solid {D['brd']};
    border-radius:3px;background:{D['bg3']};}}
QCheckBox::indicator:checked{{background:{A};border-color:{A};}}
QLabel#sec{{color:{D['txt2']};font-size:{max(fs-2,9)}px;
    text-transform:uppercase;letter-spacing:1px;padding:4px 0;}}
QLabel#hint{{color:{D['txt2']};font-size:{max(fs-2,9)}px;font-style:italic;}}
QLabel#online{{color:{A};font-weight:bold;}}
"""

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def now() -> str: return datetime.now().strftime("%H:%M:%S")
def sec_lbl(t): l=QLabel(t); l.setObjectName("sec"); return l
def hint_lbl(t): l=QLabel(t); l.setWordWrap(True); l.setObjectName("hint"); return l

def mk_btn(text:str, oid:str="") -> QPushButton:
    b = QPushButton(text)
    if oid: b.setObjectName(oid)
    return b

def confirm(parent,text:str)->bool:
    return QMessageBox.question(parent,"?",text)==QMessageBox.StandardButton.Yes

def ask_input(parent,prompt:str)->tuple[str,bool]:
    d=QDialog(parent); d.setWindowTitle("?"); d.setFixedWidth(380)
    v=QVBoxLayout(d); v.addWidget(QLabel(prompt))
    i=QLineEdit(); v.addWidget(i)
    bh=QHBoxLayout()
    ok=mk_btn("OK","pa"); ok.clicked.connect(d.accept)
    ca=mk_btn(tr("dlg_cancel","Cancel")); ca.clicked.connect(d.reject)
    bh.addWidget(ok); bh.addWidget(ca); v.addLayout(bh)
    return i.text(), d.exec()==QDialog.DialogCode.Accepted

def find_javas()->list[str]:
    found=[]
    if sys.platform=="win32":
        for base in [
            r"C:\Program Files\Java",
            r"C:\Program Files\Eclipse Adoptium",
            r"C:\Program Files\Microsoft",
            r"C:\Program Files\Eclipse Foundation",
            r"C:\Program Files\Zulu",
            r"C:\Program Files\BellSoft",
            r"C:\Program Files (x86)\Java",
            r"C:\Program Files\Amazon Corretto",
        ]:
            p=Path(base)
            if p.exists():
                for sub in p.iterdir():
                    j=sub/"bin"/"java.exe"
                    if j.exists(): found.append(str(j))
    else:
        for base in ["/usr/lib/jvm","/usr/local/lib/jvm",
                     str(Path.home()/".jdks"),"/opt"]:
            p=Path(base)
            if p.exists():
                for sub in p.iterdir():
                    j=sub/"bin"/"java"
                    if j.exists(): found.append(str(j))
    return ["java"]+found

def java_version(path:str)->str:
    try:
        out=subprocess.check_output([path,"-version"],
            stderr=subprocess.STDOUT,text=True,timeout=5,
            encoding="utf-8",errors="replace")
        m=re.search(r'version "([^"]+)"',out)
        return m.group(1) if m else "?"
    except: return "not found"

# ═══════════════════════════════════════════════════════════════
#  THREADS
# ═══════════════════════════════════════════════════════════════
class DownloadThread(QThread):
    progress=pyqtSignal(int); done=pyqtSignal(str); error=pyqtSignal(str)
    HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) CraftControl/2.1","Accept":"*/*"}
    def __init__(self,url,dest): super().__init__(); self.url=url; self.dest=dest
    def run(self):
        try:
            req=urllib.request.Request(self.url,headers=self.HEADERS)
            with urllib.request.urlopen(req,timeout=60) as resp:
                total=int(resp.headers.get("Content-Length",0))
                done=0; chunk=65536
                with open(self.dest,"wb") as f:
                    while True:
                        data=resp.read(chunk)
                        if not data: break
                        f.write(data); done+=len(data)
                        if total>0: self.progress.emit(min(int(done*100/total),100))
            self.done.emit(self.dest)
        except Exception as e: self.error.emit(str(e))


class KernelFetchThread(QThread):
    result=pyqtSignal(list); error=pyqtSignal(str)
    H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) CraftControl/2.1",
       "Accept":"application/json, */*"}

    def __init__(self,ktype,mf=""): super().__init__(); self.ktype=ktype; self.mf=mf.strip().lower()

    def _get(self,url):
        req=urllib.request.Request(url,headers=self.H)
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

    def _get_xml(self,url):
        req=urllib.request.Request(url,headers=self.H)
        with urllib.request.urlopen(req,timeout=20) as r: return r.read()

    def run(self):
        try:
            res=[]; kt=self.ktype; mf=self.mf

            if kt=="Paper":
                d=self._get("https://api.papermc.io/v2/projects/paper")
                vers=list(reversed(d.get("versions",[])))
                if mf: vers=[v for v in vers if mf in v]
                for v in vers[:60]:
                    try:
                        bd=self._get(f"https://api.papermc.io/v2/projects/paper/versions/{v}/builds")
                        bl=bd.get("builds",[])
                        if not bl: continue
                        b=bl[-1]; bnum=b["build"]
                        fname=b["downloads"]["application"]["name"]
                        url=(f"https://api.papermc.io/v2/projects/paper"
                             f"/versions/{v}/builds/{bnum}/downloads/{fname}")
                        res.append({"name":f"Paper {v} (build {bnum})","url":url,
                                    "version":v,"fname":fname})
                    except: pass

            elif kt=="Purpur":
                d=self._get("https://api.purpurmc.org/v2/purpur")
                vers=list(reversed(d.get("versions",[])))
                if mf: vers=[v for v in vers if mf in v]
                for v in vers[:60]:
                    try:
                        vd=self._get(f"https://api.purpurmc.org/v2/purpur/{v}")
                        builds=vd.get("builds",{})
                        if isinstance(builds,dict):
                            build=builds.get("latest","")
                        elif isinstance(builds,list) and builds:
                            build=str(builds[-1])
                        else: build=""
                        if not build: continue
                        url=f"https://api.purpurmc.org/v2/purpur/{v}/{build}/download"
                        res.append({"name":f"Purpur {v} (build {build})","url":url,
                                    "version":v,"fname":f"purpur-{v}.jar"})
                    except: pass

            elif kt=="Fabric":
                games=self._get("https://meta.fabricmc.net/v2/versions/game")
                stable=[x["version"] for x in games if x.get("stable")]
                if mf: stable=[v for v in stable if mf in v]
                loaders=self._get("https://meta.fabricmc.net/v2/versions/loader")
                lv=loaders[0]["version"] if loaders else ""
                insts=self._get("https://meta.fabricmc.net/v2/versions/installer")
                iv=insts[0]["version"] if insts else ""
                for v in stable[:60]:
                    url=(f"https://meta.fabricmc.net/v2/versions/loader"
                         f"/{v}/{lv}/{iv}/server/jar")
                    res.append({"name":f"Fabric {v}","url":url,
                                "version":v,"fname":f"fabric-server-{v}.jar"})

            elif kt=="Vanilla":
                d=self._get("https://launchermeta.mojang.com/mc/game/version_manifest.json")
                for vi in d["versions"]:
                    if vi["type"] not in ("release","snapshot"): continue
                    if mf and mf not in vi["id"]: continue
                    try:
                        vd=self._get(vi["url"]); dl=vd.get("downloads",{}).get("server",{})
                        if dl.get("url"):
                            tag="" if vi["type"]=="release" else " [snapshot]"
                            res.append({"name":f"Vanilla {vi['id']}{tag}","url":dl["url"],
                                        "version":vi["id"],"fname":f"vanilla-{vi['id']}.jar"})
                    except: pass
                    if len(res)>=60: break

            elif kt=="Forge":
                # Forge: парсимо XML maven-metadata
                # URL: https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml
                # Fallback: promotions_slim.json для останніх версій
                forge_versions=[]
                try:
                    raw=self._get_xml(
                        "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml")
                    root=ET.fromstring(raw)
                    # versioning/versions/version
                    for v_el in root.iter("version"):
                        vstr=v_el.text or ""
                        if vstr and "-" in vstr:
                            mc,_,forge=vstr.partition("-")
                            if mf and mf not in mc: continue
                            forge_versions.append((mc,forge,vstr))
                    forge_versions.reverse()
                except Exception as xml_err:
                    # Fallback: promotions_slim
                    try:
                        promo=self._get(
                            "https://maven.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json")
                        promos=promo.get("promos",{})
                        for key,fver in promos.items():
                            mc=key.replace("-recommended","").replace("-latest","")
                            if mf and mf not in mc: continue
                            full=f"{mc}-{fver}"
                            forge_versions.append((mc,fver,full))
                    except Exception as e2:
                        raise Exception(f"XML: {xml_err} | promotions: {e2}")

                seen=set()
                for mc,fver,full_ver in forge_versions[:80]:
                    if full_ver in seen: continue
                    seen.add(full_ver)
                    url=(f"https://maven.minecraftforge.net/net/minecraftforge/forge"
                         f"/{full_ver}/forge-{full_ver}-installer.jar")
                    res.append({
                        "name":  f"Forge {full_ver}",
                        "url":   url,
                        "version": mc,
                        "fname": f"forge-{full_ver}-installer.jar",
                        "note":  (f"INSTALLER — запусти після завантаження:\n"
                                  f"java -jar forge-{full_ver}-installer.jar --installServer"),
                    })

            elif kt=="NeoForge":
                d=self._get("https://maven.neoforged.net/api/maven/versions/releases"
                            "/net/neoforged/neoforge")
                vers=list(reversed(d.get("versions",[])))
                if mf: vers=[v for v in vers if mf in v]
                for v in vers[:60]:
                    url=(f"https://maven.neoforged.net/releases/net/neoforged/neoforge"
                         f"/{v}/neoforge-{v}-installer.jar")
                    res.append({
                        "name":  f"NeoForge {v}",
                        "url":   url,
                        "version": v,
                        "fname": f"neoforge-{v}-installer.jar",
                        "note":  (f"INSTALLER — запусти після завантаження:\n"
                                  f"java -jar neoforge-{v}-installer.jar --installServer"),
                    })

            self.result.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class ModSearchThread(QThread):
    result=pyqtSignal(list); error=pyqtSignal(str)
    H={"User-Agent":"Mozilla/5.0 CraftControl/2.1","Accept":"application/json"}

    def __init__(self,q,src,mtype): super().__init__(); self.q=q; self.src=src; self.mtype=mtype

    def _get(self,url):
        req=urllib.request.Request(url,headers=self.H)
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

    def run(self):
        try:
            res=[]; q=urllib.parse.quote(self.q)
            if self.src=="Modrinth":
                tm={"Плагін / Plugin":"plugin","Мод / Mod":"mod",
                    "Датапак / Datapack":"datapack","Шейдер / Shader":"shader",
                    "Ресурспак / Resourcepack":"resourcepack"}
                pt=tm.get(self.mtype,"")
                facets=("&facets="+urllib.parse.quote(json.dumps([[f"project_type:{pt}"]]))
                        if pt else "")
                d=self._get(f"https://api.modrinth.com/v2/search?query={q}&limit=40{facets}")
                for h in d.get("hits",[]):
                    res.append({"name":h.get("title",""),"description":h.get("description",""),
                                "downloads":h.get("downloads",0),"slug":h.get("slug",""),
                                "project_id":h.get("project_id",""),"source":"Modrinth",
                                "type":h.get("project_type","")})
            elif self.src=="Hangar (Paper)":
                d=self._get(f"https://hangar.papermc.io/api/v1/projects"
                            f"?q={q}&limit=25&sort=-downloads")
                for p in d.get("result",[]):
                    ns=p.get("namespace",{}); owner=ns.get("owner",""); slug=ns.get("slug","")
                    res.append({"name":p.get("name",""),"description":p.get("description",""),
                                "downloads":p.get("stats",{}).get("downloads",0),
                                "slug":f"{owner}/{slug}","project_id":f"{owner}/{slug}",
                                "source":"Hangar","type":"plugin",
                                "page_url":f"https://hangar.papermc.io/{owner}/{slug}"})
            self.result.emit(res)
        except Exception as e: self.error.emit(str(e))


class ModInstallThread(QThread):
    progress=pyqtSignal(int); done=pyqtSignal(str); error=pyqtSignal(str)
    H={"User-Agent":"Mozilla/5.0 CraftControl/2.1","Accept":"*/*"}

    def __init__(self,project,dest): super().__init__(); self.p=project; self.dest=dest

    def _get(self,url):
        req=urllib.request.Request(url,headers=self.H)
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

    def run(self):
        try:
            p=self.p
            if p["source"]=="Hangar":
                self.done.emit(f"browser:{p.get('page_url','https://hangar.papermc.io')}")
                return
            vers=self._get(f"https://api.modrinth.com/v2/project/{p['project_id']}/version")
            if not vers: self.error.emit("No versions"); return
            files=vers[0].get("files",[])
            if not files: self.error.emit("No files"); return
            f=next((x for x in files if x.get("primary")),files[0])
            dest=os.path.join(self.dest,f["filename"])
            req=urllib.request.Request(f["url"],headers=self.H)
            with urllib.request.urlopen(req,timeout=60) as resp:
                total=int(resp.headers.get("Content-Length",0)); done_b=0; chunk=65536
                with open(dest,"wb") as out:
                    while True:
                        data=resp.read(chunk)
                        if not data: break
                        out.write(data); done_b+=len(data)
                        if total>0: self.progress.emit(min(int(done_b*100/total),100))
            self.done.emit(dest)
        except Exception as e: self.error.emit(str(e))


class JavaFetchThread(QThread):
    result=pyqtSignal(list); error=pyqtSignal(str)
    H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) CraftControl/2.1",
       "Accept":"application/json"}

    def __init__(self,major:int): super().__init__(); self.major=major

    def _get(self,url):
        req=urllib.request.Request(url,headers=self.H)
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())

    def run(self):
        try:
            major=self.major
            os_name=("windows" if sys.platform=="win32" else
                     "mac"     if sys.platform=="darwin" else "linux")
            arch="x64"
            url=(f"https://api.adoptium.net/v3/assets/latest/{major}/hotspot"
                 f"?os={os_name}&architecture={arch}&image_type=jdk")
            data=self._get(url); res=[]
            for item in data:
                binary=item.get("binary",{}); pkg=binary.get("package",{})
                dl=pkg.get("link",""); fname=pkg.get("name","")
                ver=item.get("version",{}).get("semver",str(major))
                if dl: res.append({"name":f"Java {ver} (Temurin JDK)","url":dl,
                                   "fname":fname,"version":ver,"major":major})
            self.result.emit(res)
        except Exception as e: self.error.emit(str(e))


class ServerProcess(QThread):
    log_line    =pyqtSignal(str,str)
    stopped     =pyqtSignal()
    player_join =pyqtSignal(str)
    player_leave=pyqtSignal(str)

    def __init__(self,java,jar,ram,sdir):
        super().__init__()
        self.java=java; self.jar=jar; self.ram=ram; self.sdir=sdir
        self._proc=None; self._running=False

    def run(self):
        self._running=True
        cmd=[self.java,f"-Xmx{self.ram}M",f"-Xms{self.ram//2}M",
             "-jar",self.jar,"--nogui"]
        try:
            self._proc=subprocess.Popen(
                cmd,cwd=self.sdir,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                encoding="utf-8",errors="replace",  # UTF-8 для кирилиці
                text=True,bufsize=1)
            for line in self._proc.stdout:
                line=line.rstrip()
                if not line: continue
                ll=line.lower()
                lvl=("WARN"  if "warn"  in ll else
                     "ERROR" if any(x in ll for x in ("error","exception","fatal"))
                     else "INFO")
                self.log_line.emit(lvl,line)
                m=re.search(r':\s+(\w+) (joined|left) the game',line)
                if m:
                    nick,ev=m.group(1),m.group(2)
                    (self.player_join if ev=="joined" else self.player_leave).emit(nick)
            self._proc.wait()
        except FileNotFoundError:
            self.log_line.emit("ERROR",f"Java not found: {self.java}")
        except Exception as e:
            self.log_line.emit("ERROR",str(e))
        finally:
            self._running=False; self.stopped.emit()

    def send(self,cmd:str):
        if self._proc and self._proc.stdin:
            try: self._proc.stdin.write(cmd+"\n"); self._proc.stdin.flush()
            except: pass

    def stop(self):
        self.send("stop")
        if self._proc:
            try: self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired: self._proc.kill()

# ═══════════════════════════════════════════════════════════════
#  MINI CHART WIDGET
# ═══════════════════════════════════════════════════════════════
class MiniChart(QFrame):
    """Мінімалістичний лінійний графік"""
    def __init__(self, label:str, color:str, max_val:float=100, unit:str="%"):
        super().__init__()
        self.label=label; self.color=color
        self.max_val=max_val; self.unit=unit
        self._data:list[float]=[]
        self.setMinimumHeight(90); self.setMaximumHeight(120)
        self.setObjectName("card")
        self._cur=0.0

    def push(self,val:float):
        self._cur=val; self._data.append(val)
        if len(self._data)>80: self._data.pop(0)
        self.update()

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        D=THEMES["dark"]; w=self.width(); h=self.height()
        # bg
        p.fillRect(0,0,w,h,QColor(D["bg2"]))
        # border
        p.setPen(QPen(QColor(D["brd"]),1)); p.drawRect(0,0,w-1,h-1)
        # label + value
        p.setPen(QColor(D["txt2"]))
        p.setFont(QFont("Consolas",9))
        p.drawText(8,14,self.label)
        p.setPen(QColor(self.color))
        p.setFont(QFont("Consolas",16,QFont.Weight.Bold))
        p.drawText(8,h-8,f"{self._cur:.1f}{self.unit}")
        # line
        if len(self._data)<2: return
        pad_x=4; pad_y=20; ch=h-pad_y-30; cw=w-pad_x*2
        path=QPainterPath()
        for i,v in enumerate(self._data):
            x=pad_x+i*cw/max(len(self._data)-1,1)
            y=pad_y+ch*(1-min(v,self.max_val)/self.max_val)
            if i==0: path.moveTo(x,y)
            else:    path.lineTo(x,y)
        p.setPen(QPen(QColor(self.color),2)); p.drawPath(path)
        # fill under
        fill_path=QPainterPath(path)
        fill_path.lineTo(pad_x+cw,h-8); fill_path.lineTo(pad_x,h-8); fill_path.closeSubpath()
        c=QColor(self.color); c.setAlpha(25)
        p.fillPath(fill_path,QBrush(c))
        p.end()

# ═══════════════════════════════════════════════════════════════
#  CONSOLE TAB
# ═══════════════════════════════════════════════════════════════
class ConsoleTab(QWidget):
    def __init__(self,srv_ref,cfg):
        super().__init__(); self.srv_ref=srv_ref; self.cfg=cfg
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(8)
        self.box=QTextEdit(); self.box.setReadOnly(True); v.addWidget(self.box)
        h=QHBoxLayout()
        self.inp=QLineEdit(); self.inp.setPlaceholderText("/say Hello...")
        self.inp.returnPressed.connect(self.send); h.addWidget(self.inp)
        h.addWidget(mk_btn(tr("console_send","Send"),"pa").__class__(
            tr("console_send","Send"),clicked=self.send,objectName="pa"))
        clear_btn = mk_btn(tr("console_clear","Clear"))
        clear_btn.clicked.connect(self.box.clear)
        h.addWidget(clear_btn)
        v.addLayout(h)
        self.log("SYS",f"{APP_NAME} v{APP_VERSION}")

    def log(self,level:str,msg:str):
        D=THEMES.get(self.cfg.get("theme","dark"),THEMES["dark"])
        A=ACCENTS.get(self.cfg.get("accent","green"),ACCENTS["green"])[0]
        c={"INFO":A,"WARN":D["yel"],"ERROR":D["red"],"CMD":"#4ab4ff","SYS":D["txt2"]}.get(level,D["txt"])
        self.box.append(
            f'<span style="color:{D["txt2"]}">{now()}</span> '
            f'<span style="color:{c}">[{level}]</span> '
            f'<span style="color:{D["txt"]}">{msg}</span>')
        self.box.moveCursor(QTextCursor.MoveOperation.End)

    def send(self):
        cmd=self.inp.text().strip()
        if not cmd: return
        self.log("CMD",f"> {cmd}"); self.inp.clear()
        proc=self.srv_ref.get("process")
        if proc and proc._running: proc.send(cmd)
        else: self.log("WARN",tr("console_server_offline","Server not running"))

# ═══════════════════════════════════════════════════════════════
#  SERVERS TAB
# ═══════════════════════════════════════════════════════════════
class ServersTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        h=QHBoxLayout(self); h.setContentsMargins(0,0,0,0)
        sp=QSplitter(Qt.Orientation.Horizontal)

        lw=QWidget(); ll=QVBoxLayout(lw); ll.setContentsMargins(10,10,6,10)
        ll.addWidget(sec_lbl(tr("servers_title","Servers")))
        self.lst=QListWidget(); self.lst.currentRowChanged.connect(self._sel)
        ll.addWidget(self.lst)
        br=QHBoxLayout()
        ab=mk_btn(tr("servers_add","+ Add"),"pa"); ab.clicked.connect(self._add)
        db=mk_btn(tr("servers_del","Delete"),"pr"); db.clicked.connect(self._del)
        br.addWidget(ab); br.addWidget(db); ll.addLayout(br)

        rw=QWidget(); rl=QVBoxLayout(rw); rl.setContentsMargins(6,10,10,10)
        sc=QScrollArea(); sc.setWidgetResizable(True)
        iw=QWidget(); il=QVBoxLayout(iw); il.setSpacing(10)

        frm=QFormLayout(); frm.setSpacing(8)
        frm.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_name=QLineEdit()
        self.f_jar=QLineEdit()
        self.f_dir=QLineEdit()
        self.f_ram=QSpinBox(); self.f_ram.setRange(256,65536)
        self.f_ram.setValue(1024); self.f_ram.setSuffix(" MB")
        self.f_port=QSpinBox(); self.f_port.setRange(1024,65535); self.f_port.setValue(25565)

        # Java picker — виправлено щоб НЕ дублювати емодзі
        jcont=QWidget(); jh=QHBoxLayout(jcont); jh.setContentsMargins(0,0,0,0)
        self.f_java=QComboBox(); self.f_java.setEditable(True)
        self.f_java.setInsertPolicy(QComboBox.InsertPolicy.InsertAtTop)
        self.f_java.addItem("java (system)","java")
        jh.addWidget(self.f_java,1)
        sc_b=mk_btn("?","pb"); sc_b.setFixedWidth(34)
        sc_b.setToolTip(tr("java_scan_tip","Scan for Java"))
        sc_b.clicked.connect(self._scan_java)
        brj=mk_btn("..."); brj.setFixedWidth(34); brj.clicked.connect(self._browse_java)
        jh.addWidget(sc_b); jh.addWidget(brj)

        def _jar_row():
            c=QWidget(); ch=QHBoxLayout(c); ch.setContentsMargins(0,0,0,0)
            ch.addWidget(self.f_jar,1)
            b=mk_btn("..."); b.setFixedWidth(34); b.clicked.connect(self._browse_jar); ch.addWidget(b)
            return c
        def _dir_row():
            c=QWidget(); ch=QHBoxLayout(c); ch.setContentsMargins(0,0,0,0)
            ch.addWidget(self.f_dir,1)
            b=mk_btn("..."); b.setFixedWidth(34); b.clicked.connect(self._browse_dir); ch.addWidget(b)
            return c

        frm.addRow(tr("servers_name","Name:"),self.f_name)
        frm.addRow(tr("servers_jar","Jar:"),_jar_row())
        frm.addRow(tr("servers_dir","Dir:"),_dir_row())
        frm.addRow(tr("servers_ram","RAM:"),self.f_ram)
        frm.addRow(tr("servers_java","Java:"),jcont)
        frm.addRow(tr("servers_port","Port:"),self.f_port)
        il.addLayout(frm)

        eh=QHBoxLayout()
        self.eula_chk=QCheckBox(tr("servers_eula","Accept EULA"))
        eb=mk_btn(tr("servers_eula_btn","Create eula.txt")); eb.clicked.connect(self._eula)
        eh.addWidget(self.eula_chk); eh.addWidget(eb); eh.addStretch(); il.addLayout(eh)

        rg=QGroupBox(tr("servers_rcon_group","RCON"))
        rf=QFormLayout(rg); rf.setSpacing(6)
        self.f_rh=QLineEdit(); self.f_rh.setPlaceholderText("127.0.0.1")
        self.f_rp=QSpinBox(); self.f_rp.setRange(1,65535); self.f_rp.setValue(25575)
        self.f_rpass=QLineEdit(); self.f_rpass.setEchoMode(QLineEdit.EchoMode.Password)
        rf.addRow(tr("servers_rcon_host","Host:"),self.f_rh)
        rf.addRow(tr("servers_rcon_port","Port:"),self.f_rp)
        rf.addRow(tr("servers_rcon_pass","Pass:"),self.f_rpass)
        rf.addRow("",hint_lbl("enable-rcon=true, rcon.password=... in server.properties"))
        il.addWidget(rg)

        ag=QGroupBox(tr("servers_api_group","Custom API"))
        af=QFormLayout(ag); af.setSpacing(6)
        self.f_api_url=QLineEdit(); self.f_api_url.setPlaceholderText("http://localhost:8080")
        self.f_api_key=QLineEdit(); self.f_api_key.setPlaceholderText("api-key")
        af.addRow(tr("servers_api_url","URL:"),self.f_api_url)
        af.addRow(tr("servers_api_key","Key:"),self.f_api_key)
        af.addRow("",hint_lbl(tr("servers_api_hint","Optional REST API")))
        il.addWidget(ag)

        sv=mk_btn(tr("servers_save","Save"),"pa"); sv.clicked.connect(self._save); il.addWidget(sv)
        rh=QHBoxLayout()
        self.start_b=mk_btn(tr("servers_start","Start"),"pa"); self.start_b.clicked.connect(self._start)
        self.stop_b=mk_btn(tr("servers_stop","Stop"),"pr"); self.stop_b.clicked.connect(self._stop)
        self.stop_b.setEnabled(False)
        rh.addWidget(self.start_b); rh.addWidget(self.stop_b)
        il.addLayout(rh); il.addStretch()
        sc.setWidget(iw); rl.addWidget(sc)
        sp.addWidget(lw); sp.addWidget(rw); sp.setSizes([210,640]); h.addWidget(sp)
        self._refresh()

    def _refresh(self):
        self.lst.clear()
        for s in self.cfg.get("servers",[]): self.lst.addItem(f"  {s['name']}")

    def _sel(self,idx):
        srvs=self.cfg.get("servers",[])
        if not(0<=idx<len(srvs)): return
        s=srvs[idx]
        self.f_name.setText(s.get("name",""))
        self.f_jar.setText(s.get("jar",""))
        self.f_dir.setText(s.get("dir",""))
        self.f_ram.setValue(s.get("ram",1024))
        self.f_port.setValue(s.get("port",25565))
        jv=s.get("java","java")
        match=-1
        for i in range(self.f_java.count()):
            d=self.f_java.itemData(i)
            if d==jv or self.f_java.itemText(i).split("  [")[0].strip()==jv:
                match=i; break
        if match>=0: self.f_java.setCurrentIndex(match)
        else: self.f_java.insertItem(0,jv,jv); self.f_java.setCurrentIndex(0)
        self.f_rh.setText(s.get("rcon_host","127.0.0.1"))
        self.f_rp.setValue(s.get("rcon_port",25575))
        self.f_rpass.setText(s.get("rcon_pass",""))
        self.f_api_url.setText(s.get("api_url",""))
        self.f_api_key.setText(s.get("api_key",""))
        self.srv_ref["current_idx"]=idx

    def _get_java(self)->str:
        d=self.f_java.currentData()
        if d: return str(d)
        return self.f_java.currentText().split("  [")[0].strip() or "java"

    def _scan_java(self):
        found=find_javas()
        d=QDialog(self); d.setWindowTitle(tr("java_scan_title","Found Java")); d.setMinimumWidth(560)
        dv=QVBoxLayout(d); dv.addWidget(QLabel(tr("java_scan_select","Select Java:")))
        lw=QListWidget()
        for j in found: lw.addItem(f"{j}  [{java_version(j)}]")
        dv.addWidget(lw)
        bh=QHBoxLayout()
        ob=mk_btn("OK","pa"); ob.clicked.connect(d.accept)
        cb=mk_btn(tr("dlg_cancel","Cancel")); cb.clicked.connect(d.reject)
        bh.addWidget(ob); bh.addWidget(cb); dv.addLayout(bh)
        if d.exec()==QDialog.DialogCode.Accepted and lw.currentRow()>=0:
            j=found[lw.currentRow()]; ver=java_version(j)
            # Додаємо без дублювання
            label=f"{j}  [{ver}]"
            for i in range(self.f_java.count()):
                if self.f_java.itemData(i)==j:
                    self.f_java.setCurrentIndex(i); return
            self.f_java.insertItem(0,label,j); self.f_java.setCurrentIndex(0)
            self.con.log("INFO",f"Java: {j} [{ver}]")

    def _browse_java(self):
        f,_=QFileDialog.getOpenFileName(self,"Java","","Executable (*.exe java);;All (*)")
        if f:
            ver=java_version(f); label=f"{f}  [{ver}]"
            for i in range(self.f_java.count()):
                if self.f_java.itemData(i)==f: self.f_java.setCurrentIndex(i); return
            self.f_java.insertItem(0,label,f); self.f_java.setCurrentIndex(0)

    def _browse_jar(self):
        f,_=QFileDialog.getOpenFileName(self,"JAR","","JAR (*.jar)")
        if f:
            self.f_jar.setText(f)
            if not self.f_dir.text(): self.f_dir.setText(str(Path(f).parent))

    def _browse_dir(self):
        d=QFileDialog.getExistingDirectory(self)
        if d: self.f_dir.setText(d)

    def _eula(self):
        d=self.f_dir.text().strip()
        if not d: QMessageBox.warning(self,"!",tr("servers_no_dir","Set dir first")); return
        (Path(d)/"eula.txt").write_text("eula=true\n")
        self.con.log("INFO",f"{tr('servers_eula_done','eula.txt created')}: {d}")

    def _add(self):
        name,ok=ask_input(self,tr("servers_new_name","Server name:"))
        if ok and name:
            self.cfg.setdefault("servers",[]).append({
                "name":name,"jar":"","dir":"","ram":1024,"java":"java","port":25565,
                "rcon_host":"127.0.0.1","rcon_port":25575,"rcon_pass":"",
                "api_url":"","api_key":"","players":[]})
            save_config(self.cfg); self._refresh()
            self.lst.setCurrentRow(len(self.cfg["servers"])-1)

    def _del(self):
        idx=self.lst.currentRow()
        if idx<0: return
        if confirm(self,tr("servers_del_confirm","Delete server?")):
            self.cfg["servers"].pop(idx); save_config(self.cfg); self._refresh()

    def _save(self):
        idx=self.lst.currentRow()
        if idx<0: return
        s=self.cfg["servers"][idx]
        s.update({"name":self.f_name.text(),"jar":self.f_jar.text(),
                  "dir":self.f_dir.text(),"ram":self.f_ram.value(),
                  "java":self._get_java(),"port":self.f_port.value(),
                  "rcon_host":self.f_rh.text(),"rcon_port":self.f_rp.value(),
                  "rcon_pass":self.f_rpass.text(),
                  "api_url":self.f_api_url.text(),"api_key":self.f_api_key.text()})
        save_config(self.cfg); self._refresh(); self.lst.setCurrentRow(idx)
        self.con.log("INFO",f"{tr('servers_saved','Saved')}: {s['name']}")

    def _start(self):
        idx=self.lst.currentRow()
        if idx<0: QMessageBox.warning(self,"!",tr("servers_select","Select server")); return
        s=self.cfg["servers"][idx]
        if not s.get("jar") or not Path(s["jar"]).exists():
            QMessageBox.warning(self,"!",tr("servers_no_jar","JAR not found")); return
        sdir=s.get("dir") or str(Path(s["jar"]).parent)
        java=self._get_java()
        proc=ServerProcess(java,s["jar"],s.get("ram",1024),sdir)
        proc.log_line.connect(self.con.log); proc.stopped.connect(self._stopped)
        proc.start(); self.srv_ref["process"]=proc
        self.start_b.setEnabled(False); self.stop_b.setEnabled(True)
        self.con.log("INFO",f"{tr('servers_starting','Starting')} '{s['name']}' — Java: {java}")

    def _stop(self):
        p=self.srv_ref.get("process")
        if p: p.stop()
        self.stop_b.setEnabled(False)

    def _stopped(self):
        self.start_b.setEnabled(True); self.stop_b.setEnabled(False)
        self.con.log("WARN",tr("servers_stopped","Server stopped"))

# ═══════════════════════════════════════════════════════════════
#  PLAYERS TAB
# ═══════════════════════════════════════════════════════════════
class PlayersTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        self._online:set=set()
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(8)
        top=QHBoxLayout()
        self.nick_inp=QLineEdit(); self.nick_inp.setPlaceholderText(tr("players_nick","Nick..."))
        self.rank_cb=QComboBox()
        self.rank_cb.addItems(["Player","VIP","Moderator","Admin"]); self.rank_cb.setFixedWidth(140)
        ab=mk_btn(tr("players_add","+ Add"),"pa"); ab.clicked.connect(self._add)
        rb=mk_btn(tr("players_refresh","Refresh")); rb.clicked.connect(self._refresh)
        top.addWidget(self.nick_inp); top.addWidget(self.rank_cb)
        top.addWidget(ab); top.addWidget(rb); v.addLayout(top)
        self.online_lbl=QLabel(""); self.online_lbl.setObjectName("online"); v.addWidget(self.online_lbl)
        self.tbl=QTableWidget(0,5)
        self.tbl.setHorizontalHeaderLabels([
            tr("players_nick","Nick"),tr("players_rank","Role"),
            tr("players_status","Status"),tr("players_ip","IP"),
            tr("players_actions","Actions")])
        self.tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.tbl.setColumnWidth(4,230); self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v.addWidget(self.tbl)
        bh=QHBoxLayout()
        for lbl,oid,act in [
            (tr("players_kick","Kick"),"py",lambda:self._act("kick")),
            (tr("players_ban","Ban"),"pr",lambda:self._act("ban")),
            (tr("players_op","OP"),"pb",lambda:self._act("op")),
            (tr("players_tp","TP"),"",lambda:self._act("tp")),
        ]:
            b=mk_btn(lbl,oid); b.clicked.connect(act); bh.addWidget(b)
        bh.addStretch(); v.addLayout(bh)
        self._players=[]; self._load()

    def _load(self):
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[])
        self._players=list(srvs[idx].get("players",[])) if 0<=idx<len(srvs) else []
        self._refresh()

    def _read_max(self)->str:
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[])
        if 0<=idx<len(srvs):
            sdir=srvs[idx].get("dir","")
            if sdir:
                pp=Path(sdir)/"server.properties"
                if pp.exists():
                    for line in pp.read_text(encoding="utf-8",errors="replace").splitlines():
                        if line.startswith("max-players"):
                            return line.split("=",1)[-1].strip()
        return "?"

    def on_join(self,nick:str):
        self._online.add(nick)
        for p in self._players:
            if p["nick"].lower()==nick.lower(): p["status"]=tr("players_online","Online"); break
        else: self._players.append({"nick":nick,"rank":"Player","status":tr("players_online","Online"),"ip":"—"})
        self._save(); self._refresh()
        self.con.log("INFO",f"{nick} {tr('players_joined','joined')}")

    def on_leave(self,nick:str):
        self._online.discard(nick)
        for p in self._players:
            if p["nick"].lower()==nick.lower(): p["status"]=tr("players_offline","Offline"); break
        self._save(); self._refresh()
        self.con.log("INFO",f"{nick} {tr('players_left','left')}")

    def _refresh(self):
        mx=self._read_max()
        online=sum(1 for p in self._players if p.get("status")==tr("players_online","Online"))
        self.online_lbl.setText(
            f"{tr('players_online_label','Online')}: {online} / {mx}  "
            f"({tr('in_db','in DB')}: {len(self._players)})")
        self.tbl.setRowCount(0)
        for p in self._players:
            r=self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r,0,QTableWidgetItem(p["nick"]))
            ri=QTableWidgetItem(p.get("rank","Player"))
            ri.setForeground(QColor({"Admin":"#ff4444","Moderator":"#4ab4ff","VIP":"#ffaa00",
                                     "Адмін":"#ff4444","Модератор":"#4ab4ff"}.get(p.get("rank",""),"#aab4c4")))
            self.tbl.setItem(r,1,ri)
            st=p.get("status",tr("players_offline","Offline"))
            si=QTableWidgetItem(st)
            si.setForeground(QColor("#00cc44" if st==tr("players_online","Online") else "#556677"))
            self.tbl.setItem(r,2,si)
            self.tbl.setItem(r,3,QTableWidgetItem(p.get("ip","—")))
            self.tbl.setItem(r,4,QTableWidgetItem(""))

    def _add(self):
        nick=self.nick_inp.text().strip()
        if not nick: return
        self._players.append({"nick":nick,"rank":self.rank_cb.currentText(),
                              "status":tr("players_offline","Offline"),"ip":"—"})
        self._save(); self.nick_inp.clear(); self._refresh()
        self.con.log("INFO",f"{tr('players_added','Added')}: {nick}")

    def _save(self):
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[])
        if 0<=idx<len(srvs): srvs[idx]["players"]=self._players; save_config(self.cfg)

    def _act(self,act:str):
        row=self.tbl.currentRow()
        if row<0 or row>=len(self._players): return
        nick=self._players[row]["nick"]
        cmd={"kick":f"kick {nick}","ban":f"ban {nick}",
             "op":f"op {nick}","tp":f"tp {nick} 0 64 0"}[act]
        proc=self.srv_ref.get("process")
        if proc and proc._running: proc.send(cmd); self.con.log("CMD",f"> {cmd}")
        else: self.con.log("WARN",f"{tr('players_server_offline','Server offline')} — /{cmd}")
        if act=="ban": self._players.pop(row); self._save(); self._refresh()

# ═══════════════════════════════════════════════════════════════
#  KERNELS + MODS
# ═══════════════════════════════════════════════════════════════
class KernelsTab(QWidget):
    def __init__(self,con,cfg):
        super().__init__(); self.con=con; self.cfg=cfg
        v=QVBoxLayout(self); v.setContentsMargins(0,0,0,0)
        tabs=QTabWidget()
        tabs.addTab(self._kernels_tab(),tr("tab_kernels_kern","Kernels"))
        tabs.addTab(self._mods_tab(),tr("tab_kernels_mods","Mods/Plugins"))
        v.addWidget(tabs)

    def _kernels_tab(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(10,10,10,10); v.setSpacing(8)
        r1=QHBoxLayout()
        self.k_type=QComboBox()
        self.k_type.addItems(["Paper","Purpur","Fabric","Vanilla","Forge","NeoForge"])
        r1.addWidget(QLabel(tr("kernels_type","Type:"))); r1.addWidget(self.k_type)
        self.k_filt=QLineEdit(); self.k_filt.setPlaceholderText(tr("kernels_filter_ph","e.g. 1.21"))
        r1.addWidget(QLabel(tr("kernels_filter","Filter:"))); r1.addWidget(self.k_filt)
        fb=mk_btn(tr("kernels_fetch","Get list"),"pb"); fb.clicked.connect(self._k_fetch)
        r1.addWidget(fb); v.addLayout(r1)
        self.k_list=QListWidget(); self.k_list.currentRowChanged.connect(self._k_sel)
        v.addWidget(self.k_list)
        self.k_note=QLabel(""); self.k_note.setObjectName("hint"); v.addWidget(self.k_note)
        r2=QHBoxLayout()
        self.k_dest=QLineEdit(); self.k_dest.setPlaceholderText(tr("kernels_dest","Save folder..."))
        r2.addWidget(self.k_dest)
        br=mk_btn("..."); br.setFixedWidth(34)
        br.clicked.connect(lambda:self.k_dest.setText(
            QFileDialog.getExistingDirectory(self) or self.k_dest.text()))
        r2.addWidget(br); v.addLayout(r2)
        self.k_prog=QProgressBar(); self.k_prog.setVisible(False); v.addWidget(self.k_prog)
        self.k_stat=QLabel(""); v.addWidget(self.k_stat)
        db=mk_btn(tr("kernels_download","Download"),"pa"); db.clicked.connect(self._k_download)
        v.addWidget(db); self._kernels=[]; return w

    def _k_fetch(self):
        kt=self.k_type.currentText(); mf=self.k_filt.text()
        self.k_list.clear(); self.k_list.addItem(f"{tr('kernels_fetching','Loading')}...")
        self.con.log("INFO",f"{tr('kernels_fetch_start','Fetching')} {kt}...")
        t=KernelFetchThread(kt,mf); t.result.connect(self._k_on_list)
        t.error.connect(self._k_err); t.start(); self._kft=t

    def _k_on_list(self,kernels):
        self._kernels=kernels; self.k_list.clear()
        for k in kernels: self.k_list.addItem(k["name"])
        self.con.log("INFO",f"{tr('kernels_found','Found')}: {len(kernels)}" if kernels
                     else tr("kernels_none","Nothing found"))
        if not kernels: self.k_list.addItem(tr("kernels_none","Nothing found"))

    def _k_sel(self,idx):
        if 0<=idx<len(self._kernels):
            self.k_note.setText(self._kernels[idx].get("note",""))

    def _k_err(self,e):
        self.k_list.clear(); self.k_list.addItem(f"ERROR: {e}")
        self.con.log("ERROR",f"{tr('kernels_fetch_error','Error')}: {e}")

    def _k_download(self):
        idx=self.k_list.currentRow()
        if idx<0 or idx>=len(self._kernels):
            QMessageBox.warning(self,"!",tr("kernels_select","Select version")); return
        dd=self.k_dest.text().strip()
        if not dd: QMessageBox.warning(self,"!",tr("kernels_no_dest","Set folder")); return
        k=self._kernels[idx]
        dest=os.path.join(dd,k.get("fname",k["name"].replace(" ","_")+".jar"))
        self.k_prog.setVisible(True); self.k_prog.setValue(0)
        self.k_stat.setText(f"Downloading {k['name']}...")
        self.con.log("INFO",f"Downloading {k['name']}")
        t=DownloadThread(k["url"],dest)
        t.progress.connect(self.k_prog.setValue)
        t.done.connect(lambda p:(self.k_stat.setText(f"OK: {p}"),self.con.log("INFO",f"Done: {p}")))
        t.error.connect(lambda e:(self.k_stat.setText(f"ERROR: {e}"),self.con.log("ERROR",e)))
        t.start(); self._kdt=t

    def _mods_tab(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(10,10,10,10); v.setSpacing(8)
        r1=QHBoxLayout()
        self.m_q=QLineEdit(); self.m_q.setPlaceholderText(tr("mods_search_ph","Search..."))
        self.m_q.returnPressed.connect(self._m_search); r1.addWidget(self.m_q)
        self.m_src=QComboBox(); self.m_src.addItems(["Modrinth","Hangar (Paper)"])
        self.m_src.setFixedWidth(170)
        r1.addWidget(QLabel(tr("mods_source","Source:"))); r1.addWidget(self.m_src)
        self.m_type=QComboBox()
        self.m_type.addItems(["All","Plugin / Plugin","Mod / Mod",
                              "Datapack / Datapack","Shader / Shader","Resourcepack / Resourcepack"])
        self.m_type.setFixedWidth(230)
        r1.addWidget(QLabel(tr("mods_type","Type:"))); r1.addWidget(self.m_type)
        sb=mk_btn(tr("mods_search_btn","Search"),"pb"); sb.clicked.connect(self._m_search)
        r1.addWidget(sb); v.addLayout(r1)
        self.m_stat=QLabel(""); v.addWidget(self.m_stat)
        self.m_list=QListWidget(); self.m_list.currentRowChanged.connect(self._m_sel)
        v.addWidget(self.m_list)
        self.m_desc=QLabel(""); self.m_desc.setWordWrap(True); self.m_desc.setObjectName("hint")
        v.addWidget(self.m_desc)
        r2=QHBoxLayout(); r2.addWidget(QLabel(tr("mods_server_dir","Server folder:")))
        self.m_dest=QLineEdit(); r2.addWidget(self.m_dest)
        mb=mk_btn("..."); mb.setFixedWidth(34)
        mb.clicked.connect(lambda:self.m_dest.setText(
            QFileDialog.getExistingDirectory(self) or self.m_dest.text()))
        r2.addWidget(mb); v.addLayout(r2)
        self.m_prog=QProgressBar(); self.m_prog.setVisible(False); v.addWidget(self.m_prog)
        self.m_inst=QLabel(""); v.addWidget(self.m_inst)
        ib=mk_btn(tr("mods_install","Install"),"pa"); ib.clicked.connect(self._m_install)
        v.addWidget(ib); self._mods=[]; return w

    def _m_search(self):
        q=self.m_q.text().strip()
        if not q: return
        self.m_list.clear(); self.m_list.addItem(f"{tr('mods_searching','Searching')}...")
        t=ModSearchThread(q,self.m_src.currentText(),self.m_type.currentText())
        t.result.connect(self._m_on_list); t.error.connect(self._m_err)
        t.start(); self._mst=t

    def _m_on_list(self,mods):
        self._mods=mods; self.m_list.clear()
        if not mods:
            self.m_list.addItem(tr("mods_no_results","Nothing found"))
            self.m_stat.setText(tr("mods_no_results","Nothing")); return
        self.m_stat.setText(f"{tr('mods_results','Results')}: {len(mods)}")
        for m in mods: self.m_list.addItem(f"{m['name']}  [{m.get('type','')}]  downloads:{m.get('downloads',0):,}")

    def _m_sel(self,idx):
        if 0<=idx<len(self._mods):
            m=self._mods[idx]
            extra=f"  (browser only)" if m["source"]=="Hangar" else ""
            self.m_desc.setText(f"{m.get('description','')}  |  {m['source']} | {m.get('slug','')}{extra}")

    def _m_err(self,e):
        self.m_list.clear(); self.m_list.addItem(f"ERROR: {e}")

    def _m_install(self):
        idx=self.m_list.currentRow()
        if idx<0 or idx>=len(self._mods):
            QMessageBox.warning(self,"!",tr("mods_select","Select mod")); return
        dd=self.m_dest.text().strip()
        if not dd: QMessageBox.warning(self,"!",tr("mods_no_dir","Set folder")); return
        m=self._mods[idx]
        sub={"plugin":"plugins","mod":"mods","datapack":"datapacks",
             "shader":"shaderpacks","resourcepack":"resourcepacks"}.get(m.get("type","").lower(),"mods")
        final=os.path.join(dd,sub); os.makedirs(final,exist_ok=True)
        self.m_prog.setVisible(True); self.m_prog.setValue(0)
        self.m_inst.setText(f"{tr('mods_installing','Installing')}...")
        self.con.log("INFO",f"Installing {m['name']} -> {sub}/")
        t=ModInstallThread(m,final)
        t.progress.connect(self.m_prog.setValue)
        t.done.connect(self._m_done)
        t.error.connect(lambda e:(self.m_inst.setText(f"ERROR: {e}"),self.con.log("ERROR",e)))
        t.start(); self._mdt=t

    def _m_done(self,result:str):
        if result.startswith("browser:"):
            url=result[8:]
            QDesktopServices.openUrl(QUrl(url))
            self.m_inst.setText(f"Opened: {url}"); self.con.log("INFO",f"Hangar: {url}")
        else:
            self.m_inst.setText(f"OK: {result}"); self.con.log("INFO",f"Installed: {result}")

# ═══════════════════════════════════════════════════════════════
#  JAVA DOWNLOAD TAB
# ═══════════════════════════════════════════════════════════════
class JavaTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(10)
        v.addWidget(sec_lbl(tr("java_tab_title","Download Java")))
        v.addWidget(hint_lbl(tr("java_tab_hint",
            "Download Java JDK via Adoptium (Eclipse Temurin).\n"
            "After install — click Scan in Servers tab.")))
        r1=QHBoxLayout()
        r1.addWidget(QLabel(tr("java_version_label","Java version:")))
        self.ver_cb=QComboBox()
        # Усі актуальні LTS + non-LTS версії станом на 2025
        for major in [25,24,23,21,17,11,8]:
            lts=" (LTS)" if major in (21,17,11,8) else ""
            self.ver_cb.addItem(f"Java {major}{lts}",major)
        r1.addWidget(self.ver_cb)
        fb=mk_btn(tr("java_fetch","Find for download"),"pb"); fb.clicked.connect(self._fetch)
        r1.addWidget(fb); r1.addStretch(); v.addLayout(r1)
        self.result_lbl=QLabel(""); v.addWidget(self.result_lbl)
        self.jlist=QListWidget(); self.jlist.currentRowChanged.connect(self._on_sel)
        v.addWidget(self.jlist)
        self.desc_lbl=QLabel(""); self.desc_lbl.setObjectName("hint")
        self.desc_lbl.setWordWrap(True); v.addWidget(self.desc_lbl)
        r2=QHBoxLayout()
        r2.addWidget(QLabel(tr("java_dest","Save folder:")))
        self.dest_inp=QLineEdit(); self.dest_inp.setPlaceholderText(tr("java_dest_ph","Folder for .msi/.zip..."))
        r2.addWidget(self.dest_inp)
        br=mk_btn("..."); br.setFixedWidth(34)
        br.clicked.connect(lambda:self.dest_inp.setText(
            QFileDialog.getExistingDirectory(self) or self.dest_inp.text()))
        r2.addWidget(br); v.addLayout(r2)
        self.prog=QProgressBar(); self.prog.setVisible(False); v.addWidget(self.prog)
        self.stat=QLabel(""); v.addWidget(self.stat)
        dl=mk_btn(tr("java_download","Download Java"),"pa"); dl.clicked.connect(self._download)
        v.addWidget(dl)
        v.addWidget(hint_lbl(tr("java_install_note",
            "After download:\n"
            "  .msi / .pkg — run installer\n"
            "  .zip / .tar.gz — extract to any folder\n"
            "Then in Servers tab click Scan — the new Java will appear.")))
        v.addStretch(); self._items=[]

    def _fetch(self):
        major=self.ver_cb.currentData()
        self.jlist.clear(); self.jlist.addItem(f"{tr('java_fetching','Searching')} Java {major}...")
        t=JavaFetchThread(major); t.result.connect(self._on_result)
        t.error.connect(self._on_err); t.start(); self._jft=t

    def _on_result(self,items):
        self._items=items; self.jlist.clear()
        if not items:
            self.jlist.addItem(tr("java_none","Not found"))
            self.result_lbl.setText(tr("java_none","Not found")); return
        self.result_lbl.setText(f"{tr('java_found','Found')}: {len(items)}")
        for it in items: self.jlist.addItem(f"{it['name']}  —  {it['fname']}")
        self.jlist.setCurrentRow(0)

    def _on_sel(self,idx):
        if 0<=idx<len(self._items):
            it=self._items[idx]
            self.desc_lbl.setText(f"Version: {it['version']}  |  File: {it['fname']}")

    def _on_err(self,e):
        self.jlist.clear(); self.jlist.addItem(f"ERROR: {e}")
        self.con.log("ERROR",f"Java fetch: {e}")

    def _download(self):
        idx=self.jlist.currentRow()
        if idx<0 or idx>=len(self._items):
            QMessageBox.warning(self,"!",tr("java_select","Select version")); return
        dd=self.dest_inp.text().strip()
        if not dd: QMessageBox.warning(self,"!",tr("java_no_dest","Set folder")); return
        it=self._items[idx]; dest=os.path.join(dd,it["fname"])
        self.prog.setVisible(True); self.prog.setValue(0)
        self.stat.setText(f"Downloading {it['name']}...")
        self.con.log("INFO",f"Downloading Java {it['version']}")
        t=DownloadThread(it["url"],dest)
        t.progress.connect(self.prog.setValue)
        t.done.connect(lambda p:(self.stat.setText(f"OK: {p}"),
                                 self.con.log("INFO",f"Java saved: {p}")))
        t.error.connect(lambda e:(self.stat.setText(f"ERROR: {e}"),self.con.log("ERROR",e)))
        t.start(); self._jdt=t

# ═══════════════════════════════════════════════════════════════
#  MONITOR TAB  (графіки ресурсів)
# ═══════════════════════════════════════════════════════════════
class MonitorTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(10)
        v.addWidget(sec_lbl(tr("monitor_tab","Server Monitor")))

        self.no_srv=QLabel(tr("monitor_no_server","Start the server to see stats"))
        self.no_srv.setObjectName("hint"); self.no_srv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.no_srv)

        # Графіки
        grid=QHBoxLayout()
        A=ACCENTS.get(cfg.get("accent","green"),ACCENTS["green"])[0]
        self.ch_cpu=MiniChart(tr("monitor_cpu","CPU"),     "#4ab4ff",100,"%")
        self.ch_ram=MiniChart(tr("monitor_ram","RAM"),     A,         100,"%")
        self.ch_tps=MiniChart(tr("monitor_tps","TPS"),     "#00cc44",  20,"")
        self.ch_pl =MiniChart(tr("monitor_players","Players"),"#ffaa00",50,"")
        for c in (self.ch_cpu,self.ch_ram,self.ch_tps,self.ch_pl):
            grid.addWidget(c)
        v.addLayout(grid)

        # Stats table
        self.stats_tbl=QTableWidget(0,2)
        self.stats_tbl.setHorizontalHeaderLabels(["Metric","Value"])
        self.stats_tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.stats_tbl.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.stats_tbl.verticalHeader().setVisible(False)
        self.stats_tbl.setMaximumHeight(200); v.addWidget(self.stats_tbl)
        v.addStretch()

        # Таймер оновлення
        self._tick_n=0
        self._timer=QTimer(self); self._timer.timeout.connect(self._update)
        self._timer.start(2000)

    def _update(self):
        proc=self.srv_ref.get("process")
        alive=proc is not None and proc._running
        self.no_srv.setVisible(not alive)
        for c in (self.ch_cpu,self.ch_ram,self.ch_tps,self.ch_pl):
            c.setVisible(alive)

        if not alive: return
        self._tick_n+=1

        # Намагаємось отримати реальні дані через psutil (якщо встановлено)
        cpu_val=0.0; ram_val=0.0
        try:
            import psutil
            if proc._proc and proc._proc.pid:
                try:
                    ps=psutil.Process(proc._proc.pid)
                    cpu_val=ps.cpu_percent(interval=None)
                    mem=ps.memory_info()
                    # % від системної RAM
                    total=psutil.virtual_memory().total
                    ram_val=mem.rss*100/total if total else 0
                except Exception: pass
        except ImportError:
            # psutil не встановлено — показуємо заглушку
            import math
            cpu_val=15+10*abs(math.sin(self._tick_n*0.3))
            ram_val=30+5*abs(math.sin(self._tick_n*0.2))

        # TPS і гравці — парсимо з конфігу (реальні через RCON або лог)
        idx=self.srv_ref.get("current_idx",-1)
        srvs=self.cfg.get("servers",[])
        players=0
        if 0<=idx<len(srvs):
            players=sum(1 for p in srvs[idx].get("players",[])
                       if p.get("status") in ("Online","Онлайн"))

        tps=20.0  # нема прямого API без RCON

        self.ch_cpu.push(cpu_val); self.ch_ram.push(ram_val)
        self.ch_tps.push(tps);     self.ch_pl.push(float(players))

        # Оновлюємо таблицю
        rows=[
            (tr("monitor_cpu","CPU"),       f"{cpu_val:.1f}%"),
            (tr("monitor_ram","RAM"),        f"{ram_val:.1f}%"),
            (tr("monitor_tps","TPS"),        f"{tps:.1f}"),
            (tr("monitor_players","Players"),str(players)),
            ("PID", str(proc._proc.pid) if proc._proc else "—"),
        ]
        self.stats_tbl.setRowCount(len(rows))
        for i,(k,val) in enumerate(rows):
            self.stats_tbl.setItem(i,0,QTableWidgetItem(k))
            self.stats_tbl.setItem(i,1,QTableWidgetItem(val))

# ═══════════════════════════════════════════════════════════════
#  BACKUP TAB
# ═══════════════════════════════════════════════════════════════
class BackupTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(10)
        v.addWidget(sec_lbl(tr("backup_tab","Backup")))

        # Source
        sg=QGroupBox("Source"); sf=QFormLayout(sg); sf.setSpacing(8)
        self.src_inp=QLineEdit(); self.src_inp.setPlaceholderText("Server folder...")
        sh=QHBoxLayout(); sh.addWidget(self.src_inp)
        sb_b=mk_btn("..."); sb_b.setFixedWidth(34)
        sb_b.clicked.connect(self._browse_src); sh.addWidget(sb_b)
        sw=QWidget(); sw.setLayout(sh); sf.addRow("Server dir:",sw)
        v.addWidget(sg)

        # Destination
        dg=QGroupBox(tr("backup_dir","Backup destination"))
        df=QFormLayout(dg); df.setSpacing(8)
        self.dst_inp=QLineEdit(); self.dst_inp.setPlaceholderText("Backup folder...")
        dh=QHBoxLayout(); dh.addWidget(self.dst_inp)
        db_b=mk_btn("..."); db_b.setFixedWidth(34)
        db_b.clicked.connect(self._browse_dst); dh.addWidget(db_b)
        dw=QWidget(); dw.setLayout(dh); df.addRow(tr("backup_dir","Destination:"),dw)
        v.addWidget(dg)

        # Options
        og=QGroupBox("Options"); of=QFormLayout(og); of.setSpacing(8)
        self.zip_chk=QCheckBox("ZIP archive"); self.zip_chk.setChecked(True)
        self.worlds_chk=QCheckBox("Include world"); self.worlds_chk.setChecked(True)
        self.plugins_chk=QCheckBox("Include plugins/"); self.plugins_chk.setChecked(True)
        self.props_chk=QCheckBox("Include server.properties"); self.props_chk.setChecked(True)
        of.addRow("",self.zip_chk); of.addRow("",self.worlds_chk)
        of.addRow("",self.plugins_chk); of.addRow("",self.props_chk)
        v.addWidget(og)

        # Auto backup
        ag=QGroupBox(tr("backup_auto","Auto backup"))
        af=QFormLayout(ag); af.setSpacing(8)
        self.auto_chk=QCheckBox(tr("backup_auto","Enable auto backup"))
        self.auto_chk.toggled.connect(self._toggle_auto)
        self.interval_sp=QSpinBox(); self.interval_sp.setRange(5,1440)
        self.interval_sp.setValue(60); self.interval_sp.setSuffix(" min")
        af.addRow("",self.auto_chk)
        af.addRow(tr("backup_interval","Interval:"),self.interval_sp)
        v.addWidget(ag)

        # Run
        self.run_b=mk_btn(tr("backup_run","Create Backup Now"),"pa")
        self.run_b.clicked.connect(self._run); v.addWidget(self.run_b)
        self.stat_lbl=QLabel(""); v.addWidget(self.stat_lbl)
        self.prog=QProgressBar(); self.prog.setVisible(False); v.addWidget(self.prog)

        # Log
        v.addWidget(sec_lbl("Log"))
        self.log_box=QTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120); v.addWidget(self.log_box)
        v.addStretch()

        self._auto_timer=QTimer(self); self._auto_timer.timeout.connect(self._auto_backup)
        self._preload()

    def _preload(self):
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[])
        if 0<=idx<len(srvs):
            self.src_inp.setText(srvs[idx].get("dir",""))

    def _browse_src(self):
        d=QFileDialog.getExistingDirectory(self)
        if d: self.src_inp.setText(d)

    def _browse_dst(self):
        d=QFileDialog.getExistingDirectory(self)
        if d: self.dst_inp.setText(d)

    def _toggle_auto(self,enabled:bool):
        if enabled:
            mins=self.interval_sp.value()
            self._auto_timer.start(mins*60*1000)
            self._log(f"Auto backup enabled every {mins} min")
        else:
            self._auto_timer.stop(); self._log("Auto backup disabled")

    def _auto_backup(self): self._run(auto=True)

    def _log(self,msg:str):
        self.log_box.append(f'<span style="color:#556677">{now()}</span> {msg}')
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)

    def _run(self,auto=False):
        src=self.src_inp.text().strip(); dst=self.dst_inp.text().strip()
        if not src: QMessageBox.warning(self,"!","Set server folder"); return
        if not dst: QMessageBox.warning(self,"!",tr("backup_no_dir","Set backup folder")); return
        if not Path(src).exists(): QMessageBox.warning(self,"!","Source folder not found"); return

        self.run_b.setEnabled(False)
        self.stat_lbl.setText(tr("backup_running","Running backup..."))
        self.prog.setVisible(True); self.prog.setValue(0)
        label="AUTO" if auto else "MANUAL"
        self._log(f"[{label}] Starting backup: {src} -> {dst}")
        self.con.log("INFO",f"Backup [{label}]: {src}")

        t=threading.Thread(target=self._do_backup,args=(src,dst),daemon=True)
        t.start()

    def _do_backup(self,src:str,dst:str):
        from PyQt6.QtCore import QMetaObject, Q_ARG
        try:
            from datetime import datetime
            stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
            name=f"backup_{Path(src).name}_{stamp}"

            # Збираємо файли
            items=[]
            if self.worlds_chk.isChecked():
                for sub in ["world","world_nether","world_the_end"]:
                    p=Path(src)/sub
                    if p.exists(): items.append(p)
            if self.plugins_chk.isChecked():
                p=Path(src)/"plugins"
                if p.exists(): items.append(p)
            if self.props_chk.isChecked():
                for f in ["server.properties","ops.json","whitelist.json","banned-players.json"]:
                    p=Path(src)/f
                    if p.exists(): items.append(p)

            if not items:
                # backup entire server dir
                items=[Path(src)]

            if self.zip_chk.isChecked():
                import zipfile
                zip_path=Path(dst)/f"{name}.zip"
                total_files=sum(1 for item in items
                               for _ in (item.rglob("*") if item.is_dir() else [item]))
                done=0
                with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,
                                     compresslevel=6) as zf:
                    for item in items:
                        if item.is_dir():
                            for f in item.rglob("*"):
                                if f.is_file():
                                    zf.write(f,f.relative_to(Path(src).parent))
                                    done+=1
                                    if total_files>0:
                                        pct=int(done*100/total_files)
                                        self.prog.setValue(pct)
                        else:
                            zf.write(item,item.name); done+=1
                result=str(zip_path)
            else:
                out=Path(dst)/name; out.mkdir(parents=True,exist_ok=True)
                for item in items:
                    if item.is_dir():
                        shutil.copytree(item,out/item.name,dirs_exist_ok=True)
                    else:
                        shutil.copy2(item,out/item.name)
                result=str(out)

            self.prog.setValue(100)
            self.stat_lbl.setText(f"OK: {result}")
            self._log(f"Done: {result}")
            self.con.log("INFO",f"Backup done: {result}")
        except Exception as e:
            self.stat_lbl.setText(f"ERROR: {e}")
            self._log(f"ERROR: {e}")
            self.con.log("ERROR",f"Backup error: {e}")
        finally:
            self.run_b.setEnabled(True)
            self.prog.setVisible(False)

# ═══════════════════════════════════════════════════════════════
#  PROPERTIES TAB
# ═══════════════════════════════════════════════════════════════
PROPS_SCHEMA=[
    ("server-port",         "Port",                   "spin",  "25565",""),
    ("max-players",         "Max players",             "spin",  "20",""),
    ("gamemode",            "Gamemode",                "combo", "survival","survival,creative,adventure,spectator"),
    ("difficulty",          "Difficulty",              "combo", "normal","peaceful,easy,normal,hard"),
    ("level-name",          "World name",              "line",  "world",""),
    ("motd",                "MOTD",                   "line",  "A Minecraft Server","Shown in server list"),
    ("online-mode",         "Online mode",             "check", "true","Mojang auth"),
    ("white-list",          "Whitelist",              "check", "false",""),
    ("pvp",                 "PvP",                    "check", "true",""),
    ("enable-command-block","Command Blocks",          "check", "false",""),
    ("spawn-monsters",      "Spawn monsters",          "check", "true",""),
    ("spawn-animals",       "Spawn animals",           "check", "true",""),
    ("view-distance",       "View distance",           "spin",  "10","2–32"),
    ("simulation-distance", "Simulation distance",    "spin",  "10","2–32"),
    ("level-seed",          "Seed",                   "line",  "","Empty = random"),
    ("level-type",          "World type",             "combo", "minecraft:normal",
     "minecraft:normal,minecraft:flat,minecraft:large_biomes,minecraft:amplified"),
    ("allow-nether",        "Nether",                 "check", "true",""),
    ("spawn-protection",    "Spawn protection",        "spin",  "16","Radius in blocks"),
    ("enable-rcon",         "RCON",                   "check", "false",""),
    ("rcon.port",           "RCON port",              "spin",  "25575",""),
    ("rcon.password",       "RCON password",          "line",  "",""),
]

class PropertiesTab(QWidget):
    def __init__(self,cfg,srv_ref,con):
        super().__init__(); self.cfg=cfg; self.srv_ref=srv_ref; self.con=con
        self._path=None; self._wmap={}
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(6)
        top=QHBoxLayout()
        lb=mk_btn(tr("props_load","Load"),"pb"); lb.clicked.connect(self._load)
        sb=mk_btn(tr("props_save","Save"),"pa"); sb.clicked.connect(self._save)
        self.mode_b=mk_btn(tr("props_text_mode","Text mode"))
        self.mode_b.clicked.connect(self._toggle)
        top.addWidget(lb); top.addWidget(sb); top.addWidget(self.mode_b); top.addStretch()
        v.addLayout(top)
        self.stack=QStackedWidget()
        gui_w=QWidget(); gs=QScrollArea(); gs.setWidgetResizable(True)
        gi=QWidget(); gf=QFormLayout(gi)
        gf.setSpacing(8); gf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for key,label,wtype,default,comment in PROPS_SCHEMA:
            if wtype=="spin":
                w=QSpinBox(); w.setRange(0,99999)
                try: w.setValue(int(default))
                except: w.setValue(0)
            elif wtype=="combo":
                w=QComboBox()
                for opt in comment.split(","): w.addItem(opt.strip())
                i=w.findText(default)
                if i>=0: w.setCurrentIndex(i)
            elif wtype=="check":
                w=QCheckBox(); w.setChecked(default.lower()=="true")
            else:
                w=QLineEdit(); w.setText(default)
            self._wmap[key]=(w,wtype)
            ql=QLabel(f"<b>{label}</b><br><small style='color:#556677'>{key}</small>")
            ql.setTextFormat(Qt.TextFormat.RichText); gf.addRow(ql,w)
            if comment and wtype not in ("combo","check"):
                gf.addRow("",hint_lbl(comment))
        gs.setWidget(gi); gvl=QVBoxLayout(gui_w); gvl.addWidget(gs)
        self.stack.addWidget(gui_w)
        self.txt=QTextEdit(); self.txt.setFont(QFont("Consolas",11))
        self.txt.setPlaceholderText("# server.properties\n...")
        self.stack.addWidget(self.txt); v.addWidget(self.stack)

    def _toggle(self):
        if self.stack.currentIndex()==0:
            self.txt.setPlainText(self._gui_to_text())
            self.stack.setCurrentIndex(1); self.mode_b.setText(tr("props_gui_mode","GUI mode"))
        else:
            self._text_to_gui(self.txt.toPlainText())
            self.stack.setCurrentIndex(0); self.mode_b.setText(tr("props_text_mode","Text mode"))

    def _gui_to_text(self)->str:
        lines=["# server.properties","# Generated by CraftControl",""]
        for key,(w,wtype) in self._wmap.items():
            val=(str(w.value()) if wtype=="spin" else w.currentText() if wtype=="combo"
                 else("true" if w.isChecked() else "false") if wtype=="check" else w.text())
            lines.append(f"{key}={val}")
        return "\n".join(lines)

    def _text_to_gui(self,text:str):
        kv={}
        for line in text.splitlines():
            line=line.strip()
            if line.startswith("#") or "=" not in line: continue
            k,_,val=line.partition("="); kv[k.strip()]=val.strip()
        for key,(w,wtype) in self._wmap.items():
            val=kv.get(key)
            if val is None: continue
            if wtype=="spin":
                try: w.setValue(int(val))
                except: pass
            elif wtype=="combo":
                i=w.findText(val)
                if i>=0: w.setCurrentIndex(i)
            elif wtype=="check": w.setChecked(val.lower()=="true")
            else: w.setText(val)

    def _load(self):
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[]); sdir=""
        if 0<=idx<len(srvs): sdir=srvs[idx].get("dir","")
        f,_=QFileDialog.getOpenFileName(self,"server.properties",sdir,
                                        "Properties (*.properties);;All (*)")
        if not f: return
        self._path=f; text=Path(f).read_text(encoding="utf-8",errors="replace")
        self.txt.setPlainText(text); self._text_to_gui(text)
        self.con.log("INFO",f"{tr('props_loaded','Loaded')}: {f}")

    def _save(self):
        if not self._path:
            f,_=QFileDialog.getSaveFileName(self,"Save","server.properties","Properties (*.properties)")
            if not f: return; self._path=f
        text=self._gui_to_text() if self.stack.currentIndex()==0 else self.txt.toPlainText()
        Path(self._path).write_text(text,encoding="utf-8")
        self.con.log("INFO",f"{tr('props_saved','Saved')}: {self._path}")

# ═══════════════════════════════════════════════════════════════
#  WIKI TAB
# ═══════════════════════════════════════════════════════════════
class WikiTab(QWidget):
    ARTICLES=[
        {"title":"Quick Start","content":"# Quick Start\n\n1. Go to Kernels tab\n2. Select Paper → Get list → Download\n3. Servers tab → Add → set JAR + folder\n4. Click Create eula.txt\n5. Click Start"},
        {"title":"Playit.gg","content":"# Playit.gg\n\nNo port forwarding needed.\n1. Download playit.exe from playit.gg\n2. Run it → get your address\n3. Use that address to connect"},
        {"title":"TPS Optimization","content":"# TPS Optimization\n\nTarget: 20 TPS. Below 15 = lag.\n\nreduce view-distance=8\nreduce simulation-distance=6\n\nPlugins: Spark, ClearLag"},
        {"title":"Forge / NeoForge","content":"# Forge / NeoForge\n\n1. Download installer from Kernels tab\n2. Run: java -jar forge-...-installer.jar --installServer\n3. Run generated run.bat"},
        {"title":"Backups","content":"# Backups\n\nUse the Backup tab to zip:\n- world/\n- plugins/\n- server.properties"},
    ]

    def __init__(self):
        super().__init__()
        h=QHBoxLayout(self); h.setContentsMargins(0,0,0,0)
        sp=QSplitter(Qt.Orientation.Horizontal)
        lw=QWidget(); ll=QVBoxLayout(lw); ll.setContentsMargins(10,10,6,10)
        ll.addWidget(sec_lbl(tr("wiki_articles","Articles")))
        self.al=QListWidget(); self.al.currentRowChanged.connect(self._show); ll.addWidget(self.al)
        rw=QWidget(); rl=QVBoxLayout(rw); rl.setContentsMargins(6,10,10,10)
        self.tlbl=QLabel(""); self.tlbl.setStyleSheet("font-size:15px;font-weight:bold;padding:4px 0;")
        self.cont=QTextEdit(); self.cont.setReadOnly(True); self.cont.setFont(QFont("Consolas",11))
        wiki_url=tr("wiki_url","https://github.com/slavik2280034/CraftControl_Launcher_V2/wiki/Home_ua")
        self.link=QLabel(f'{tr("wiki_link_text","More info:")} <a href="{wiki_url}">{wiki_url}</a>')
        self.link.setOpenExternalLinks(True); self.link.setObjectName("hint"); self.link.setWordWrap(True)
        rl.addWidget(self.tlbl); rl.addWidget(self.cont); rl.addWidget(self.link)
        sp.addWidget(lw); sp.addWidget(rw); sp.setSizes([200,640]); h.addWidget(sp)
        self._arts=list(self.ARTICLES)
        for a in self._arts: self.al.addItem(a["title"])
        if self._arts: self.al.setCurrentRow(0)

    def _show(self,idx):
        if 0<=idx<len(self._arts):
            a=self._arts[idx]; self.tlbl.setText(a["title"]); self.cont.setPlainText(a["content"])

# ═══════════════════════════════════════════════════════════════
#  SETTINGS TAB
# ═══════════════════════════════════════════════════════════════
class SettingsTab(QWidget):
    apply_theme=pyqtSignal()

    def __init__(self,cfg):
        super().__init__(); self.cfg=cfg
        v=QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(12)

        ug=QGroupBox(tr("settings_ui_group","Interface")); uf=QFormLayout(ug); uf.setSpacing(8)
        self.lang_cb=QComboBox()
        if _LANGS:
            for code,info in _LANGS.items(): self.lang_cb.addItem(info["name"],code)
            cur=self.cfg.get("lang","uk")
            for i in range(self.lang_cb.count()):
                if self.lang_cb.itemData(i)==cur: self.lang_cb.setCurrentIndex(i); break
        else:
            self.lang_cb.addItem("No langs — add .py to langs/","none")
            self.lang_cb.setEnabled(False)
        uf.addRow(tr("settings_lang","Language:"),self.lang_cb)

        self.theme_cb=QComboBox()
        self.theme_cb.addItem(tr("settings_theme_dark","Dark"),"dark")
        self.theme_cb.addItem(tr("settings_theme_light","Light"),"light")
        if self.cfg.get("theme")=="light": self.theme_cb.setCurrentIndex(1)
        uf.addRow(tr("settings_theme","Theme:"),self.theme_cb)

        self.accent_cb=QComboBox()
        for k,l in [("green",tr("settings_accent_green","Green")),
                    ("blue",tr("settings_accent_blue","Blue")),
                    ("purple",tr("settings_accent_purple","Purple")),
                    ("orange",tr("settings_accent_orange","Orange"))]:
            self.accent_cb.addItem(l,k)
        ca=self.cfg.get("accent","green")
        for i in range(self.accent_cb.count()):
            if self.accent_cb.itemData(i)==ca: self.accent_cb.setCurrentIndex(i); break
        uf.addRow(tr("settings_accent","Accent:"),self.accent_cb)

        self.font_sp=QSpinBox(); self.font_sp.setRange(9,20); self.font_sp.setValue(self.cfg.get("font_size",12))
        uf.addRow(tr("settings_font_size","Font:"),self.font_sp)
        v.addWidget(ug)

        jg=QGroupBox(tr("settings_java_group","Java")); jf=QFormLayout(jg); jf.setSpacing(8)
        jh=QHBoxLayout(); self.java_inp=QLineEdit(); self.java_inp.setText(self.cfg.get("java_path","java"))
        jh.addWidget(self.java_inp,1)
        jbr=mk_btn("..."); jbr.setFixedWidth(34); jbr.clicked.connect(self._browse_java); jh.addWidget(jbr)
        jw=QWidget(); jw.setLayout(jh); jf.addRow(tr("settings_java_path","Path:"),jw)
        sh=QHBoxLayout()
        sb=mk_btn(tr("settings_java_detect","Scan for Java"),"pb"); sb.clicked.connect(self._scan_java)
        self.jver=QLabel(""); self.jver.setObjectName("hint")
        sh.addWidget(sb); sh.addWidget(self.jver); jf.addRow("",sh)
        v.addWidget(jg)

        pg=QGroupBox(tr("settings_playit_group","Playit.gg")); pf=QFormLayout(pg); pf.setSpacing(8)
        ph=QHBoxLayout(); self.playit_inp=QLineEdit(); self.playit_inp.setText(self.cfg.get("playit_path",""))
        ph.addWidget(self.playit_inp,1)
        pbr=mk_btn("..."); pbr.setFixedWidth(34); pbr.clicked.connect(self._browse_playit); ph.addWidget(pbr)
        pw=QWidget(); pw.setLayout(ph); pf.addRow(tr("settings_playit_path","playit.exe:"),pw)
        plh=QHBoxLayout()
        lb=mk_btn(tr("settings_playit_launch","Launch Playit"),"pa"); lb.clicked.connect(self._launch_playit)
        wb=mk_btn(tr("settings_playit_site","Website")); wb.clicked.connect(lambda:QDesktopServices.openUrl(QUrl("https://playit.gg")))
        plh.addWidget(lb); plh.addWidget(wb); plh.addStretch(); pf.addRow("",plh)
        v.addWidget(pg)

        svb=mk_btn(tr("settings_save","Save settings"),"pa"); svb.clicked.connect(self._save)
        self.slbl=QLabel(""); v.addWidget(svb); v.addWidget(self.slbl); v.addStretch()

    def _browse_java(self):
        f,_=QFileDialog.getOpenFileName(self,"Java","","Executable (*.exe java);;All (*)")
        if f: self.java_inp.setText(f); self.jver.setText(java_version(f))

    def _scan_java(self):
        found=find_javas()
        d=QDialog(self); d.setWindowTitle("Java"); d.setMinimumWidth(560)
        dv=QVBoxLayout(d); dv.addWidget(QLabel(tr("java_scan_select","Select Java:")))
        lw=QListWidget()
        for j in found: lw.addItem(f"{j}  [{java_version(j)}]")
        dv.addWidget(lw)
        bh=QHBoxLayout()
        ob=mk_btn("OK","pa"); ob.clicked.connect(d.accept)
        cb=mk_btn(tr("dlg_cancel","Cancel")); cb.clicked.connect(d.reject)
        bh.addWidget(ob); bh.addWidget(cb); dv.addLayout(bh)
        if d.exec()==QDialog.DialogCode.Accepted and lw.currentRow()>=0:
            j=found[lw.currentRow()]; self.java_inp.setText(j); self.jver.setText(java_version(j))

    def _browse_playit(self):
        f,_=QFileDialog.getOpenFileName(self,"playit","","Executable (*.exe);;All (*)")
        if f: self.playit_inp.setText(f)

    def _launch_playit(self):
        p=self.playit_inp.text().strip()
        if p and Path(p).exists(): subprocess.Popen([p])
        else: QDesktopServices.openUrl(QUrl("https://playit.gg/download"))

    def _save(self):
        self.cfg.update({"lang":self.lang_cb.currentData(),"theme":self.theme_cb.currentData(),
                         "accent":self.accent_cb.currentData(),"font_size":self.font_sp.value(),
                         "java_path":self.java_inp.text(),"playit_path":self.playit_inp.text()})
        save_config(self.cfg); _apply_lang(self.cfg["lang"])
        self.slbl.setText(f"OK! {tr('settings_saved','Restart for lang/theme changes.')}")
        self.apply_theme.emit()

# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg=load_config(); self.srv_ref={"process":None,"current_idx":-1}
        _apply_lang(self.cfg.get("lang","uk"))
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100,720); self.resize(1320,860)
        self._apply_css()

        self.con  =ConsoleTab(self.srv_ref,self.cfg)
        self.srvs =ServersTab(self.cfg,self.srv_ref,self.con)
        self.plrs =PlayersTab(self.cfg,self.srv_ref,self.con)
        self.kern =KernelsTab(self.con,self.cfg)
        self.jtab =JavaTab(self.cfg,self.srv_ref,self.con)
        self.mon  =MonitorTab(self.cfg,self.srv_ref,self.con)
        self.bkp  =BackupTab(self.cfg,self.srv_ref,self.con)
        self.prop =PropertiesTab(self.cfg,self.srv_ref,self.con)
        self.wiki =WikiTab()
        self.sets =SettingsTab(self.cfg)
        self.sets.apply_theme.connect(self._apply_css)

        # Hook player events
        orig=self.srvs._start
        def _patched():
            orig()
            proc=self.srv_ref.get("process")
            if proc:
                proc.player_join.connect(self.plrs.on_join)
                proc.player_leave.connect(self.plrs.on_leave)
        self.srvs._start=_patched

        self.tabs=QTabWidget()
        for w,l in [
            (self.con,  tr("tab_console","Console")),
            (self.srvs, tr("tab_servers","Servers")),
            (self.plrs, tr("tab_players","Players")),
            (self.kern, tr("tab_kernels","Kernels")),
            (self.jtab, tr("tab_java","Java")),
            (self.mon,  tr("monitor_tab","Monitor")),
            (self.bkp,  tr("backup_tab","Backup")),
            (self.prop, tr("tab_props","Properties")),
            (self.wiki, tr("tab_wiki","Wiki")),
            (self.sets, tr("tab_settings","Settings")),
        ]:
            self.tabs.addTab(w,l)
        self.setCentralWidget(self.tabs)

        tb=QToolBar(); tb.setMovable(False); self.addToolBar(tb)
        self.slbl=QLabel(f"  {tr('status_offline','Offline')}  "); tb.addWidget(self.slbl)
        tb.addSeparator()
        for lbl,fn in [
            (tr("toolbar_open_dir","Folder"),self._open_dir),
            (tr("toolbar_playit","Playit.gg"),lambda:QDesktopServices.openUrl(QUrl("https://playit.gg"))),
            (tr("toolbar_papermc","PaperMC"),lambda:QDesktopServices.openUrl(QUrl("https://papermc.io"))),
        ]:
            a=QAction(lbl,self); a.triggered.connect(fn); tb.addAction(a)

        self.sb=QStatusBar(); self.setStatusBar(self.sb)
        self.sb.showMessage(f"{APP_NAME} v{APP_VERSION}  |  {CONFIG_FILE}")
        self._timer=QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(2000)

    def _apply_css(self):
        self.setStyleSheet(build_css(self.cfg.get("theme","dark"),
                                     self.cfg.get("accent","green"),
                                     self.cfg.get("font_size",12)))

    def _tick(self):
        proc=self.srv_ref.get("process")
        A=ACCENTS.get(self.cfg.get("accent","green"),ACCENTS["green"])[0]
        D=THEMES.get(self.cfg.get("theme","dark"),THEMES["dark"])
        if proc and proc._running:
            self.slbl.setText(f"  {tr('status_online','Online')}  ")
            self.slbl.setStyleSheet(f"color:{A};font-size:12px")
        else:
            self.slbl.setText(f"  {tr('status_offline','Offline')}  ")
            self.slbl.setStyleSheet(f"color:{D['txt2']};font-size:12px")

    def _open_dir(self):
        idx=self.srv_ref.get("current_idx",-1); srvs=self.cfg.get("servers",[])
        if 0<=idx<len(srvs):
            d=srvs[idx].get("dir","")
            if d and Path(d).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(d)); return
        QMessageBox.information(self,"",tr("no_dir","Directory not set"))

    def closeEvent(self,e):
        proc=self.srv_ref.get("process")
        if proc and proc._running:
            if confirm(self,tr("dlg_exit","Server is running. Stop and exit?")):
                proc.stop(); e.accept()
            else: e.ignore()
        else: e.accept()

if __name__=="__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME)
    w=MainWindow(); w.show(); sys.exit(app.exec())
