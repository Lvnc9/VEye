"use client";

import { useState, type FormEvent } from "react";
import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  computeTitle,
  type AccessLevel,
  type AccessRoll,
  type PersonnelWritePayload,
} from "@/lib/types";
import { apiPost, ApiError } from "@/lib/api-client";
import { ErrorBanner, LoadingBanner } from "@/components/StatusBanner";
import { useCurrentUser } from "@/lib/current-user";

/**
 * Personnel Register page (skeleton.md §2/§3).
 *
 * Deviation note: the "Select" button previews the resulting Title by
 * computing it CLIENT-SIDE against the same 3x3 TITLE_MATRIX the backend
 * uses (lib/types.ts), rather than calling GET /personnel/{id}/title/.
 * That endpoint needs an existing personnel id, which doesn't exist yet
 * for a brand-new registration — computing locally gives an instant
 * preview before Save, matching V1's "Select" button behavior.
 */
export default function PersonnelRegisterPage() {
  const { can, loading: userLoading } = useCurrentUser();
  const [fullName, setFullName] = useState("");
  const [nationalCode, setNationalCode] = useState("");
  const [mobilePhone, setMobilePhone] = useState("");
  const [accessRoll, setAccessRoll] = useState<AccessRoll>("EMPLOYER");
  const [accessLevel, setAccessLevel] = useState<AccessLevel>("L1");
  const [password, setPassword] = useState("");

  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function handleSelect() {
    setPreviewTitle(computeTitle(accessRoll, accessLevel));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const payload: PersonnelWritePayload = {
        full_name: fullName,
        national_code: nationalCode,
        mobile_phone: mobilePhone,
        access_roll: accessRoll,
        access_level: accessLevel,
        ...(password ? { password } : {}),
      };
      await apiPost("/personnel/", payload);
      setSuccess("پروفایل پرسنل با موفقیت ثبت شد.");
      setFullName("");
      setNationalCode("");
      setMobilePhone("");
      setPassword("");
      setPreviewTitle(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت پروفایل پرسنل ممکن نشد.");
    } finally {
      setSaving(false);
    }
  }

  if (userLoading) return <LoadingBanner />;
  if (!can("manage_personnel")) {
    return (
      <div className="max-w-xl">
        <h1 className="mb-4 text-2xl font-bold text-slate-900">ساخت پروفایل پرسنل</h1>
        <ErrorBanner message="شما دسترسی لازم برای مدیریت پرسنل را ندارید." />
      </div>
    );
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">ساخت پروفایل پرسنل</h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        {error && <ErrorBanner message={error} />}
        {success && (
          <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
            {success}
          </div>
        )}

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">نام و نام خانوادگی</label>
          <input
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">کد ملی</label>
          <input
            type="text"
            required
            value={nationalCode}
            onChange={(e) => setNationalCode(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">تلفن همراه</label>
          <input
            type="text"
            required
            value={mobilePhone}
            onChange={(e) => setMobilePhone(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">رمز عبور اولیه</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
            placeholder="اختیاری"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">نوع دسترسی</label>
            <select
              value={accessRoll}
              onChange={(e) => setAccessRoll(e.target.value as AccessRoll)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              {(Object.keys(ACCESS_ROLL_LABELS) as AccessRoll[]).map((roll) => (
                <option key={roll} value={roll}>
                  {ACCESS_ROLL_LABELS[roll]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">سطح دسترسی</label>
            <select
              value={accessLevel}
              onChange={(e) => setAccessLevel(e.target.value as AccessLevel)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              {(Object.keys(ACCESS_LEVEL_LABELS) as AccessLevel[]).map((level) => (
                <option key={level} value={level}>
                  {ACCESS_LEVEL_LABELS[level]}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSelect}
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            انتخاب
          </button>
          {previewTitle && (
            <span className="text-sm text-slate-600">
              سمت شما: <span className="font-semibold text-slate-900">{previewTitle}</span>
            </span>
          )}
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </button>
      </form>
    </div>
  );
}
