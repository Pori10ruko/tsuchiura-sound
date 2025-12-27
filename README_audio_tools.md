# Audio tools

`audio/` 内の新規 mp3（例: 鈴木・塚本）を安全にリネームし、`spots.json` の各ピン `playlist` に自動で追記するツールです。

## 使い方

### 1) まずプレビュー（変更しない）

```bash
python3 scripts/audio_rename_and_assign.py --dry-run
```

### 2) 実行（Y/n で確認してから適用）

```bash
python3 scripts/audio_rename_and_assign.py
```

### オプション

- 名前を英語化（例: 鈴木→Suzuki）

```bash
python3 scripts/audio_rename_and_assign.py --romanize-names
```

- 鈴木（WAV）ファイルのIDを残さない

```bash
python3 scripts/audio_rename_and_assign.py --no-keep-suzuki-id
```

- 日付がない場合に今日の日付を入れる

```bash
python3 scripts/audio_rename_and_assign.py --unknown-date today
```

- 確認を省略して実行（注意）

```bash
python3 scripts/audio_rename_and_assign.py --yes
```

## 注意

- 文字化け対策として、JSONはUTF-8/`ensure_ascii=false`で保存します。
- ピン判定はファイル名のキーワード推定なので、`[assign] ピン判定できず` に出たものは手動で振り分けてください。
