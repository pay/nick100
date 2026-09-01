"""XMPP MUC nick 1-100 — join 1 MUC dengan 100 nick, drop semua pesan, idle.

Logika dasar ditiru dari ~/xmpp/nick_flood.py.
Beda: 100 nick dari nicks.txt (sudah berisi nick001..nick100, resource
random, display name), 100 connection paralel setelah join selesai.
"""
import os
import sys
import signal
import time
import logging
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = Path(os.environ.get("NICK100_ENV", str(BASE_DIR / ".env")))
NICKS_PATH = BASE_DIR / "nicks.txt"


def load_env(path: Path) -> dict:
    cfg = {}
    if not path.exists():
        return cfg
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def load_nicks(path: Path):
    """Return list of (nick, resource)."""
    nicks = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 2:
            continue
        nicks.append((parts[0].strip(), parts[1].strip()))
    return nicks


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("nick100")

import xmpp as xmpppy  # noqa: E402
from xmpp.protocol import Presence  # noqa: E402


def main():
    cfg = load_env(ENV_PATH)
    SERVER = cfg.get("SERVER", "").strip()
    ROOM = cfg.get("MUC", "").strip()
    NICKS_PER_JID = int(cfg.get("NICKS_PER_JID", "20") or "20")
    JOIN_DELAY = float(cfg.get("JOIN_DELAY", "0.3") or "0.3")
    AUTO_RECONNECT = cfg.get("AUTO_RECONNECT", "off").strip().lower() in ("1", "true", "on", "yes")

    if not ROOM:
        log.error("MUC kosong di %s", ENV_PATH)
        sys.exit(1)

    # Parse JID1..JIDn + PASSWORD1..PASSWORDn
    accounts = []
    i = 1
    while True:
        jid = cfg.get(f"JID{i}", "").strip()
        pw = cfg.get(f"PASSWORD{i}", "").strip()
        if not jid or not pw:
            break
        node, _, rest = jid.partition("@")
        domain = rest.split("/", 1)[0]
        accounts.append({"idx": i, "jid": jid, "node": node, "domain": domain, "password": pw})
        i += 1

    if not accounts:
        log.error("Tidak ada JID1/PASSWORD1 dst. di %s", ENV_PATH)
        sys.exit(1)

    nicks_per_jid_map = {}  # idx -> list[(nick,resource)]
    for acc in accounts:
        per_path = NICKS_PATH.parent / f"nick{acc['idx']}.txt"
        if per_path.exists():
            nicks_per_jid_map[acc["idx"]] = load_nicks(per_path)
        else:
            # fallback: slice dari nicks.txt utama (urutan)
            pass

    # Hitung total nick yang dibutuhkan & validasi
    if nicks_per_jid_map:
        # mode per-JID file
        for acc in accounts:
            got = nicks_per_jid_map.get(acc["idx"], [])
            need = NICKS_PER_JID
            if len(got) < need:
                log.error("nick%d.txt cuma punya %d nick, butuh %d",
                          acc["idx"], len(got), need)
                sys.exit(1)
            # slice sesuai NICKS_PER_JID
            nicks_per_jid_map[acc["idx"]] = got[:need]
        nicks_all = None  # tidak dipakai di mode ini
    else:
        # fallback: baca nicks.txt utama & slice
        nicks_all = load_nicks(NICKS_PATH)
        if not nicks_all:
            log.error("nicks.txt kosong & tidak ada nick{i}.txt per-JID")
            sys.exit(1)
        total_needed = len(accounts) * NICKS_PER_JID
        if total_needed > len(nicks_all):
            log.error("Butuh %d nick, tapi nicks.txt cuma %d", total_needed, len(nicks_all))
            sys.exit(1)

    log.info("Setup: %d JID × %d nick = %d total → %s",
             len(accounts), NICKS_PER_JID, len(accounts) * NICKS_PER_JID, ROOM)

    _clients = []   # list of (nick, cl, idx)
    _stop = threading.Event()
    _lock = threading.Lock()

    def drop(_conn, _msg):
        return True

    def connect_nick(nick: str, resource: str, acc: dict, retries: int = 2) -> bool:
        server = SERVER or acc["domain"]
        backoff = 2  # detik
        for attempt in range(retries + 1):
            cl = xmpppy.Client(server, debug=[])
            try:
                if not cl.connect((server, 5222)):
                    if attempt < retries:
                        log.warning("[%s] connect fail, retry in %ds (try %d/%d)",
                                    nick, backoff, attempt + 1, retries)
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 10)
                        continue
                    log.error("[%s] connect failed (after %d tries)", nick, retries + 1)
                    return False
            except Exception as e:
                if attempt < retries:
                    log.warning("[%s] connect error: %s, retry in %ds (try %d/%d)",
                                nick, e, backoff, attempt + 1, retries)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 10)
                    continue
                log.error("[%s] connect error: %s (after %d tries)", nick, e, retries + 1)
                return False
            # connect berhasil
            try:
                if not cl.auth(acc["node"], acc["password"], resource=resource):
                    log.error("[%s] auth failed (jid=%s)", nick, acc["jid"])
                    try:
                        cl.disconnect()
                    except Exception:
                        pass
                    return False
            except Exception as e:
                log.error("[%s] auth error: %s", nick, e)
                return False
            cl.send(Presence())

            # Join MUC, no backlog
            p = Presence(to=f"{ROOM}/{nick}")
            p.setTag("x", namespace="http://jabber.org/protocol/muc")
            p.setTag("x").setTag("history", attrs={"maxchars": "0", "maxstanzas": "0"})
            cl.send(p)

            cl.RegisterHandler("message", drop)
            with _lock:
                _clients.append((nick, cl, acc))
            log.info("[%s] joined %s as %s (resource=%s)",
                     nick, ROOM, acc["jid"], resource)
            return True
        return False

    # Sequential joins per JID: JID1 → 20 nick → JID2 → 20 nick → ...
    nick_offset = 0
    for acc in accounts:
        if nicks_per_jid_map:
            chunk = nicks_per_jid_map[acc["idx"]]
            log.info("--- JID%d (%s) mulai %d nick (per-file) ---",
                     acc["idx"], acc["jid"], len(chunk))
        else:
            chunk = nicks_all[nick_offset:nick_offset + NICKS_PER_JID]
            if len(chunk) < NICKS_PER_JID:
                log.error("nicks.txt tidak cukup untuk JID%d (sisa %d, butuh %d)",
                          acc["idx"], len(chunk), NICKS_PER_JID)
                break
            nick_offset += NICKS_PER_JID
            log.info("--- JID%d (%s) mulai %d nick ---", acc["idx"], acc["jid"], len(chunk))
        for nick, resource in chunk:
            if _stop.is_set():
                log.info("stop requested before %s", nick)
                break
            ok = connect_nick(nick, resource, acc)
            if not ok:
                log.warning("[%s] gagal, skip & lanjut (JID%d)", nick, acc["idx"])
                # tetap lanjut, jangan stop semua
                continue
            # sleep responsif ke SIGINT
            slept = 0.0
            while slept < JOIN_DELAY and not _stop.is_set():
                time.sleep(0.05)
                slept += 0.05
        if _stop.is_set():
            break

    log.info("All %d nicks joined. Idling (drop all messages)...", len(_clients))
    log.info("Press Ctrl+C to stop.")

    # SIGINT handler: cukup set flag, KeyboardInterrupt di-raise oleh Python
    # setelah cl.Process() kembali (poll timeout 0.2s cukup cepat).
    def _on_sigint(signum, frame):
        if not _stop.is_set():
            log.warning("SIGINT received — stopping...")
        _stop.set()
    signal.signal(signal.SIGINT, _on_sigint)

    # Reconnect helper — dinonaktifkan kecuali AUTO_RECONNECT=on
    def reconnect_one(nick: str, acc: dict) -> bool:
        if not AUTO_RECONNECT:
            return False  # silent
        # resource deterministik dari nick + timestamp
        resource = "rs" + nick.replace("_", "")[-8:] + str(int(time.time()) % 1000)
        return connect_nick(nick, resource, acc)

    try:
        while not _stop.is_set():
            with _lock:
                snapshot = list(_clients)
            for nick, cl, acc in snapshot:
                if _stop.is_set():
                    break
                try:
                    cl.Process(0.5)
                except Exception as e:
                    if AUTO_RECONNECT:
                        log.warning("[%s] process error: %s — reconnect", nick, e)
                        def _do_reconnect(n=nick, a=acc):
                            with _lock:
                                for i, (nn, cc, aa) in enumerate(_clients):
                                    if nn == n and cc is cl:
                                        _clients.pop(i)
                                        break
                            if reconnect_one(n, a):
                                log.info("[%s] reconnected", n)
                            else:
                                log.error("[%s] reconnect failed, will drop", n)
                        threading.Thread(target=_do_reconnect, daemon=True).start()
                    else:
                        log.debug("[%s] process error: %s", nick, e)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — stopping...")
    finally:
        _stop.set()
        with _lock:
            for _nick, cl, _ in _clients:
                try:
                    cl.disconnect()
                except Exception:
                    pass
        log.info("All clients disconnected")


if __name__ == "__main__":
    main()