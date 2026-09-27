# zaiko-relay

Zaiko の HLS 配信をローカルで再生するための HTTP relay です。公式 Web で再生中に playback token の再生成がうまく動かない場合に、relay が upstream の 401 を受け取ると token を取り直して同じリクエストを再試行します。

再生例では FFmpeg の ffplay を使います。relay は playlist や segment を解析・書き換えず、そのまま中継します。

```sh
uv run python zaiko-relay.py 'https://.../tokengenerate?payload=...'
```

```sh
ffplay http://127.0.0.1:8765/index.m3u8
```
