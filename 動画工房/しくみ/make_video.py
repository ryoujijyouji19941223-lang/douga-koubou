# -*- coding: utf-8 -*-
"""台本.txt から、声・字幕・絵の付いた動画を作る。
動画を作る.bat から呼ばれる。中身は触らんでええ。"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
WORK = P("しくみ", "作業用")
OUT = P("できた動画")
VOICEDIR = P("自分の声")
PICDIR = P("絵")
W, H, FPS = 1920, 1080, 30
TEST = os.environ.get("DOUGA_TEST") == "1"


def say(msg=""):
    print(msg, flush=True)


def stop(msg):
    say()
    say("×  " + msg)
    say()
    sys.exit(1)


# ---------- 設定 ----------
def read_settings():
    s = {"聞く役の名前": "ととまる", "答える役の声": "青山龍星", "聞く役の仮の声": "玄野武宏", "話す速さ": "1.1"}
    path = P("設定.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            s[k.strip()] = v.strip()
    try:
        s["話す速さ"] = float(s["話す速さ"])
    except ValueError:
        s["話す速さ"] = 1.1
    return s


# ---------- 台本 ----------
def pick_script():
    """ダウンロードに新しい台本があれば、それを取り込む。"""
    local = P("台本.txt")
    dl = os.path.join(os.path.expanduser("~"), "Downloads")
    cands = [f for f in glob.glob(os.path.join(dl, "台本*.txt")) if os.path.isfile(f)]
    if cands:
        newest = max(cands, key=os.path.getmtime)
        if not os.path.exists(local) or os.path.getmtime(newest) > os.path.getmtime(local) + 1:
            if os.path.exists(local):
                os.makedirs(P("しくみ", "前の台本"), exist_ok=True)
                shutil.copy2(local, P("しくみ", "前の台本", time.strftime("%Y%m%d-%H%M%S") + ".txt"))
            shutil.copy2(newest, local)
            say("・ダウンロードにあった新しい台本を取り込んだ：" + os.path.basename(newest))
    if not os.path.exists(local):
        stop("台本.txt が見つからへん。このフォルダに 台本.txt を置いてな。")
    return local


def parse_script(path):
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    theme, lines = "", []
    i, n = 0, len(text)
    while i < n:
        # 行の頭
        j = text.find("\n", i)
        j = n if j < 0 else j
        head = text[i:j].strip()
        if not head:
            i = j + 1
            continue
        if head.startswith("#"):
            if not theme:
                theme = head.lstrip("#").strip()
            i = j + 1
            continue
        k = text.find("「", i)
        if k < 0 or k > j:
            i = j + 1  # 形の合わん行は飛ばす
            continue
        name = text[i:k].strip()
        k += 1
        buf = []
        while k < n:
            c = text[k]
            if c == "\\" and k + 1 < n and text[k + 1] in "「」":
                buf.append(text[k + 1]); k += 2; continue
            if c == "」":
                break
            buf.append(c); k += 1
        serif = "".join(buf).strip()
        if serif:
            lines.append({"name": name, "text": serif})
        e = text.find("\n", k)
        i = n if e < 0 else e + 1
    if not lines:
        stop("台本の中にセリフが見つからへん。「名前「セリフ」」の形で1行ずつ書いてな。")
    return theme or "動画", lines


# ---------- 道具の確認 ----------
def need_ffmpeg():
    if not shutil.which("ffmpeg"):
        stop("動画を組み立てる道具（ffmpeg）が入ってへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。")


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        say(r.stderr[-1500:])
        stop("動画の組み立てで失敗した。上のメッセージを Claude に見せてな。")


# ---------- 声 ----------
ENGINE = "http://127.0.0.1:50021"
_speakers = None


def speaker_id(voice):
    global _speakers
    if _speakers is None:
        try:
            with urllib.request.urlopen(ENGINE + "/speakers", timeout=5) as r:
                _speakers = json.load(r)
        except Exception:
            stop("VOICEVOX が開いてへん。VOICEVOX を起動して、開いたままもう一回ダブルクリックしてな。")
    for sp in _speakers:
        if sp["name"] == voice:
            styles = sp["styles"]
            for st in styles:
                if st["name"] == "ノーマル":
                    return st["id"]
            return styles[0]["id"]
    names = "、".join(sp["name"] for sp in _speakers[:12])
    stop(f"VOICEVOX に「{voice}」という声が見つからへん。設定.txt の声の名前を確認してな。（使える声の例：{names}）")


def tts(text, voice, speed, out):
    if TEST:  # 試験用：ピー音
        dur = max(0.6, len(text) / 7.0)
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={330 if voice != '青山龍星' else 220}:duration={dur}", out])
        return
    sid = speaker_id(voice)
    q = urllib.parse.urlencode({"text": text, "speaker": sid})
    req = urllib.request.Request(ENGINE + "/audio_query?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        query = json.load(r)
    query["speedScale"] = speed
    req = urllib.request.Request(ENGINE + f"/synthesis?speaker={sid}", data=json.dumps(query).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        open(out, "wb").write(r.read())


def find_recording(no):
    for ext in ("wav", "m4a", "mp3", "aac", "ogg", "flac", "webm", "mp4", "3gp", "amr"):
        f = os.path.join(VOICEDIR, f"{no}.{ext}")
        if os.path.exists(f):
            return f
    return None


TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,")


def normalize(src, dst, trim, pad=0.35):
    af = (TRIM if trim else "") + f"loudnorm=I=-16:TP=-1.5,apad=pad_dur={pad}"
    run(["ffmpeg", "-y", "-i", src, "-af", af, "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", dst])


def wav_len(f):
    with wave.open(f) as w:
        return w.getnframes() / w.getframerate()


# ---------- 絵 ----------
def font(size):
    from PIL import ImageFont
    for f in ["C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/BIZ-UDGothicB.ttc",
              "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def find_pic(base):
    for ext in ("png", "jpg", "jpeg", "webp"):
        f = os.path.join(PICDIR, f"{base}.{ext}")
        if os.path.exists(f):
            return f
    return None


def wrap(draw, text, fnt, width):
    out, cur = [], ""
    for ch in text.replace("\n", ""):
        if draw.textlength(cur + ch, font=fnt) > width:
            if ch in "、。！？…ー」』）!?,.":  # 句読点は行頭に来させへん
                cur += ch; out.append(cur); cur = ""; continue
            if cur and cur[-1] in "「『（":  # 開きカッコは行末に残さへん
                out.append(cur[:-1]); cur = cur[-1] + ch
            else:
                out.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


class Painter:
    QCOL, ACOL = (74, 128, 196), (70, 150, 96)

    def __init__(self, theme, qname, aname):
        from PIL import Image, ImageDraw
        self.Image, self.Draw = Image, ImageDraw
        self.theme, self.qname, self.aname = theme, qname, aname
        self.bg = self.make_bg()
        self.chars = {"Q": self.load_char("聞く役", qname, self.QCOL), "A": self.load_char("答える役", aname, self.ACOL)}

    def make_bg(self):
        Image = self.Image
        f = find_pic("背景")
        if f:
            im = Image.open(f).convert("RGB")
            s = max(W / im.width, H / im.height)
            im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
            l, t = (im.width - W) // 2, (im.height - H) // 2
            return im.crop((l, t, l + W, t + H))
        im = Image.new("RGB", (W, H))
        px = self.Draw.Draw(im)
        for y in range(H):
            k = y / H
            px.line([(0, y), (W, y)], fill=(int(28 + 18 * k), int(40 + 22 * k), int(46 + 20 * k)))
        return im

    def load_char(self, base, name, col):
        Image = self.Image
        f = find_pic(base)
        maxh, maxw = 680, 620
        if f:
            im = Image.open(f).convert("RGBA")
            s = min(maxh / im.height, maxw / im.width)
            return im.resize((int(im.width * s), int(im.height * s)))
        # 絵が無いときの仮の人影
        im = Image.new("RGBA", (420, 520), (0, 0, 0, 0))
        d = self.Draw.Draw(im)
        d.ellipse((120, 20, 300, 200), fill=col + (255,))
        d.rounded_rectangle((50, 230, 370, 640), radius=120, fill=col + (255,))
        fnt = font(48)
        tw = d.textlength(name, font=fnt)
        d.text(((420 - tw) / 2, 320), name, font=fnt, fill=(255, 255, 255, 255))
        return im

    def frame(self, who, text, path):
        Image, Draw = self.Image, self.Draw
        im = self.bg.copy().convert("RGBA")
        # キャラ：話してない方は暗く（表紙では出さへん）
        for role, x_side in (() if who is None else (("Q", "left"), ("A", "right"))):
            c = self.chars[role]
            if who != role:
                dark = Image.new("RGBA", c.size, (0, 0, 0, 0))
                dark.paste((0, 0, 0, 120), (0, 0), c)
                c = Image.alpha_composite(c, dark)
            x = 60 if x_side == "left" else W - 60 - c.width
            im.alpha_composite(c, (x, 800 - c.height))
        d = Draw.Draw(im)
        # 題名
        tf = font(40)
        tw = d.textlength(self.theme, font=tf)
        d.rounded_rectangle((40, 36, 40 + tw + 56, 36 + 72), radius=36, fill=(0, 0, 0, 150))
        d.text((68, 48), self.theme, font=tf, fill=(255, 255, 255))
        if who is None:  # 表紙
            big = font(96)
            lines = wrap(d, self.theme, big, W - 400)
            y = H / 2 - len(lines) * 60
            for ln in lines:
                lw = d.textlength(ln, font=big)
                d.text(((W - lw) / 2, y), ln, font=big, fill=(255, 255, 255), stroke_width=6, stroke_fill=(20, 30, 25))
                y += 120
            im.convert("RGB").save(path)
            return
        # 字幕
        box = (200, 770, W - 200, H - 40)
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        Draw.Draw(overlay).rounded_rectangle(box, radius=28, fill=(10, 14, 12, 200))
        im = Image.alpha_composite(im, overlay)
        d = Draw.Draw(im)
        col = self.QCOL if who == "Q" else self.ACOL
        name = self.qname if who == "Q" else self.aname
        nf = font(36)
        nw = d.textlength(name, font=nf)
        d.rounded_rectangle((box[0] + 30, box[1] - 30, box[0] + 30 + nw + 48, box[1] + 30), radius=24, fill=col)
        d.text((box[0] + 54, box[1] - 22), name, font=nf, fill=(255, 255, 255))
        for size in (56, 50, 44, 38):
            f = font(size)
            lines = wrap(d, text, f, box[2] - box[0] - 100)
            if len(lines) * (size + 16) <= box[3] - box[1] - 60:
                break
        y = box[1] + 46
        for ln in lines:
            d.text((box[0] + 50, y), ln, font=f, fill=(255, 255, 255))
            y += size + 16
        im.convert("RGB").save(path)


# ---------- 本体 ----------
def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    say("=== 動画づくりを始めるで ===")
    need_ffmpeg()
    try:
        import PIL  # noqa
    except ImportError:
        stop("絵を描く道具（Pillow）が入ってへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。")
    s = read_settings()
    theme, lines = parse_script(pick_script())
    qname = s["聞く役の名前"]
    names = [l["name"] for l in lines]
    aname = next((n for n in names if n != qname), "解説")
    for l in lines:
        l["who"] = "Q" if l["name"] == qname else "A"
    say(f"・題名：{theme}")
    say(f"・セリフ {len(lines)} 行（{qname} {sum(l['who']=='Q' for l in lines)} 行／{aname} {sum(l['who']=='A' for l in lines)} 行）")

    for d in (WORK, OUT, VOICEDIR, PICDIR, os.path.join(WORK, "声"), os.path.join(WORK, "絵")):
        os.makedirs(d, exist_ok=True)

    # 録音リスト（番号は台本の上から数えた、聞く役のセリフの順番）
    rec_lines, no = [f"録音リスト：{theme}", "番号のファイル名で、このフォルダに入れてな（例：1.wav 2.m4a）", ""], 0
    for l in lines:
        if l["who"] == "Q":
            no += 1
            l["rec"] = no
            rec_lines.append(f"{no}.  {l['text']}")
    open(os.path.join(VOICEDIR, "録音リスト.txt"), "w", encoding="utf-8-sig").write("\n".join(rec_lines) + "\n")

    # 声
    say("・声を作ってる…")
    used_voices, own = set(), 0
    for idx, l in enumerate(lines, 1):
        rec = find_recording(l["rec"]) if l["who"] == "Q" else None
        if rec:
            key = hashlib.md5((rec + str(os.path.getmtime(rec))).encode()).hexdigest()[:16]
            dst = os.path.join(WORK, "声", f"rec_{key}.wav")
            if not os.path.exists(dst):
                normalize(rec, dst, trim=True)
            own += 1
        else:
            voice = s["聞く役の仮の声"] if l["who"] == "Q" else s["答える役の声"]
            used_voices.add(voice)
            key = hashlib.md5(f"{voice}|{s['話す速さ']}|{l['text']}".encode()).hexdigest()[:16]
            dst = os.path.join(WORK, "声", f"tts_{key}.wav")
            if not os.path.exists(dst):
                raw = dst + ".raw.wav"
                tts(l["text"], voice, s["話す速さ"], raw)
                normalize(raw, dst, trim=False)
                os.remove(raw)
        l["wav"] = dst
        print(f"\r  {idx}/{len(lines)}", end="", flush=True)
    say()
    if own:
        say(f"・自分の声を {own} 行使った")

    # 絵とつなぎ
    say("・絵を描いてる…")
    painter = Painter(theme, qname, aname)
    cover = os.path.join(WORK, "絵", "000.png")
    painter.frame(None, "", cover)
    COVER_SEC = 2.5
    silence = os.path.join(WORK, "声", "cover.wav")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono", "-t", str(COVER_SEC), "-c:a", "pcm_s16le", silence])

    clips = [(cover, silence)]
    for i, l in enumerate(lines, 1):
        img = os.path.join(WORK, "絵", f"{i:03}.png")
        painter.frame(l["who"], l["text"], img)
        clips.append((img, l["wav"]))

    # 音をつなぐ
    say("・組み立ててる…")
    allwav = os.path.join(WORK, "全部の声.wav")
    with wave.open(allwav, "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000)
        for _, w in clips:
            with wave.open(w) as src:
                out.writeframes(src.readframes(src.getnframes()))

    listfile = os.path.join(WORK, "並び.txt")
    t, srt, k = 0.0, [], 0
    with open(listfile, "w", encoding="utf-8") as f:
        for n, (img, w) in enumerate(clips):
            dur = wav_len(w)
            f.write(f"file '{os.path.relpath(img, WORK).replace(os.sep, '/')}'\nduration {dur:.3f}\n")
            if n > 0:
                k += 1
                l = lines[n - 1]
                srt.append(f"{k}\n{ts(t)} --> {ts(t + dur - 0.3)}\n{l['name']}：{l['text']}\n")
            t += dur
        f.write(f"file '{os.path.relpath(clips[-1][0], WORK).replace(os.sep, '/')}'\n")

    safe = re.sub(r'[\\/:*?"<>|]', "", theme).strip()[:40] or "動画"
    mp4 = os.path.join(OUT, safe + ".mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "並び.txt", "-i", "全部の声.wav",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
         os.path.abspath(mp4)], cwd=WORK)
    open(os.path.join(OUT, safe + ".srt"), "w", encoding="utf-8-sig").write("\n".join(srt))

    credit = "、".join(f"VOICEVOX:{v}" for v in sorted(used_voices))
    note = ["動画の説明欄に、下の行を貼ってな（使った声の決まり）", "", credit] if credit else ["VOICEVOXの声は使ってへん"]
    open(os.path.join(OUT, "説明欄に貼る文.txt"), "w", encoding="utf-8-sig").write("\n".join(note) + "\n")

    m, sec = divmod(int(t), 60)
    say()
    say(f"○ できた！  {m}分{sec:02}秒")
    say(f"   {mp4}")
    say()
    if os.name == "nt" and os.environ.get("DOUGA_NO_OPEN") != "1":
        os.startfile(OUT)  # できた動画のフォルダを開く
    left = no - own
    if left > 0:
        say(f"自分の声がまだの行が {left} 行ある。録る行は「自分の声」フォルダの 録音リスト.txt を見てな。")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        say(repr(e))
        stop("思わぬところで止まった。上のメッセージを Claude に見せてな。")
