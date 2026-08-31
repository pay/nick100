#!/bin/bash
# nick100 — start|stop|restart|log
# Usage: ./run.sh {start|stop|restart|log|status}

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PIDFILE="$SCRIPT_DIR/run.pid"
LOGFILE="$SCRIPT_DIR/run.log"

start() {
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "already running (PID $(cat "$PIDFILE"))"
        return 0
    fi
    if pgrep -f 'python3.*run\.py' >/dev/null; then
        PID=$(pgrep -f 'python3.*run\.py' | head -1)
        echo "$PID" > "$PIDFILE"
        echo "already running (PID $PID, no pidfile)"
        return 0
    fi
    echo "starting nick100..."
    nohup python3 -u run.py >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1
    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "started (PID $(cat "$PIDFILE")) — log: $LOGFILE"
    else
        echo "FAILED to start. Last log lines:"
        tail -20 "$LOGFILE"
        rm -f "$PIDFILE"
        return 1
    fi
}

stop() {
    if [[ ! -f "$PIDFILE" ]]; then
        PID=$(pgrep -f 'python3.*run\.py' | head -1 || true)
        if [[ -z "$PID" ]]; then
            echo "not running"
            return 0
        fi
        echo "$PID" > "$PIDFILE"
    fi
    PID=$(cat "$PIDFILE")
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "not running (stale pidfile)"
        rm -f "$PIDFILE"
        return 0
    fi
    echo "stopping PID $PID (SIGINT, graceful)..."
    kill -INT "$PID"
    for i in 1 2 3 4 5 6 7 8 9 10; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "stopped"
            rm -f "$PIDFILE"
            return 0
        fi
        sleep 1
    done
    echo "still running after 10s, forcing SIGKILL"
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PIDFILE"
    echo "killed"
}

restart() {
    stop || true
    sleep 1
    start
}

log() {
    if [[ ! -f "$LOGFILE" ]]; then
        echo "no log file at $LOGFILE"
        return 1
    fi
    tail -f "$LOGFILE"
}

status() {
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "running (PID $(cat "$PIDFILE"))"
    else
        PID=$(pgrep -f 'python3.*run\.py' | head -1 || true)
        if [[ -n "$PID" ]]; then
            echo "running (PID $PID, no pidfile)"
        else
            echo "not running"
        fi
    fi
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    log)     log ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|stop|restart|log|status}"
        exit 1
        ;;
esac
