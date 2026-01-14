# Cleaning Shorts App Backend

Self-serve content generator for cleaning businesses. Delivers daily short-form video scripts with zero support overhead.

## Architecture

- **FastAPI** backend with Supabase (Postgres + Auth)
- **Stripe** for subscriptions ($9/mo or $79/yr)
- **Pre-generated templates** - no AI at runtime
- **Deterministic delivery** - one script per user per day

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your Supabase and Stripe credentials

# Set up database (outputs SQL to run in Supabase)
python scripts/setup_database.py

# Load content templates
python scripts/load_templates.py

# Run development server
uvicorn src.api.main:app --reload
```

## API Endpoints

### Content
- `GET /content/today` - Get today's content (requires subscription)
- `GET /content/stats` - Get delivery statistics

### Subscription
- `GET /subscription/status` - Current subscription status
- `POST /subscription/checkout` - Create checkout session
- `POST /subscription/cancel` - Cancel at period end
- `POST /subscription/refund` - Self-serve refund (7-day window)
- `GET /subscription/portal` - Stripe billing portal URL
- `GET /subscription/prices` - Available subscription prices

### User
- `GET /user/profile` - Get user profile
- `POST /user/onboard` - Set service type and timezone
- `PUT /user/service-type` - Update service type
- `PUT /user/timezone` - Update timezone

### Webhooks
- `POST /webhooks/stripe` - Stripe webhook handler

## Content Library

600 pre-generated templates:
- **200 deep_clean** - Residential deep cleaning
- **200 airbnb** - Airbnb/vacation rental turnovers
- **200 move_out** - Move-out/move-in cleans

Categories per service type:
- before_after
- process
- pricing
- objections
- trust
- social_proof
- education
- urgency
- faq
- simple

## Admin Scripts

```bash
# Database statistics
python scripts/admin.py stats

# List recent users
python scripts/admin.py users

# Template counts
python scripts/admin.py templates

# Deactivate/activate templates
python scripts/admin.py deactivate 123
python scripts/admin.py activate 123
```

## Design Principles

1. **No AI at runtime** - Pre-generated content eliminates hallucinations, unpredictability, and compute costs
2. **Deterministic delivery** - Same user + same day = same content (cached)
3. **No duplicates** - Users cycle through entire library before seeing repeats
4. **Self-serve everything** - Billing, cancellation, refunds - no support needed
5. **One refund per account** - Prevents abuse while honoring guarantees

## Environment Variables

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_MONTHLY=price_monthly_id
STRIPE_PRICE_YEARLY=price_yearly_id

APP_ENV=development
APP_SECRET_KEY=your-secret-key
REFUND_WINDOW_DAYS=7
```

## Testing

### Smoke Tests (No Database Required)

Run the smoke tests to validate templates and business logic:

```bash
# All smoke tests
python tests/test_a_templates.py      # Template counts + validation
python tests/test_b_determinism.py    # Deterministic delivery
python tests/test_c_timezone.py       # Timezone boundary handling
python tests/test_d_stripe.py         # Stripe subscription sync
```

### Content Inventory Gate (Requires Database)

The inventory gate validates that the `content_templates` table meets minimum requirements before deploys:

```bash
# Run with pytest (recommended)
pytest tests/test_content_inventory_gate.py -v

# Run standalone
python tests/test_content_inventory_gate.py
```

**Requirements:**
- PostgreSQL database with `content_templates` table
- `DATABASE_URL` environment variable set

**Default Thresholds:**
| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_TEMPLATES_TOTAL` | 450 | Minimum total active templates |
| `MIN_TEMPLATES_DEEP_CLEAN` | 150 | Minimum deep_clean templates |
| `MIN_TEMPLATES_AIRBNB` | 150 | Minimum airbnb templates |
| `MIN_TEMPLATES_MOVE_OUT` | 150 | Minimum move_out templates |
| `REQUIRED_CTA` | `DM 'CLEAN' for pricing & availability.` | Required CTA text |

**Override thresholds:**
```bash
# Lower thresholds for development
MIN_TEMPLATES_TOTAL=100 MIN_TEMPLATES_DEEP_CLEAN=30 \
  pytest tests/test_content_inventory_gate.py -v
```

**What it checks:**
1. Total template count meets minimum
2. Per-service-type counts meet minimums
3. No NULL values in required fields (script, caption, cta, service_type)
4. All CTAs match required format
5. All service_types are valid (deep_clean, airbnb, move_out)

### CI/CD

GitHub Actions runs both smoke tests and inventory gate on every push/PR:

```yaml
# .github/workflows/ci.yml
# - smoke-tests: Runs template validation (no DB)
# - inventory-gate: Runs DB tests with Postgres service container
# - all-tests: Requires both to pass before merge
```

## Deployment

This backend is designed for serverless deployment:
- Vercel (recommended)
- AWS Lambda
- Google Cloud Functions

The FastAPI app exports as `src.api.main:app`.
