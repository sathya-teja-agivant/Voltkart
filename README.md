# ⚡ VoltKart — AI-Powered Next-Gen Laptop Marketplace

VoltKart is a full-stack, enterprise-grade e-commerce application and intelligent AI shopping assistant tailored for laptop discovery, specification comparisons, and customer support. 

VoltKart pairs a modern, responsive React frontend with a high-performance FastAPI backend powered by PostgreSQL and Groq LLMs. The AI shopping assistant is engineered with strict grounding guardrails to eliminate hallucinations, ensuring every specification, price, and policy delivered to the customer is verified against the database.

---

## 🎬 Demo Video
Watch a quick walkthrough of VoltKart: [Demo Video](https://drive.google.com/file/d/1IbhZrMvK2WBThyqh_nq_HXZV93mbuCLi/view?usp=sharing)

---
##  Presentation
Understand a quick walkthrough of VoltKart: [Demo Presentation](https://docs.google.com/presentation/d/14xzo6pwmdEVW_YsRfpiFXSG5-b86j4S7/edit?usp=sharing&ouid=112291766809407717646&rtpof=true&sd=true)

---

## 🌟 Key Features

### 🛍️ Modern E-Commerce Catalog
- **Interactive Hardware Filtering**: Filter dynamically by brand (Dell, Apple, Lenovo, HP, ASUS, Acer), RAM (8GB, 16GB, 32GB+), price brackets (< ₹60k, ₹60k–₹1L, ₹1L+), and stock availability.
- **Dynamic Sorting**: Instant sorting by featured specs, price (low-to-high, high-to-low), highest RAM, or longest battery life.
- **Product Visuals & Fallbacks**: Dedicated product image previews with resilient fallback handling to prevent broken image displays.
- **Quick Specs Modal**: Detailed modal displaying processor, RAM, SSD, screen size, battery life, weight, operating system, and official manufacturer warranty.
- **Side-by-Side Comparison Dock**: Select up to 4 laptops to review specs in a side-by-side comparison matrix with one-click AI analysis.

### 🤖 Intelligent AI Shopping Assistant
- **Multi-Turn Context Memory**: Remembers previous queries and recommendations within the conversation session. Supports intuitive follow-up prompts such as *"Show me something lighter"*, *"Which one has better battery?"*, or *"Compare the first two"*.
- **Intent Recognition & Extraction**: Automatically extracts budget limits, minimum RAM, storage criteria, brand preferences, and intended usage (gaming, coding, student, office).
- **100% Grounded Responses**: The LLM is provided only verified database facts. Before any response is rendered to the user, a deterministic verification layer validates all prices and specs. If the LLM generates unverified details, a fallback response is used.
- **Deterministic Out-of-Scope Handling**: Questions about topics absent from store policies (e.g., custom EMI financing, unlisted discounts) deterministically return *"I don't have that information available in the system."*
- **Rich Interactive Payloads**: Chat responses return formatted text along with structured UI widgets (interactive product recommendation cards and specification comparison matrices).

### 🛡️ Admin & Store Operations
- **Role-Based Access Control (RBAC)**: Secure authentication utilizing JWT tokens and bcrypt password hashing with distinct `USER` and `ADMIN` roles.
- **Product Management**: Full CRUD operations for products, including hardware specs, stock status, pricing, and image URLs.
- **Policy Management & PDF Ingestion**: Create and edit store FAQs, or upload corporate policy PDFs (`POST /api/v1/admin/policies/upload-pdf`) which are automatically extracted, partitioned, and indexed for assistant retrieval.

---

## 🏗️ Architecture & Assistant Pipeline

VoltKart enforces a three-stage **Understand ➔ Retrieve ➔ Respond** architecture:

```mermaid
flowchart TD
    User([User Prompt]) --> ChatEndpoint[POST /api/v1/chat/message]
    ChatEndpoint --> UnderstandStep[1. UNDERSTAND]
    
    subgraph Understand [Stage 1: Intent & Filter Extraction]
        UnderstandStep --> GroqIntent[Groq LLM Intent Detection]
        GroqIntent --> SchemaValidate[Pydantic IntentResult Validation]
        SchemaValidate --> CodeFallback{Valid JSON?}
        CodeFallback -- No --> RuleParser[Rule-based Regex Parser]
        CodeFallback -- Yes --> ExtractedFilters[Extracted Criteria & Intent]
        RuleParser --> ExtractedFilters
    end
    
    ExtractedFilters --> RetrieveStep[2. RETRIEVE]
    
    subgraph Retrieve [Stage 2: Database Retrieval]
        RetrieveStep --> DBQuery[PostgreSQL Filter Query: In-Stock Only]
        DBQuery --> Ranker[Weighted Spec Ranking / Refinement]
        Ranker --> PolicySearch[Policy / FAQ Keyword Lookup]
    end
    
    Ranker --> RespondStep[3. RESPOND & VERIFY]
    PolicySearch --> RespondStep
    
    subgraph Respond [Stage 3: Grounded Generation & Guardrail]
        RespondStep --> GroqGrounded[Groq LLM Prompted with Verified Facts Only]
        GroqGrounded --> GuardrailCheck{Facts Grounded?}
        GuardrailCheck -- Yes --> VerifiedOutput[Grounded Text Response]
        GuardrailCheck -- Invalidation Detected --> DeterministicFallback[Deterministic Code-Generated Response]
    end
    
    VerifiedOutput --> PayloadBuilder[Bundle Response + Product Cards + Comparison Matrix]
    DeterministicFallback --> PayloadBuilder
    PayloadBuilder --> ReactUI([React Chat UI & Catalog])
```

---

## 💻 Tech Stack

### Frontend
- **Framework**: [React 18](https://react.dev/) with [Vite](https://vitejs.dev/)
- **Icons**: [Lucide React](https://lucide.dev/)
- **HTTP Client**: [Axios](https://axios-http.com/) (configured with bearer token authentication interceptors)
- **Styling**: Custom modern SaaS design system with CSS variables, fluid responsive layouts, glassmorphic accents, and micro-animations.

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **ORM & Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with [psycopg3](https://www.psycopg.org/) & [PostgreSQL](https://www.postgresql.org/) (hosted on [Neon Serverless Postgres](https://neon.tech/))
- **LLM Engine**: [Groq Cloud SDK](https://groq.com/) (leveraging `llama-3.3-70b-versatile` / `openai/gpt-oss-120b`)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/) with `pydantic-settings`
- **Security & Auth**: [PyJWT](https://pyjwt.readthedocs.io/) and [bcrypt](https://pypi.org/project/bcrypt/)
- **PDF Extraction**: [pypdf](https://pypdf.readthedocs.io/) for document parsing and policy ingestion

---

## 📁 Repository Structure

```text
VoltKart_MVP/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py         # App configuration & environment loader
│   │   │   ├── deps.py           # Dependency injection (DB session, JWT auth)
│   │   │   └── security.py       # Password hashing & JWT token generation
│   │   ├── database/
│   │   │   ├── base.py           # Declarative base
│   │   │   └── connection.py     # SQLAlchemy engine & session pool
│   │   ├── models/
│   │   │   ├── product.py        # Product table schema
│   │   │   ├── policy.py         # Policy / FAQ table schema
│   │   │   ├── user.py           # User & Admin account schema
│   │   │   ├── conversation.py   # Chat conversation sessions
│   │   │   ├── message.py        # Chat messages with persistent UI payloads
│   │   │   └── conversation_context.py # Tracked memory & prior recommendation IDs
│   │   ├── routers/
│   │   │   ├── auth.py           # User registration, login, and current profile
│   │   │   ├── products.py       # Public product catalog queries & details
│   │   │   ├── chat.py           # Real-time conversational assistant endpoint
│   │   │   ├── conversations.py  # Session history & message management
│   │   │   └── admin.py          # Admin product/policy CRUD & PDF ingest
│   │   ├── services/
│   │   │   ├── assistant.py      # Core AI pipeline: Intent parsing, retrieval, grounding
│   │   │   └── pdf_ingest.py     # PDF parsing & chunked policy indexing
│   │   ├── schemas.py            # Pydantic schemas for request & response models
│   │   └── main.py               # FastAPI application entrypoint & CORS setup
│   ├── seed.py                   # Database seeder (25 laptop models + 12 policy FAQs)
│   ├── requirements.txt          # Python dependencies
│   └── .env                      # Environment secrets
│
└── frontend/
    ├── src/
    │   ├── assets/               # Logos and static media
    │   ├── App.jsx               # Main application routing & auth gating
    │   ├── ProductsPage.jsx      # Interactive laptop catalog, filter bar & compare dock
    │   ├── ChatWidget.jsx        # Floating / expandable AI assistant widget
    │   ├── Admin.jsx             # Admin dashboard (Product CRUD, Policies & PDF upload)
    │   ├── Login.jsx             # Login & Registration authentication modal
    │   ├── auth.jsx              # React Auth context & token persistence
    │   ├── api.js                # Axios HTTP client configuration
    │   └── style.css             # Complete SaaS design system
    ├── package.json              # NPM dependencies & build scripts
    └── vite.config.js            # Vite bundler configuration
```

---

## 🚀 Getting Started

### Prerequisites
- **Python**: Version 3.10, 3.11, or 3.12+
- **Node.js**: Version 18.x or 20.x+ (with `npm`)
- **PostgreSQL Database**: Local PostgreSQL instance or a free cloud instance on [Neon.tech](https://neon.tech/)
- **Groq API Key**: Obtain a free API key from the [Groq Console](https://console.groq.com/)

---

### 1. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd VoltKart_MVP/backend
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a `.env` file in `VoltKart_MVP/backend/` with the following variables:
   ```env
   # PostgreSQL Connection String (psycopg3 driver)
   DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require

   # Groq Cloud AI
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=openai/gpt-oss-120b

   # JWT Authentication
   JWT_SECRET=your_super_secret_jwt_key_minimum_32_characters
   JWT_EXPIRE_MINUTES=480

   # Initial Bootstrap Admin
   ADMIN_EMAIL=admin@voltkart.com
   ADMIN_PASSWORD=YourSecurePassword123!
   ```

5. **Seed the Database**:
   Populate the database with the initial 25 laptop products, store policies, and bootstrap the administrator account:
   ```bash
   python seed.py
   ```

6. **Start the FastAPI Backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   * Interactive API Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   * Alternative ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 2. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd VoltKart_MVP/frontend
   ```

2. **Install node dependencies**:
   ```bash
   npm install
   ```

3. **Run the Development Server**:
   ```bash
   npm run dev
   ```
   * Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 📡 API Endpoints Reference

### 🔐 Authentication (`/api/v1/auth`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user | Public |
| `POST` | `/api/v1/auth/login` | Login and obtain JWT access token | Public |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile & role | Authenticated |

### 💻 Products (`/api/v1/products`)
| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/api/v1/products` | `brand`, `max_price`, `min_ram` | List all laptops matching filters |
| `GET` | `/api/v1/products/{id}` | `product_id` (UUID) | Retrieve comprehensive product specs |

### 💬 Chat & Conversations (`/api/v1/chat`, `/api/v1/conversations`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat/message` | Send message to AI assistant; returns answer, product cards, and comparison matrix |
| `GET` | `/api/v1/conversations` | List conversation history for the current user |
| `POST` | `/api/v1/conversations` | Create a new conversation session |
| `GET` | `/api/v1/conversations/{id}/messages` | Retrieve full message thread with saved UI payloads |
| `DELETE` | `/api/v1/conversations/{id}` | Delete a conversation thread |

### 🛠️ Admin (`/api/v1/admin`)
| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/v1/admin/products` | Create a new product listing | Admin Only |
| `PATCH` | `/api/v1/admin/products/{id}` | Update product details, pricing, stock, or image | Admin Only |
| `DELETE` | `/api/v1/admin/products/{id}` | Remove a product from the catalog | Admin Only |
| `POST` | `/api/v1/admin/policies` | Add or update a store policy entry | Admin Only |
| `PATCH` | `/api/v1/admin/policies/{id}` | Modify existing policy content | Admin Only |
| `POST` | `/api/v1/admin/policies/upload-pdf` | Ingest and index store policy PDF document | Admin Only |

---

## 🛡️ Grounding & Verification Rules

1. **Unlisted Information**: Topics not present in VoltKart policies (e.g., custom EMI, special external coupons) return:
   > *"I don't have that information available in the system."*
2. **Missing Spec Safeguards**: If a customer inquires about unindexed attributes (e.g., specific chassis color variations or touchscreen features not in data), the assistant explicitly states that the spec is not listed in the verified catalog.
3. **Spec Integrity Check**: Every numerical value returned in the LLM's response (RAM, SSD, price, weight, battery life) is cross-referenced against the SQL record. Any discrepancy automatically triggers a deterministic code fallback.
4. **Contextual Refinements**: Follow-up filters (e.g., *"Show me something cheaper"* or *"Show me something with better battery"*) dynamically compute thresholds using the items recommended in the previous turn.

---

## 🧪 Testing & Verification

### Run Backend Unit & Integration Tests
```bash
cd VoltKart_MVP/backend
pytest -q
```

### Build Frontend for Production
```bash
cd VoltKart_MVP/frontend
npm run build
```

---

## 📄 License
This project is developed for educational, demonstration, and MVP purposes. All product names and specifications are synthetic or illustrative.
