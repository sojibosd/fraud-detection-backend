from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
import random

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_risk_level(score):
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE,
            fraud_score REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            txn_id TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            amount REAL NOT NULL,
            fraud_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()

    cursor.execute("SELECT COUNT(*) as cnt FROM accounts")
    count = cursor.fetchone()["cnt"]

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
            "INSERT INTO accounts (account_id, fraud_score) VALUES (%s, %s)",
            sample_data,
        )
        conn.commit()
        print(f"[INFO] {len(sample_data)} ta sample account database e add kora holo.")

    cursor.close()
    conn.close()


@app.route("/accounts", methods=["GET"])
def get_accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, fraud_score FROM accounts")
    rows = cursor.fetchall()
    cursor.close()
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
    data = request.get_json()

    if not data or "account_id" not in data or "fraud_score" not in data:
        return jsonify({"error": "account_id o fraud_score dorkar"}), 400

    account_id = data["account_id"]
    fraud_score = float(data["fraud_score"])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (account_id, fraud_score) VALUES (%s, %s)",
            (account_id, fraud_score),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": f"'{account_id}' age theke ache"}), 409

    cursor.close()
    conn.close()
    return jsonify({
        "message": "Account jog kora hoyeche",
        "account_id": account_id,
        "fraud_score": fraud_score,
        "risk_level": get_risk_level(fraud_score),
    }), 201


@app.route("/accounts/<account_id>", methods=["PUT"])
def update_account(account_id):
    data = request.get_json()

    if not data or "fraud_score" not in data:
        return jsonify({"error": "fraud_score dorkar"}), 400

    fraud_score = float(data["fraud_score"])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE accounts SET fraud_score = %s WHERE account_id = %s",
        (fraud_score, account_id),
    )
    conn.commit()
    updated_count = cursor.rowcount
    cursor.close()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE account_id = %s", (account_id,))
    conn.commit()
    deleted_count = cursor.rowcount
    cursor.close()
    conn.close()

    if deleted_count == 0:
        return jsonify({"error": f"'{account_id}' pawa jay nai"}), 404

    return jsonify({"message": f"'{account_id}' delete kora hoyeche"})


@app.route("/transactions", methods=["GET"])
def get_transactions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT txn_id, account_id, amount, fraud_score, risk_level, created_at
        FROM transactions
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "txn_id": row["txn_id"],
            "account_id": row["account_id"],
            "amount": row["amount"],
            "fraud_score": row["fraud_score"],
            "risk_level": row["risk_level"],
            "created_at": str(row["created_at"]),
        })

    return jsonify({"transactions": transactions})


@app.route("/transactions", methods=["POST"])
def add_transaction():
    data = request.get_json()

    if not data or "account_id" not in data or "amount" not in data:
        return jsonify({"error": "account_id o amount dorkar"}), 400

    account_id = data["account_id"]
    amount = float(data["amount"])

    if amount <= 0:
        return jsonify({"error": "amount 0 er beshi hote hobe"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE account_id = %s", (account_id,))
    account = cursor.fetchone()

    if not account:
        cursor.close()
        conn.close()
        return jsonify({"error": f"'{account_id}' account pawa jay nai"}), 404

    base_score = min(amount / 100000, 0.6)
    account_score = account["fraud_score"] * 0.4
    fraud_score = round(min(base_score + account_score, 0.99), 2)
    risk_level = get_risk_level(fraud_score)

    txn_id = f"TXN-{random.randint(100000, 999999)}"

    cursor.execute(
        """
        INSERT INTO transactions
        (txn_id, account_id, amount, fraud_score, risk_level)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (txn_id, account_id, amount, fraud_score, risk_level),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "message": "Transaction save holo",
        "txn_id": txn_id,
        "account_id": account_id,
        "amount": amount,
        "fraud_score": fraud_score,
        "risk_level": risk_level,
        "decision": "BLOCK" if risk_level == "HIGH" else ("REVIEW" if risk_level == "MEDIUM" else "APPROVED"),
    }), 201


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Fraud Detection API is running. Try /accounts or /transactions"
    })


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
