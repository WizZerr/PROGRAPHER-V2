# ProGrapher V15.1.1 — Build Fix

תוקנה שגיאת TSX ב-Darkroom compare stage.

ב-V15.1 היה `</div>` מיותר בין `darkroomZoomLayer` לבין `compareLine`, ולכן Next.js פירש את המשך ה-JSX בצורה שגויה והחזיר `Unterminated regexp literal` בשורה 1696.

הוסר רק ה-closing tag המיותר. אין שינוי בלוגיקת ה-Zoom, ב-Backend או בעיצוב.

הקובץ `page.tsx` עבר בדיקת syntax דרך TypeScript compiler לאחר התיקון.
