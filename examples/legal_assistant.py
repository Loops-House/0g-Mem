"""
Demo: Legal Contract Assistant with Verifiable Memory

Modes:
  python examples/legal_assistant.py          # local mock (no keys needed)
  python examples/legal_assistant.py --live   # real 0g testnet (needs AGENT_KEY + funds)

Live mode requires:
    export AGENT_KEY=<your_0g_chain_private_key>   # funded from https://faucet.0g.ai
    export MEMORY_REGISTRY_ADDRESS=<deployed_contract>
    export OPENAI_API_KEY=<key>  # optional, for better embeddings
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIVE_MODE = "--live" in sys.argv

if not LIVE_MODE:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
    from test_memory import MockStorage, MockCompute, MockDA, MockChain

from ogmem import VerifiableMemory


CONTRACT_CLAUSES = [
    "Section 3.1 Liability: The total liability of either party shall not exceed "
    "the fees paid in the twelve (12) months preceding the claim.",

    "Section 4.2 Termination: Either party may terminate this agreement with "
    "30 days written notice. Immediate termination is permitted in case of material breach.",

    "Section 5.1 Confidentiality: Both parties agree to keep confidential all "
    "proprietary information disclosed during the term and for 3 years thereafter.",

    "Section 6.3 Intellectual Property: All work product created by the service provider "
    "under this agreement shall be considered work-for-hire and owned by the client.",

    "Section 7.1 Governing Law: This agreement shall be governed by the laws of "
    "the State of Delaware, without regard to conflict of law provisions.",

    "Section 8.2 Force Majeure: Neither party shall be liable for delays caused by "
    "circumstances beyond their reasonable control, including acts of God, war, or pandemic.",

    "Section 9.1 Dispute Resolution: Any disputes shall first be subject to mediation. "
    "If mediation fails, disputes shall be resolved by binding arbitration in New York.",

    "Section 10.4 Amendment: This agreement may only be amended by written consent "
    "signed by authorized representatives of both parties.",
]

QUESTIONS = [
    "What is the liability cap?",
    "How much notice is required to terminate?",
    "How long does the confidentiality obligation last?",
    "Who owns the work product?",
    "Where will disputes be resolved?",
]


def main():
    print("=" * 60)
    print("0g Mem — Legal Assistant Demo")
    print("Verifiable AI Memory on 0g Labs")
    print("=" * 60)
    print()

    if LIVE_MODE:
        print("Mode: LIVE (0g Testnet)")
        memory = VerifiableMemory(
            agent_id="legal-assistant-demo",
            private_key=os.environ["AGENT_KEY"],
            network="0g-testnet",
            registry_contract_address=os.environ.get("MEMORY_REGISTRY_ADDRESS"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
    else:
        print("Mode: LOCAL MOCK (no keys needed)")
        print("  Run with --live for real 0g testnet submission")
        memory = VerifiableMemory(
            agent_id="legal-assistant-demo",
            private_key="0x" + "a" * 64,
            network="0g-testnet",
            _storage=MockStorage(),
            _compute=MockCompute(),
            _da=MockDA(),
            _chain=MockChain(),
        )
    print()

    print("Ingesting contract clauses into 0g Mem...")
    print()

    receipts = []
    for i, clause in enumerate(CONTRACT_CLAUSES):
        receipt = memory.add(clause, metadata={"section": f"clause_{i+1}"})
        receipts.append(receipt)
        print(f"  Clause {i+1} stored")
        print(f"    blob_id:      {receipt.blob_id[:20]}...")
        print(f"    merkle_root:  {receipt.merkle_root[:20]}...")
        print(f"    da_tx_hash:   {receipt.da_tx_hash[:20]}...")
        print(f"    chain_tx:     {receipt.chain_tx_hash[:20]}...")
        print()

    print(f"{len(CONTRACT_CLAUSES)} clauses stored on 0g Storage")
    print(f"All writes cryptographically anchored on 0g Chain")
    print()

    print("Answering questions with verifiable retrieval...")
    print()

    for question in QUESTIONS:
        results, proof = memory.query(question, top_k=2)

        print(f"Q: {question}")
        print(f"A: {results[0] if results else 'No relevant clause found'}")
        print()
        print(f"  Proof:")
        print(f"  query_hash:    {proof.query_hash[:20]}...")
        print(f"  retrieved:     {len(proof.blob_ids)} clauses")
        print(f"  scores:        {[round(s, 3) for s in proof.scores]}")
        print(f"  merkle_root:   {proof.merkle_root[:20]}...")
        print(f"  da_read_tx:    {proof.da_read_tx[:20]}...")
        print(f"  chain_block:   {proof.chain_block}")
        print()

        is_valid = memory.verify_proof(proof)
        print(f"  Proof valid: {is_valid}")
        print("-" * 60)
        print()

    print("Generating audit report...")
    print()

    report = memory.export_audit()

    print(report.summary())
    print()
    print(f"  Total operations: {report.total_writes + report.total_reads}")
    print(f"  Writes: {report.total_writes}")
    print(f"  Reads:  {report.total_reads}")
    print(f"  EU AI Act Articles: {', '.join(report.eu_ai_act_articles)}")
    print()
    print("  Exporting to audit_report.json...")
    with open("audit_report.json", "w") as f:
        f.write(report.to_json())
    print("  Saved to audit_report.json")
    print()
    print("=" * 60)
    print("Demo complete. Every answer is cryptographically provable")
    print("and verifiable on 0g Chain + DA.")
    print("=" * 60)


if __name__ == "__main__":
    main()
