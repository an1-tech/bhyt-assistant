# Cẩm nang BHYT · Toàn bệnh viện

## Current UI contract · Ux/Ui · 11/11/2026

Người thực hiện: **Đỗ Quốc An**.

This section supersedes the historical visual contracts below. The user approved the mint medical-squirrel mockups and explicitly requested their implementation. The old achromatic palette and no-image restriction therefore no longer apply.

- One chat input, no sidebar or patient form. Welcome uses an original medical-squirrel illustration, two short example questions and a prominent composer. The welcome and examples disappear during conversation.
- Colours: offwhite `#fafbf5`, white surface, forest ink `#123e36`, teal action `#176756`, mint surface `#e9f3e9`, muted text `#526a62`, border `#dce6dd`. Locally hosted Geist; 16px body, secondary text at least 11px; 12–20px corner radii.
- The approved welcome title uses 52px on desktop, 44px on tablet and 38px on phones. This is a specific welcome-screen exception to the toolkit's compact app-title preference. No large title inside the working conversation.
- Desktop welcome is two columns; phones stack text, mascot and composer. Chat uses an 840px reading column and sticky composer. Controls have visible focus and touch targets of at least 44px. Reduced-motion preferences disable smooth scrolling and transitions.
- Source preview is a native modal dialog: right-side drawer on desktop, near-full-screen on phones; Escape/close returns focus to its trigger. It clones the same verbatim source and highlight spans already displayed in the answer. Original source-page and PDF links remain available.
- Drug quotations use progressive disclosure; conclusions, conditions, uncertainty, confirmation buttons and review status remain visible. Laboratory conditions remain visible in full. Copy retains the complete original answer and citations, including collapsed material.
- Source relevance refinement (12/11/2026): render and copy only citations explicitly linked to the answered drug/lab rows, plus transition rules used by the answer. Do not append automatically retrieved clinical/background groups or repeat an already quoted drug source. A direct policy lookup still shows its policy sources. Keep the full catalogue on the separate Sources page.
- Optional OpenAI assistance (12/11/2026): a changed interpretation is previewed for confirmation with one button and an edit action. The AI editorial plan selects approved wording and emphasizes 1–3 full conditions; remaining drug conditions use an explicit disclosure with a reminder that all conditions apply. Lab conditions stay fully visible. Copy always includes the original full conditions. The composer discloses OpenAI processing when enabled. API failure uses the local answer with a short fallback note. This optional compact presentation supersedes the earlier always-expanded drug-conditions rule.
- No changes to clinical rules, payment conclusions, source freshness claims or reviewer identities. Author attribution uses Đỗ Quốc An; attribution is not a hospital review attestation.
- Check real output at 1440, 768, 390 and 320px, keyboard use, source dialog, failure recovery and conversation reset. Validation details are in `docs/UI_UX_2026-11-11.md`.

## Historical design records

One question: thuốc này có căn cứ BHYT nào và cần đáp ứng điều kiện gì?
Scope: all departments; the department is context, never a filter excluding medicines.
Style: Achromatic ledger, seed 1920156577. No redraws.
Face: clinical blue-grey ground, white evidence sheets, source locators beside each answer.
Signature: the three-part answer Kết luận / Lý do / Nguồn, preserving original conditions.
Shell: no sidebar, labelled top navigation, 1200px centered content, 24px desktop / 16px mobile gutters.
Grid: 1200 = 856 + 24 + 320; below 1000px the context follows the main content.
Type: locally hosted Geist, Vietnamese subset; 16px body, 28px title, 14px metadata.
Tokens: ground #f2f4f7; surface #fff; ink #17191c; muted #535b65; border #dce0e5;
primary #17191c; evidence #1d5fbf; warning #92400e. Radius 8px, controls 6px.
Touch targets >=44px; visible focus; semantic forms; polite live updates; reduced-motion supported.
No images, charts, invented figures, brand logo, deployment or paid API calls required.
Data counts derived from corpus. Source snapshot is a supplied snapshot, not a claim of fresh legal validation.


## UI refinement v1.2 · 06/11/2026
Retain the Achromatic ledger direction and local Geist; improve the working flow rather than add decoration.
Khoa is inside the search form and available on phones before sending. Evidence links are visible beside each source locator; verbatim excerpts stay expandable.
Newest response is shown first; earlier turns collapse and retain their original context. No persistent history or new external data transfer.
Phone catalogue exposes search first, then an accessible expandable group/type filter; no-results includes a reset action.
Metadata type is 13px; body answers 16px desktop / 15px phone. Controls >=44px; response and keyboard focus clear of the sticky header.
Three-part answer and all medical conditions/data remain unchanged. No API key is needed for UI or local lookup.


## Case workbench v1.6 · 07/11/2026
The question: with this product and clinical context, which source conditions match and what is missing?
Keep the existing Achromatic ledger direction, seed 1920156577; no redraw or font/palette change.
Objects: one medication variant, user-entered product identity, non-identifying clinical facts, source-linked criteria.
Data: real imported 1037/59 item lists; five preliminary source-note profiles; no invented product registry.
People: physicians across departments; keyboard on desktop and touch on phones.
Primary job: select a drug and compare a single case; separate generic document lookup remains available.
Face: the clinical evidence sheet, local Geist and blue-grey ground from the existing contract.
Signature: each criterion places the entered fact beside a named status and its expandable evidence.
Grid: case-specific 1200 = 460 + 24 + 716; below 1000px input and evidence stack. Existing lookup keeps its grid.
States: match / mismatch / missing / needs review / recorded; no automatic insurance entitlement approval.
Examples: three explicitly fictional case inputs using real drugs; no fabricated patient identifiers or brand data.
Edits invalidate prior results and copy actions. Copy includes all clinical facts, limitations and source excerpts.
No motion beyond interaction feedback; visible focus, >=44px controls, explicit labels and reduced-motion support.


## Source update v1.7 · 07/11/2026
Keep the existing tokens and case layout. Put newly added clinical references first on the source page. Show publication and check dates separately, per-document quality status and local PDF links. Clinical evidence uses named page citations with collapsed excerpts. Source coverage depends on selected ingredient and indication; a PDF pointer does not imply verified clinical rules or payment authority.


## Chat-only workflow v1.8 · 07/11/2026
This section replaces the v1.6 case-form route as the primary experience. One question: does the source provide BHYT payment for this medicine in this disease/indication? The user's requirement is one chatbot with no patient-detail form. Keep Achromatic ledger, local Geist and the existing palette. Main chat column is capped at 840px and centred; sources retain the wider two-panel desktop layout. One textarea, visible label, Enter to send, Shift+Enter to add a line. Show source conditions in the reply, never require them as patient inputs. Preserve chat order, new-chat reset and copy with provenance. Sources are secondary reference material. No disease-matched conclusion from an unrelated earlier topic. The inspector's unused-canvas warning reflects a horizontal-nav/sidebar heuristic; the capped conversation has equal margins and is intentional.


## Follow-up chips v1.9 · 07/11/2026
Keep tokens, layout and the single chat input. Optional "Hỏi tiếp" chips under an answer reuse the existing .actions button style (>=44px); they send a question, never open a form. Brand-conversion notes use the existing notice style. Drug branches/rates come from data/indication_rules.json.


## Confirmation buttons · 08/11/2026
Unclear conditions are confirmed, not inferred. Each answer may carry a "Xác nhận để đối chiếu" block on the surface token with one labelled group per condition and existing .actions buttons (>=44px), options "met / not met / Chưa rõ". Buttons send structured facts; confirmed conditions stay changeable. Keyboard focus inside the conversation is scrolled clear of the sticky header and composer.

## Laboratory lookup v1.11 · 10/11/2026
Keep Achromatic ledger, local Geist, palette and the centred single chat. The question now covers a medicine or laboratory service, with no new patient form. Objects: HbA1c and EGFR mutation testing; source date, full conditions, optional non-identifying purpose and test dates. Magnitudes: exactly two curated services; do not imply hospital catalogue coverage. Physicians can ask generic conditions immediately or continue a case in the same input. Mixed replies show a laboratory section and a medication section with independent sources. Each lab reply exposes a direct source-row link beside its locator. The reader shows a complete source crop and expandable accessible transcription, plus full PDF/consolidated-document links. Every source link is keyboard reachable, opens separately, and leaves the chat intact. Preserve reduced motion. The 840px capped chat remains deliberately centred; the inspector's existing unused-canvas heuristic is not a sidebar requirement.

## Laboratory lookup completed · 11/11/2026
Objects: 41 laboratory rows with their own payment condition (17 from the TT39 text layer, 24 read from the 17/VBHN-BYT scan); replaces "exactly two curated services". The reply block is a verbatim list titled "Nguyên văn điều kiện trong nguồn": the branch compared with the case is wrapped in `mark` (same yellow as the drug quotation), with one hint line under it. Danh mục 1 rows show the rate column, either paired under each condition (`.lab-rate`) or as a second block. Scan-read rows carry an amber notice and the suffix "chép từ bản scan, chờ thẩm định" in the locator; their reader shows the full page image with the transcription open. Rows without an automatic rule say so in the conclusion; they never use the word "khớp". Unlisted tests and other technical services answer in one paragraph with two document links, no result card. The source catalogue lists the 41 rows inside one collapsed `details`.
