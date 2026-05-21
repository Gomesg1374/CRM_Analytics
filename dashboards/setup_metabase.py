#!/usr/bin/env python3
"""
setup_metabase.py — Cria os 5 dashboards do CRM Analytics no Metabase via API.

Pré-requisitos:
  1. Metabase rodando (default: http://localhost:3000)
  2. Banco crm_analytics já conectado no Metabase (Admin → Databases)
  3. Credenciais de um usuário admin do Metabase

Uso (PowerShell):
  $env:METABASE_USER="admin@crm.local"; $env:METABASE_PASS="sua_senha"
  python dashboards/setup_metabase.py

  Com URL customizada:
  $env:METABASE_URL="http://meu-servidor:3000"
  python dashboards/setup_metabase.py

Flags:
  --clean   Remove dashboards e cards com o mesmo nome antes de recriar (idempotente)
"""

import os
import re
import sys
import requests

MB_URL  = os.getenv("METABASE_URL",  "http://localhost:3000").rstrip("/")
MB_USER = os.getenv("METABASE_USER", "")
MB_PASS = os.getenv("METABASE_PASS", "")

COLLECTION_NAME = "CRM Analytics"
DASHBOARDS_DIR  = os.path.dirname(os.path.abspath(__file__))

DASHBOARD_SPECS = [
    (
        "01_funil_comercial.sql",
        "Funil Comercial",
        "Leads recebidos, agendamentos, visitas e vendas — taxas de conversão por etapa e motivos de perda.",
    ),
    (
        "02_performance_vendas.sql",
        "Performance de Vendas",
        "Vendas vs meta por vendedor e loja; ticket médio; desconto médio; margem bruta.",
    ),
    (
        "03_financeiro.sql",
        "Financeiro",
        "Lucro líquido, comissões pagas e impostos — margem líquida por loja e por vendedor.",
    ),
    (
        "04_canais_leads.sql",
        "Canais e Leads",
        "Volume de leads por canal ao longo do tempo e taxa de conversão por canal.",
    ),
    (
        "05_estoque_marca.sql",
        "Estoque e Marca",
        "Vendas por marca e modelo; participação de mercado; estoque atual por situação.",
    ),
]


# ---------------------------------------------------------------------------
# Chart type resolution
# ---------------------------------------------------------------------------

def _resolve_display(hint: str) -> str:
    h = hint.lower()
    if "funnel"    in h:                        return "funnel"
    if "scalar"    in h or "kpi" in h:          return "scalar"
    if "number"    in h and "bar" not in h:     return "scalar"
    if "horizontal" in h:                       return "row"
    if "combo"     in h:                        return "combo"
    if "line"      in h:                        return "line"
    if "pie"       in h:                        return "pie"
    if "scatter"   in h:                        return "scatter"
    if "bar"       in h:                        return "bar"
    if "heatmap"   in h or "table" in h:        return "table"
    return "table"


def _viz_settings(display: str, stacked: bool) -> dict:
    if display == "bar" and stacked:
        return {"stackable.stack_type": "stacked"}
    if display == "row":
        return {"graph.x_axis.scale": "ordinal"}
    return {}


# ---------------------------------------------------------------------------
# SQL file parser
# ---------------------------------------------------------------------------

def parse_sql_file(path: str) -> list[dict]:
    """Return list of {name, display, stacked, sql} from a dashboard SQL file."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    parts = re.split(r"(?m)(?=^-- CARD \d+:)", content)
    cards = []
    for part in parts:
        if not re.match(r"-- CARD \d+:", part.strip()):
            continue

        first_line = part.splitlines()[0]

        m_name  = re.search(r"-- CARD \d+:\s*(.+?)(?:\s*\(gráfico:|$)", first_line)
        m_chart = re.search(r"\(gráfico:\s*(.+?)\)", first_line, re.IGNORECASE)

        name       = m_name.group(1).strip()  if m_name  else "Card"
        chart_hint = m_chart.group(1).strip() if m_chart else "table"
        display    = _resolve_display(chart_hint)
        stacked    = "empilhado" in chart_hint.lower()

        # Extract SQL: everything from the first SELECT or WITH keyword
        sql_lines = []
        collecting = False
        for line in part.splitlines():
            stripped = line.strip().upper()
            if not collecting and (stripped.startswith("SELECT") or stripped.startswith("WITH")):
                collecting = True
            if collecting:
                sql_lines.append(line)

        sql = "\n".join(sql_lines).strip()
        if sql:
            cards.append({
                "name":    name,
                "display": display,
                "stacked": stacked,
                "sql":     sql,
            })

    return cards


# ---------------------------------------------------------------------------
# Metabase API helpers
# ---------------------------------------------------------------------------

class MetabaseClient:
    def __init__(self, url: str, user: str, password: str):
        self.url = url
        self.s   = requests.Session()
        self.s.headers["Content-Type"] = "application/json"
        self._authenticate(user, password)

    def _authenticate(self, user: str, password: str):
        resp = self.s.post(
            f"{self.url}/api/session",
            json={"username": user, "password": password},
            timeout=15,
        )
        if resp.status_code == 400:
            raise RuntimeError("Credenciais inválidas — verifique METABASE_USER e METABASE_PASS.")
        resp.raise_for_status()
        self.s.headers["X-Metabase-Session"] = resp.json()["id"]

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def find_database(self, name: str) -> int:
        resp = self.s.get(f"{self.url}/api/database", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        dbs  = data.get("data", data) if isinstance(data, dict) else data
        for db in dbs:
            if name.lower() in db.get("name", "").lower():
                return db["id"]
        raise RuntimeError(
            f"Banco '{name}' não encontrado no Metabase.\n"
            "  → Admin → Databases → Add Database → PostgreSQL\n"
            "  → Name: crm_analytics, Host: localhost, Port: 5432\n"
            "  → Database: crm_analytics, User: crm, Password: crm123"
        )

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def find_or_create_collection(self, name: str) -> int:
        resp = self.s.get(f"{self.url}/api/collection", timeout=10)
        resp.raise_for_status()
        for col in resp.json():
            if col.get("name") == name:
                return col["id"]
        resp = self.s.post(
            f"{self.url}/api/collection",
            json={"name": name, "color": "#509EE3"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    # ------------------------------------------------------------------
    # Cards (questions)
    # ------------------------------------------------------------------

    def create_card(
        self,
        db_id:         int,
        collection_id: int,
        name:          str,
        sql:           str,
        display:       str,
        viz_settings:  dict,
    ) -> int:
        payload = {
            "name":    name,
            "display": display,
            "dataset_query": {
                "type":   "native",
                "native": {"query": sql, "template-tags": {}},
                "database": db_id,
            },
            "visualization_settings": viz_settings,
            "collection_id": collection_id,
        }
        resp = self.s.post(f"{self.url}/api/card", json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["id"]

    def delete_cards_in_collection(self, collection_id: int):
        resp = self.s.get(
            f"{self.url}/api/collection/{collection_id}/items",
            params={"models": "card", "limit": 200},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("data", [])
        for item in items:
            self.s.delete(f"{self.url}/api/card/{item['id']}", timeout=10)

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    def create_dashboard(self, collection_id: int, name: str, description: str) -> int:
        payload = {
            "name":          name,
            "description":   description,
            "collection_id": collection_id,
        }
        resp = self.s.post(f"{self.url}/api/dashboard", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["id"]

    def add_card_to_dashboard(
        self,
        dashboard_id: int,
        card_id:      int,
        col:          int,
        row:          int,
        size_x:       int = 9,
        size_y:       int = 4,
    ):
        resp = self.s.post(
            f"{self.url}/api/dashboard/{dashboard_id}/cards",
            json={"cardId": card_id, "col": col, "row": row, "size_x": size_x, "size_y": size_y},
            timeout=10,
        )
        resp.raise_for_status()

    def delete_dashboards_by_name(self, collection_id: int, names: list[str]):
        resp = self.s.get(
            f"{self.url}/api/collection/{collection_id}/items",
            params={"models": "dashboard", "limit": 200},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("data", [])
        for item in items:
            if item.get("name") in names:
                self.s.delete(f"{self.url}/api/dashboard/{item['id']}", timeout=10)


# ---------------------------------------------------------------------------
# Grid layout helper
# ---------------------------------------------------------------------------

def _layout(i: int, display: str) -> tuple[int, int, int, int]:
    """Return (col, row, size_x, size_y) for card index i."""
    if display == "scalar":
        # Scalars: 4 wide, 2 tall — up to 4 per row
        col    = (i % 4) * 4 + (i % 4 > 3) * 2  # coerce to grid
        col    = (i % 2) * 9
        row    = (i // 2) * 2
        return col, row, 9, 2
    # Charts: 2 per row, 9 wide, 4 tall
    col = (i % 2) * 9
    row = (i // 2) * 4
    return col, row, 9, 4


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    clean = "--clean" in sys.argv

    if not MB_USER or not MB_PASS:
        print("❌  Defina as variáveis de ambiente antes de executar:")
        print("    $env:METABASE_USER=\"admin@crm.local\"")
        print("    $env:METABASE_PASS=\"sua_senha\"")
        sys.exit(1)

    print(f"Conectando a {MB_URL} …")
    try:
        client = MetabaseClient(MB_URL, MB_USER, MB_PASS)
    except requests.exceptions.ConnectionError:
        print(f"❌  Não foi possível conectar a {MB_URL}")
        print("    Verifique se o Metabase está rodando:")
        print("    docker ps | grep metabase")
        sys.exit(1)

    db_id = client.find_database("crm_analytics")
    print(f"✅ Autenticado | Database crm_analytics → ID {db_id}")

    col_id = client.find_or_create_collection(COLLECTION_NAME)
    print(f"✅ Collection '{COLLECTION_NAME}' → ID {col_id}\n")

    if clean:
        print("🧹 --clean: removendo dashboards e cards existentes …")
        dash_names = [spec[1] for spec in DASHBOARD_SPECS]
        client.delete_dashboards_by_name(col_id, dash_names)
        client.delete_cards_in_collection(col_id)
        print()

    created = []
    for filename, dash_name, description in DASHBOARD_SPECS:
        path  = os.path.join(DASHBOARDS_DIR, filename)
        cards = parse_sql_file(path)
        print(f"📊  {dash_name}  ({len(cards)} cards)")

        dash_id = client.create_dashboard(col_id, dash_name, description)

        for i, card in enumerate(cards):
            viz   = _viz_settings(card["display"], card["stacked"])
            cid   = client.create_card(db_id, col_id, card["name"], card["sql"], card["display"], viz)
            col_pos, row_pos, sx, sy = _layout(i, card["display"])
            client.add_card_to_dashboard(dash_id, cid, col=col_pos, row=row_pos, size_x=sx, size_y=sy)
            print(f"     [{i+1}] {card['name']}  ({card['display']})")

        created.append((dash_name, dash_id))
        print()

    print("=" * 55)
    print("✅ Dashboards criados com sucesso!\n")
    for name, did in created:
        print(f"   {MB_URL}/dashboard/{did}  —  {name}")
    print()
    print(f"   Ou acesse a collection: {MB_URL}/collection/{col_id}")


if __name__ == "__main__":
    main()
