# nick100 — XMPP Multi-JID MUC Bot

Bot XMPP ringan yang join ke 1 room MUC dengan banyak nick dari banyak JID sekaligus. Semua nick idle drop-pesan setelah join.

## Fitur
- Multi-JID (1 s/d N), tiap JID punya nick sendiri-sendiri
- Per-JID atau shared MUC room
- 1 JID = 1+ nick (default 20)
- Drop semua pesan masuk (tidak reply)
- Idle selamanya setelah join
- SIGINT handler (Ctrl+C stop graceful)
- Configurable via `.env`

## Struktur File
```
~/bot/nick100/
├── run.py              # main script
├── .env                # config (JID, password, MUC, dll)
├── nicks.txt           # (opsional) master nick pool 136 entry
├── nick1.txt           # 20 nick untuk JID1
├── nick2.txt           # 20 nick untuk JID2
├── nick3.txt           # 20 nick untuk JID3
├── nick4.txt           # 20 nick untuk JID4
├── nick5.txt           # 20 nick untuk JID5
├── requirements.txt    # dependency pip
└── README.md           # file ini
```

## Format Nick File
Tiap baris = 1 nick, format pipe-separated:
```
nick|resource|display|full_name|kota_full
dani_cjr|mtSbIBbu|dani_cjr|Dani|Parepare
```
Kolom:
- `nick` — nama MUC (harus unik 1 room)
- `resource` — random string per klien (beda tiap nick)
- `display` — display name (XEP-0172)
- `full_name` — nama lengkap (untuk display)
- `kota_full` — kota asal (display only)

## Instalasi
```bash
pip install -r ~/bot/nick100/requirements.txt
```
Dependensi: `xmpppy>=0.7.0` (stdlib lain: `os, sys, signal, time, logging, threading, pathlib`).

## Konfigurasi `.env`
```ini
# JID1..JIDn (sampai sebanyak yang dibutuhkan)
JID1=botol1@conversations.im
PASSWORD1=password_rahasia
JID2=botol2@conversations.im
PASSWORD2=password_rahasia
# ... tambah JID3, JID4, dst.

# 1 MUC shared untuk semua JID
MUC=indonesia@conference.conversations.im

# Nick per JID (default 20)
NICKS_PER_JID=20

# Opsional
JOIN_DELAY=0.3      # detik jeda antar join (default 0.3)
SERVER=             # kosong = auto-resolve dari JID domain
```

## Cara Pakai
```bash
cd ~/bot/nick100
python3 run.py
```

Output:
```
2026-08-31 22:19:09 INFO nick100: Setup: 5 JID × 20 nick = 100 total → indonesia@conference.conversations.im
2026-08-31 22:19:09 INFO nick100: --- JID1 (botol1@conversations.im) mulai 20 nick ---
2026-08-31 22:19:12 INFO nick100: [dani_cjr] joined ... as botol1@conversations.im (resource=mtSbIBbu)
...
2026-08-31 22:24:32 INFO nick100: All 100 nicks joined. Idling (drop all messages)...
2026-08-31 22:24:32 INFO nick100: Press Ctrl+C to stop.
```

Tunggu 5-6 menit untuk 100 nick join semua, lalu bot idle.

## Stop
- **Ctrl+C** sekali → stop graceful (tunggu current join selesai, lalu disconnect)
- **Ctrl+C** dua kali → kill paksa
- `pkill -INT -f run.py` dari terminal lain

## Cara Kerja
1. Parse `JID1..JIDn` + `PASSWORD1..PASSWORDn` dari `.env`
2. Untuk tiap JID, baca `nick{i}.txt` (atau fallback `nicks.txt`)
3. Auth ke server (`conversations.im:5222` via TLS+SASL)
4. Join MUC dengan nick pertama, tunggu ~3-4 detik, lanjut nick berikutnya
5. Setelah semua join, masuk loop idle yang drop semua message
6. Connect per-nick (1 socket per nick = 100 socket total) — ringan karena idle

## Tambah/Kurangi JID
Tambah blok di `.env`:
```ini
JID6=user6@conversations.im
PASSWORD6=***
```
Lalu buat `nick6.txt` dengan 20 nick unik (tidak bentrok dengan nick1-5).

## Troubleshooting
- **"auth failed"** → password salah atau JID belum terdaftar. Test manual:
  ```bash
  python3 -c "import xmpp; c=xmpp.Client('conversations.im', debug=[]); print(c.connect(('conversations.im',5222))); print(c.auth('botol1','PASSWORD', resource='test'))"
  ```
- **"connect failed"** → cek DNS server & firewall. `conversations.im` resolve ke `78.47.177.120`, port `5222` harus terbuka.
- **Rate limit** → naikkan `JOIN_DELAY=1.0` di `.env`
- **MUC component tidak resolve** → `xmpppy` pakai XMPP service discovery, bukan `getaddrinfo` DNS. Server `conversations.im` mengarahkan MUC stanza via internal routing — `conference.conversations.im` tidak perlu resolve dari sisi client.

## Logika Asal
Pattern sequential join + idle Process loop ditiru dari `~/xmpp/nick_flood.py`. Penambahannya: multi-JID, per-JID nick file, SIGINT handler, fallback `nicks.txt` master.
