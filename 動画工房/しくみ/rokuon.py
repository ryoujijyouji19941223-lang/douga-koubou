# -*- coding: utf-8 -*-
"""録音スタジオ。台本のAIのセリフを聞きながら、自分のセリフを録音する。
録音する.bat から呼ばれる。ブラウザで http://localhost:8765/ が開く。"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_video as mv  # noqa: E402

PORT = int(os.environ.get("ROKUON_PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()


class Problem(Exception):
    pass


def _stop(msg):
    raise Problem(msg)


mv.stop = _stop  # 止まるかわりに、画面にメッセージを返す


def load():
    s = mv.read_settings()
    theme, lines = mv.parse_script(mv.pick_script())
    q = s["聞く役の名前"]
    no = 0
    for i, l in enumerate(lines):
        l["i"] = i
        l["who"] = "Q" if l["name"] == q else "A"
        if l["who"] == "Q":
            no += 1
            l["rec"] = no
            l["has"] = bool(mv.find_recording(no))
    return s, theme, lines


def ai_voice(i):
    """i 行目の読み上げ（AIの行も、まだ録ってない自分の行の仮の声も）を作って、場所を返す。"""
    s, _, lines = load()
    if not (0 <= i < len(lines)):
        raise Problem("その行は台本に無いみたいや。ページを読み込み直してな。")
    l = lines[i]
    voice = s["聞く役の仮の声"] if l["who"] == "Q" else s["答える役の声"]
    key = hashlib.md5(f"{voice}|{s['話す速さ']}|{l['text']}".encode()).hexdigest()[:16]
    os.makedirs(os.path.join(mv.WORK, "声"), exist_ok=True)
    dst = os.path.join(mv.WORK, "声", f"tts_{key}.wav")  # 動画工房と同じ置き場所＝作り直しが要らん
    with LOCK:
        if not os.path.exists(dst):
            raw = dst + ".raw.wav"
            mv.tts(l["text"], voice, s["話す速さ"], raw)
            mv.normalize(raw, dst, trim=False)
            os.remove(raw)
    return dst


def save_take(no, data, ctype):
    os.makedirs(mv.VOICEDIR, exist_ok=True)
    old = os.path.join(mv.VOICEDIR, "前の録音")
    for ext in ("wav", "m4a", "mp3", "aac", "ogg", "flac", "webm", "mp4", "3gp", "amr"):
        f = os.path.join(mv.VOICEDIR, f"{no}.{ext}")
        if os.path.exists(f):
            os.makedirs(old, exist_ok=True)
            shutil.move(f, os.path.join(old, f"{no}_{time.strftime('%H%M%S')}.{ext}"))
    ext = "ogg" if "ogg" in ctype else "mp4" if "mp4" in ctype else "webm"
    with tempfile.NamedTemporaryFile(suffix="." + ext, delete=False) as t:
        t.write(data)
    try:
        r = subprocess.run(["ffmpeg", "-y", "-i", t.name, "-ac", "1", "-ar", "48000",
                            os.path.join(mv.VOICEDIR, f"{no}.wav")], capture_output=True)
        if r.returncode != 0:
            raise Problem("録音を保存できへんかった。もう一回録ってみて。")
    finally:
        os.remove(t.name)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file(self, path, ctype):
        with open(path, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p == "/":
                return self.file(os.path.join(HERE, "rokuon.html"), "text/html; charset=utf-8")
            if p == "/api/script":
                s, theme, lines = load()
                return self.send(200, {"theme": theme, "me": s["聞く役の名前"],
                                       "lines": [{k: l.get(k) for k in ("i", "name", "who", "text", "rec", "has")} for l in lines]})
            if p.startswith("/audio/ai/"):
                return self.file(ai_voice(int(p.rsplit("/", 1)[1])), "audio/wav")
            if p.startswith("/audio/rec/"):
                f = mv.find_recording(int(p.rsplit("/", 1)[1]))
                if not f:
                    return self.send(404, {"error": "まだ録ってへん"})
                return self.file(f, "audio/wav" if f.endswith(".wav") else "application/octet-stream")
            self.send(404, {"error": "無い"})
        except Problem as e:
            self.send(503, {"error": str(e)})
        except Exception as e:
            self.send(500, {"error": "思わぬところで止まった：" + repr(e)})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            if self.headers.get("Origin") not in (None, f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"):
                return self.send(403, {"error": "よそのページからは使えへん"})
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n)
            if p.startswith("/api/rec/"):
                save_take(int(p.rsplit("/", 1)[1]), data, self.headers.get("Content-Type", ""))
                return self.send(200, {"ok": True})
            if p == "/api/build":
                r = subprocess.run([sys.executable, os.path.join(HERE, "make_video.py")], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace",
                                   env=dict(os.environ, PYTHONIOENCODING="utf-8", DOUGA_NO_OPEN="1"))
                return self.send(200, {"ok": r.returncode == 0, "log": (r.stdout + r.stderr)[-3000:]})
            self.send(404, {"error": "無い"})
        except Problem as e:
            self.send(503, {"error": str(e)})
        except Exception as e:
            self.send(500, {"error": "思わぬところで止まった：" + repr(e)})


def main():
    if not shutil.which("ffmpeg"):
        print("× 録音を保存する道具（ffmpeg）が入ってへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。")
        sys.exit(1)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        print("録音スタジオはもう開いてるみたいや。ブラウザを見てな。")
        webbrowser.open(f"http://localhost:{PORT}/")
        return
    url = f"http://localhost:{PORT}/"
    print("=== 録音スタジオ ===")
    print("ブラウザで開いたで。開かへんかったら、ブラウザで " + url + " を開いてな。")
    print("終わったら、この黒い画面を閉じたら終了。")
    if os.environ.get("ROKUON_NO_BROWSER") != "1":
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
