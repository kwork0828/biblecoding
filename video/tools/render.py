"""script.json 한 개로 강의 영상 한 편을 만든다.

사용법:
    python video/tools/render.py video/ep01/script.json
    python video/tools/render.py video/ep02/script.json --draft-root "D:/CapCutDrafts"

옵션:
    --tts edge     edge-tts(ko-KR-InJoonNeural)로 음성 생성 (기본값)
    --tts silent   음성 없이 글자 수로 길이를 추정한 무음 미리보기 (네트워크가 막힌 환경용)
    --no-capcut    캡컷 드래프트 생성 생략
    --draft-root   캡컷 드래프트 루트 폴더 직접 지정

산출물 (script.json이 있는 폴더):
    epNN.mp4 (무음 모드면 epNN_preview_silent.mp4), epNN.srt, thumbnail.png, upload.txt
    build/  중간 파일 (문장별 음성, 장면 이미지, 장면 영상, fonts.json)
    캡컷 드래프트 "EPNN_bible"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- 상수
W, H = 1920, 1080
FPS = 30
SR = 48000                      # 오디오 샘플레이트
SAMPLES_PER_FRAME = SR // FPS   # 1600: 장면 길이를 프레임 경계에 맞추기 위함
LEAD_S, GAP_S, TAIL_S = 0.4, 0.3, 0.6
CONTENT_BOTTOM = 860            # 이 아래는 번인 자막 자리 (자막 2줄 윗선 ≈ 888px)
SUB_MAX_CHARS = 25

NAVY = (14, 26, 51)
NAVY_2 = (22, 38, 72)
WHITE = (245, 247, 250)
MUTED = (160, 172, 196)
GOLD = (232, 182, 76)
TERM_BG = (8, 13, 26)
HILITE = (255, 214, 64)

FONT_CANDIDATES = {
    "title": ["C:/Windows/Fonts/malgunbd.ttf",
              "/System/Library/Fonts/AppleSDGothicNeo.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],
    "body": ["C:/Windows/Fonts/malgun.ttf",
             "/System/Library/Fonts/AppleSDGothicNeo.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
    "code": ["C:/Windows/Fonts/consola.ttf",
             "/System/Library/Fonts/Menlo.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
}
PREFERRED = {"title": "malgunbd.ttf", "body": "malgun.ttf", "code": "consola.ttf"}

SECRET_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "****"),
    (re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_-]{8,}"), "****"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{10,}"), "****"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), "****"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|password|passwd)\s*[:=]\s*)(['\"]?)[^'\"\s,;]+"), r"\1\2****"),
]


def mask(text: str) -> str:
    for pat, rep in SECRET_PATTERNS:
        text = pat.sub(rep, text)
    return text


# ---------------------------------------------------------------- 폰트
class Fonts:
    def __init__(self) -> None:
        self.paths: dict[str, tuple[str, int]] = {}
        self.notes: list[str] = []
        for role, cands in FONT_CANDIDATES.items():
            for p in cands:
                if os.path.exists(p):
                    self.paths[role] = (p, self._korean_index(p))
                    if not p.endswith(PREFERRED[role]):
                        self.notes.append(f"{role}: {PREFERRED[role]} 없음 → {os.path.basename(p)} 사용")
                    break
            else:
                raise SystemExit(f"[{role}] 폰트를 찾지 못했습니다: {cands}")
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    @staticmethod
    def _korean_index(path: str) -> int:
        if not path.lower().endswith(".ttc"):
            return 0
        for i in range(12):
            try:
                name = ImageFont.truetype(path, 20, index=i).getname()[0]
            except OSError:
                break
            if "KR" in name or "Gothic Neo" in name:
                return i
        return 0

    def get(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        key = (role, size)
        if key not in self._cache:
            p, idx = self.paths[role]
            self._cache[key] = ImageFont.truetype(p, size, index=idx)
        return self._cache[key]

    def family(self, role: str) -> str:
        return self.get(role, 20).getname()[0]


# ---------------------------------------------------------------- 그리기 도우미
def text_w(draw: ImageDraw.ImageDraw, s: str, font) -> int:
    return int(draw.textlength(s, font=font))


def wrap(draw, text: str, font, max_w: int) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = word if not line else f"{line} {word}"
            if text_w(draw, cand, font) <= max_w:
                line = cand
                continue
            if line:
                out.append(line)
            # 단어 하나가 너무 길면 글자 단위로 자른다
            while text_w(draw, word, font) > max_w:
                cut = len(word)
                while cut > 1 and text_w(draw, word[:cut], font) > max_w:
                    cut -= 1
                out.append(word[:cut])
                word = word[cut:]
            line = word
        out.append(line)
    return out


def base_canvas(ep: str, series: str, fonts: Fonts) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(H):  # 위에서 아래로 아주 약한 그라데이션
        t = y / H
        c = tuple(int(NAVY[i] * (1 - t) + NAVY_2[i] * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    f = fonts.get("title", 34)
    tw = text_w(d, ep, f)
    d.rounded_rectangle([56, 44, 56 + tw + 44, 44 + 58], radius=14, outline=GOLD, width=3)
    d.text((56 + 22, 44 + 29), ep, font=f, fill=GOLD, anchor="lm")
    fs = fonts.get("body", 26)
    d.text((W - 60, 44 + 29), series, font=fs, fill=MUTED, anchor="rm")
    return img


def draw_heading(d, text: str, fonts: Fonts, y: int = 150) -> int:
    f = fonts.get("title", 72)
    lines = wrap(d, text, f, W - 240)
    for ln in lines:
        d.text((120, y), ln, font=f, fill=WHITE)
        y += 92
    d.rectangle([120, y + 8, 120 + 140, y + 14], fill=GOLD)
    return y + 60


def fit_bullets(d, bullets: list[str], fonts: Fonts, top: int, bottom: int, max_w: int):
    for size in range(56, 30, -2):
        f = fonts.get("body", size)
        blocks = [wrap(d, b, f, max_w) for b in bullets]
        lh = int(size * 1.45)
        total = sum(len(b) * lh for b in blocks) + (len(blocks) - 1) * int(size * 0.55)
        if top + total <= bottom:
            return f, blocks, lh, int(size * 0.55)
    return f, blocks, lh, int(size * 0.55)


def draw_mixed(d, xy, text: str, fonts: Fonts, size: int, fill) -> None:
    """코드 폰트엔 한글이 없어서, ASCII는 코드 폰트로 나머지는 본문 폰트로 이어 그린다."""
    x, y = xy
    code_f, body_f = fonts.get("code", size), fonts.get("body", size - 2)
    run, run_ascii = "", None
    for ch in text + "\0":
        is_ascii = ord(ch) < 128
        if ch == "\0" or (run and is_ascii != run_ascii):
            f = code_f if run_ascii else body_f
            d.text((x, y), run, font=f, fill=fill, anchor="ls")
            x += text_w(d, run, f)
            run = ""
        if ch != "\0":
            run += ch
            run_ascii = is_ascii


# ---------------------------------------------------------------- 장면별 슬라이드
def slide_title(s, ep, series, fonts):
    img = base_canvas(ep, series, fonts)
    d = ImageDraw.Draw(img)
    scr = s["screen"]
    f = fonts.get("title", 104)
    lines = wrap(d, scr["title"], f, W - 300)
    lh = 132
    y = (CONTENT_BOTTOM + 60) // 2 - (len(lines) * lh) // 2 - 30
    for ln in lines:
        d.text((W // 2, y), ln, font=f, fill=WHITE, anchor="mt")
        y += lh
    d.rectangle([W // 2 - 90, y + 20, W // 2 + 90, y + 27], fill=GOLD)
    if scr.get("subtitle"):
        d.text((W // 2, y + 62), scr["subtitle"], font=fonts.get("body", 44), fill=GOLD, anchor="mt")
    return img


def slide_explain(s, ep, series, fonts):
    img = base_canvas(ep, series, fonts)
    d = ImageDraw.Draw(img)
    scr = s["screen"]
    y = draw_heading(d, scr["heading"], fonts)
    bottom = CONTENT_BOTTOM - (70 if scr.get("note") else 0)

    if scr.get("columns"):
        hl = set(scr.get("highlight_items", []))
        f = fonts.get("body", 46)
        col_w = (W - 240) // len(scr["columns"])
        rows = max(len(c) for c in scr["columns"])
        y += max(0, int((bottom - y - rows * 78) * 0.4))
        for ci, col in enumerate(scr["columns"]):
            yy = y
            for item in col:
                on = item in hl
                x = 120 + ci * col_w
                if on:
                    d.rounded_rectangle([x - 18, yy - 8, x + col_w - 60, yy + 64], radius=12, fill=(44, 58, 92))
                d.text((x, yy), item, font=f, fill=GOLD if on else WHITE)
                yy += 78
    else:
        emph = scr.get("emphasis")
        f, blocks, lh, gap = fit_bullets(d, scr.get("bullets", []), fonts, y, bottom, W - 340)
        used = sum(len(b) * lh for b in blocks) + (len(blocks) - 1) * gap
        y += max(0, int((bottom - y - used) * 0.4))  # 위에 몰리지 않게
        for i, lines in enumerate(blocks):
            color = GOLD if i == emph else WHITE
            r = f.size // 5
            d.ellipse([140 - r, y + f.size * 0.62 - r, 140 + r, y + f.size * 0.62 + r], fill=GOLD)
            for ln in lines:
                d.text((180, y), ln, font=f, fill=color)
                y += lh
            y += gap
    if scr.get("note"):
        d.text((120, CONTENT_BOTTOM - 40), scr["note"], font=fonts.get("body", 32), fill=MUTED)
    return img


def slide_prompt(s, ep, series, fonts):
    img = base_canvas(ep, series, fonts)
    d = ImageDraw.Draw(img)
    scr = s["screen"]
    y = draw_heading(d, scr["heading"], fonts, y=130)
    box = [120, y, W - 120, CONTENT_BOTTOM]
    d.rounded_rectangle(box, radius=24, fill=TERM_BG, outline=(60, 76, 110), width=2)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (98, 197, 84)]):
        cx = box[0] + 40 + i * 34
        d.ellipse([cx - 10, box[1] + 28, cx + 10, box[1] + 48], fill=c)
    d.text((box[2] - 30, box[1] + 38), "Claude Code", font=fonts.get("body", 26), fill=MUTED, anchor="rm")
    text = mask(scr["prompt"])
    inner_w = box[2] - box[0] - 170
    for size in range(54, 30, -2):
        f = fonts.get("body", size)
        lines = wrap(d, text, f, inner_w)
        lh = int(size * 1.5)
        if box[1] + 90 + len(lines) * lh <= box[3] - 30:
            break
    ty = box[1] + 90
    d.text((box[0] + 50, ty), ">", font=fonts.get("code", size), fill=GOLD)
    for ln in lines:
        d.text((box[0] + 110, ty), ln, font=f, fill=WHITE)
        ty += lh
    return img


def slide_code(s, ep, series, fonts, repo_root: Path):
    img = base_canvas(ep, series, fonts)
    d = ImageDraw.Draw(img)
    scr = s["screen"]
    y = draw_heading(d, scr["heading"], fonts, y=130)
    src = (repo_root / scr["file"]).read_text(encoding="utf-8").splitlines()
    a, b = scr["start_line"], scr["end_line"]
    lines = [mask(x) for x in src[a - 1:b]]
    hl = set(scr.get("highlight", []))
    box = [120, y, W - 120, CONTENT_BOTTOM]
    d.rounded_rectangle(box, radius=20, fill=TERM_BG)
    d.text((box[0] + 30, box[1] + 22), scr["file"], font=fonts.get("code", 26), fill=MUTED)
    avail = box[3] - box[1] - 80
    size = max(26, min(48, int(avail / len(lines) / 1.4)))
    lh = int(size * 1.4)
    ty = box[1] + 70
    for i, ln in enumerate(lines):
        n = a + i
        if n in hl:
            d.rectangle([box[0] + 6, ty, box[2] - 6, ty + lh - 4], fill=(70, 60, 20))
            d.rectangle([box[0] + 6, ty, box[0] + 14, ty + lh - 4], fill=HILITE)
        d.text((box[0] + 100, ty + lh * 0.72), str(n), font=fonts.get("code", size), fill=MUTED, anchor="rs")
        draw_mixed(d, (box[0] + 130, ty + lh * 0.72), ln, fonts, size, HILITE if n in hl else WHITE)
        ty += lh
    return img


def slide_screen(s, ep, series, fonts, ep_dir: Path):
    scr = s["screen"]
    p = ep_dir / scr["image"] if scr.get("image") else None
    if not p or not p.exists():
        fallback = dict(s, screen={"heading": scr.get("heading", "화면"), "bullets": scr.get("fallback", [])})
        return slide_explain(fallback, ep, series, fonts)
    shot = Image.open(p).convert("RGB")
    bg = shot.resize((W, int(W * shot.height / shot.width)) if shot.width / shot.height < W / H
                     else (int(H * shot.width / shot.height), H))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), NAVY), 0.55)
    top = 140
    max_w, max_h = W - 300, CONTENT_BOTTOM - top
    scale = min(max_w / shot.width, max_h / shot.height)
    shot = shot.resize((int(shot.width * scale), int(shot.height * scale)))
    bg.paste(shot, ((W - shot.width) // 2, top + (max_h - shot.height) // 2))
    badge = base_canvas(ep, series, fonts).crop((0, 0, W, 110))
    bg.paste(badge, (0, 0))
    if scr.get("heading"):
        ImageDraw.Draw(bg).text((W // 2, 118), scr["heading"], font=fonts.get("title", 40), fill=WHITE, anchor="mm")
    return bg


def make_slide(s, meta, fonts, ep_dir, repo_root) -> Image.Image:
    ep, series = meta["episode"], meta.get("series", "")
    t = s["type"]
    if t == "title":
        return slide_title(s, ep, series, fonts)
    if t in ("explain", "recap"):
        return slide_explain(s, ep, series, fonts)
    if t == "prompt":
        return slide_prompt(s, ep, series, fonts)
    if t == "code":
        return slide_code(s, ep, series, fonts, repo_root)
    if t == "screen":
        return slide_screen(s, ep, series, fonts, ep_dir)
    raise ValueError(f"알 수 없는 장면 type: {t}")


# ---------------------------------------------------------------- 음성
def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(cmd[:6])} ...\n{r.stderr[-2000:]}")
    return r.stderr


async def _edge_tts(text: str, voice: str, out: Path) -> None:
    import ssl
    import edge_tts
    import edge_tts.communicate as comm
    cafile = os.environ.get("EDGE_TTS_CAFILE")  # 사내 프록시 등 인증서가 다른 환경용
    if cafile:
        comm._SSL_CTX = ssl.create_default_context(cafile=cafile)
    await edge_tts.Communicate(text, voice).save(str(out))


def tts_sentence(text: str, voice: str, mode: str, mp3: Path, wav: Path) -> None:
    if wav.exists():
        return
    if mode == "silent":
        n = int(SR * (len(text) / 6.5 + 0.2))  # 한국어 TTS 대략 초당 6.5자로 추정
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(b"\0\0" * n)
        return
    last = None
    for attempt in range(3):
        try:
            asyncio.run(_edge_tts(text, voice, mp3))
            if mp3.stat().st_size > 0:
                break
        except Exception as e:  # 네트워크 오류는 재시도
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"edge-tts 3회 실패: {last}\n→ 네트워크가 막혀 있으면 --tts silent 로 미리보기만 만들 수 있습니다.")
    run(["ffmpeg", "-y", "-i", str(mp3), "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(wav)])


def read_pcm(p: Path) -> bytes:
    with wave.open(str(p), "rb") as w:
        return w.readframes(w.getnframes())


@dataclass
class SceneTiming:
    start_samples: int = 0
    samples: int = 0
    cues: list[tuple[int, int, str]] = field(default_factory=list)  # (start, end, text) 전체 타임라인 샘플 기준


def build_scene_audio(s, idx_start: int, voice: str, mode: str, build: Path) -> tuple[SceneTiming, Path]:
    adir = build / f"audio_{mode}"  # 무음/실음성 결과가 섞이지 않게 폴더를 나눈다
    adir.mkdir(parents=True, exist_ok=True)
    pcm = bytearray(b"\0\0" * int(SR * LEAD_S))
    cues = []
    for i, text in enumerate(s["narration"]):
        base = adir / f"{s['id']}_{i:02d}"
        tts_sentence(text, voice, mode, base.with_suffix(".mp3"), base.with_suffix(".wav"))
        chunk = read_pcm(base.with_suffix(".wav"))
        st = len(pcm) // 2
        pcm += chunk
        cues.append((idx_start + st, idx_start + len(pcm) // 2, text))
        if i < len(s["narration"]) - 1:
            pcm += b"\0\0" * int(SR * GAP_S)
    pcm += b"\0\0" * int(SR * TAIL_S)
    min_samples = int(SR * s.get("screen", {}).get("min_seconds", 0))
    n = max(len(pcm) // 2, min_samples)
    n = math.ceil(n / SAMPLES_PER_FRAME) * SAMPLES_PER_FRAME  # 프레임 경계에 맞춤
    pcm += b"\0\0" * (n - len(pcm) // 2)
    out = build / "scenes" / f"{s['id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or read_pcm(out) != bytes(pcm):  # 바뀐 장면만 저장 (장면 영상 캐시 유지)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(bytes(pcm))
    return SceneTiming(idx_start, n, cues), out


# ---------------------------------------------------------------- 자막
def split_sub(text: str, limit: int = SUB_MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    # "Claude Code"처럼 영어 단어 사이 공백에서는 나누지 않는다
    spaces = [i for i, c in enumerate(text) if c == " "
              and not (text[i - 1].isascii() and text[i - 1].isalpha() and text[i + 1].isascii() and text[i + 1].isalpha())]
    best = None
    for i in spaces:
        a, b = text[:i], text[i + 1:]
        if len(a) <= limit and len(b) <= limit:
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    if best:
        return best[1]
    mid = len(text) // 2
    return [text[:mid], text[mid:]]


def srt_time(samples: int) -> str:
    ms = round(samples * 1000 / SR)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(timings: list[SceneTiming], out: Path) -> list[tuple[int, int, str]]:
    cues = [c for t in timings for c in t.cues]
    with out.open("w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n" + "\n".join(split_sub(mask(text))) + "\n\n")
    return cues


# ---------------------------------------------------------------- 영상
def render_scene_video(png: Path, wav: Path, samples: int, out: Path) -> None:
    frames = samples // SAMPLES_PER_FRAME
    dur = samples / SR
    zoom = f"zoompan=z='1+0.04*on/{max(frames - 1, 1)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}"
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.6f}", "-i", str(png),
         "-i", str(wav),
         "-filter_complex", f"[0:v]scale={W * 2}:{H * 2},{zoom},format=yuv420p[v]",
         "-map", "[v]", "-map", "1:a", "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", str(out)])


def ass_escape_path(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    return s.replace(":", r"\:").replace("'", r"\'")


def finalize(concat_mp4: Path, srt: Path, fonts: Fonts, out: Path, loudnorm: bool) -> None:
    fontdir = Path(fonts.paths["body"][0]).parent
    style = (f"FontName={fonts.family('body')},FontSize=15,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,"
             "Bold=1,Alignment=2,MarginV=18")
    vf = f"subtitles='{ass_escape_path(srt)}':fontsdir='{ass_escape_path(fontdir)}':force_style='{style}'"
    af = []
    if loudnorm:
        log = run(["ffmpeg", "-i", str(concat_mp4), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                   "-f", "null", "-"])
        m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
        af = ["-af", ("loudnorm=I=-14:TP=-1.5:LRA=11:"
                      f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
                      f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")]
    run(["ffmpeg", "-y", "-i", str(concat_mp4), "-vf", vf, *af,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", str(out)])


# ---------------------------------------------------------------- 썸네일 / 업로드 문구
def make_thumbnail(meta, fonts: Fonts, out: Path) -> None:
    tw, th = 1280, 720
    img = base_canvas(meta["episode"], "", fonts).resize((tw, th))
    d = ImageDraw.Draw(img)
    tn = meta.get("thumbnail", {})
    title = tn.get("title", meta["title"])
    for size in range(120, 60, -4):
        f = fonts.get("title", size)
        lines = wrap(d, title, f, tw - 160)
        if len(lines) * size * 1.25 <= 420:
            break
    y = 150
    for i, ln in enumerate(lines):
        d.text((80, y), ln, font=f, fill=GOLD if i == len(lines) - 1 else WHITE)
        y += int(size * 1.25)
    d.rectangle([80, y + 20, 240, y + 30], fill=GOLD)
    if tn.get("subtitle"):
        d.text((80, th - 90), tn["subtitle"], font=fonts.get("body", 40), fill=MUTED)
    img.save(out)


def fmt_ts(samples: int) -> str:
    s = samples // SR
    return f"{s // 60}:{s % 60:02d}"


def write_upload(meta, timings: list[SceneTiming], out: Path, estimated: bool) -> list[str]:
    chapters = []
    for s, t in zip(meta["scenes"], timings):
        if s.get("chapter"):
            chapters.append((t.start_samples, s["chapter"]))
    if chapters and chapters[0][0] != 0:
        chapters.insert(0, (0, "인트로"))
    warnings = []
    for (a, _), (b, name) in zip(chapters, chapters[1:]):
        if (b - a) / SR < 10:
            warnings.append(f"챕터 '{name}' 앞 구간이 10초 미만 (유튜브 챕터 조건 미달)")
    lines = [
        "[제목]",
        f"[{meta['episode']}] {meta['title']} | {meta.get('series', '')}",
        "",
        "[설명]",
        meta.get("upload", {}).get("description", ""),
        "",
        "[챕터]" + (" (무음 미리보기 기준 추정치. 실제 음성으로 다시 렌더링하면 바뀜)" if estimated else ""),
        *[f"{fmt_ts(a)} {name}" for a, name in chapters],
        "",
        "[태그]",
        ", ".join(meta.get("upload", {}).get("tags", [])),
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return warnings


# ---------------------------------------------------------------- 캡컷 드래프트
def default_draft_root() -> Path | None:
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        p = Path(os.environ["LOCALAPPDATA"]) / "CapCut/User Data/Projects/com.lveditor.draft"
    elif sys.platform == "darwin":
        p = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
    else:
        return None
    return p if p.exists() else None


def make_capcut_draft(meta, timings, slides: list[Path], scene_wavs: list[Path], root: Path) -> Path:
    import pycapcut as cc
    from pycapcut import ClipSettings, TextBorder, TextStyle, TrackType

    name = f"{meta['episode']}_bible"
    root.mkdir(parents=True, exist_ok=True)
    script = cc.DraftFolder(str(root)).create_draft(name, W, H, FPS, allow_replace=True)
    draft = root / name
    mats = draft / "materials"
    mats.mkdir(exist_ok=True)

    script.add_track(TrackType.video)
    script.add_track(TrackType.audio)
    script.add_track(TrackType.text)

    us = lambda samples: samples * 1_000_000 // SR  # noqa: E731  마이크로초 정수
    cursor = 0
    for t, png, wav in zip(timings, slides, scene_wavs):
        dur = us(t.start_samples + t.samples) - us(t.start_samples)  # 반올림 오차 없이 이어 붙임
        p_img = mats / png.name
        p_wav = mats / wav.name
        shutil.copy2(png, p_img)
        shutil.copy2(wav, p_wav)
        script.add_segment(cc.VideoSegment(cc.VideoMaterial(str(p_img)), cc.trange(cursor, dur)))
        audio = cc.AudioMaterial(str(p_wav))
        # mediainfo는 길이를 ms 단위로 잘라 주므로 소재 길이를 넘지 않게 clamp
        script.add_segment(cc.AudioSegment(audio, cc.trange(cursor, min(dur, audio.duration))))
        cursor += dur
    total_us = cursor

    style = TextStyle(size=7.0, bold=True, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True, max_line_width=0.8)
    for t in timings:
        for a, b, text in t.cues:
            seg = cc.TextSegment("\n".join(split_sub(mask(text))), cc.trange(us(a), us(b) - us(a)),
                                 style=style, border=TextBorder(width=40.0),
                                 clip_settings=ClipSettings(transform_y=-0.8))
            script.add_segment(seg)

    script.save()
    shutil.copy2(draft / "draft_content.json", draft / "draft_info.json")

    meta_p = draft / "draft_meta_info.json"
    m = json.loads(meta_p.read_text(encoding="utf-8"))
    now_us = int(time.time() * 1_000_000)
    m.update({
        "draft_id": str(uuid.uuid4()).upper(),
        "draft_name": name,
        "draft_fold_path": str(draft.resolve()).replace("\\", "/"),
        "draft_root_path": str(root.resolve()).replace("\\", "/"),
        "tm_duration": total_us,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
    })
    meta_p.write_text(json.dumps(m, ensure_ascii=False, indent=4), encoding="utf-8")
    return draft


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--tts", choices=["edge", "silent"], default="edge")
    ap.add_argument("--no-capcut", action="store_true")
    ap.add_argument("--draft-root")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg가 없습니다. Windows: winget install Gyan.FFmpeg 실행 후 새 터미널에서 다시 시도하세요.")

    script_path = Path(args.script).resolve()
    ep_dir = script_path.parent
    repo_root = Path(__file__).resolve().parents[2]
    meta = json.loads(script_path.read_text(encoding="utf-8"))
    ep = meta["episode"].lower()
    build = ep_dir / "build"
    (build / "slides").mkdir(parents=True, exist_ok=True)

    fonts = Fonts()
    (build / "fonts.json").write_text(json.dumps(
        {"paths": {k: v[0] for k, v in fonts.paths.items()}, "notes": fonts.notes}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    timings, slides, wavs = [], [], []
    cursor = 0
    for s in meta["scenes"]:
        png = build / "slides" / f"{s['id']}.png"
        img = make_slide(s, meta, fonts, ep_dir, repo_root)
        if not png.exists() or Image.open(png).tobytes() != img.tobytes():
            img.save(png)  # 바뀐 장면만 저장해야 장면 영상 캐시가 유지된다
        t, wav = build_scene_audio(s, cursor, meta.get("voice", "ko-KR-InJoonNeural"), args.tts, build)
        cursor += t.samples
        timings.append(t); slides.append(png); wavs.append(wav)
        print(f"  {s['id']:5s} {s['type']:8s} {t.samples / SR:6.1f}s")

    srt = ep_dir / f"{ep}.srt"
    write_srt(timings, srt)

    scene_mp4s = []
    for s, t, png, wav in zip(meta["scenes"], timings, slides, wavs):
        out = build / "scenes" / f"{s['id']}.mp4"
        # 이미지·음성이 그대로면 다시 인코딩하지 않는다 (장면 영상 렌더링이 가장 오래 걸림)
        if not out.exists() or out.stat().st_mtime < max(png.stat().st_mtime, wav.stat().st_mtime):
            render_scene_video(png, wav, t.samples, out)
        scene_mp4s.append(out)
    lst = build / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in scene_mp4s), encoding="utf-8")
    joined = build / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])

    final = ep_dir / (f"{ep}_preview_silent.mp4" if args.tts == "silent" else f"{ep}.mp4")
    finalize(joined, srt, fonts, final, loudnorm=args.tts != "silent")

    make_thumbnail(meta, fonts, ep_dir / "thumbnail.png")
    warns = write_upload(meta, timings, ep_dir / "upload.txt", estimated=args.tts == "silent")

    draft = None
    if not args.no_capcut:
        root = Path(args.draft_root) if args.draft_root else (default_draft_root() or ep_dir / "capcut")
        draft = make_capcut_draft(meta, timings, slides, wavs, root)

    total = cursor / SR
    print(f"\n완료: {final}  ({int(total // 60)}분 {total % 60:.1f}초, 장면 {len(meta['scenes'])}개)")
    if draft:
        print(f"캡컷 드래프트: {draft}")
    for n in fonts.notes + warns:
        print("주의:", n)


if __name__ == "__main__":
    main()
