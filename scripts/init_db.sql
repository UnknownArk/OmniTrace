-- OmniTrace v2 Enterprise Incident Triage Database Schema
-- Provides single-store ACID-compliant relational telemetry and PGVector hybrid retrieval.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Unstructured Context: SRE Incident Runbooks & Postmortems
CREATE TABLE IF NOT EXISTS runbooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    severity_level VARCHAR(20) NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fast Approximate Nearest Neighbor Index (HNSW) for sub-10ms vector similarity
CREATE INDEX IF NOT EXISTS idx_runbooks_embedding_hnsw 
ON runbooks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Structured System Telemetry Logs (Relational)
CREATE TABLE IF NOT EXISTS service_telemetry_logs (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    status_code INT NOT NULL,
    latency_ms NUMERIC(8, 2) NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_service_time 
ON service_telemetry_logs(service_name, timestamp DESC);
