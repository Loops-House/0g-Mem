# AI Accelerator by 0G & Blockchain Builders — Application
> Stanford Approach | 10-Week Program | apollo.0g.ai

---

## Contact Information

**Email**
violinadoley21@gmail.com

---

## Project

**Startup / Project name**
0G Mem

**One-line description of your idea / project**
Cryptographically verifiable, encrypted, on-chain memory for AI agents — provable, pluggable, and owned by you.

---

## Team

**Main contact person**
[FILL IN: Your full name]

**Email of main contact**
violinadoley21@gmail.com

**Names / Roles / Emails of all team members**
- [FILL IN: Name] — Founder / Full-Stack Engineer — violinadoley21@gmail.com
- [FILL IN: Name] — [Role] — [Email]
*(Please include at least one technical team member)*

**Telegram of main contact**
[FILL IN: e.g. @yourhandle]

**LinkedIn of main contact**
[FILL IN: linkedin.com/in/yourprofile]

**LinkedIn of technical team member(s)**
[FILL IN: linkedin.com/in/technicalteammember]

---

## Team Background

*(Year of graduation, school, degree, subject, relevant experience, LinkedIn)*

- **[FILL IN: Name]** — [Year], [School], [Degree] in [Subject]. [Relevant experience — e.g. previously built X, worked at Y, contributed to Z]. [LinkedIn URL]
- **[FILL IN: Name]** — [Year], [School], [Degree] in [Subject]. [Relevant experience]. [LinkedIn URL]

---

**How did your team meet and how long have you been working together?**
[FILL IN: e.g. "We met at [event/university/online community] and have been working together for [X months/years]."]

---

**Previous experience in web3 / crypto**
[FILL IN: e.g. Developer, Retail investor, DAO contributor, etc. — be specific about what you've built or done]

---

**Previous experience in AI / ML**
Built 0G Mem end-to-end: designed and implemented a semantic vector search pipeline using sentence-transformers (all-MiniLM-L6-v2, dim=384), AES-256-GCM client-side encryption with HKDF-SHA256 key derivation, and a LangChain-compatible memory interface. Integrated local embedding generation with cosine similarity search and Merkle proof generation for every retrieval event.

---

## Project Details

**Describe your project**
0G Mem is a cryptographically verifiable, encrypted, user-owned memory layer for AI agents built on 0G Labs. When an AI agent writes or reads a memory, 0G Mem encrypts the data client-side (AES-256-GCM), uploads it to 0G Storage, logs a commitment to 0G DA, and anchors a Merkle root on 0G Chain. Every retrieval returns a QueryProof that any third party can independently verify. Memory ownership is tied to the user's wallet via an ERC-7857-style NFT, with per-blob shard access control for multi-agent systems. It is a drop-in replacement for LangChain's memory interface and produces EU AI Act Article 12-compliant audit reports by construction.

---

**What technical innovation are you introducing?**
Three core innovations:

1. **Verifiable memory reads** — every `query()` call returns a `QueryProof` containing Merkle inclusion proofs, a DA read log hash, and an on-chain block reference. Any third party can independently verify that a specific agent retrieved specific memories at a specific point in time — without trusting 0G Mem as a company. This is the first memory system with this property.

2. **Wallet-derived client-side encryption** — encryption keys are derived from the user's wallet private key via HKDF-SHA256. The server never sees plaintext. No key management service is required. Key rotation is not needed because the key is derived on-demand.

3. **NFT memory ownership with per-blob shard access control** — memory is minted as an ERC-7857-style NFT. Access can be granted to specific agents for specific memory blobs (shards), enforced on-chain and revocable at any time. Transferring the NFT transfers complete memory ownership. No existing memory system has a portable, on-chain ownership primitive.

---

**Which category is your project in?**
- [x] AI Agent or Agentic Infrastructure
- [x] AI Infrastructure
- [x] Blockchain Infrastructure

---

**What stages have you completed?**
- [x] Ideation
- [x] Need Validation
- [x] Technical Design
- [x] Product Design
- [x] Product Development

**Completed in v0.1.0:**
- `VerifiableMemory` SDK — `add()`, `query()`, `verify_proof()`, `export_audit()`
- 0G Storage integration via @0gfoundation/0g-ts-sdk
- 0G DA integration — gRPC write/read commitments
- 0G Chain integration — MemoryRegistry + MemoryNFT deployed on Galileo testnet
- AES-256-GCM encryption + HKDF-SHA256 key derivation
- SHA-256 Merkle tree with inclusion proof generation and verification
- LangChain BaseMemory drop-in (3 lines of code)
- EU AI Act Article 12 audit export (JSON)
- FastAPI REST server (8 endpoints)
- 43 tests

**Smart contracts deployed (0G Galileo Testnet, Chain ID 16602):**
- MemoryRegistry: `0xEDF95D9CFb157F5F38C1125B7DFB3968E05d2c4b`
- MemoryNFT: `0x70ad85300f522A41689954a4153744BF6E57E488`

---

**Who are your competitors, and what is your primary advantage and differentiator?**

| Competitor | What they do | Our differentiator |
|---|---|---|
| **Mem0** ($24M Series A, 186M API calls/quarter) | Centralized AI memory layer | Mem0 stores memory on their servers, unencrypted, unverifiable. 0G Mem is the first solution with client-side encryption, on-chain proof, and user NFT ownership. |
| **Zep** | Temporal knowledge graph for agent memory | Centralized, no cryptographic proofs, no ownership primitive |
| **LangMem** (LangChain) | Open-source memory module | No encryption standard, no cross-framework portability, no proof of integrity |
| **Filecoin / Arweave** | Decentralized storage | Built for cold archival, not real-time agent memory. No semantic retrieval, no ownership layer, no compliance tooling |
| **ORA Protocol / Ritual** | On-chain AI inference | Focused on compute/inference — no persistent, portable memory layer |

**Primary advantage:** No direct competitor has built verifiable, encrypted, user-owned agent memory. The differentiators are architectural — EU AI Act Article 12 compliance is built into the write pipeline by construction, not bolted on. Competitors cannot replicate this without rebuilding from scratch.

---

**What is your go-to-market strategy?**

**Phase 1 — Developer adoption (now):**
- GitHub open-source release targeting 1M+ LangChain developers. Zero-friction drop-in: one line of code replaces `ConversationBufferMemory`. Developers get verifiable, encrypted memory with no architecture change.
- 0G ecosystem: publish on 0G's developer portal, apply for 0G ecosystem fund grants, co-market with 0G Labs (they have $88.8M ecosystem fund and Google Cloud / Chainlink / Alibaba Cloud partnerships).

**Phase 2 — Compliance-driven enterprise (Q3 2026):**
- EU AI Act Article 12 enforcement hits August 2026. Enterprise AI teams at healthcare, financial services, and legal firms are actively seeking compliant memory solutions. 0G Mem is the only memory layer that is Article 12-compliant by construction. Target these buyers directly with a compliance-first message.
- Partner with enterprise AI framework vendors (LangChain Enterprise, CrewAI Pro) as a certified compliant memory backend.

**Phase 3 — Agent economy (2026+):**
- ERC-7857 agent NFTs create a market for AI agents with memory as an asset. 0G Mem is the natural memory backend for ERC-7857 agents. Position as infrastructure for the agent identity and memory economy.

---

**What traction do you have to date?**
- v0.1.0 shipped: fully working SDK, smart contracts deployed on 0G Galileo Testnet, 43 passing tests, FastAPI REST server, LangChain drop-in, EU AI Act audit export
- GitHub repository live: [FILL IN: github.com/violinadoley/0g-Mem]
- Smart contracts deployed and verified on 0G Galileo Testnet
- Twitter/X: @0G_Mem — launching social presence April 2026
- [FILL IN: any additional traction — beta users, developer feedback, partnerships]

---

**Have you raised capital to date?**
[FILL IN: e.g. "No capital raised to date, bootstrapped." or "Raised $X from Y."]

---

**Presentations or 1-pagers**
[FILL IN: Upload PDF if available]

**Whitepaper or research**
[FILL IN: Upload PDF if available — can export ARCHITECTURE.md + PROJECT_DESCRIPTION.md as PDF]

**Other material**
- GitHub: [FILL IN: github.com/violinadoley/0g-Mem]
- [FILL IN: any demo video, live demo link, etc.]

---

**What areas do you hope the accelerator can best support you on?**
1. **Go-to-market and distribution** — identifying the highest-leverage early adopters among enterprise AI teams and Web3-native agent builders, and getting in front of them quickly
2. **Fundraising** — connecting with investors who understand the intersection of verifiable AI infrastructure and on-chain ownership
3. **Technical partnerships** — introductions to LangChain, CrewAI, and enterprise AI framework teams for integration partnerships
4. **Legal / compliance** — guidance on positioning 0G Mem for EU AI Act Article 12 enterprise sales and understanding the regulatory landscape
5. **0G ecosystem** — deeper collaboration with 0G Labs to co-develop the ERC-7857 memory standard and become the reference memory implementation

---

**Any other information you would like to add?**
0G Mem is not just a product — it is infrastructure for a property right that doesn't exist yet: the right for an AI agent's memory to be cryptographically owned, portable, and provable. The timing is deliberate: 0G Mainnet is live, ERC-7857 is in draft, and EU AI Act enforcement is three months away. We are building the memory layer that the agentic economy needs before it needs it.

---

**How did you hear about the 0G Blockchain Builders AIccelerator?**
[FILL IN: e.g. Twitter/X, 0G Discord, referred by someone, etc.]

**Has anyone from 0G, Blockchain Builders, or the Apollo program mentors referred you?**
[FILL IN: Name of referrer, or "No"]

**What time zone will you be in during the program?**
[FILL IN: e.g. PST / EST / IST / GMT+X]
