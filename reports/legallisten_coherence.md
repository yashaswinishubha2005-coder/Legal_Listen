# LegalListen conversation coherence (offline mode)

40 hand-written natural client messages (eval/legallisten_coherence.jsonl). Written by the developers; used to find and fix off-topic questioning, so the scores are optimistic — not a blind test.

- Correct issue identified or offered for the client to choose: **1.0**
- Fact questions outside the client's legal area: **0.0**
- Facts already stated that were asked again: **0**
- Mean fact questions: 2.1 · cases where the client was asked to pick the problem: 2

| id | lang | gold | considered | offered choice | ok | asked | off-topic |
|---|---|---|---|---|---|---|---|
| c01 | en | prop.forged_documents | prop.forged_documents |  | ✓ | 2 | 0 |
| c02 | en | prop.forged_documents | prop.coheir_sale_without_consent, prop.forged_documents |  | ✓ | 5 | 0 |
| c03 | en | prop.inheritance_partition | prop.inheritance_partition |  | ✓ | 2 | 0 |
| c04 | en | prop.encroachment | prop.encroachment |  | ✓ | 3 | 0 |
| c05 | en | prop.coheir_sale_without_consent | prop.coheir_sale_without_consent, prop.inheritance_partition |  | ✓ | 5 | 0 |
| c06 | en | prop.boundary_dispute | prop.boundary_dispute |  | ✓ | 3 | 0 |
| c07 | en | crim.hurt_assault | crim.hurt_assault |  | ✓ | 2 | 0 |
| c08 | en | crim.theft | crim.theft |  | ✓ | 2 | 0 |
| c09 | en | crim.cheating | crim.cheating |  | ✓ | 2 | 0 |
| c10 | en | crim.police_refusal_fir | crim.police_refusal_fir |  | ✓ | 1 | 0 |
| c11 | en | crim.criminal_intimidation | crim.criminal_intimidation |  | ✓ | 2 | 0 |
| c12 | en | fam.divorce | fam.divorce |  | ✓ | 0 | 0 |
| c13 | en | fam.maintenance | fam.maintenance | fam.domestic_violence, fam.maintenance, fam.custody, other | ✓ | 2 | 0 |
| c14 | en | fam.domestic_violence | fam.domestic_violence |  | ✓ | 2 | 0 |
| c15 | en | fam.dowry_harassment | fam.domestic_violence, fam.dowry_harassment |  | ✓ | 3 | 0 |
| c16 | en | fam.custody | fam.custody |  | ✓ | 2 | 0 |
| c17 | en | cyb.phishing_account_takeover | cyb.phishing_account_takeover |  | ✓ | 1 | 0 |
| c18 | en | cyb.upi_payment_fraud | cyb.upi_payment_fraud |  | ✓ | 3 | 0 |
| c19 | en | cyb.impersonation | cyb.impersonation | cyb.impersonation, cyb.cyberstalking, cyb.morphed_intimate_image, fin.unauthorized_bank_txn, other | ✓ | 1 | 0 |
| c20 | en | cyb.cyberstalking | cyb.cyberstalking |  | ✓ | 1 | 0 |
| c21 | en | cyb.morphed_intimate_image | cyb.morphed_intimate_image |  | ✓ | 2 | 0 |
| c22 | en | con.defective_product | con.defective_product |  | ✓ | 1 | 0 |
| c23 | en | con.deficiency_in_service | con.deficiency_in_service |  | ✓ | 2 | 0 |
| c24 | en | fin.unauthorized_bank_txn | fin.unauthorized_bank_txn |  | ✓ | 2 | 0 |
| c25 | en | con.refund_refusal | con.refund_refusal |  | ✓ | 3 | 0 |
| c26 | en | fin.loan_recovery_harassment | fin.loan_recovery_harassment |  | ✓ | 1 | 0 |
| c27 | kn | prop.forged_documents | prop.forged_documents |  | ✓ | 2 | 0 |
| c28 | kn | prop.inheritance_partition | prop.inheritance_partition |  | ✓ | 1 | 0 |
| c29 | kn | fam.maintenance | fam.maintenance |  | ✓ | 1 | 0 |
| c30 | kn | cyb.impersonation | cyb.impersonation |  | ✓ | 1 | 0 |
| c31 | kn | con.defective_product | con.defective_product |  | ✓ | 2 | 0 |
| c32 | kn | crim.theft | crim.theft |  | ✓ | 3 | 0 |
| c33 | hi | prop.forged_documents | prop.encroachment, prop.forged_documents |  | ✓ | 3 | 0 |
| c34 | hi | prop.encroachment | prop.encroachment |  | ✓ | 2 | 0 |
| c35 | hi | fam.dowry_harassment, fam.domestic_violence | fam.domestic_violence, fam.dowry_harassment |  | ✓ | 2 | 0 |
| c36 | hi | cyb.upi_payment_fraud, cyb.phishing_account_takeover, fin.unauthorized_bank_txn | cyb.phishing_account_takeover |  | ✓ | 3 | 0 |
| c37 | hi | crim.cheating | crim.cheating |  | ✓ | 2 | 0 |
| c38 | hi | fam.custody | fam.custody |  | ✓ | 2 | 0 |
| c39 | kn | fin.loan_recovery_harassment | fin.loan_recovery_harassment |  | ✓ | 2 | 0 |
| c40 | en | prop.forged_documents, prop.inheritance_partition | prop.forged_documents |  | ✓ | 3 | 0 |
