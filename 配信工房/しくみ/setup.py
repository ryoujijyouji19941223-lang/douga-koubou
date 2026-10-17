# -*- coding: utf-8 -*-
"""配信工房の準備。OBS に「配信工房」のシーン一式を入れて、アバターとOBSをつなぐ。
はじめに一回だけ.bat から呼ばれる。フォルダを動かしたら、もう一回動かしてな。"""
import configparser, json, os, secrets, shutil, subprocess, sys, time, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "配信工房"
W, H = 1920, 1080


def say(m=""):
    print(m, flush=True)


def stop(m):
    say(); say("×  " + m); say(); sys.exit(1)


def fwd(p):
    return os.path.abspath(p).replace("\\", "/")


# ---------- OBS の場所 ----------
appdata = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
OBS_DIR = os.environ.get("OBS_CONFIG_DIR") or os.path.join(appdata, "obs-studio")
TEST = os.environ.get("HAISHIN_TEST") == "1"


def obs_running():
    if os.name != "nt":
        return False
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True, errors="replace")
    return "obs64.exe" in r.stdout


# ---------- 部品づくり ----------
def src(kind, versioned, name, settings, **extra):
    d = {"id": kind, "versioned_id": versioned, "name": name, "uuid": str(uuid.uuid4()),
         "settings": settings, "enabled": True, "muted": False, "volume": 1.0, "balance": 0.5,
         "mixers": 255, "flags": 0, "sync": 0, "monitoring_type": 0, "hotkeys": {},
         "private_settings": {}, "filters": [], "deinterlace_mode": 0, "deinterlace_field_order": 0,
         "push-to-mute": False, "push-to-mute-delay": 0, "push-to-talk": False, "push-to-talk-delay": 0}
    d.update(extra)
    return d


def item(s, idx, x=0, y=0, scale=1.0, visible=True, bounds=None, locked=False):
    it = {"name": s["name"], "source_uuid": s["uuid"], "id": idx, "visible": visible, "locked": locked,
          "rot": 0.0, "pos": {"x": float(x), "y": float(y)}, "scale": {"x": scale, "y": scale},
          "align": 5, "bounds_type": 0, "bounds_align": 0, "bounds": {"x": 0.0, "y": 0.0},
          "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
          "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
          "group_item_backup": False, "private_settings": {},
          "show_transition": {"duration": 0}, "hide_transition": {"duration": 0}}
    if bounds:
        it["bounds_type"] = 2  # 枠の中におさめる
        it["bounds"] = {"x": float(bounds[0]), "y": float(bounds[1])}
    return it


def scene(name, items):
    return src("scene", "scene", name, {"items": items, "id_counter": len(items), "custom_size": False})


def build_collection():
    P = lambda *a: fwd(os.path.join(ROOT, *a))
    browser = lambda name, file, w, h: src("browser_source", "browser_source", name, {
        "is_local_file": True, "local_file": P(file), "width": w, "height": h, "fps": 30,
        "css": "body { background-color: rgba(0, 0, 0, 0); margin: 0px auto; overflow: hidden; }",
        "shutdown": False, "restart_when_active": False, "reroute_audio": False})

    avatar = browser("アバター", "アバター.html", 800, 900)
    wait = browser("待機画面", "待機画面.html", W, H)
    end = browser("おわり画面", "おわり画面.html", W, H)
    title = src("text_gdiplus", "text_gdiplus_v2", "タイトル", {
        "read_from_file": True, "file": P("タイトル.txt"),
        "font": {"face": "BIZ UDPGothic", "size": 72, "style": "Bold", "flags": 1},
        "color": 4294967295, "outline": True, "outline_size": 8, "outline_color": 4279902226, "outline_opacity": 100})
    bgcolor = src("color_source", "color_source_v3", "背景の色", {"color": 4281022999, "width": W, "height": H})
    bgimage = src("image_source", "image_source", "背景の絵", {"file": P("背景", "背景.png"), "unload": False})
    game = src("game_capture", "game_capture", "ゲーム画面", {"capture_mode": "any_fullscreen", "capture_cursor": True})
    gamewin = src("window_capture", "window_capture", "ゲーム画面（ウィンドウ）", {"method": 2, "cursor": True})
    vsee = src("game_capture", "game_capture", "3Dアバター（VSeeFace）", {
        "capture_mode": "window", "window": "VSeeFace:UnityWndClass:VSeeFace.exe",
        "allow_transparency": True, "capture_cursor": False})

    zatsudan = scene("雑談", [
        item(bgcolor, 1, locked=True),
        item(bgimage, 2, bounds=(W, H), locked=True),
        item(avatar, 3, x=W - 800 - 120, y=H - 900),
        item(vsee, 4, visible=False, bounds=(W, H)),
        item(title, 5, x=70, y=50),
    ])
    gaming = scene("ゲーム", [
        item(game, 1, bounds=(W, H)),
        item(gamewin, 2, visible=False, bounds=(W, H)),
        item(avatar, 3, x=W - 360 - 30, y=H - 405, scale=0.45),
        item(vsee, 4, visible=False, x=W - 520, y=H - 585, bounds=(520, 585)),
        item(title, 5, x=30, y=24, scale=0.6),
    ])
    waiting = scene("待機中", [item(wait, 1, locked=True)])
    ending = scene("おわり", [item(end, 1, locked=True)])

    mic = src("wasapi_input_capture", "wasapi_input_capture", "マイク", {"device_id": "default"})
    mic["filters"] = [src("noise_suppress_filter", "noise_suppress_filter_v2", "雑音カット", {"method": "rnnoise"})]
    desk = src("wasapi_output_capture", "wasapi_output_capture", "デスクトップ音声", {"device_id": "default"})

    sources = [waiting, zatsudan, gaming, ending, avatar, wait, end, title, bgcolor, bgimage, game, gamewin, vsee]
    return {
        "name": NAME,
        "current_scene": "待機中", "current_program_scene": "待機中",
        "scene_order": [{"name": "待機中"}, {"name": "雑談"}, {"name": "ゲーム"}, {"name": "おわり"}],
        "sources": sources, "groups": [],
        "AuxAudioDevice1": mic, "DesktopAudioDevice1": desk,
        "current_transition": "フェード", "transition_duration": 300,
        "transitions": [{"id": "fade_transition", "name": "フェード", "settings": {}}],
        "quick_transitions": [], "saved_projectors": [], "modules": {},
        "preview_locked": False, "scaling_enabled": False, "scaling_level": 0,
        "scaling_off_x": 0.0, "scaling_off_y": 0.0,
    }


# ---------- ini の書き換え（ほかの設定は残す） ----------
def edit_ini(path, section, values, create=True):
    if not os.path.exists(path) and not create:
        return False
    cp = configparser.RawConfigParser(strict=False)
    cp.optionxform = str
    if os.path.exists(path):
        cp.read(path, encoding="utf-8-sig")
    if not cp.has_section(section):
        cp.add_section(section)
    for k, v in values.items():
        cp.set(section, k, v)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    return True


def main():
    say("=== 配信工房の準備 ===")
    if obs_running():
        stop("OBS が開いてる。OBS を閉じてから、もう一回ダブルクリックしてな。")
    if not os.path.isdir(OBS_DIR) and not TEST:
        stop("OBS をまだ一回も開いてないみたいや。OBS を一回開いて、最初の質問に答えて閉じてから、もう一回ダブルクリックしてな。")

    # 1. シーン一式
    scenes_dir = os.path.join(OBS_DIR, "basic", "scenes")
    os.makedirs(scenes_dir, exist_ok=True)
    out = os.path.join(scenes_dir, NAME + ".json")
    if os.path.exists(out):
        shutil.copy2(out, out + time.strftime(".%Y%m%d-%H%M%S.bak"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(build_collection(), f, ensure_ascii=False, indent=2)
    say("・シーンを入れた（待機中／雑談／ゲーム／おわり）")

    # 2. 画面の大きさと録画の置き場所
    prof = os.path.join(OBS_DIR, "basic", "profiles", NAME, "basic.ini")
    edit_ini(prof, "General", {"Name": NAME})
    edit_ini(prof, "Video", {"BaseCX": str(W), "BaseCY": str(H), "OutputCX": str(W), "OutputCY": str(H),
                             "FPSType": "0", "FPSCommon": "30"})
    edit_ini(prof, "Output", {"Mode": "Simple"})
    edit_ini(prof, "SimpleOutput", {"FilePath": os.path.join(ROOT, "録画"), "RecQuality": "Small"})
    say("・画面の大きさ（1920×1080）と、録画の置き場所を決めた")

    # 3. アバターがOBSからマイクの音量を受け取れるようにする
    pwfile = os.path.join(ROOT, "しくみ", "パスワード.txt")
    if os.path.exists(pwfile):
        pw = open(pwfile, encoding="utf-8").read().strip()
    else:
        pw = secrets.token_urlsafe(12)
        open(pwfile, "w", encoding="utf-8").write(pw)
    ws = {"ServerEnabled": "true", "ServerPort": "4455", "AuthRequired": "true",
          "ServerPassword": pw, "FirstLoad": "false", "AlertsEnabled": "false"}
    done = False
    for ini in ("user.ini", "global.ini"):
        done |= edit_ini(os.path.join(OBS_DIR, ini), "OBSWebSocket", ws, create=False)
    if not done:
        edit_ini(os.path.join(OBS_DIR, "user.ini"), "OBSWebSocket", ws)
    jdir = os.path.join(OBS_DIR, "plugin_config", "obs-websocket")
    os.makedirs(jdir, exist_ok=True)
    jpath = os.path.join(jdir, "config.json")
    try:
        j = json.load(open(jpath, encoding="utf-8")) if os.path.exists(jpath) else {}
    except Exception:
        j = {}
    j.update({"server_enabled": True, "server_port": 4455, "auth_required": True,
              "server_password": pw, "first_load": False, "alerts_enabled": False})
    json.dump(j, open(jpath, "w", encoding="utf-8"), indent=2)
    with open(os.path.join(ROOT, "しくみ", "接続.js"), "w", encoding="utf-8") as f:
        f.write("// 「はじめに一回だけ」で自動で書き換わる。触らんでええ。\n")
        f.write(f"OBS接続パスワード = {json.dumps(pw)};\nOBS接続ポート = 4455;\n")
    say("・アバターとOBSをつないだ")

    say()
    say("○ 準備できた！")
    say("   「雑談を録る」か「OBSを開く」をダブルクリックして始めてな。")
    say("   ※ このフォルダを別の場所に動かしたら、これをもう一回やってな。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        say(repr(e))
        stop("思わぬところで止まった。上のメッセージを Claude に見せてな。")
