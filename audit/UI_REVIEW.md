# UI review — interface v1.2

Direction preserved: Achromatic ledger, seed 1920156577. No redraw. The face remains clinical blue-grey, quiet white sheets and local Geist. Main question: what is the source basis for this medicine, and which condition or route remains to check?

## Observed before / after

Both inspected builds have 0 FAIL / 0 WARN at 1440, 768, 390px. The refinement concerns use and reading rather than a claimed change in the machine score.

1. Search context: the department moved from the side rail to the form, making it available before submission on phones. Header action remains on one row after fixing an observed mobile stacking issue.
2. Evidence: document links are visible next to the appendix/STT and route; expanding is required only for the original excerpt. Route variants no longer have indistinguishable headings.
3. History: latest answer leads; earlier turns collapse. A browser test switched from Paracetamol to Metformin, reopened the earlier Paracetamol turn, selected injection, and correctly received Paracetamol.
4. Phone catalogue: collapsed filters allow initial rows earlier in the viewport. The count reflects selected filters; the zero-result action restores all 1096 items.
5. Keyboard: Metfo suggestions prioritize Metformin. ArrowDown focuses it; Escape returns to the textarea and hides suggestions. Controls retain visible focus and labels.
6. Tablet: a half-width orphan source panel seen in the first iteration was replaced by a full-width three-metric strip.
7. Counts remain 1037 + 59 = 1096 unique items, 1194 variants and 1243 evidence chunks. All display counts come from the existing metadata. No medical source rows changed.

All final inspector screenshots and the extra 375px reduced-motion, 844px landscape, catalogue and sources images were opened and reviewed. No horizontal overflow was found. Reduced motion renders with zero transitions and auto scroll. Source font remains actually loaded Geist.

No photos, charts, decorative motion, framework migration, generated metrics or API calls were introduced. No inspector exceptions were used. The existing 45 backend/data/HTTP tests passed.

Limits: long verbatim legal conditions still require vertical scrolling by design. Screen-reader audio and physical devices were not tested. Hospital/clinical review and real AI API testing remain outside this UI change.
