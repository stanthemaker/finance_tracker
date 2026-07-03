import sys
sys.path.insert(0, ".")
from database import get_conn
from categorizer import categorize, infer_tx_type

with get_conn() as conn:
    rows = conn.execute(
        "SELECT t.id, t.description, t.amount, t.tx_type, t.category, t.is_override, "
        "s.account_type FROM transactions t JOIN statements s ON t.statement_id = s.id "
        "WHERE t.is_override = 0"
    ).fetchall()

    updates = []
    cat_changes = {}
    type_changes = {}

    for row in rows:
        new_type = infer_tx_type(row["description"], row["amount"], row["account_type"])
        # "payment" is an import-only skip sentinel and never a stored type;
        # keep the existing type if it ever surfaces here.
        if new_type == "payment":
            new_type = row["tx_type"]
        new_cat  = categorize(row["description"], new_type)

        if new_cat != row["category"] or new_type != row["tx_type"]:
            updates.append((new_cat, new_type, row["id"]))
            if new_cat != row["category"]:
                key = f"{row['category']} -> {new_cat}"
                cat_changes[key] = cat_changes.get(key, 0) + 1
            if new_type != row["tx_type"]:
                key = f"{row['tx_type']} -> {new_type}"
                type_changes[key] = type_changes.get(key, 0) + 1

    if updates:
        conn.executemany(
            "UPDATE transactions SET category=?, tx_type=? WHERE id=?", updates
        )

    print(f"Updated {len(updates)} / {len(rows)} transactions")
    print("\nCategory changes:")
    for k, v in sorted(cat_changes.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    print("\nType changes:")
    for k, v in sorted(type_changes.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
