# app.py
from flask import Flask, jsonify, request, send_file, render_template
import json
import csv
from uuid import uuid4
from datetime import datetime
from typing import List, Optional
import os

DATA_FILE = "data.json"

class Entry:
    def __init__(self, title: str, amount: float, category: str, kind: str, note: str = "", date: Optional[str] = None, id: Optional[str] = None):
        """
        kind: "income" or "expense"
        date: ISO format string (YYYY-MM-DD) or None -> set today
        """
        self.id = id or str(uuid4())
        self.title = title
        self.amount = float(amount)
        self.category = category
        self.kind = kind  # "income" or "expense"
        self.note = note
        self.date = date or datetime.now().date().isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "amount": self.amount,
            "category": self.category,
            "kind": self.kind,
            "note": self.note,
            "date": self.date
        }

    @staticmethod
    def from_dict(d):
        return Entry(
            title=d.get("title",""),
            amount=d.get("amount",0),
            category=d.get("category",""),
            kind=d.get("kind","expense"),
            note=d.get("note",""),
            date=d.get("date", None),
            id=d.get("id", None)
        )

class Ledger:
    def __init__(self):
        self.entries: List[Entry] = []
        self.load()

    def add(self, entry: Entry):
        self.entries.append(entry)
        self.save()

    def delete(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.id != entry_id]
        changed = len(self.entries) < before
        if changed:
            self.save()
        return changed

    def update(self, entry_id: str, **kwargs) -> Optional[Entry]:
        for e in self.entries:
            if e.id == entry_id:
                for k,v in kwargs.items():
                    if hasattr(e, k) and v is not None:
                        # type conversions
                        if k == "amount":
                            setattr(e, k, float(v))
                        else:
                            setattr(e, k, v)
                self.save()
                return e
        return None

    def search(self, keyword: str):
        kw = keyword.lower()
        return [e for e in self.entries if kw in e.title.lower() or kw in e.category.lower() or kw in e.note.lower()]

    def list_all(self):
        # return list sorted by date desc
        return sorted(self.entries, key=lambda x: x.date or "", reverse=True)

    def total_balance(self):
        income = sum(e.amount for e in self.entries if e.kind == "income")
        expense = sum(e.amount for e in self.entries if e.kind == "expense")
        return {"income": income, "expense": expense, "balance": income - expense}

    def save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.entries], f, ensure_ascii=False, indent=2)

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [Entry.from_dict(d) for d in data]
            except Exception as ex:
                print("โหลดไฟล์ล้มเหลว:", ex)
                self.entries = []
        else:
            self.entries = []

    def export_csv(self, csv_path="export.csv"):
        fieldnames = ["id","date","title","category","kind","amount","note"]
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for e in self.list_all():
                row = e.to_dict()
                writer.writerow(row)
        return csv_path

ledger = Ledger()
app = Flask(__name__, template_folder="templates", static_folder="static")

# Routes
@app.route("/")
def index():
    return render_template("index.html")



@app.route("/api/entries", methods=["GET"])
def api_list():
    q = request.args.get("q","")
    if q:
        results = ledger.search(q)
    else:
        results = ledger.list_all()
    return jsonify([e.to_dict() for e in results])

@app.route("/api/entries/<entry_id>", methods=["GET"])
def api_get(entry_id):
    for e in ledger.entries:
        if e.id == entry_id:
            return jsonify(e.to_dict())
    return ("Not found", 404)

@app.route("/api/entries", methods=["POST"])
def api_create():
    data = request.get_json(force=True)
    required = ["title","amount","category","kind"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"Missing field {r}"}), 400
    entry = Entry(
        title=data["title"],
        amount=data["amount"],
        category=data["category"],
        kind=data["kind"],
        note=data.get("note",""),
        date=data.get("date", None)
    )
    ledger.add(entry)
    return jsonify(entry.to_dict()), 201

@app.route("/api/entries/<entry_id>", methods=["PUT"])
def api_update(entry_id):
    data = request.get_json(force=True)
    e = ledger.update(entry_id,
                      title=data.get("title"),
                      amount=data.get("amount"),
                      category=data.get("category"),
                      kind=data.get("kind"),
                      note=data.get("note"),
                      date=data.get("date"))
    if e:
        return jsonify(e.to_dict())
    else:
        return ("Not found", 404)

@app.route("/api/entries/<entry_id>", methods=["DELETE"])
def api_delete(entry_id):
    ok = ledger.delete(entry_id)
    if ok:
        return ("",204)
    else:
        return ("Not found", 404)

@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(ledger.total_balance())

@app.route("/api/export", methods=["GET"])
def api_export():
    path = ledger.export_csv()
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
