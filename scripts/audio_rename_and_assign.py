#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


NAME_ROMAJI = {
    "鈴木": "Suzuki",
    "塚本": "Tsukamoto",
    "高野": "Takano",
}


KEYWORD_TO_SPOT_TITLE = [
    # Strong / unambiguous
    ("帆曳船", "りんりんポート土浦"),
    ("white iris", "りんりんポート土浦"),
    ("ホワイトアイリス", "りんりんポート土浦"),
    ("帰港", "りんりんポート土浦"),
    ("鐘", "幸せの鐘"),
    ("水車", "水車"),
    ("風車", "風車"),
    ("野球", "多目的広場"),
    ("サッカー", "多目的広場"),
    ("ソフトボール", "多目的広場"),
    ("滝", "水郷の滝"),
    ("ひこうき", "ツェッペリン号"),
    ("飛行機", "ツェッペリン号"),
    # Medium confidence
    ("水路", "風車"),
    ("板", "風車"),
    ("デッキ", "レストハウス"),
    ("じゃり", "レストハウス"),
    ("自販機", "レストハウス"),
    ("扉", "レストハウス"),
    ("箱", "レストハウス"),
    ("鉄琴", "レストハウス"),
    ("鎖", "レストハウス"),
    ("水槽", "レストハウス"),
    ("階段", "風車"),
    ("砂", "散歩道"),
    ("足音", "ジョギングコース"),
    ("枯葉", "ジョギングコース"),
    ("ドングリ", "ジョギングコース"),
    ("どんぐり", "ジョギングコース"),
    ("鳥", "森1"),
    ("さえずり", "森1"),
    ("薮", "森1"),
    ("虫", "森1"),
    ("木", "森1"),
    # Weak fallback
    ("水", "水郷の滝"),
    ("池", "水郷の滝"),
    ("川", "水郷の滝"),
]


@dataclass(frozen=True)
class RenamePlanItem:
    src: Path
    dst: Path


@dataclass(frozen=True)
class ParsedAudioName:
    speaker: str
    date_yyyymmdd: str
    time_hhmmss: Optional[str]
    descriptor: str
    source_kind: str  # "A" | "B" | "Other"
    keep_id: Optional[str] = None


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _clean_separators(text: str) -> str:
    t = _nfc(text)
    t = t.replace("＿", "_")
    t = t.replace(" ", "")
    t = re.sub(r"\.+", ".", t)  # collapse repeated dots
    t = t.replace("..", ".")
    t = t.replace(".", "")
    t = re.sub(r"_+", "_", t)
    t = t.strip("_")
    return t


def _strip_mp3_token(text: str) -> str:
    # e.g. "鉄琴mp3" -> "鉄琴"
    return re.sub(r"(?i)mp3", "", text)


def _parse_tsukamoto_style(stem: str) -> Optional[ParsedAudioName]:
    # Example: 塚本20251012_121402公園内散策_野球
    m = re.match(r"^(?P<speaker>[^0-9_]+)(?P<date>\d{8})_(?P<time>\d{6})(?P<rest>.*)$", stem)
    if not m:
        return None

    speaker = m.group("speaker")
    date = m.group("date")
    time = m.group("time")
    rest = m.group("rest")

    rest = _strip_mp3_token(rest)
    rest = _clean_separators(rest)

    # Normalize take markers.
    rest = rest.replace("(1)", "take1_")
    rest = rest.replace("(2)", "take2_")
    rest = rest.replace("(3)", "take3_")

    rest = _clean_separators(rest)
    descriptor = rest if rest else "UnknownContent"

    return ParsedAudioName(
        speaker=speaker,
        date_yyyymmdd=date,
        time_hhmmss=time,
        descriptor=descriptor,
        source_kind="B",
    )


def _parse_suzuki_style(stem: str, unknown_date: str, keep_id: bool) -> Optional[ParsedAudioName]:
    # Example: 鈴木_WAV_0018_001._滝_1
    m = re.match(r"^(?P<speaker>[^_]+)_WAV_(?P<id1>\d{4})_(?P<id2>\d{3})(?P<rest>.*)$", stem)
    if not m:
        return None

    speaker = m.group("speaker")
    id1 = m.group("id1")
    id2 = m.group("id2")
    rest = m.group("rest")

    rest = _strip_mp3_token(rest)
    rest = _clean_separators(rest)

    # Sometimes rest begins with an underscore.
    if rest.startswith("_"):
        rest = rest[1:]

    descriptor = rest if rest else "UnknownContent"
    kept = None
    if keep_id:
        kept = f"WAV{id1.zfill(4)}_{id2.zfill(3)}"

    return ParsedAudioName(
        speaker=speaker,
        date_yyyymmdd=unknown_date,
        time_hhmmss=None,
        descriptor=descriptor,
        source_kind="A",
        keep_id=kept,
    )


def parse_audio_name(filename: str, *, unknown_date: str, keep_suzuki_id: bool) -> Optional[ParsedAudioName]:
    p = Path(filename)
    if p.suffix.lower() != ".mp3":
        return None
    stem = _nfc(p.stem)

    parsed_b = _parse_tsukamoto_style(stem)
    if parsed_b:
        return parsed_b

    parsed_a = _parse_suzuki_style(stem, unknown_date=unknown_date, keep_id=keep_suzuki_id)
    if parsed_a:
        return parsed_a

    return None


def build_new_filename(parsed: ParsedAudioName, *, romanize_names: bool) -> str:
    speaker = parsed.speaker
    if romanize_names:
        speaker = NAME_ROMAJI.get(speaker, speaker)

    parts: list[str] = [speaker, parsed.date_yyyymmdd]
    if parsed.time_hhmmss:
        parts.append(parsed.time_hhmmss)
    if parsed.keep_id:
        parts.append(parsed.keep_id)

    parts.append(parsed.descriptor)
    joined = "_".join(parts)
    joined = _clean_separators(joined)
    if not joined:
        joined = f"{speaker}_{parsed.date_yyyymmdd}_UnknownContent"

    return f"{joined}.mp3"


def plan_renames(audio_dir: Path, *, targets: set[str], romanize_names: bool, unknown_date: str, keep_suzuki_id: bool) -> list[RenamePlanItem]:
    items: list[RenamePlanItem] = []

    for entry in sorted(audio_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() != ".mp3":
            continue

        stem = _nfc(entry.stem)
        # Target only specified speakers (prefix).
        speaker_prefix = re.match(r"^([^0-9_]+)", stem)
        if not speaker_prefix:
            continue
        speaker = speaker_prefix.group(1)
        if speaker not in targets:
            continue

        parsed = parse_audio_name(entry.name, unknown_date=unknown_date, keep_suzuki_id=keep_suzuki_id)
        if not parsed:
            continue

        new_name = build_new_filename(parsed, romanize_names=romanize_names)
        dst = entry.with_name(new_name)

        items.append(RenamePlanItem(src=entry, dst=dst))

    # Resolve collisions (dst exists or duplicates within plan)
    used: set[Path] = set()
    resolved: list[RenamePlanItem] = []
    for item in items:
        dst = item.dst
        base = dst.stem
        suffix = dst.suffix
        i = 1
        while dst.exists() or dst in used:
            dst = dst.with_name(f"{base}_dup{i}{suffix}")
            i += 1
        used.add(dst)
        resolved.append(RenamePlanItem(src=item.src, dst=dst))

    # Remove no-op renames
    resolved = [it for it in resolved if it.src.name != it.dst.name]
    return resolved


def _apply_renames(plan: list[RenamePlanItem]) -> None:
    # Two-phase rename to avoid edge cases.
    tmp_items: list[tuple[Path, Path]] = []
    for item in plan:
        tmp = item.src.with_name(item.src.name + ".__renametmp__")
        if tmp.exists():
            tmp.unlink()
        tmp_items.append((item.src, tmp))

    for src, tmp in tmp_items:
        src.rename(tmp)

    for (src, tmp), item in zip(tmp_items, plan, strict=True):
        tmp.rename(item.dst)


def guess_spot_title(descriptor: str) -> Optional[str]:
    d = _nfc(descriptor)
    for keyword, spot in KEYWORD_TO_SPOT_TITLE:
        if keyword.lower() in d.lower():
            return spot
    return None


def load_spots(spots_json: Path) -> list[dict]:
    with spots_json.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_spots(spots_json: Path, spots: list[dict]) -> None:
    with spots_json.open("w", encoding="utf-8") as f:
        json.dump(spots, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _build_track_name(speaker: str, descriptor: str, *, romanize_names: bool) -> str:
    if romanize_names:
        speaker = NAME_ROMAJI.get(speaker, speaker)
    return f"{speaker}:{descriptor}"


def plan_spots_additions(
    *,
    spots: list[dict],
    audio_files: Iterable[Path],
    audio_dir: Path,
    unknown_date: str,
    keep_suzuki_id: bool,
    romanize_names: bool,
    targets: set[str],
) -> tuple[dict[str, list[dict]], list[Path]]:
    title_to_spot: dict[str, dict] = {s.get("title", ""): s for s in spots}

    additions: dict[str, list[dict]] = {t: [] for t in title_to_spot.keys()}
    unmapped: list[Path] = []

    for f in sorted(audio_files):
        if f.suffix.lower() != ".mp3":
            continue

        stem = _nfc(f.stem)
        sp = re.match(r"^([^0-9_]+)", stem)
        if not sp:
            continue
        speaker = sp.group(1)
        if speaker not in targets:
            continue

        parsed = parse_audio_name(f.name, unknown_date=unknown_date, keep_suzuki_id=keep_suzuki_id)
        if not parsed:
            continue

        spot_title = guess_spot_title(parsed.descriptor)
        if not spot_title or spot_title not in title_to_spot:
            unmapped.append(f)
            continue

        rel = f"audio/{f.name}"
        track = {
            "name": _build_track_name(parsed.speaker, parsed.descriptor, romanize_names=romanize_names),
            "file": rel,
        }

        spot = title_to_spot[spot_title]
        playlist = spot.get("playlist") or []
        if any(t.get("file") == rel for t in playlist):
            continue

        additions[spot_title].append(track)

    # prune empty
    additions = {k: v for k, v in additions.items() if v}
    return additions, unmapped


def plan_spots_additions_from_rename_plan(
    *,
    spots: list[dict],
    rename_plan: list[RenamePlanItem],
    unknown_date: str,
    keep_suzuki_id: bool,
    romanize_names: bool,
    targets: set[str],
) -> tuple[dict[str, list[dict]], list[Path]]:
    title_to_spot: dict[str, dict] = {s.get("title", ""): s for s in spots}
    additions: dict[str, list[dict]] = {t: [] for t in title_to_spot.keys()}
    unmapped: list[Path] = []

    for it in rename_plan:
        parsed = parse_audio_name(it.src.name, unknown_date=unknown_date, keep_suzuki_id=keep_suzuki_id)
        if not parsed:
            continue
        if parsed.speaker not in targets:
            continue

        spot_title = guess_spot_title(parsed.descriptor)
        if not spot_title or spot_title not in title_to_spot:
            unmapped.append(it.dst)
            continue

        rel = f"audio/{it.dst.name}"
        track = {
            "name": _build_track_name(parsed.speaker, parsed.descriptor, romanize_names=romanize_names),
            "file": rel,
        }

        spot = title_to_spot[spot_title]
        playlist = spot.get("playlist") or []
        if any(t.get("file") == rel for t in playlist):
            continue
        additions[spot_title].append(track)

    additions = {k: v for k, v in additions.items() if v}
    return additions, unmapped


def apply_spots_additions(spots: list[dict], additions: dict[str, list[dict]]) -> None:
    title_to_spot: dict[str, dict] = {s.get("title", ""): s for s in spots}
    for title, tracks in additions.items():
        spot = title_to_spot.get(title)
        if not spot:
            continue
        if "playlist" not in spot or spot["playlist"] is None:
            spot["playlist"] = []
        spot["playlist"].extend(tracks)


def _print_rename_plan(plan: list[RenamePlanItem]) -> None:
    if not plan:
        print("[rename] 対象ファイルは見つかりませんでした")
        return
    print("[rename] 変更前 -> 変更後")
    for it in plan:
        print(f"- {it.src.name} -> {it.dst.name}")


def _print_assign_plan(additions: dict[str, list[dict]], unmapped: list[Path]) -> None:
    if additions:
        print("[assign] spots.json へ追加予定")
        for title in sorted(additions.keys()):
            print(f"- {title}: +{len(additions[title])}")
            for t in additions[title]:
                print(f"    - {t['name']} ({t['file']})")
    else:
        print("[assign] 追加対象はありません")

    if unmapped:
        print("[assign] ピン判定できずスキップ（要手動確認）")
        for p in unmapped:
            print(f"- {p.name}")


def _confirm(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    ans = input(prompt).strip().lower()
    return ans in ("", "y", "yes")


def main(argv: list[str]) -> int:
    _stdout_utf8()

    ap = argparse.ArgumentParser(description="audio/*.mp3 を安全にリネームし、spots.json のplaylistへ自動追加します")
    ap.add_argument("--audio-dir", default="audio", help="音声ディレクトリ (default: audio)")
    ap.add_argument("--spots-json", default="spots.json", help="spots.json のパス")
    ap.add_argument("--targets", default="鈴木,塚本", help="処理対象の先頭名をカンマ区切りで指定")
    ap.add_argument("--romanize-names", action="store_true", help="鈴木/塚本を Suzuki/Tsukamoto に変換")
    ap.add_argument("--unknown-date", default="UnknownDate", help="日付がない場合の表記 (default: UnknownDate / 'today' も可)")
    ap.add_argument("--keep-suzuki-id", action="store_true", default=True, help="鈴木(WAV)のIDを残す (default: on)")
    ap.add_argument("--no-keep-suzuki-id", dest="keep_suzuki_id", action="store_false", help="鈴木(WAV)のIDを残さない")
    ap.add_argument("--no-rename", action="store_true", help="リネームを行わない")
    ap.add_argument("--no-assign", action="store_true", help="spots.json 更新を行わない")
    ap.add_argument("--dry-run", action="store_true", help="変更を適用せず計画のみ表示")
    ap.add_argument("--yes", action="store_true", help="確認を省略して実行")

    args = ap.parse_args(argv)

    audio_dir = Path(args.audio_dir)
    spots_json = Path(args.spots_json)
    targets = {t.strip() for t in args.targets.split(",") if t.strip()}

    if args.unknown_date == "today":
        unknown_date = _dt.date.today().strftime("%Y%m%d")
    else:
        unknown_date = args.unknown_date

    if not audio_dir.exists() or not audio_dir.is_dir():
        print(f"audio-dir が見つかりません: {audio_dir}", file=sys.stderr)
        return 2

    # 1) Rename
    rename_plan: list[RenamePlanItem] = []
    if not args.no_rename:
        rename_plan = plan_renames(
            audio_dir,
            targets=targets,
            romanize_names=args.romanize_names,
            unknown_date=unknown_date,
            keep_suzuki_id=args.keep_suzuki_id,
        )
        _print_rename_plan(rename_plan)

    # 2) Assign (plan uses post-rename names)
    additions: dict[str, list[dict]] = {}
    unmapped: list[Path] = []
    if not args.no_assign:
        if not spots_json.exists():
            print(f"spots.json が見つかりません: {spots_json}", file=sys.stderr)
            return 2
        spots = load_spots(spots_json)

        if rename_plan:
            additions, unmapped = plan_spots_additions_from_rename_plan(
                spots=spots,
                rename_plan=rename_plan,
                unknown_date=unknown_date,
                keep_suzuki_id=args.keep_suzuki_id,
                romanize_names=args.romanize_names,
                targets=targets,
            )
        else:
            files_for_assign = [p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"]
            additions, unmapped = plan_spots_additions(
                spots=spots,
                audio_files=files_for_assign,
                audio_dir=audio_dir,
                unknown_date=unknown_date,
                keep_suzuki_id=args.keep_suzuki_id,
                romanize_names=args.romanize_names,
                targets=targets,
            )
        _print_assign_plan(additions, unmapped)

    if args.dry_run:
        print("[dry-run] 変更は適用していません")
        return 0

    # Apply rename
    if rename_plan:
        if not _confirm("\nリネームを実行しますか？ (Y/n): ", assume_yes=args.yes):
            print("[rename] キャンセルしました")
            return 0
        _apply_renames(rename_plan)
        print(f"[rename] 完了: {len(rename_plan)} files")

    # Apply spots.json updates
    if not args.no_assign and additions:
        if not _confirm("\nspots.json を更新しますか？ (Y/n): ", assume_yes=args.yes):
            print("[assign] キャンセルしました")
            return 0
        spots = load_spots(spots_json)
        apply_spots_additions(spots, additions)
        save_spots(spots_json, spots)
        print("[assign] 完了: spots.json を更新しました")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
