# Data dictionary

| Field | Meaning / handling |
|---|---|
| complaint_id | Public complaint ID; unique and nonmissing required. |
| received / sent | Source timestamps parsed as UTC; analytical dates use UTC. |
| product | Mortgage filter validated locally. |
| issue / subissue | Original complaint categories; not confirmed causes. |
| company | Named provider in public data, not a measure of exposure. |
| channel | Submitted-via category; missing values displayed as Not provided. |
| response | Published company-response category, not independent resolution verification. |
| timely | Original Yes/No label. Unknown labels remain outside the rate denominator. |
| late_response | Yes→0, No→1, anything else→null. |
| forwarding_days | Calendar days between received and sent. Negative intervals excluded from lag summaries and audited. |
| known_timeliness | Number of Yes/No labels, denominator of late-response rate. |
| wilson_low / wilson_high | 95% Wilson bounds; independent-binomial model, not a correction for selection bias. |

Date window is enforced locally as [2024-01-01, 2025-01-01). Original export contains records beyond the year. No narrative text is present. ZIP codes and tags are unused; raw fields remain in the local source download. Issue-rate chart shows categories with at least 100 known labels; CSV output retains all categories.
