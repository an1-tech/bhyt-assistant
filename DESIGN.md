# Cẩm nang BHYT · Toàn bệnh viện

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
