# Provision verification checklist (Gate 1)

Every provision the benchmark cites is listed here. **All are TO_VERIFY.** A human must open the official text, confirm that the section exists, that its heading matches the hint, and that it applies to the issue, and only then mark it `verified` in `data/corpus/provision_registry.jsonl`.

- Provisions referenced: **79**
- Found in the parsed corpus: **73** (the corpus is empty until the Act PDFs are added)

| Provision | Title hint (expected heading) | In corpus | Heading match | Old/new mapping | Used by | Note | Verified by | Date |
|---|---|---|---|---|---|---|---|---|
| `BNS:115(2)` | Voluntarily causing hurt | yes | yes | IPC:323 | crim.hurt_assault |  |  |  |
| `BNS:118(1)` | Voluntarily causing hurt by dangerous weapons or means | yes | yes | IPC:324 | crim.hurt_assault | only if the weapon/means qualifies; verify |  |  |
| `BNS:303(2)` | Theft (punishment) | yes | yes | IPC:379 | crim.theft |  |  |  |
| `BNS:318(4)` | Cheating and dishonestly inducing delivery of property | yes | yes | IPC:420 | crim.cheating, cyb.phishing_account_takeover, cyb.upi_payment_fraud |  |  |  |
| `BNS:319(2)` | Cheating by personation (punishment) | yes | yes | IPC:419 | cyb.impersonation |  |  |  |
| `BNS:329(3)` | Criminal trespass (punishment) | yes | yes | IPC:447 | prop.encroachment |  |  |  |
| `BNS:336` | Forgery | yes | yes |  | prop.forged_documents |  |  |  |
| `BNS:338` | Forgery of valuable security, will, etc. | yes | yes | IPC:467 | prop.forged_documents |  |  |  |
| `BNS:340` | Forged document or electronic record and using it as genuine | yes | yes | IPC:471 | prop.forged_documents |  |  |  |
| `BNS:351(2)` | Criminal intimidation (punishment) | yes | yes | IPC:506 | crim.criminal_intimidation, cyb.cyberstalking, fin.loan_recovery_harassment |  |  |  |
| `BNS:351(3)` | Threat to cause death or grievous hurt | yes | **NO** |  | crim.criminal_intimidation |  |  |  |
| `BNS:356(2)` | Defamation (punishment) | yes | yes | IPC:500 | fin.loan_recovery_harassment |  |  |  |
| `BNS:78` | Stalking | yes | yes | IPC:354D | cyb.cyberstalking |  |  |  |
| `BNS:79` | Word, gesture or act intended to insult the modesty of a woman | yes | yes | IPC:509 | cyb.morphed_intimate_image |  |  |  |
| `BNS:85` | Husband or relative of husband of a woman subjecting her to cruelty | yes | yes | IPC:498A | fam.domestic_violence, fam.dowry_harassment |  |  |  |
| `BNS:86` | Cruelty defined | yes | yes |  | fam.dowry_harassment |  |  |  |
| `BNSS:144` | Order for maintenance of wives, children and parents | yes | yes |  | fam.maintenance | applies irrespective of religion; verify |  |  |
| `BNSS:173` | Information in cognizable cases | yes | yes | CrPC:154 | crim.cheating, crim.police_refusal_fir, crim.theft, cyb.upi_payment_fraud | sub-section (4) on approaching the Superintendent of Police; verify |  |  |
| `BNSS:174` | Information as to non-cognizable cases | yes | yes | CrPC:155 | crim.criminal_intimidation, crim.hurt_assault | cognizability depends on the limb; verify; simple hurt may be non-cognizable; verify |  |  |
| `BNSS:175(3)` | Magistrate may order investigation | yes | **NO** | CrPC:156(3) | crim.police_refusal_fir |  |  |  |
| `CPA:2(10)` | Defect (definition) | yes | **NO** |  | con.defective_product |  |  |  |
| `CPA:2(11)` | Deficiency (definition) | yes | **NO** |  | con.deficiency_in_service, con.refund_refusal, fin.unauthorized_bank_txn | banking is a service; verify applicability |  |  |
| `CPA:2(47)` | Unfair trade practice (definition) | yes | **NO** |  | con.refund_refusal |  |  |  |
| `CPA:2(7)` | Consumer (definition) | yes | **NO** |  | con.defective_product |  |  |  |
| `CPA:35` | Manner in which complaint shall be made | yes | yes |  | con.defective_product, con.deficiency_in_service, con.refund_refusal, fin.unauthorized_bank_txn |  |  |  |
| `CPA:69` | Limitation period | yes | yes |  | con.defective_product, con.deficiency_in_service, con.refund_refusal |  |  |  |
| `CPA:84` | Liability of product manufacturer | yes | yes |  | con.defective_product |  |  |  |
| `CrPC:154` | Information in cognizable cases | no |  | BNSS:173 | crim.cheating, crim.police_refusal_fir, crim.theft, cyb.upi_payment_fraud | sub-section (3) on SP; verify |  |  |
| `CrPC:155` | Information as to non-cognizable cases | no |  | BNSS:174 | crim.criminal_intimidation, crim.hurt_assault |  |  |  |
| `CrPC:156(3)` | Magistrate may order investigation | no |  | BNSS:175(3) | crim.police_refusal_fir |  |  |  |
| `DPA:3` | Penalty for giving or taking dowry | yes | yes |  | fam.dowry_harassment |  |  |  |
| `DPA:4` | Penalty for demanding dowry | yes | yes |  | fam.dowry_harassment |  |  |  |
| `GWA:17` | Matters to be considered by the Court in appointing guardian | yes | yes |  | fam.custody |  |  |  |
| `GWA:25` | Title of guardian to custody of ward | yes | yes |  | fam.custody |  |  |  |
| `GWA:7` | Power of the Court to make order as to guardianship | yes | yes |  | fam.custody |  |  |  |
| `HMA:13` | Divorce | yes | yes |  | fam.divorce |  |  |  |
| `HMA:13B` | Divorce by mutual consent | yes | yes |  | fam.divorce |  |  |  |
| `HMA:14` | No petition for divorce to be presented within one year of marriage | yes | yes |  | fam.divorce |  |  |  |
| `HSA:22` | Preferential right to acquire property in certain cases | yes | yes |  | prop.coheir_sale_without_consent |  |  |  |
| `HSA:6` | Devolution of interest in coparcenary property | yes | yes |  | prop.inheritance_partition |  |  |  |
| `HSA:8` | General rules of succession in the case of males | yes | yes |  | prop.inheritance_partition |  |  |  |
| `IPC:323` | Punishment for voluntarily causing hurt | yes | yes | BNS:115(2) | crim.hurt_assault |  |  |  |
| `IPC:324` | Voluntarily causing hurt by dangerous weapons or means | yes | yes | BNS:118(1) | crim.hurt_assault | only if the weapon/means qualifies; verify |  |  |
| `IPC:354D` | Stalking | yes | yes | BNS:78 | cyb.cyberstalking |  |  |  |
| `IPC:379` | Punishment for theft | yes | yes | BNS:303(2) | crim.theft |  |  |  |
| `IPC:419` | Punishment for cheating by personation | yes | yes | BNS:319(2) | cyb.impersonation |  |  |  |
| `IPC:420` | Cheating and dishonestly inducing delivery of property | yes | yes | BNS:318(4) | crim.cheating, cyb.phishing_account_takeover, cyb.upi_payment_fraud |  |  |  |
| `IPC:447` | Punishment for criminal trespass | yes | yes | BNS:329(3) | prop.encroachment |  |  |  |
| `IPC:467` | Forgery of valuable security, will, etc. | yes | yes | BNS:338 | prop.forged_documents |  |  |  |
| `IPC:471` | Using as genuine a forged document or electronic record | yes | yes | BNS:340 | prop.forged_documents |  |  |  |
| `IPC:498A` | Husband or relative of husband of a woman subjecting her to cruelty | yes | yes | BNS:85 | fam.domestic_violence, fam.dowry_harassment |  |  |  |
| `IPC:500` | Punishment for defamation | yes | yes | BNS:356(2) | fin.loan_recovery_harassment |  |  |  |
| `IPC:506` | Punishment for criminal intimidation | yes | yes | BNS:351(2) | crim.criminal_intimidation, fin.loan_recovery_harassment |  |  |  |
| `IPC:509` | Word, gesture or act intended to insult the modesty of a woman | yes | yes | BNS:79 | cyb.morphed_intimate_image |  |  |  |
| `ITA:43` | Penalty and compensation for damage to computer system | yes | yes |  | cyb.phishing_account_takeover, fin.unauthorized_bank_txn |  |  |  |
| `ITA:66` | Computer related offences | yes | yes |  | cyb.phishing_account_takeover |  |  |  |
| `ITA:66C` | Punishment for identity theft | yes | yes |  | cyb.impersonation, cyb.phishing_account_takeover, fin.unauthorized_bank_txn |  |  |  |
| `ITA:66D` | Punishment for cheating by personation by using computer resource | yes | yes |  | cyb.impersonation, cyb.phishing_account_takeover, cyb.upi_payment_fraud |  |  |  |
| `ITA:66E` | Punishment for violation of privacy | yes | yes |  | cyb.morphed_intimate_image |  |  |  |
| `ITA:67` | Punishment for publishing or transmitting obscene material in electronic form | yes | yes |  | cyb.morphed_intimate_image |  |  |  |
| `ITA:67A` | Punishment for publishing or transmitting material containing sexually explicit act in electronic form | yes | yes |  | cyb.morphed_intimate_image |  |  |  |
| `KLRA:TBD-boundary` | Karnataka Land Revenue Act: provisions on survey and boundary marks | no |  |  | prop.boundary_dispute | section number deliberately NOT assigned; identify from the parsed Act |  |  |
| `LIMA:Art.110` | Suit by a person excluded from joint family property to enforce a right to share | no |  |  | prop.inheritance_partition | Schedule article; numbering to be verified |  |  |
| `LIMA:Art.59` | To cancel or set aside an instrument | no |  |  | prop.coheir_sale_without_consent | Schedule article; numbering to be verified |  |  |
| `PWDV:12` | Application to Magistrate | yes | yes |  | fam.domestic_violence |  |  |  |
| `PWDV:18` | Protection orders | yes | yes |  | fam.domestic_violence |  |  |  |
| `PWDV:19` | Residence orders | yes | yes |  | fam.domestic_violence |  |  |  |
| `PWDV:20` | Monetary reliefs | yes | yes |  | fam.maintenance |  |  |  |
| `PWDV:3` | Definition of domestic violence | yes | yes |  | fam.domestic_violence |  |  |  |
| `RA:17` | Documents of which registration is compulsory | yes | yes |  | prop.inheritance_partition | a partition deed of immovable property generally needs registration; verify |  |  |
| `SMA:27` | Divorce | yes | yes |  | fam.divorce |  |  |  |
| `SMA:28` | Divorce by mutual consent | yes | yes |  | fam.divorce |  |  |  |
| `SRA:31` | When cancellation may be ordered | yes | yes |  | prop.coheir_sale_without_consent, prop.forged_documents |  |  |  |
| `SRA:34` | Discretion of court as to declaration of status or right | yes | yes |  | prop.boundary_dispute |  |  |  |
| `SRA:38` | Perpetual injunction when granted | yes | yes |  | prop.boundary_dispute, prop.encroachment |  |  |  |
| `SRA:5` | Recovery of specific immovable property | yes | yes |  | prop.encroachment |  |  |  |
| `SRA:6` | Suit by person dispossessed of immovable property | yes | yes |  | prop.encroachment | summary remedy within six months of dispossession; verify |  |  |
| `TPA:44` | Transfer by one co-owner | yes | yes |  | prop.coheir_sale_without_consent |  |  |  |
| `TPA:54` | Sale defined | yes | yes |  | prop.coheir_sale_without_consent |  |  |  |
