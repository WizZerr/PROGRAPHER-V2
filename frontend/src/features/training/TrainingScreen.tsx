import FeatureScreen from "@/components/common/FeatureScreen";

export default function TrainingScreen() {
  return (
    <FeatureScreen
      eyebrow="למידת הסגנון"
      title="מעבדת למידה"
      description="כאן ינוהלו Dataset, בדיקות איכות והשוואות בין גרסאות המוח — בלי להציג מדדי איכות שלא נמדדו בפועל."
      modules={[
        {
          title: "הכנת חומר",
          description: "בדיקת זוגות RAW ועריכות סופיות לפני שהם נכנסים לאימון.",
        },
        {
          title: "השוואת מודלים",
          description: "השוואה עקבית מול Baseline וגרסאות מוח קודמות על אותם נתונים.",
        },
        {
          title: "בדיקת איכות",
          description: "תוצאות מספריות ובדיקה אנושית לפני סימון מודל כמוכן.",
        },
      ]}
    />
  );
}
