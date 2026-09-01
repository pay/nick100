# nick100

XMPP MUC bot: join 1 room dengan banyak nick dari banyak JID, lalu idle. Multi-JID, drop semua pesan, configurable.

## Quick Start
```bash
git clone https://github.com/pay/nick100.git
cd nick100
cp .env.example .env
$EDITOR .env          # isi JID + PASSWORD + MUC
pip install -r requirements.txt
./run.sh start        # jalan di background
./run.sh log          # tail log
./run.sh stop         # stop graceful
```

## Konfigurasi `.env`
```ini
# Multi-JID: tambah JIDn/PASSWORDn sebanyak yang dibutuhkan
JID1=jid1@domain.tld
PASSWORD1=***
JID2=jid2@domain.tld
PASSWORD2=***
# ... JID3, JID4, dst.

# 1 MUC shared untuk semua JID
MUC=nama_room@conference.domain.tld

# Nick per JID (total = N_JID × NICKS_PER_JID)
NICKS_PER_JID=20

# Jeda antar join dalam detik. Naikkan kalau kena rate-limit/presence flood.
JOIN_DELAY=3

# Auto-reconnect saat disconnect (on/off). Default off.
# ON  = nick yang diskonek akan dicoba reconnect (risiko presence flood).
# OFF = nick yang diskonek dibiarkan offline (hemat, anti-flood).
AUTO_RECONNECT=off
```

## Format `nicks.txt`
Tiap baris = 1 nick, pipe-separated:
```
nick|resource|display|full_name|kota_full
dani_cjr|abc123|dani_cjr|Dani|Parepare
```
100 nick pertama dibaca berurutan per JID (20 → JID1, 21-40 → JID2, dst). `nicks.txt` punya 136 entry siap.

## Commands (`run.sh`)
| Command   | Fungsi                                        |
|-----------|-----------------------------------------------|
| start     | Start bot di background, simpan PID ke `run.pid` |
| stop      | SIGINT graceful (10s), lalu SIGKILL          |
| restart   | stop + start                                 |
| log       | `tail -f run.log`                            |
| status    | Cek running                                  |

## Struktur File
```
run.py            # main bot
run.sh            # start|stop|restart|log|status
nicks.txt         # 136 nick nama_kota
.env              # config (JID, password, MUC) — JANGAN commit
.env.example      # template
requirements.txt  # xmpppy>=0.7.0
.gitignore        # exclude .env, *.log, __pycache__
```

## Dependensi
- Python ≥ 3.8
- `xmpppy>=0.7.0` (stdlib lain sudah built-in)
- `xmpp.Client` (`xmpppy`) — sync, single-connection-per-nick, ringan

## Tips Operasional
- **Rate-limit / "presence flood"**: naikkan `JOIN_DELAY=3` atau lebih.
- **100 nick offline setelah join**: cek apakah MUC server kick dengan logika flood — set `AUTO_RECONNECT=off` (default).
- **Tambah JID**: tambah `JIDn`/`PASSWORDn` di `.env`, tambah 20 nick baru di `nicks.txt` (atau buat `nickN.txt` kalau mau per-JID file).

## Logika Inti
Tiru pola sequential-join + idle-Process dari `~/xmpp/nick_flood.py`. Tambah: multi-JID, per-JID nick slicing, skip-on-fail, retry 2x dengan exponential backoff, SIGINT handler, env-driven config.
