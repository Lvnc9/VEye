/**
 * Placeholder. The desktop app had a تنظیمات button in its sidebar too, but it
 * was never wired to anything (V_1.0 main.py:938 points it at change_to_poster,
 * which raises TypeError when called with no arguments). Kept as a nav entry
 * pending a decision on what settings should actually contain.
 */
export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">تنظیمات</h1>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
        این بخش هنوز پیاده‌سازی نشده است.
      </div>
    </div>
  );
}
