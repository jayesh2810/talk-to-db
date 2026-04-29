# Implementation Plan: Prescriptive Retention Engine

The goal is to transition from **Predictive** (Who will churn?) to **Prescriptive** (How do we stop them?). We will implement a "Recovery Path" analysis that finds users who shared similar risk signals but managed to stay active, and extracts the "intervening" factor that saved them.

---

## Phase 1: The "Recovery Path" Logic (Backend)
We need to find "Positive Outliers"—users who looked like they were going to churn but didn't.

1.  **Identify the Risk Profile**: Use the existing `score_churn` to identify the `top_factors` for a high-risk customer.
2.  **Find the "Survivors"**: 
    *   Search the graph for peers with similar `top_factors` (e.g., same `peer_churn_rate` and `days_since_last_order` buckets).
    *   Filter this group for users who are currently **Low Risk** (score < 0.3).
3.  **Extract the Intervention**:
    *   Analyze the most recent events (the last 30 days) for these survivors.
    *   Identify the most frequent "Positive" events:
        *   **Campaigns**: Which campaign did they convert on?
        *   **Products**: Which "Bridge Product" did they purchase?
        *   **Interactions**: Was a specific issue resolved?
4.  **Calculate Success Probability**: $\frac{\text{Survivors who took Action A}}{\text{Total peers with similar risk profiles}}$.

## Phase 2: Engine & API Integration
1.  **`backend/prediction/engine.py`**: 
    *   Create a new function `get_prescriptive_action(customer_id, risk_signals)`.
    *   This function will coordinate the "Survivor" search and event extraction.
2.  **`backend/pql/executor.py`**:
    *   Update `_run_churn` to call `get_prescriptive_action` for every customer in the result set.
    *   Add `recommended_action` and `success_probability` to the result rows.
3.  **`backend/models/schemas.py`**:
    *   Update the result schema to include the new prescriptive fields.

## Phase 3: LLM & UI Enhancement
1.  **`backend/llm/prompts.py`**:
    *   Update `SUMMARIZATION_SYSTEM` to synthesize the risk and the cure.
    *   *Prompt Change*: "Instead of just reporting risk, identify the `recommended_action` and explain it as a data-backed strategy: 'We recommend [Action] because it successfully recovered X% of similar customers.'"
2.  **Frontend (`frontend/src/components/...`)**:
    *   Update the results table to display the **Recommended Action** and **Confidence Score**.
    *   Add a visual indicator (e.g., a "Save" badge) for customers with a high-probability recovery path.

---

## Summary of Changes

| Component | File | Change |
| :--- | :--- | :--- |
| **Logic** | `backend/prediction/engine.py` | Add `get_prescriptive_action()` logic |
| **Execution** | `backend/pql/executor.py` | Integrate prescription into `_run_churn` |
| **Schema** | `backend/models/schemas.py` | Add `recommended_action` and `success_probability` |
| **Reasoning** | `backend/llm/prompts.py` | Update prompt to explain the "Cure" |
| **UI** | `frontend/src/...` | Display prescriptions in the results table |
