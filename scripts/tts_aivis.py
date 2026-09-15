# -*- coding: utf-8 -*-
"""台本(Nana: / Sou: の行) → AivisSpeech Engine(無料・OSS)で音声合成 → mp3。
使い方:
  python3 tts_aivis.py 台本.txt 出力.mp3 [--voices voices.json] [--speed 0.92] [--sentpause 0.35] [--parapause 1.0] [--sectpause 1.6]
前提: AivisSpeech Engine が http://127.0.0.1:10101 で起動していること(公式Dockerイメージ)。
話者ごとの声(モデルUUID・話者名・スタイル・ピッチ)は voices.json。モデルが未インストールなら
AivisHub から自動でインストールする。
台本の書き方:
  ・1行 = 1つのまとまり。行頭に「Nana: 」「Sou: 」(voices.json にある名前 + コロン)
  ・空行 = 段落の区切り。「#」で始まる行はコメント(読まれない)。
    「# ──本題──」のように罫線を含むコメント行はコーナーの切れ目で、段落より長い間が入る
外部ライブラリ不要(標準ライブラリ+ffmpeg)。
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid as uuidlib
import wave
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://127.0.0.1:10101"
ROOT = Path(__file__).resolve().parent.parent


def api(path: str, method="GET", body=None, timeout=180):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else b"",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        data = r.read()
        return json.loads(data) if "json" in ct else data


def ensure_model(model_uuid: str):
    """モデルが未インストールなら AivisHub からインストールする"""
    if model_uuid in api("/aivm_models"):
        return
    print(f"  モデル {model_uuid} を AivisHub からインストール中...")
    dl = f"https://api.aivis-project.com/v1/aivm-models/{model_uuid}/download?model_type=AIVMX"
    boundary = uuidlib.uuid4().hex
    body = (f"--{boundary}\r\n" 'Content-Disposition: form-data; name="url"\r\n\r\n'
            f"{dl}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(BASE + "/aivm_models/install", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        print(f"  インストール完了: HTTP {r.status}")
    for _ in range(30):     # /speakers に反映されるまで少し待つ
        if model_uuid in api("/aivm_models"):
            return
        time.sleep(2)
    raise SystemExit(f"モデル {model_uuid} をインストールしたが認識されない")


def resolve_style(speaker_name: str, style_name: str):
    """話者名+スタイル名 → styleId"""
    speakers = api("/speakers")
    for sp in speakers:
        if sp["name"] != speaker_name:
            continue
        for st in sp["styles"]:
            if st["name"] == style_name:
                return st["id"]
        return sp["styles"][0]["id"]      # スタイル名が無ければ先頭
    names = sorted(set(sp["name"] for sp in speakers))
    raise SystemExit(f"話者 '{speaker_name}' がエンジンに無い。利用可能: {names}")


def split_sentences(paragraph: str):
    parts = re.split(r"(?<=[。！？!?])", paragraph)
    return [p.strip() for p in parts if p.strip()]


def synthesize(text: str, style_id: int, speed: float, pitch: float, intona: float) -> bytes:
    q = api(f"/audio_query?speaker={style_id}&text={urllib.parse.quote(text)}", method="POST")
    q["speedScale"] = speed
    q["pitchScale"] = pitch
    q["intonationScale"] = intona
    return api(f"/synthesis?speaker={style_id}", method="POST", body=q)


def parse_script(text: str, names):
    """行を (speaker, text) のリストに変換。空行は "para"、罫線コメント行は "sect" を挟む。"""
    items = []

    def mark(kind):
        if not items:
            return
        if items[-1] in ("para", "sect"):
            if kind == "sect":
                items[-1] = "sect"
            return
        items.append(kind)

    tag = re.compile(r"^(" + "|".join(re.escape(n) for n in names) + r")\s*[:：]\s*(.+)$")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            mark("para")
            continue
        if line.startswith("#"):
            if re.search(r"[─―—–\-=＝]{2,}", line):
                mark("sect")
            continue
        m = tag.match(line)
        if not m:
            raise SystemExit(f"話者タグが無い行が見つかった({'/'.join(names)} で始まっていない): {line!r}")
        items.append((m.group(1), m.group(2)))
    while items and items[-1] in ("para", "sect"):
        items.pop()
    return items


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            opts[sys.argv[i]] = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    if len(args) < 2:
        raise SystemExit(__doc__)
    src, dst = Path(args[0]), Path(args[1])

    voices_path = Path(opts.get("--voices", ROOT / "voices.json"))
    voices = json.loads(voices_path.read_text(encoding="utf-8"))
    glob = voices.get("_global", {})
    names = [k for k in voices if not k.startswith("_")]

    speed = float(opts.get("--speed", glob.get("speed", 1.0)))
    sent_pause = float(opts.get("--sentpause", glob.get("sentpause", 0.3)))
    para_pause = float(opts.get("--parapause", glob.get("parapause", 1.0)))
    sect_pause = float(opts.get("--sectpause", glob.get("sectpause", para_pause * 1.6)))

    version = api("/version")
    print(f"engine {version} / 速度 {speed} / 間: 文{sent_pause}秒 段落{para_pause}秒 コーナー{sect_pause}秒")

    text = src.read_text(encoding="utf-8")
    items = parse_script(text, names)
    used = sorted(set(it[0] for it in items if it not in ("para", "sect")))

    voice = {}
    for n in used:
        v = voices[n]
        ensure_model(v["model_uuid"])
        style = v.get("style", "ノーマル")
        sid = resolve_style(v["speaker"], style)
        voice[n] = {"id": sid, "pitch": float(v.get("pitch", 0.0)),
                    "intonation": float(v.get("intonation", 1.0)),
                    "speed": speed * float(v.get("speed", 1.0))}
        print(f"{n}: {v['speaker']}({style}) styleId={sid} / pitch {voice[n]['pitch']} / 速度 {voice[n]['speed']:.2f}")

    total = sum(1 for it in items if it not in ("para", "sect"))
    print(f"セリフ行 {total}")

    frames = bytearray()
    params = None
    done = 0
    segments = []

    def silence(sec):
        n = int(params.framerate * sec)
        return b"\x00" * (n * params.sampwidth * params.nchannels)

    def cur_time():
        if params is None:
            return 0.0
        return len(frames) / (params.framerate * params.sampwidth * params.nchannels)

    pending_pause = 0.0
    first = True
    for item in items:
        if item in ("para", "sect"):
            pending_pause = max(pending_pause, para_pause if item == "para" else sect_pause)
            continue
        if not first and pending_pause == 0.0 and sent_pause > 0:
            pending_pause = sent_pause
        speaker, line_text = item
        spk = voice[speaker]
        if pending_pause > 0 and params is not None:
            frames += silence(pending_pause)
        pending_pause = 0.0
        first = False
        sentences = split_sentences(line_text)
        for si, s in enumerate(sentences):
            sent_start = cur_time()
            for attempt in range(3):
                try:
                    wav_bytes = synthesize(s, spk["id"], spk["speed"], spk["pitch"], spk["intonation"])
                    break
                except Exception as e:      # エンジンの一時的な失敗は少し待って再試行
                    if attempt == 2:
                        raise
                    print(f"  合成失敗({e})。再試行 {attempt + 1}/2")
                    time.sleep(5)
            with wave.open(io.BytesIO(wav_bytes)) as w:
                if params is None:
                    params = w.getparams()
                    sent_start = cur_time()
                frames += w.readframes(w.getnframes())
            segments.append({"speaker": speaker, "text": s,
                             "start": round(sent_start, 3), "end": round(cur_time(), 3)})
            if sent_pause > 0 and si < len(sentences) - 1:
                frames += silence(sent_pause)
        done += 1
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total} 行 合成済み")

    dur = len(frames) / (params.framerate * params.sampwidth * params.nchannels)
    tmp_wav = Path(tempfile.gettempdir()) / "radio_tmp.wav"
    with wave.open(str(tmp_wav), "wb") as w:
        w.setparams(params)
        w.writeframes(bytes(frames))

    if dst.suffix.lower() == ".wav":
        shutil.copy(tmp_wav, dst)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_wav),
                        "-b:a", "96k", str(dst)], check=True)
    tmp_wav.unlink(missing_ok=True)
    dst.with_suffix(".segments.json").write_text(json.dumps(segments, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    print(f"完成: {dst} ({dur/60:.1f}分, {dst.stat().st_size/1024/1024:.1f}MB)")


if __name__ == "__main__":
    main()
