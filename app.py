from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
import random

app = Flask(__name__)
CORS(app)  # eta na dile Flutter Web theke request block hoye jabe (CORS error)

# Supabase (PostgreSQL) er connection string. Eta Render e Environment
# Variable hishebe 'DATABASE_URL' naam e set kora thakbe - code er modhye
# shorashori password likhte hoy na, eta beshi nirapod.
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_risk_level(score):
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


def get_db_connection():
    """
    Supabase (PostgreSQL) database er shathe connection toiri kore.
    cursor_factory die row gulo dict er moto (row['account_id']) access
    kora jay, thik sqlite3.Row er moto e.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """
    'accounts' table toiri kore jodi age theke na thake. Table khali
    thakle (prothom bar), kichu sample data dhukiye deya hoy.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE,
            fraud_score REAL NOT NULL
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
    """
    Shob account database theke niye JSON banaye pathay.
    """
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
    """
    Ekta existing account er fraud score update korar jonne.
    Body te ei rokom JSON pathate hobe:
    { "fraud_score": 0.65 }
    """
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
    """
    Kono account delete korar jonne (URL e account_id disi).
    """
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


@app.route("/seed-demo-data", methods=["GET"])
def seed_demo_data():
    """
    500 ta random demo account database e add kore. 'ON CONFLICT DO
    NOTHING' die, age theke thaka account_id gulo automatic skip hoye
    jay - kono error hoy na.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM accounts")
    existing_count = cursor.fetchone()["cnt"]

    new_accounts = []
    start_number = 5000  # ACC-5000 theke shuru, jate age er account gulor shathe collision na hoy
    for i in range(500):
        account_id = f"ACC-{start_number + i}"
        fraud_score = round(random.uniform(0.02, 0.98), 2)
        new_accounts.append((account_id, fraud_score))

    cursor.executemany(
        "INSERT INTO accounts (account_id, fraud_score) VALUES (%s, %s) ON CONFLICT (account_id) DO NOTHING",
        new_accounts,
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) as cnt FROM accounts")
    new_total = cursor.fetchone()["cnt"]
    added_count = new_total - existing_count

    cursor.close()
    conn.close()

    return jsonify({
        "message": f"{added_count} ta notun demo account add kora hoyeche!",
        "accounts_before": existing_count,
        "accounts_added": added_count,
        "accounts_now_total": new_total,
    })


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Fraud Detection API is running (PostgreSQL/Supabase - sthayi database!). Try /accounts"
    })


# init_db() ke module level e call kora hocche, jate 'python app.py' die
# local e chalale, ebong 'gunicorn app:app' die deploy kore chalale -
# dutokhetreই database toiri hoy.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
