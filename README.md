# zaiko-relay

Zaiko の HLS 配信をローカルで再生するための HTTP relay です。
公式 Web クライアントでは再生中に再生が止まったり解像度が下がってしまうため、ローカルで中継して安定した再生を実現します。

```sh
uv run python zaiko-relay.py 'https://.../tokengenerate?payload=...'
```

```sh
ffplay http://127.0.0.1:8765/index.m3u8
```
