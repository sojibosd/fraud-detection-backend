from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)  # eta na dile Flutter Web theke request block hoye jabe (CORS error)

DB_NAME = "fraud_detection.db"


def get_risk_level(score):
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


def init_db():
    """
    Ei function database file (fraud_detection.db) toiri kore
    ebong 'accounts' table banay jodi age theke na thake.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL UNIQUE,
            fraud_score REAL NOT NULL
        )
    """)
    conn.commit()

    # Table ta jodi khali thake (prothom bar run), tahole kichu sample data dhukiye dao
    cursor.execute("SELECT COUNT(*) FROM accounts")
    count = cursor.fetchone()[0]

    if count == 0:
        sample_data = [
            ("ACC-1001", 0.92),
            ("ACC-1002", 0.15),
            ("ACC-1003", 0.55),
            ("ACC-1004", 0.08),
            ("ACC-1005", 0.78),
            ("ACC-1006", 0.33),
            ("ACC-1007", 0.61),
            ("ACC-1008", 0.05),
        ]
        cursor.executemany(
            "INSERT INTO accounts (account_id, fraud_score) VALUES (?, ?)",
            sample_data,
        )
        conn.commit()
        print(f"[INFO] {len(sample_data)} ta sample account database e add kora holo.")

    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # eta dile row gulo dict er moto access kora jabe
    return conn


@app.route("/accounts", methods=["GET"])
def get_accounts():
    """
    Shob account database theke niye JSON banaye pathay.
    """
    conn = get_db_connection()
    rows = conn.execute("SELECT account_id, fraud_score FROM accounts").fetchall()
    conn.close()

    accounts = []
    for row in rows:
        accounts.append({
            "account_id": row["account_id"],
            "fraud_score": row["fraud_score"],
            "risk_level": get_risk_level(row["fraud_score"]),
        })

    return jsonify({"accounts": accounts})


@app.route("/accounts", methods=["POST"])
def add_account():
    """
    Notun account database e add korar jonne.
    Body te ei rokom JSON pathate hobe:
    { "account_id": "ACC-2001", "fraud_score": 0.45 }
    """
    data = request.get_json()

    if not data or "account_id" not in data or "fraud_score" not in data:
        return jsonify({"error": "account_id o fraud_score dorkar"}), 400

    account_id = data["account_id"]
    fraud_score = float(data["fraud_score"])

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO accounts (account_id, fraud_score) VALUES (?, ?)",
            (account_id, fraud_score),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"'{account_id}' age theke ache"}), 409

    conn.close()
    return jsonify({
        "message": "Account jog kora hoyeche",
        "account_id": account_id,
        "fraud_score": fraud_score,
        "risk_level": get_risk_level(fraud_score),
    }), 201


@app.route("/accounts/<account_id>", methods=["PUT"])
def update_account(account_id):
    """
    Ekta existing account er fraud score update korar jonne.
    Body te ei rokom JSON pathate hobe:
    { "fraud_score": 0.65 }
    Example: PUT http://localhost:5000/accounts/ACC-1001
    """
    data = request.get_json()

    if not data or "fraud_score" not in data:
        return jsonify({"error": "fraud_score dorkar"}), 400

    fraud_score = float(data["fraud_score"])

    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE accounts SET fraud_score = ? WHERE account_id = ?",
        (fraud_score, account_id),
    )
    conn.commit()
    updated_count = cursor.rowcount
    conn.close()

    if updated_count == 0:
        return jsonify({"error": f"'{account_id}' pawa jay nai"}), 404

    return jsonify({
        "message": f"'{account_id}' update kora hoyeche",
        "account_id": account_id,
        "fraud_score": fraud_score,
        "risk_level": get_risk_level(fraud_score),
    })


@app.route("/accounts/<account_id>", methods=["DELETE"])
def delete_account(account_id):
    """
    Kono account delete korar jonne (URL e account_id disi).
    Example: DELETE http://localhost:5000/accounts/ACC-1001
    """
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
    conn.commit()
    deleted_count = cursor.rowcount
    conn.close()

    if deleted_count == 0:
        return jsonify({"error": f"'{account_id}' pawa jay nai"}), 404

    return jsonify({"message": f"'{account_id}' delete kora hoyeche"})


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Fraud Detection API is running (SQLite database use hocche). Try /accounts"})


# init_db() ke module level e call kora hocche, jate 'python app.py' die
# local e chalale, ebong 'gunicorn app:app' die deploy kore chalale -
# dutokhetreই database toiri hoy. Age eta shudhu __main__ block e chilo,
# tai gunicorn e run korle eta kokhono call hoto na.
init_db()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Render/hosting service PORT env var use kore
    app.run(host="0.0.0.0", port=port, debug=False)
