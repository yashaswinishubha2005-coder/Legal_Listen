# LegalListen system evaluation (offline mode, no LLM)

Interactive simulation on the LexVaani-IN **test** split: 1014 consultations (every test narrative, all six language variants). The simulated client answers from the hidden scenario spec.

| Metric | Adaptive policy (LegalListen) | Fixed questionnaire baseline |
|---|---|---|
| Issue identification micro-F1 (T1, end of consultation) | 0.98 | 0.98 |
| Critical facts correctly established (revealable ones) | 0.935 | 0.935 |
| Questions asked (mean) | 2.368 | 2.743 |
| Questions asked (median) | 2.0 | 2.0 |
| Triage accuracy (T13) | 0.98 | 0.98 |
| Urgent-case recall (T13) | 0.996 | 0.996 |
| IPC/BNS regime routed correctly | 0.987 | 0.983 |
| Provision precision (T10) | 0.961 | 0.961 |
| Provision recall (T10) | 0.989 | 0.989 |
| Provision F1 (T10) | 0.969 | 0.969 |
| Case Graphs passing structural validation | 1 | 1 |

Per language variant (adaptive): exact issue-set match / mean questions

| variant | exact issue set | questions |
|---|---|---|
| en | 0.923 | 2.26 |
| hi | 0.941 | 2.467 |
| hi-en_latn | 0.935 | 2.172 |
| kn | 0.959 | 2.515 |
| kn-en_latn | 0.964 | 2.337 |
| kn-en_mixed | 0.994 | 2.456 |

## Free-form narratives (hand-written, opening turn only)

36 short narratives written by the developers in English, Kannada, Hindi and romanised Kanglish / Hinglish (eval/legallisten_freeform.jsonl). Not template-generated, not native-reviewed, and **used during development** to tune the rule cues (co-occurrence and risk keywords) — so these scores are optimistic and are not a blind test.

- Gold issue among the top-3 hypotheses after the first message: **1.0** (by language: {'en': 1.0, 'kn': 1.0, 'hi': 1.0})
- Top-1 hypothesis correct: **1.0**
- Urgent cases flagged from the first message: **1.0** recall, 0 false alarms

| id | lang | gold | top-3 hypotheses | hit@3 | risks |
|---|---|---|---|---|---|
| ff01 | en | prop.coheir_sale_without_consent, prop.inheritance_partition | prop.inheritance_partition, prop.coheir_sale_without_consent | ✓ |  |
| ff02 | en | crim.hurt_assault | crim.hurt_assault | ✓ |  |
| ff03 | en | cyb.upi_payment_fraud | cyb.upi_payment_fraud | ✓ | golden_hour_fraud |
| ff04 | en | con.defective_product | con.defective_product | ✓ |  |
| ff05 | en | fam.domestic_violence, fam.dowry_harassment | fam.dowry_harassment, fam.domestic_violence | ✓ | ongoing_abuse |
| ff06 | en | cyb.impersonation | cyb.impersonation | ✓ |  |
| ff07 | en | crim.police_refusal_fir, crim.theft | crim.police_refusal_fir, crim.theft | ✓ |  |
| ff08 | en | fin.loan_recovery_harassment | fin.loan_recovery_harassment, crim.cheating | ✓ |  |
| ff09 | en | x.out_of_scope |  | ✓ |  |
| ff10 | en | prop.encroachment | prop.encroachment | ✓ |  |
| ff11 | en | cyb.morphed_intimate_image | cyb.morphed_intimate_image | ✓ |  |
| ff12 | en | con.refund_refusal | con.refund_refusal | ✓ |  |
| ff13 | kn | prop.coheir_sale_without_consent, prop.inheritance_partition | prop.coheir_sale_without_consent, prop.inheritance_partition | ✓ |  |
| ff14 | kn | crim.hurt_assault | crim.hurt_assault | ✓ |  |
| ff15 | kn | cyb.upi_payment_fraud | cyb.upi_payment_fraud | ✓ | golden_hour_fraud |
| ff16 | kn | fam.domestic_violence, fam.dowry_harassment | fam.dowry_harassment, fam.domestic_violence | ✓ | ongoing_abuse |
| ff17 | kn | prop.encroachment | prop.encroachment | ✓ |  |
| ff18 | kn | con.defective_product | con.defective_product | ✓ |  |
| ff19 | kn | cyb.impersonation | cyb.impersonation | ✓ |  |
| ff20 | kn | fam.maintenance | fam.maintenance | ✓ |  |
| ff21 | kn | crim.police_refusal_fir, crim.theft | crim.theft, crim.police_refusal_fir | ✓ |  |
| ff22 | kn | x.non_legal |  | ✓ |  |
| ff23 | kn | fin.loan_recovery_harassment | fin.loan_recovery_harassment, cyb.cyberstalking, crim.cheating | ✓ |  |
| ff24 | kn | prop.forged_documents | prop.forged_documents | ✓ |  |
| ff25 | hi | prop.coheir_sale_without_consent, prop.inheritance_partition | prop.coheir_sale_without_consent | ✓ |  |
| ff26 | hi | crim.hurt_assault | crim.hurt_assault | ✓ |  |
| ff27 | hi | cyb.upi_payment_fraud | cyb.upi_payment_fraud | ✓ | golden_hour_fraud |
| ff28 | hi | fam.domestic_violence, fam.dowry_harassment | fam.domestic_violence, fam.dowry_harassment | ✓ | ongoing_abuse |
| ff29 | hi | con.refund_refusal | con.refund_refusal | ✓ |  |
| ff30 | hi | fam.custody | fam.custody | ✓ |  |
| ff31 | hi | cyb.morphed_intimate_image | cyb.morphed_intimate_image | ✓ |  |
| ff32 | hi | fin.unauthorized_bank_txn | fin.unauthorized_bank_txn | ✓ |  |
| ff33 | hi | crim.criminal_intimidation | crim.criminal_intimidation | ✓ |  |
| ff34 | hi | con.deficiency_in_service | con.deficiency_in_service | ✓ |  |
| ff35 | kn | cyb.cyberstalking | cyb.cyberstalking | ✓ |  |
| ff36 | kn | x.out_of_scope |  | ✓ |  |

## How to read these numbers

- The interactive numbers use template-generated narratives and a simulated client that always answers truthfully from the scenario, so they are an **upper bound** for real conversations.
- The free-form probe is small (36 items), written by the developers and used while tuning the rule cues; a blind, native-speaker-written test set is still needed. With Gemini enabled, extraction is done by the LLM (not measured here).
- Provision metrics compare against the dataset's gold provision ids, which are themselves TO_VERIFY.
