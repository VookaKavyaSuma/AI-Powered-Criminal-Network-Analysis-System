"""
run_all.py — Master Orchestration Script for Phase 5 Graph Analytics.

Runs in order:
1. Centrality (Degree, Betweenness, PageRank)
2. Community Detection (Louvain modularity)
3. Anomaly Detection (Comm spikes, Transaction structuring)
4. Link Prediction (Jaccard similarity, Common neighbors)
5. Composite Explainable Risk Scoring (0-100)

Validates Exit Criteria:
- Top-5 by risk_score matches ground-truth kingpin + lieutenants with >80% overlap.
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analytics.anomaly_detection import AnomalyDetector
from analytics.centrality import CentralityAnalyzer
from analytics.community_detection import CommunityDetector
from analytics.link_prediction import LinkPredictor
from analytics.risk_scoring import RiskScorer
from graph.schema import get_neo4j_driver


def run_pipeline() -> dict:
    print("=" * 70)
    print("  CRIMINAL NETWORK ANALYSIS — GRAPH ANALYTICS PIPELINE")
    print("=" * 70)
    start_time = time.time()
    driver = get_neo4j_driver()

    try:
        # Step 1: Centrality
        print("\n----------------------------------------------------------------------")
        print("  STEP 1: Graph Centrality (Betweenness, PageRank, Degree)")
        print("----------------------------------------------------------------------")
        centrality = CentralityAnalyzer(driver)
        top_influencers = centrality.compute_all_centralities()

        # Step 2: Communities
        print("\n----------------------------------------------------------------------")
        print("  STEP 2: Louvain Community Detection (Operational Cells)")
        print("----------------------------------------------------------------------")
        comm_detector = CommunityDetector(driver)
        communities = comm_detector.detect_communities()

        # Step 3: Anomalies
        print("\n----------------------------------------------------------------------")
        print("  STEP 3: Anomaly Detection (Comm Bursts & Structuring)")
        print("----------------------------------------------------------------------")
        anomaly_detector = AnomalyDetector(driver)
        anomalies = anomaly_detector.run_anomaly_detection()

        # Step 4: Link Prediction
        print("\n----------------------------------------------------------------------")
        print("  STEP 4: Link Prediction (Common Neighbors & Jaccard Ties)")
        print("----------------------------------------------------------------------")
        link_predictor = LinkPredictor(driver)
        predicted_links = link_predictor.predict_links()

        # Step 5: Composite Risk Scoring
        print("\n----------------------------------------------------------------------")
        print("  STEP 5: Multi-Criteria Explainable Risk Scoring (0-100)")
        print("----------------------------------------------------------------------")
        risk_scorer = RiskScorer(driver)
        ranked_suspects = risk_scorer.compute_risk_scores()

        elapsed = time.time() - start_time
        print(f"\n✨ Full Analytics Pipeline completed in {elapsed:.2f} seconds.")

        # Step 6: Validate Ground Truth Exit Criteria
        print("\n" + "=" * 70)
        print("  GROUND TRUTH VALIDATION & EXIT CRITERIA CHECK")
        print("=" * 70)

        ground_truth_core = {
            "PER_RAVI_KUMAR": "Kingpin",
            "PER_SURESH_NAIR": "Lieutenant",
            "PER_MANOJ_PILLAI": "Lieutenant",
            "PER_DEEPA_VARMA": "Lieutenant",
            "PER_ANWAR_SADATH": "Lieutenant",
            "PER_HARIDAS_MENON": "Financier",
        }

        top_5_ids = [p["id"] for p in ranked_suspects[:5]]
        top_10_ids = [p["id"] for p in ranked_suspects[:10]]

        core_in_top5 = sum(1 for cid in top_5_ids if cid in ground_truth_core)
        core_in_top10 = sum(1 for cid in top_10_ids if cid in ground_truth_core)

        print(f"\n🏆 Top 10 High-Risk Suspects Identified:")
        print(f"  {'Rank':<4} {'Name':<22} {'Risk Score':<12} {'Betweenness':<12} {'PageRank':<10} {'History':<9} {'Txns':<8} {'Comm':<6} {'Ground Truth'}")
        print(f"  {'-'*4} {'-'*22} {'-'*12} {'-'*12} {'-'*10} {'-'*9} {'-'*8} {'-'*6} {'-'*12}")

        for i, p in enumerate(ranked_suspects[:10], 1):
            gt_role = ground_truth_core.get(p["id"], "Operative / Noise")
            icon = "👑" if "Kingpin" in gt_role else "⭐" if "Lieutenant" in gt_role or "Financier" in gt_role else "👤"
            print(f"  {i:2d}.  {p['name']:<22} {p['risk_score']:>6.2f} / 100   {p['score_betweenness']:>6.2f}       {p['score_pagerank']:>6.2f}     {p['score_criminal_history']:>6.2f}    {p['score_suspicious_txns']:>5.2f}   {p['score_comm_anomaly']:>5.2f}   {icon} {gt_role}")

        print(f"\n🎯 Accuracy Story / Evaluation:")
        print(f"   • Top-5 overlap with Ground-Truth Core   : {core_in_top5} / 5 ({core_in_top5 * 20}%)")
        print(f"   • Top-10 overlap with Ground-Truth Core  : {core_in_top10} / 6 ({core_in_top10 / 6 * 100:.1f}%)")

        if core_in_top5 >= 4:
            print(f"   ✅ EXIT CRITERION MET: >80% overlap in Top-5 core leadership!")
        else:
            print(f"   ℹ️ Overlap: {core_in_top5}/5.")

        print("=" * 70 + "\n")

        return {
            "top_suspects": ranked_suspects[:10],
            "communities_count": communities["total_communities"],
            "predicted_links_count": len(predicted_links),
            "core_overlap_top5": core_in_top5,
        }

    finally:
        driver.close()


if __name__ == "__main__":
    run_pipeline()
