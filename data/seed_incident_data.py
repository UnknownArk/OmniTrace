import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "telemetry.db"
RUNBOOKS_DIR = DATA_DIR / "sample_runbooks"

def seed_telemetry_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS service_telemetry_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_name TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        latency_ms REAL NOT NULL,
        error_message TEXT,
        timestamp TEXT NOT NULL
    );
    """)

    logs = [
        # Normal checkout baseline
        ("checkout-service", "/api/v1/checkout/pay", 200, 115.4, None, "2026-11-10T14:00:00Z"),
        ("checkout-service", "/api/v1/checkout/pay", 200, 98.2, None, "2026-11-10T14:01:00Z"),
        # Spiking Incident: Checkout 504 Gateway Timeout
        ("checkout-service", "/api/v1/checkout/pay", 504, 5020.1, "Upstream payment-gateway timed out after 5000ms", "2026-11-10T14:05:12Z"),
        ("checkout-service", "/api/v1/checkout/pay", 504, 5015.8, "Upstream payment-gateway timed out after 5000ms", "2026-11-10T14:05:30Z"),
        ("checkout-service", "/api/v1/checkout/pay", 504, 5040.0, "Upstream payment-gateway timed out after 5000ms", "2026-11-10T14:06:05Z"),
        ("checkout-service", "/api/v1/checkout/pay", 504, 5010.4, "Upstream payment-gateway timed out after 5000ms", "2026-11-10T14:06:45Z"),
        ("checkout-service", "/api/v1/checkout/pay", 200, 140.2, None, "2026-11-10T14:07:00Z"),
        
        # Payment Gateway telemetry
        ("payment-gateway", "/charge", 504, 4998.2, "Bank acquirer connection reset by peer", "2026-11-10T14:05:10Z"),
        ("payment-gateway", "/charge", 504, 5001.0, "Bank acquirer connection reset by peer", "2026-11-10T14:05:25Z"),
        ("payment-gateway", "/charge", 200, 210.0, None, "2026-11-10T14:07:05Z"),

        # Auth Service Incident: Redis connection pool exhaustion
        ("auth-service", "/api/v1/auth/token", 500, 1850.5, "RedisConnectionError: Connection pool exhausted (max 100 connections)", "2026-11-10T14:10:00Z"),
        ("auth-service", "/api/v1/auth/token", 500, 1920.0, "RedisConnectionError: Connection pool exhausted (max 100 connections)", "2026-11-10T14:10:15Z"),
        ("auth-service", "/api/v1/auth/token", 200, 45.0, None, "2026-11-10T14:12:00Z"),

        # Inventory baseline
        ("inventory-service", "/api/v1/items/stock", 200, 32.5, None, "2026-11-10T14:05:00Z"),
        ("inventory-service", "/api/v1/items/stock", 200, 28.1, None, "2026-11-10T14:06:00Z")
    ]

    cur.executemany("""
    INSERT INTO service_telemetry_logs (service_name, endpoint, status_code, latency_ms, error_message, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, logs)

    conn.commit()
    conn.close()

def seed_runbooks():
    RUNBOOKS_DIR.mkdir(parents=True, exist_ok=True)

    runbooks = [
        {
            "id": "rb-chk-504",
            "service_name": "checkout-service",
            "title": "Checkout Service 504 Gateway Timeout Runbook",
            "severity_level": "P1-CRITICAL",
            "content": (
                "SYMPTOMS: Checkout-service throws 504 Gateway Timeout on /api/v1/checkout/pay. "
                "P99 latency spikes above 5000ms.\n"
                "ROOT CAUSE: Upstream payment-gateway service or banking partner acquirer connection is failing to acknowledge requests.\n"
                "DIAGNOSIS: Check service_telemetry_logs for payment-gateway error messages and bank partner response times.\n"
                "REMEDIATION: Trigger circuit breaker trip to fallback provider via: "
                "`kubectl exec -it deployment/checkout-service -- /scripts/trip_circuit_breaker.sh --provider=stripe_fallback`. "
                "Notify financial operations team immediately."
            ),
            "keywords": ["checkout", "504", "gateway timeout", "payment", "p99", "acquirer", "circuit breaker"]
        },
        {
            "id": "rb-auth-500",
            "service_name": "auth-service",
            "title": "Auth Service Redis Connection Pool Exhaustion",
            "severity_level": "P2-HIGH",
            "content": (
                "SYMPTOMS: Auth service returns 500 Internal Server Error on /api/v1/auth/token. "
                "Error logs indicate 'RedisConnectionError: Connection pool exhausted'.\n"
                "ROOT CAUSE: Session token validation leaks connections under sudden traffic bursts without releasing pool sockets.\n"
                "DIAGNOSIS: Inspect telemetry logs for Redis connection error messages and peak connection counts.\n"
                "REMEDIATION: Purge idle Redis socket pool and restart deployment pods via: "
                "`kubectl rollout restart deployment/auth-service -n production`. "
                "Scale connection pool ceiling in ConfigMap if traffic volume is sustained."
            ),
            "keywords": ["auth", "redis", "connection pool", "500", "token", "rollout restart"]
        },
        {
            "id": "rb-gen-p99",
            "service_name": "payment-gateway",
            "title": "Payment Gateway P99 Latency & Connection Reset Runbook",
            "severity_level": "P1-CRITICAL",
            "content": (
                "SYMPTOMS: Payment gateway /charge latency exceeding 4000ms with connection resets.\n"
                "ROOT CAUSE: Primary banking acquirer socket hang or rate-limiting.\n"
                "DIAGNOSIS: Verify if downstream status_code 504 is isolated to primary acquirer.\n"
                "REMEDIATION: Execute emergency traffic switch to secondary banking tunnel: "
                "`kubectl set env deployment/payment-gateway ACQUIRER_ROUTE=secondary`."
            ),
            "keywords": ["payment-gateway", "acquirer", "connection reset", "p99", "latency"]
        }
    ]

    out_file = RUNBOOKS_DIR / "runbooks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(runbooks, f, indent=2)

if __name__ == "__main__":
    seed_telemetry_database()
    seed_runbooks()
    print("SRE telemetry database and runbooks successfully seeded.")
