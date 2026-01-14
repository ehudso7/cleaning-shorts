"""
Database schema for Cleaning Shorts app.
Designed for Supabase (Postgres) with Row Level Security.

Tables:
- users: Core user data + subscription status
- profiles: Service type + timezone preferences
- content_templates: Pre-generated scripts (600+)
- daily_deliveries: Tracks what was sent to prevent duplicates

Key design decisions:
1. No AI at runtime - all content is pre-generated
2. One delivery per user per day
3. Never repeat content for the same user
4. Self-serve subscription management via Stripe
"""

SCHEMA_SQL = """
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
-- Minimal: just auth + subscription status
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    subscription_status TEXT DEFAULT 'trialing' CHECK (
        subscription_status IN ('active', 'canceled', 'past_due', 'trialing')
    ),
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    subscription_started_at TIMESTAMPTZ,
    subscription_ends_at TIMESTAMPTZ,
    refund_used BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ
);

-- User profiles
-- Service type + timezone only - no bloat
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    service_type TEXT DEFAULT 'deep_clean' CHECK (
        service_type IN ('deep_clean', 'airbnb', 'move_out')
    ),
    timezone TEXT DEFAULT 'America/New_York',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content templates
-- Pre-generated content library - the core asset
-- No AI at runtime = no hallucinations = no support tickets
CREATE TABLE IF NOT EXISTS content_templates (
    id SERIAL PRIMARY KEY,
    service_type TEXT NOT NULL CHECK (
        service_type IN ('deep_clean', 'airbnb', 'move_out')
    ),
    script TEXT NOT NULL,
    caption TEXT NOT NULL CHECK (char_length(caption) <= 180),
    cta TEXT DEFAULT 'DM ''CLEAN'' for pricing & availability.',
    category TEXT, -- before_after, process, pricing, objections, trust, urgency
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Daily deliveries
-- Tracks what content was sent to each user each day
-- Prevents duplicates, enables rotation through entire library
CREATE TABLE IF NOT EXISTS daily_deliveries (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    template_id INTEGER REFERENCES content_templates(id) NOT NULL,
    delivered_at TIMESTAMPTZ DEFAULT NOW(),
    delivery_date DATE NOT NULL, -- Calendar date in user's timezone

    -- One delivery per user per day
    UNIQUE(user_id, delivery_date)
);

-- Refund log (for audit trail)
CREATE TABLE IF NOT EXISTS refund_log (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    stripe_refund_id TEXT,
    amount_cents INTEGER,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security (RLS) policies
-- Users can only access their own data

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_deliveries ENABLE ROW LEVEL SECURITY;

-- Users can read their own record
CREATE POLICY users_select_own ON users
    FOR SELECT USING (auth.uid() = id);

-- Users can update limited fields on their own record
CREATE POLICY users_update_own ON users
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Profiles: users can read/update their own
CREATE POLICY profiles_select_own ON profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY profiles_update_own ON profiles
    FOR UPDATE USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY profiles_insert_own ON profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Daily deliveries: users can only read their own
CREATE POLICY deliveries_select_own ON daily_deliveries
    FOR SELECT USING (auth.uid() = user_id);

-- Content templates: readable by all authenticated users
ALTER TABLE content_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY templates_select_active ON content_templates
    FOR SELECT USING (is_active = TRUE);
"""

INDEXES_SQL = """
-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_users_subscription_status ON users(subscription_status);

CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_service_type ON profiles(service_type);

CREATE INDEX IF NOT EXISTS idx_templates_service_type ON content_templates(service_type);
CREATE INDEX IF NOT EXISTS idx_templates_active ON content_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_templates_category ON content_templates(category);

CREATE INDEX IF NOT EXISTS idx_deliveries_user ON daily_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_date ON daily_deliveries(delivery_date);
CREATE INDEX IF NOT EXISTS idx_deliveries_user_date ON daily_deliveries(user_id, delivery_date);
CREATE INDEX IF NOT EXISTS idx_deliveries_template ON daily_deliveries(template_id);
"""

# Function to get next unused template for a user
GET_NEXT_TEMPLATE_SQL = """
-- Get the next unused template for a user's service type
-- Returns a random template they haven't received yet
SELECT ct.* FROM content_templates ct
WHERE ct.service_type = $1
  AND ct.is_active = TRUE
  AND ct.id NOT IN (
      SELECT template_id FROM daily_deliveries WHERE user_id = $2
  )
ORDER BY RANDOM()
LIMIT 1;
"""

# Function to check and reset if user has seen all templates
CHECK_TEMPLATE_RESET_SQL = """
-- Count remaining unseen templates for this user/service
SELECT COUNT(*) as remaining
FROM content_templates ct
WHERE ct.service_type = $1
  AND ct.is_active = TRUE
  AND ct.id NOT IN (
      SELECT template_id FROM daily_deliveries WHERE user_id = $2
  );
"""
