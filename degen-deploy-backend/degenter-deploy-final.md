# 📘 **DEGEN DEPLOY — Complete Technical Documentation**

## Version: 2.0 (Final)
## Status: Production-Ready Specification
## Chain: Solana

---

## 🎯 **EXECUTIVE SUMMARY**

**Degen Deploy** is a **yield optimization system** that automatically distributes user deposits across the highest-yielding Solana protocols based on APY rankings and user risk preferences. It operates as a **per-user position manager** where each user has individual protocol positions, rebalances only on user request, and respects each protocol's native lock periods.

### Core Philosophy
> "One smart contract logic, millions of independent users — each controlling their own positions."

---

## 📋 **TABLE OF CONTENTS**

1. [System Overview](#1-system-overview)
2. [Core Concepts](#2-core-concepts)
3. [User Flow — Complete Walkthrough](#3-user-flow--complete-walkthrough)
4. [Protocol Universe](#4-protocol-universe)
5. [Risk Profile System](#5-risk-profile-system)
6. [Investment Logic — The "Equal Distribution" Rule](#6-investment-logic--the-equal-distribution-rule)
7. [Rebalancing — User-Initiated Only](#7-rebalancing--user-initiated-only)
8. [Withdrawal — Respecting Protocol Locks](#8-withdrawal--respecting-protocol-locks)
9. [AI Assistant — Chat + Execution](#9-ai-assistant--chat--execution)
10. [Database Architecture](#10-database-architecture)
11. [Complete Flow Examples](#11-complete-flow-examples)
12. [API Endpoints Summary](#12-api-endpoints-summary)

---

## 1. **SYSTEM OVERVIEW**

### What Degen Deploy Is

Degen Deploy is a **non-custodial yield optimization system** where:

- Users deposit USDC
- System scans all integrated Solana protocols for current APY
- Funds are **distributed equally** across the top 3 highest-yielding protocols
- Users can specify **risk preference** (Any/Low/Medium/High)
- Users can **manually rebalance** to any protocol or best APY
- **Only the requesting user's funds** move during rebalance
- **Protocol-native lock periods** are respected
- Users can withdraw anytime (subject to protocol locks)

### What Degen Deploy Is NOT

| ❌ Not This | ✅ This |
|------------|---------|
| Auto-rebalancing bot | User-initiated rebalance only |
| Shared vault for all users | Per-user independent positions |
| Global lock period | Protocol-specific lock periods |
| AI makes investment decisions | AI executes user commands |
| One-size-fits-all strategy | User-specific risk profiles |

---

## 2. **CORE CONCEPTS**

### 2.1 **Per-User Positions**

Each user has **independent positions** in the database. User A's $100 in Orca is completely separate from User B's $100 in Orca.

```
USER A POSITIONS:
├── Orca: $50
└── Raydium: $50

USER B POSITIONS:
├── Kamino: $70
└── Save: $30
```

**Why:** Rebalancing should only affect the user who requested it. This allows:
- User A to rebalance to Kamino without affecting User B
- Different risk profiles per user
- Independent withdrawal decisions

### 2.2 **Equal Distribution Across Top 3 Protocols**

When a user deposits, the system:
1. Scans all protocols for current APY
2. Sorts by APY descending
3. Takes the **top 3 protocols**
4. **Distributes the deposit equally** across them

```
Example: User deposits $300

Protocol Rankings:
1. Meteora: 28% APY
2. Orca: 22.7% APY
3. Raydium: 18.4% APY
4. Kamino: 6.2% APY

Distribution:
├── Meteora: $100
├── Orca: $100
└── Raydium: $100
```

### 2.3 **Risk Filtering**

If the user specifies a risk preference, the system **filters protocols before ranking**:

| Risk Profile | Allowed Protocols |
|--------------|-------------------|
| **Any** | All protocols |
| **Low** | Only Kamino, Save (lending only) |
| **Medium** | Kamino, Marginfi, Save, Raydium, Orca (excludes Meteora) |
| **High** | All protocols |

```
Example: User deposits $300 with LOW risk

Filtered Protocols:
1. Kamino: 6.2% APY
2. Save: 5.5% APY

Distribution:
├── Kamino: $150
└── Save: $150
```

### 2.4 **Protocol Lock Periods**

**Degen Deploy DOES NOT impose lock periods.** Instead, it respects each protocol's native lock period.

| Protocol | Lock Period | Withdrawal Fee |
|----------|-------------|----------------|
| Kamino | 0 days | 0% |
| Marginfi | 0 days | 0% |
| Save | 0 days | 0% |
| Raydium | 0 days | 0.1% |
| Orca | 0 days | 0.1% |
| Meteora | 7 days | 0.2% |

**User Experience:**
- If user's funds are in Kamino → can withdraw immediately
- If user's funds are in Meteora → must wait 7 days
- System shows lock status for each position

---

## 3. **USER FLOW — COMPLETE WALKTHROUGH**

### 3.1 **User Onboarding**

```
Step 1: User connects wallet (Phantom/Backpack)
Step 2: System creates user record in database
Step 3: User can now deposit, withdraw, rebalance
```

### 3.2 **Investment Flow — Full Example**

**User:** Alice wants to invest $1,000 with "Any" risk profile.

```
STEP 1: Alice calls POST /api/invest
        { userId: "alice-123", amount: 1000, riskProfile: "any" }

STEP 2: System scans all protocols
        ├── Meteora: 28.0% APY
        ├── Orca: 22.7% APY
        ├── Raydium: 18.4% APY
        ├── Kamino: 6.2% APY
        ├── Marginfi: 5.8% APY
        └── Save: 5.5% APY

STEP 3: System filters by risk = "any" → All protocols

STEP 4: System takes top 3 by APY:
        ├── Meteora: 28.0%
        ├── Orca: 22.7%
        └── Raydium: 18.4%

STEP 5: System distributes equally:
        ├── Meteora: $333.33
        ├── Orca: $333.33
        └── Raydium: $333.34

STEP 6: System creates positions in database:
        ┌─────────────────────────────────────────────────────────────┐
        │ user_positions                                             │
        ├─────────────────────────────────────────────────────────────┤
        │ id: pos-1, user_id: alice-123, protocol: Meteora, $333.33 │
        │ id: pos-2, user_id: alice-123, protocol: Orca, $333.33    │
        │ id: pos-3, user_id: alice-123, protocol: Raydium, $333.34 │
        └─────────────────────────────────────────────────────────────┘

STEP 7: System returns unsigned transactions to Alice's wallet

STEP 8: Alice signs and submits transactions

STEP 9: System confirms → positions marked "active"

STEP 10: Alice's portfolio:
         ┌────────────────────────────────────────────────────────────┐
         │ Total Invested: $1,000                                    │
         │ Current APY: 23.0% (weighted average)                     │
         │ Meteora: $333.33 @ 28.0% (lock: 7 days)                  │
         │ Orca: $333.33 @ 22.7% (lock: 0 days)                     │
         │ Raydium: $333.34 @ 18.4% (lock: 0 days)                  │
         └────────────────────────────────────────────────────────────┘
```

### 3.3 **Risk Filtering — Example**

**Alice** now wants to invest another $500 but with LOW risk only.

```
STEP 1: Alice calls POST /api/invest
        { userId: "alice-123", amount: 500, riskProfile: "low" }

STEP 2: System filters protocols by risk = "low"
        ├── Kamino: 6.2% APY (LOW)
        └── Save: 5.5% APY (LOW)

STEP 3: System takes top 3 = only 2 available:
        ├── Kamino: 6.2%
        └── Save: 5.5%

STEP 4: System distributes equally:
        ├── Kamino: $250
        └── Save: $250

STEP 5: New positions created:
        ┌─────────────────────────────────────────────────────────────┐
        │ id: pos-4, user_id: alice-123, protocol: Kamino, $250     │
        │ id: pos-5, user_id: alice-123, protocol: Save, $250       │
        └─────────────────────────────────────────────────────────────┘

STEP 6: Alice now has 5 active positions:
        ┌────────────────────────────────────────────────────────────┐
        │ Meteora: $333.33 @ 28.0%                                  │
        │ Orca: $333.33 @ 22.7%                                     │
        │ Raydium: $333.34 @ 18.4%                                  │
        │ Kamino: $250 @ 6.2%                                       │
        │ Save: $250 @ 5.5%                                         │
        └────────────────────────────────────────────────────────────┘
```

---

## 4. **PROTOCOL UNIVERSE**

### 4.1 **Supported Protocols**

| Protocol | Type | Risk | Lock Period | APY Source |
|----------|------|------|-------------|------------|
| **Kamino** | Lending | Low | 0 days | SDK |
| **Marginfi** | Lending | Medium | 0 days | SDK |
| **Save** | Lending | Low | 0 days | REST API |
| **Raydium** | LP | Medium | 0 days | REST API |
| **Orca** | LP | Medium | 0 days | REST API |
| **Meteora** | LP | High | 7 days | REST API |

### 4.2 **Protocol Characteristics**

#### Lending Protocols (Kamino, Marginfi, Save)
- **How they work:** Users deposit stablecoins → Others borrow → User earns interest
- **Lock Period:** None (withdraw anytime)
- **Risk:** Low (only smart contract risk)
- **Yield Source:** Borrower interest payments
- **APY Range:** 5-15%

#### LP Protocols (Raydium, Orca, Meteora)
- **How they work:** Users deposit two assets (USDC + SOL) → Traders swap → User earns fees
- **Lock Period:** Varies by protocol
- **Risk:** Medium to High (impermanent loss risk)
- **Yield Source:** Swap fees
- **APY Range:** 15-40%

---

## 5. **RISK PROFILE SYSTEM**

### 5.1 **Risk Definitions**

| Profile | Description | Allowed Protocols |
|---------|-------------|-------------------|
| **Any** | No risk restriction | All protocols |
| **Low** | Only lending protocols | Kamino, Save |
| **Medium** | Lending + Stable LP | Kamino, Marginfi, Save, Raydium, Orca |
| **High** | All protocols | Kamino, Marginfi, Save, Raydium, Orca, Meteora |

### 5.2 **User Risk Selection Flow**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    USER RISK SELECTION FLOW                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "I want to invest $500"                                          │
│         ↓                                                              │
│  System: "What risk profile?"                                          │
│         ↓                                                              │
│  User: "Medium risk"                                                   │
│         ↓                                                              │
│  System: Filtering protocols where risk != 'high'                     │
│         ├── Kamino: 6.2% (LOW) ✓                                       │
│         ├── Marginfi: 5.8% (MEDIUM) ✓                                 │
│         ├── Save: 5.5% (LOW) ✓                                        │
│         ├── Raydium: 18.4% (MEDIUM) ✓                                 │
│         ├── Orca: 22.7% (MEDIUM) ✓                                    │
│         └── Meteora: 28.0% (HIGH) ✗ (EXCLUDED)                        │
│         ↓                                                              │
│  System: Taking top 3 from filtered list                               │
│         ├── Orca: 22.7%                                                │
│         ├── Raydium: 18.4%                                             │
│         └── Kamino: 6.2%                                               │
│         ↓                                                              │
│  System: Distributing equally                                          │
│         ├── Orca: $166.67                                              │
│         ├── Raydium: $166.67                                           │
│         └── Kamino: $166.66                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. **INVESTMENT LOGIC — THE "EQUAL DISTRIBUTION" RULE**

### 6.1 **Core Logic**

```text
Rule: Always distribute EQUALLY across top 3 protocols (by APY)

Why Top 3?
- Diversification reduces risk
- Captures best yields without over-concentration
- Simpler for users to understand

Why Equal?
- Fair distribution
- No complex weighting calculations
- Easy to explain to users
```

### 6.2 **Investment Decision Tree**

```
                    User Deposits USDC
                           │
                           ▼
                ┌──────────────────┐
                │  Risk Specified? │
                └──────┬───────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
       Low Risk    Medium Risk   High Risk/Any
          │            │            │
          ▼            ▼            ▼
    Filter:         Filter:     Filter:
    only low       exclude     all protocols
    risk           high risk
    protocols      protocols
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Sort by APY DESC │
            └──────┬───────────┘
                   │
                   ▼
            ┌──────────────────┐
            │ Take Top 3       │
            └──────┬───────────┘
                   │
                   ▼
            ┌──────────────────┐
            │ Distribute       │
            │ EQUALLY          │
            └──────┬───────────┘
                   │
                   ▼
            ┌──────────────────┐
            │ Create Positions │
            └──────────────────┘
```

---

## 7. **REBALANCING — USER-INITIATED ONLY**

### 7.1 **Core Concept**

> **Rebalancing is NEVER automatic.** Only the user who requests rebalance has their funds moved. Other users' positions remain unchanged.

### 7.2 **Rebalance Scenarios**

#### Scenario A: Rebalance to Best APY

```
User: "Rebalance my funds"
System: "Finding best APY protocol..."
        ┌─────────────────────────────────────────────────┐
        │ Current APYs:                                   │
        │ ├── Meteora: 28.0% (but user is NOT in this)  │
        │ ├── Orca: 14.0% (user IS in this)             │
        │ └── Raydium: 12.0% (user IS in this)          │
        └─────────────────────────────────────────────────┘
System: "Best APY = Meteora at 28.0%"
        "Moving your funds from Orca + Raydium to Meteora"
        ┌─────────────────────────────────────────────────┐
        │ BEFORE:                                         │
        │ ├── Orca: $50                                   │
        │ └── Raydium: $50                                │
        │                                                 │
        │ AFTER:                                          │
        │ └── Meteora: $100                               │
        └─────────────────────────────────────────────────┘
Result: ONLY this user's funds moved to Meteora
```

#### Scenario B: Rebalance to Specific Protocol

```
User: "Move my funds to Kamino"
System: "Checking Kamino..."
        ┌─────────────────────────────────────────────────┐
        │ Kamino APY: 6.2%                               │
        │ Kamino Lock: 0 days                            │
        └─────────────────────────────────────────────────┘
System: "Moving your funds to Kamino"
        ┌─────────────────────────────────────────────────┐
        │ BEFORE:                                         │
        │ ├── Orca: $50                                   │
        │ └── Raydium: $50                                │
        │                                                 │
        │ AFTER:                                          │
        │ └── Kamino: $100                                │
        └─────────────────────────────────────────────────┘
Result: ONLY this user's funds moved to Kamino
```

#### Scenario C: Partial Rebalance

```
User: "Move 50% of my funds to Kamino"
System: "Moving 50% to Kamino"
        ┌─────────────────────────────────────────────────┐
        │ BEFORE:                                         │
        │ ├── Orca: $50                                   │
        │ └── Raydium: $50                                │
        │                                                 │
        │ AFTER:                                          │
        │ ├── Kamino: $50                                 │
        │ ├── Orca: $25                                   │
        │ └── Raydium: $25                                │
        └─────────────────────────────────────────────────┘
```

### 7.3 **Why User-Initiated Only?**

| Reason | Explanation |
|--------|-------------|
| **Control** | Users decide when to rebalance, not the system |
| **Gas Costs** | Auto-rebalancing for lakhs of users = massive gas fees |
| **Lock Periods** | Auto-rebalance might get stuck in locked protocols |
| **User Intent** | User might prefer lower APY for specific reasons |
| **Transparency** | Users know exactly when and why funds moved |

---

## 8. **WITHDRAWAL — RESPECTING PROTOCOL LOCKS**

### 8.1 **Core Concept**

> Degen Deploy **does not impose** any lock period. Withdrawal availability depends entirely on each protocol's native lock period.

### 8.2 **Withdrawal Flow — Complete Example**

**Alice** wants to withdraw all her funds.

```
Alice's Positions:
┌─────────────────────────────────────────────────────────────┐
│ Position 1: Meteora $333.33 (7-day lock, deposited 3 days ago)│
│ Position 2: Orca $333.33 (0-day lock)                        │
│ Position 3: Raydium $333.34 (0-day lock)                     │
│ Position 4: Kamino $250 (0-day lock)                         │
│ Position 5: Save $250 (0-day lock)                           │
└─────────────────────────────────────────────────────────────┘

Alice: "Withdraw my funds"

System checks each position:
┌─────────────────────────────────────────────────────────────┐
│ Position 1: Meteora → 7-day lock, 4 days remaining        │
│             Status: LOCKED ❌                               │
│             Message: "Cannot withdraw until June 26, 2026" │
│                                                             │
│ Position 2: Orca → 0-day lock → AVAILABLE ✅               │
│                                                             │
│ Position 3: Raydium → 0-day lock → AVAILABLE ✅            │
│                                                             │
│ Position 4: Kamino → 0-day lock → AVAILABLE ✅             │
│                                                             │
│ Position 5: Save → 0-day lock → AVAILABLE ✅               │
└─────────────────────────────────────────────────────────────┘

System Response:
{
  "totalWithdrawn": $1166.67,
  "locked": [
    {
      "protocol": "Meteora",
      "amount": $333.33,
      "unlockDate": "2026-06-26",
      "daysRemaining": 4
    }
  ],
  "withdrawn": [
    {"protocol": "Orca", "amount": $333.33},
    {"protocol": "Raydium", "amount": $333.34},
    {"protocol": "Kamino", "amount": $250},
    {"protocol": "Save", "amount": $250}
  ]
}
```

### 8.3 **Protocol Lock Periods — Reference**

| Protocol | Lock Period | Withdrawal Fee |
|----------|-------------|----------------|
| Kamino | 0 days | 0% |
| Marginfi | 0 days | 0% |
| Save | 0 days | 0% |
| Raydium | 0 days | 0.1% |
| Orca | 0 days | 0.1% |
| Meteora | 7 days | 0.2% |

---

## 9. **AI ASSISTANT — CHAT + EXECUTION**

### 9.1 **AI Role**

The AI assistant is a **chat interface** that:
1. **Answers questions** about Degen Deploy
2. **Executes user commands** (invest, rebalance, withdraw)
3. **Explains positions** and APY
4. **Does NOT** make decisions — only executes user instructions

### 9.2 **AI Capabilities**

| Capability | Example | AI Action |
|------------|---------|-----------|
| **Answer Questions** | "Mera current APY kya hai?" | Fetches from database |
| **Invest** | "Invest $100 low risk" | Calls invest API |
| **Rebalance** | "Move my funds to Kamino" | Calls rebalance API |
| **Withdraw** | "Withdraw my funds" | Calls withdraw API |
| **Explain Rebalance** | "Kyun rebalance hua?" | Fetches rebalance logs |
| **Check Lock Status** | "Kab tak locked hain?" | Checks protocol locks |

### 9.3 **AI Conversation Examples**

#### Example 1: Investment
```
User: "I want to invest $500"
AI: "Sure! What risk profile would you like?"
    "Options: Any, Low, Medium, High"
User: "Medium"
AI: "✅ Processing your investment..."
    "Current top protocols for Medium risk:"
    "1. Orca: 22.7% APY"
    "2. Raydium: 18.4% APY"
    "3. Kamino: 6.2% APY"
    "Distribution: Orca $166.67, Raydium $166.67, Kamino $166.66"
    "Please sign the transactions in your wallet."
```

#### Example 2: Rebalance
```
User: "What's my current APY?"
AI: "Your current positions:"
    "Meteora: $333.33 @ 28.0%"
    "Orca: $333.33 @ 14.0% (APY dropped)"
    "Raydium: $333.34 @ 12.0% (APY dropped)"
    "Total APY: 18.0%"
User: "Rebalance my funds to best APY"
AI: "✅ Finding best APY..."
    "Meteora is currently best at 28.0%"
    "I'll move your Orca ($333.33) and Raydium ($333.34) to Meteora"
    "Your new positions:"
    "Meteora: $1000 @ 28.0%"
    "Please sign the transactions."
```

#### Example 3: Withdrawal with Lock
```
User: "Withdraw my funds"
AI: "Checking your positions..."
    "Meteora: $333.33 (locked until June 26, 2026)"
    "Orca: $333.33 (available)"
    "Raydium: $333.34 (available)"
    "Kamino: $250 (available)"
    "Save: $250 (available)"
    "Available to withdraw: $1166.67"
    "Locked: $333.33 (4 days remaining)"
    "Proceed with withdraw?"
User: "Yes, withdraw available funds"
AI: "✅ Withdrawing $1166.67..."
```

---

## 10. **DATABASE ARCHITECTURE**

### 10.1 **Core Tables**

#### `users`
Stores user wallet addresses and preferences.

```sql
Table: users
├── id (UUID, Primary Key)
├── wallet_address (TEXT, Unique, Not Null)
├── risk_profile (TEXT, Default: 'any')
├── created_at (TIMESTAMP, Default: NOW())
└── updated_at (TIMESTAMP)
```

#### `user_positions`
Stores each user's individual protocol positions.

```sql
Table: user_positions
├── id (UUID, Primary Key)
├── user_id (UUID, Foreign Key → users.id)
├── protocol_name (TEXT, Not Null)
├── protocol_type (TEXT, Check: 'lending' or 'lp')
├── amount_usdc (DECIMAL, Not Null)
├── apy_at_deposit (DECIMAL)
├── deposit_date (TIMESTAMP, Default: NOW())
├── lock_until (TIMESTAMP)  -- Protocol-specific lock end date
├── status (TEXT, Check: 'active' or 'withdrawn')
└── created_at (TIMESTAMP, Default: NOW())
```

#### `user_rebalance_logs`
Tracks all rebalance actions per user.

```sql
Table: user_rebalance_logs
├── id (UUID, Primary Key)
├── user_id (UUID, Foreign Key → users.id)
├── from_protocol (TEXT)
├── to_protocol (TEXT)
├── from_amount (DECIMAL)
├── to_amount (DECIMAL)
├── executed_at (TIMESTAMP, Default: NOW())
└── notes (TEXT)
```

#### `protocol_configs`
Stores protocol-specific configurations.

```sql
Table: protocol_configs
├── id (UUID, Primary Key)
├── protocol_name (TEXT, Unique, Not Null)
├── protocol_type (TEXT, Check: 'lending' or 'lp')
├── risk_level (TEXT, Check: 'low', 'medium', 'high')
├── lock_period_days (INTEGER, Default: 0)
├── withdrawal_fee (DECIMAL, Default: 0)
├── is_active (BOOLEAN, Default: TRUE)
└── apy_source (TEXT)  -- 'sdk', 'api', 'baseline'
```

#### `protocol_snapshots`
Historical APY data for analytics.

```sql
Table: protocol_snapshots
├── id (UUID, Primary Key)
├── protocol_name (TEXT)
├── apy (DECIMAL)
├── tvl (DECIMAL)
├── captured_at (TIMESTAMP, Default: NOW())
└── source (TEXT)  -- 'scanner' or 'manual'
```

### 10.2 **Key Relationships**

```
users
  │
  ├── 1──┐
  │     │
  │     ▼
  │   user_positions
  │     │
  │     ├── protocol_name → protocol_configs
  │     │
  │     └── user_id → users
  │
  └── 1──┐
        │
        ▼
      user_rebalance_logs
        │
        ├── from_protocol → protocol_configs
        ├── to_protocol → protocol_configs
        └── user_id → users
```

---

## 11. **COMPLETE FLOW EXAMPLES**

### 11.1 **Full User Journey — Alice**

```
Day 1: Alice joins Degen Deploy
├── Connects wallet: 0xAlice123
├── System creates user record
└── Alice sees dashboard (zero balance)

Day 1 (Later): Alice invests $1,000 "Any" risk
├── System scans protocols
│   ├── Meteora: 28.0%
│   ├── Orca: 22.7%
│   ├── Raydium: 18.4%
│   ├── Kamino: 6.2%
│   ├── Marginfi: 5.8%
│   └── Save: 5.5%
├── System takes top 3: Meteora, Orca, Raydium
├── Distribution: $333.33 each
├── Positions created (status: intent)
├── Alice signs transactions
├── Positions marked active
└── Alice's portfolio: $1,000 @ 23.0% APY

Day 2: Orca APY drops to 14%
├── System scans (background)
│   ├── Meteora: 28.0%
│   ├── Kamino: 6.2%
│   ├── Raydium: 18.4%
│   └── Orca: 14.0%
├── Alice checks dashboard
│   └── Sees Orca APY dropped
└── No auto-rebalance (waiting for Alice)

Day 3: Alice checks her position
└── User: "Meri position ka APY kya hai?"
    AI: "Current positions:"
        "Meteora: $333.33 @ 28.0%"
        "Orca: $333.33 @ 14.0%"
        "Raydium: $333.34 @ 18.4%"
        "Total APY: 20.1%"

Day 3 (Later): Alice rebalances
User: "Rebalance my funds to best APY"
AI: "Finding best APY... Meteora at 28.0%"
    "Moving Orca ($333.33) and Raydium ($333.34) to Meteora"
    "New positions: Meteora: $1000 @ 28.0%"
Alice signs transactions
    └── Rebalance executed (ONLY Alice's funds)

Day 5: Alice invests $500 Low Risk
User: "Invest $500 low risk"
AI: "Filtering protocols for Low risk..."
    "Kamino: 6.2%, Save: 5.5%"
    "Distribution: Kamino $250, Save $250"
Alice signs transactions
    └── New positions created

Day 30: Alice withdraws $500 from Low Risk positions
User: "Withdraw $500 from my low risk positions"
AI: "Withdrawing Kamino ($250) and Save ($250)"
    "Total withdrawn: $500"
Alice receives USDC

Day 60: Alice withdraws remaining Meteora position
User: "Withdraw all funds"
AI: "Meteora: $1050 (yield earned: $50)"
    "Lock period: 0 days (already passed)"
    "Total withdrawn: $1050"
Alice receives USDC
    └── All positions closed
```

### 11.2 **Multi-User Scenario — Independence**

```
Alice and Bob both use Degen Deploy.

Alice:
├── Deposits $1,000 → Meteora, Orca, Raydium
└── Rebalances to Meteora (ONLY Alice's funds move)

Bob:
├── Deposits $500 → Kamino, Save
└── Does nothing (positions unchanged)

RESULT:
Alice's positions: Meteora $1000
Bob's positions: Kamino $250, Save $250

Alice's rebalance did NOT affect Bob.
Each user controls their own positions.
```

---

## 12. **API ENDPOINTS SUMMARY**

### 12.1 **Core Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/invest` | Invest USDC with risk profile |
| POST | `/api/rebalance` | User-initiated rebalance |
| POST | `/api/withdraw` | Withdraw funds |
| GET | `/api/position/:userId` | Get user's positions |
| GET | `/api/apy/all` | Get all protocol APYs |
| GET | `/api/apy/:protocol` | Get specific protocol APY |
| GET | `/api/balance/:wallet` | Get wallet USDC balance |
| GET | `/api/rebalance/history/:userId` | Get user's rebalance history |
| POST | `/api/ai/chat` | AI assistant chat |

### 12.2 **Request/Response Examples**

#### Invest
```json
POST /api/invest
{
  "userId": "alice-123",
  "amount": 1000,
  "riskProfile": "any"
}

Response:
{
  "success": true,
  "positions": [
    {"protocol": "Meteora", "amount": 333.33, "lockUntil": "2026-06-26"},
    {"protocol": "Orca", "amount": 333.33, "lockUntil": null},
    {"protocol": "Raydium", "amount": 333.34, "lockUntil": null}
  ],
  "totalAPY": 23.0,
  "transactions": ["tx1", "tx2", "tx3"]
}
```

#### Rebalance
```json
POST /api/rebalance
{
  "userId": "alice-123",
  "targetProtocol": "Kamino"  // Optional
}

Response:
{
  "success": true,
  "moved": [
    {"from": "Orca", "to": "Kamino", "amount": 333.33},
    {"from": "Raydium", "to": "Kamino", "amount": 333.34}
  ],
  "totalMoved": 666.67,
  "transactions": ["tx1", "tx2"]
}
```

#### Withdraw
```json
POST /api/withdraw
{
  "userId": "alice-123"
}

Response:
{
  "success": true,
  "totalWithdrawn": 666.67,
  "locked": [
    {"protocol": "Meteora", "amount": 333.33, "unlockDate": "2026-06-26"}
  ],
  "withdrawn": [
    {"protocol": "Orca", "amount": 333.33},
    {"protocol": "Raydium", "amount": 333.34}
  ]
}
```

---

## 📊 **FINAL SUMMARY — EVERYTHING IN ONE PLACE**

| Aspect | Implementation |
|--------|----------------|
| **Investment** | Equal distribution across top 3 APY protocols |
| **Risk Filtering** | Low = only lending; Medium = lending + stable LP; High/Any = all |
| **User Positions** | Per-user, independent records in database |
| **Rebalancing** | User-initiated ONLY; moves ONLY requesting user's funds |
| **Rebalance Target** | User-specified OR best APY |
| **Lock Periods** | Protocol-specific; NOT imposed by Degen Deploy |
| **Withdrawal** | Respects each protocol's lock period |
| **AI Role** | Chat assistant + command executor |
| **Scalability** | Works for lakhs of users (per-user records) |
| **Core Philosophy** | User controls their own positions |











FINAL SUMMARY
    Aspect	Implementation
    Investment	Equal distribution across top 3 APY protocols
    Risk Filtering	Low = only lending; Medium = lending + stable LP; High/Any = all
    User Positions	Per-user, independent records in database
    Rebalancing	User-initiated ONLY; moves ONLY requesting user's funds
    Rebalance Target	User-specified OR best APY
    Lock Periods	Protocol-specific; NOT imposed by Degen Deploy
    Withdrawal	Respects each protocol's lock period
    AI Role	Chat assistant + command executor
    Scalability	Works for lakhs of users (per-user records)
    Core Philosophy	User controls their own positions


    

✅ What This Document Contains
    Section	Content
    Executive Summary	One-page overview
    System Overview	Architecture diagram + high-level flow
    Core Concepts	Per-user positions, equal distribution, risk filtering, lock periods
    Protocol Universe	6 protocols with types, risks, lock periods
    Risk Profile System	4 risk levels + selection flow
    Investment Logic	Equal distribution decision tree
    Rebalancing	User-initiated only, 3 scenarios
    Withdrawal	Protocol lock respect, full example
    AI Assistant	Chat + execution, 3 conversation examples
    Database Architecture	5 tables + relationships
    Complete Flow Examples	Alice's full journey + multi-user scenario
    API Endpoints	9 endpoints + request/response examples
    Final Summary	One-page cheat sheet