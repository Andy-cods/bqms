-- Song Chau ERP Database Schema
-- Based on SuperMap v3 Architecture

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enums
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'procurement', 'warehouse', 'staff');
CREATE TYPE po_status AS ENUM ('draft', 'pending', 'approved', 'confirmed', 'in_transit', 'received', 'closed', 'cancelled');
CREATE TYPE wf_state AS ENUM ('draft', 'pending_l1', 'pending_l2', 'approved', 'rejected', 'in_progress', 'completed');
CREATE TYPE rfq_status AS ENUM ('draft', 'sent', 'receiving', 'comparing', 'selected', 'closed');

-- ============================================
-- CORE TABLES
-- ============================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'staff',
    department TEXT,
    hashed_pw TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE suppliers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE,
    contact_email TEXT,
    contact_phone TEXT,
    country TEXT DEFAULT 'VN',
    payment_terms TEXT,
    rating NUMERIC(3,1) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    bqms_code TEXT UNIQUE,
    product_name TEXT NOT NULL,
    spec TEXT,
    maker TEXT,
    category TEXT,
    unit TEXT DEFAULT 'EA',
    type TEXT CHECK(type IN ('gc', 'tm')),
    min_stock NUMERIC DEFAULT 0,
    current_stock NUMERIC DEFAULT 0,
    location TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TRANSACTION TABLES (from TT XNK BQMS Excel)
-- ============================================

CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_date DATE,
    rfq_no TEXT,
    bqms_code TEXT,
    spec TEXT,
    maker TEXT,
    quantity NUMERIC,
    unit TEXT DEFAULT 'EA',
    price_rmb NUMERIC(15,2),
    price_vnd NUMERIC(15,2),
    price_quoted NUMERIC(15,2),
    version TEXT,
    result TEXT,
    person_in_charge TEXT,
    customer TEXT DEFAULT 'Samsung',
    notes TEXT,
    source_file TEXT,
    source_sheet TEXT,
    source_row INTEGER,
    row_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- PURCHASE ORDER TABLES
-- ============================================

CREATE TABLE purchase_orders (
    id BIGSERIAL PRIMARY KEY,
    po_number TEXT UNIQUE NOT NULL,
    supplier_id BIGINT REFERENCES suppliers(id),
    total_amount NUMERIC(15,2),
    currency TEXT DEFAULT 'VND',
    status po_status DEFAULT 'draft',
    eta_date DATE,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    attachment_path TEXT,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE po_line_items (
    id BIGSERIAL PRIMARY KEY,
    po_id BIGINT REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id),
    bqms_code TEXT,
    spec TEXT,
    quantity NUMERIC NOT NULL,
    unit_price NUMERIC(15,2),
    total_price NUMERIC(15,2),
    notes TEXT
);

-- ============================================
-- RFQ TABLES
-- ============================================

CREATE TABLE rfq (
    id BIGSERIAL PRIMARY KEY,
    rfq_no TEXT UNIQUE NOT NULL,
    status rfq_status DEFAULT 'draft',
    deadline TIMESTAMPTZ,
    person_in_charge TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE rfq_items (
    id BIGSERIAL PRIMARY KEY,
    rfq_id BIGINT REFERENCES rfq(id) ON DELETE CASCADE,
    bqms_code TEXT,
    spec TEXT,
    maker TEXT,
    quantity NUMERIC,
    unit TEXT DEFAULT 'EA',
    price_v1 NUMERIC(15,2),
    price_v2 NUMERIC(15,2),
    price_v3 NUMERIC(15,2),
    price_v4 NUMERIC(15,2),
    result TEXT,
    notes TEXT
);

-- ============================================
-- DELIVERY TRACKING
-- ============================================

CREATE TABLE deliveries (
    id BIGSERIAL PRIMARY KEY,
    po_id BIGINT REFERENCES purchase_orders(id),
    po_number TEXT,
    delivery_date DATE,
    received_date DATE,
    quantity_expected NUMERIC,
    quantity_received NUMERIC,
    status TEXT DEFAULT 'waiting',
    receiver TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- MONTHLY REPORTS (from BC BQMS files)
-- ============================================

CREATE TABLE monthly_reports (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    report_date DATE,
    bqms_code TEXT,
    spec TEXT,
    maker TEXT,
    quantity NUMERIC,
    unit TEXT,
    price NUMERIC(15,2),
    currency TEXT DEFAULT 'VND',
    person_in_charge TEXT,
    source_file TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(year, month, bqms_code, spec)
);

-- ============================================
-- MARKET SEARCH (Tool 5 data)
-- ============================================

CREATE TABLE market_prices (
    id BIGSERIAL PRIMARY KEY,
    bqms_code TEXT,
    product_name TEXT NOT NULL,
    spec TEXT,
    maker TEXT,
    platform TEXT,
    supplier_name TEXT,
    supplier_url TEXT,
    price NUMERIC(15,4),
    currency TEXT DEFAULT 'USD',
    price_usd NUMERIC(15,4),
    moq INTEGER,
    rating NUMERIC(3,1),
    certifications TEXT,
    match_confidence NUMERIC(3,2),
    search_query TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    confirmed_by UUID REFERENCES users(id),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- AUDIT LOG
-- ============================================

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    table_name TEXT,
    record_id TEXT,
    old_data JSONB,
    new_data JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- FILE METADATA (for document indexing)
-- ============================================

CREATE TABLE file_metadata (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    file_size BIGINT,
    category TEXT,
    linked_po TEXT,
    linked_rfq TEXT,
    linked_bqms_code TEXT,
    checksum TEXT,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ETL JOB LOG
-- ============================================

CREATE TABLE etl_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_type TEXT NOT NULL,
    source_file TEXT,
    status TEXT DEFAULT 'running',
    rows_processed INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    errors TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- ============================================
-- INDEXES
-- ============================================

-- Transactions
CREATE INDEX idx_tx_date ON transactions(transaction_date DESC);
CREATE INDEX idx_tx_rfq ON transactions(rfq_no);
CREATE INDEX idx_tx_bqms ON transactions(bqms_code);
CREATE INDEX idx_tx_hash ON transactions(row_hash);

-- Products
CREATE INDEX idx_prod_name_trgm ON products USING GIN(product_name gin_trgm_ops);
CREATE INDEX idx_prod_spec_trgm ON products USING GIN(spec gin_trgm_ops);
CREATE INDEX idx_prod_maker ON products(maker);
CREATE INDEX idx_prod_type ON products(type);

-- PO
CREATE INDEX idx_po_status ON purchase_orders(status);
CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_po_date ON purchase_orders(created_at DESC);

-- RFQ
CREATE INDEX idx_rfq_status ON rfq(status);
CREATE INDEX idx_rfq_date ON rfq(created_at DESC);

-- Deliveries
CREATE INDEX idx_del_po ON deliveries(po_id);
CREATE INDEX idx_del_date ON deliveries(delivery_date DESC);

-- Market prices
CREATE INDEX idx_mp_bqms ON market_prices(bqms_code);
CREATE INDEX idx_mp_platform ON market_prices(platform);

-- Audit
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_date ON audit_log(created_at DESC);
CREATE INDEX idx_audit_table ON audit_log(table_name);

-- Files
CREATE INDEX idx_file_category ON file_metadata(category);
CREATE INDEX idx_file_po ON file_metadata(linked_po);
CREATE INDEX idx_file_rfq ON file_metadata(linked_rfq);

-- ============================================
-- DEFAULT ADMIN USER (password: admin123 - CHANGE IMMEDIATELY)
-- ============================================

INSERT INTO users (email, full_name, role, hashed_pw)
VALUES ('admin@songchau.vn', 'Admin', 'admin',
        '$2b$12$LJ3m4ys5NY4RzN.O8sFJauPGDXy9xkVn9HnGkPQr8H0kbR6HVUUOC');

-- Grant
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO scadmin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO scadmin;
