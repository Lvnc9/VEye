import { FileQuestion } from "lucide-react";
import { ErrorScreen } from "@/components/ErrorScreen";

export default function NotFound() {
  return (
    <ErrorScreen
      fullPage
      code="۴۰۴"
      icon={<FileQuestion />}
      title="صفحه‌ای پیدا نشد"
      message="نشانی را اشتباه وارد کرده‌اید یا این صفحه دیگر وجود ندارد."
    />
  );
}
