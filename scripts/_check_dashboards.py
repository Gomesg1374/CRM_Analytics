import requests

BASE  = "http://localhost:3000"
CREDS = {"username": "ggguarda@gmail.com", "password": "crm@2026"}

token = requests.post(f"{BASE}/api/session", json=CREDS).json()["id"]
h = {"X-Metabase-Session": token}

for did in [12, 13, 14, 15, 16]:
    d     = requests.get(f"{BASE}/api/dashboard/{did}", headers=h).json()
    cards = d.get("dashcards", [])
    ok, errors = [], []

    for dc in cards:
        card = dc.get("card", {})
        cid  = card.get("id")
        name = card.get("name", "?")
        if not cid:
            continue
        r = requests.post(f"{BASE}/api/card/{cid}/query", headers=h, json={})
        if r.status_code == 202:
            data   = r.json()
            status = data.get("status", "?")
            rows   = len(data.get("data", {}).get("rows", [])) if status == "completed" else -1
            if status == "completed":
                ok.append(f"    OK  [{cid}] {name} ({rows} linhas)")
            else:
                err = data.get("error", status)
                errors.append(f"    ERR [{cid}] {name} — {err[:100]}")
        else:
            try:
                msg = r.json().get("error", r.text[:120])
            except Exception:
                msg = r.text[:120]
            errors.append(f"    ERR [{cid}] {name} — HTTP {r.status_code}: {msg[:100]}")

    status_icon = "OK" if not errors else "FALHA"
    print(f"\n[{status_icon}] {d['name']} (id={did}) — {len(cards)} cards")
    for line in ok:     print(line)
    for line in errors: print(line)
