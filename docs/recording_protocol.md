# Recording and human-writing protocol (`test_human/`, audio)

v0.1 ships **no** audio and **no** human-written items. This protocol must be followed before any are added.

## 1. Consent and ethics
- Participants are adults (18+) who give informed, written consent (`consent_form_id` in `data/audio/manifest.csv`),
  covering recording, annotation, and release under the dataset licence. They may withdraw at any time; withdrawn
  items are deleted in the next release.
- Obtain institutional ethics approval (IRB/IEC) before collection.
- **Participants never tell their own legal problems.** They read or retell a *synthetic* scenario card
  (generated from a `test`-split spec) in their own words. No real names, addresses, phone or account numbers:
  card slots use the synthetic name lists in `resources/lexicon.yaml`.
- Topics include domestic violence and intimate-image abuse; participants may skip any card, and helpline
  information (112, 181, 1930) is shown at the end of each session.

## 2. Scenario cards
- One card = issue, key facts (as bullet points, not sentences), the conversation date, and the language variant
  to use. Cards come only from test-split families, so human items never leak into train/dev.
- Writers produce: (a) a free narrative (60–200 words), (b) optionally a spoken version of the same.

## 3. Audio
| Item | Requirement |
|---|---|
| Format | WAV, 16 kHz, 16-bit, mono |
| Devices | the participant's own phone (record `device`), no studio |
| Environments | quiet room, street/market, inside a vehicle (record `environment`) |
| Length | 20–120 s per narrative |
| Speakers | balance gender, age group, region (North / South Karnataka, Hindi belt), urban/rural |

## 4. Transcription and annotation
1. Verbatim transcription in the variant's script (romanised for `*-en_latn`), keeping disfluencies; no normalisation.
2. Annotate with `docs/annotation_guidelines.md`, two annotators per item, adjudicated; report IAA.
3. Validate with `NarrativeSample` (exact spans) before release; store under `release/.../test_human/`.

## 5. Manifest
`data/audio/manifest.csv` columns: `audio_id, speaker_id, sample_id, lang_variant, device, environment,
duration_sec, sample_rate_hz, consent_form_id, transcript_path, recorded_on`. `speaker_id` is a random pseudonym;
the mapping to real identities is stored separately, offline, and never released.
