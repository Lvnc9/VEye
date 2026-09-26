/**
 * Page geometry of the form PDF, in millimetres — the same numbers as
 * backend/apps/pdfgen/form_renderer.py, so the designer's A4 canvas looks like
 * the printed page. Change both together.
 */
export const PAGE = {
  portrait: { width: 210, height: 297 },
  landscape: { width: 297, height: 210 },
} as const;

export const MARGIN_SIDE = 12;
export const MARGIN_TOP = 10;
export const MARGIN_BOTTOM = 8;
export const HEADER_HEIGHT = 24;
export const HEADER_GAP = 4;
export const FOOTER_HEIGHT = 16;
export const FOOTER_GAP = 3;
export const LOGO_CELL = 26;
export const META_CELL = 46;

/** Line height as a multiple of the font size (form_renderer.LEADING). */
export const LEADING = 1.55;
/** Points above the base size for heading levels 1–3 (form_renderer.Heading.SIZES). */
export const HEADING_SIZE_BONUS: Record<1 | 2 | 3, number> = { 1: 2.5, 2: 1.5, 3: 0.5 };

export const PT_IN_MM = 25.4 / 72;

// Input elements (form_renderer.py)
export const PHOTO_WIDTH = 30;
export const PHOTO_HEIGHT = 40;
export const PHOTO_GAP = 4;
export const ANSWER_LINE = 8;
export const SIGNATURE_GAP = 3;
