import FeatureScreen from "@/components/common/FeatureScreen";

export default function GalleryScreen() {
  return (
    <FeatureScreen
      eyebrow="ספריית התמונות"
      title="גלריה"
      description="מרכז העבודה הוויזואלי של האירוע: תמונות, סטטוס עיבוד, בחירות וחלוקה לסצנות."
      modules={[
        {
          title: "תצוגת תמונות",
          description: "גריד מהיר לעבודה עם אלפי תמונות בלי להעמיס על הממשק.",
        },
        {
          title: "סטטוס עריכה",
          description: "הפרדה ברורה בין תמונות מוכנות, לבדיקה ולטיפול ידני.",
        },
        {
          title: "סצנות ורצפים",
          description: "קיבוץ תמונות לפי הקשר האירוע כשמנוע הסצנות יהיה פעיל.",
        },
      ]}
    />
  );
}
