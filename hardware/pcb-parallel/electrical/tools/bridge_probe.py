"""Read-only engine probe over the EasyEDA run-api-gateway bridge.

Usage:  python bridge_probe.py <js-file>
Prints the bridge's JSON response. Mutates nothing on the board.
"""
import json
import sys
import urllib.error
import urllib.request


def bridge_port():
    for port in range(49620, 49630):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:%d/health" % port, timeout=1
            ) as r:
                body = json.loads(r.read().decode("utf-8"))
            if body.get("service") == "easyeda-bridge":
                return port, body
        except Exception:
            continue
    return None, None


def execute(port, code, timeout=900):
    req = urllib.request.Request(
        "http://127.0.0.1:%d/execute" % port,
        data=json.dumps({"code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return {"httpError": e.code, "body": json.loads(raw)}
        except Exception:
            return {"httpError": e.code, "body": raw}


def main():
    if len(sys.argv) < 2:
        print("usage: bridge_probe.py <js-file>")
        return 2
    code = open(sys.argv[1], encoding="utf-8").read()

    port, health = bridge_port()
    if port is None:
        print("NO_BRIDGE: no easyeda-bridge on 49620-49629")
        return 1
    print("bridge port=%d edaConnected=%s windows=%s"
          % (port, health.get("edaConnected"), health.get("edaWindowCount")))
    if not health.get("edaConnected"):
        print("EDA_NOT_CONNECTED: enable 'External Interactions' for run-api-gateway")
        return 1

    out = execute(port, code)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
