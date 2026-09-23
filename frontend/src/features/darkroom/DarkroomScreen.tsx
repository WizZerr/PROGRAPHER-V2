import FeatureScreen from "@/components/common/FeatureScreen";

export default function DarkroomScreen() {
  return (
    <FeatureScreen
      eyebrow="סביבת עריכה"
      title="חדר עריכה"
      description="סביבת הבדיקה המקצועית של ProGrapher לפני העברה ל-Lightroom — תמונה גדולה, בקרות מדויקות והשוואה נקייה."
      modules={[
        {
          title: "תמונה לפני ואחרי",
          description: "השוואה ישירה תוך שמירה על המקור ללא שינוי.",
        },
        {
          title: "בקרות עריכה",
          description: "Exposure, White Balance ובקרות נוספות לפי חוזה העריכה המאומת.",
        },
        {
          title: "אישור ותיקון",
          description: "אישור תוצאה, סימון לתיקון ומשוב שישמש את תהליך הלמידה.",
        },
      ]}
    />
  );
}
