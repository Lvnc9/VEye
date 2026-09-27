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
import { DarkError, darkInput, ghostButton, primaryButton } from "@/components/setup/ui";
import { ErrorBanner } from "@/components/StatusBanner";
import { PlacementCascade } from "@/components/personnel/PlacementCascade";
import { normalizeNationalCode } from "@/lib/login";
import type { OrgTreeResponse } from "@/lib/organization";
import { EMPTY_PLACEMENT, placedMessage, placementPayload, type PlacementForm, type RegisteredPerson } from "@/lib/personnel-org";
import { useApiQuery } from "@/lib/use-api-query";

const LIGHT = {
  wrap: "space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm",
  label: "mb-1 block text-sm font-medium text-slate-700",
  input: "w-full rounded border border-slate-300 px-3 py-2 text-sm",
  select: "w-full rounded border border-slate-300 px-3 py-2 text-sm",
  primaryButton: "w-full rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50",
  secondaryButton: "rounded border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50",
  success: "rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700",
  hint: "text-sm text-slate-600",
};

const DARK = {
  wrap: "space-y-4",
  label: "mb-1.5 block text-sm font-medium text-slate-300",
  input: darkInput,
  select: darkInput,
  primaryButton: primaryButton,
  secondaryButton: ghostButton,
  success: "rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-200",
  hint: "text-sm text-slate-400",
};

interface CreatePersonnelPayload extends PersonnelWritePayload {
  placement?: { node: number; is_lead: boolean; position_label: string };
}

/**
 * «ساخت پروفایل پرسنل» — register a person, optionally placing them in the org chart in the same
 * request (ADR-010 §B). Used both by `/personnel/register` and by A1's setup-wizard people step
 * (`tone="dark"`, to match `components/setup/ui.tsx`).
 */
export function PersonnelForm({
  onRegistered,
  tone = "light",
}: {
  onRegistered?: (person: RegisteredPerson) => void;
  tone?: "light" | "dark";
}) {
  const t = tone === "dark" ? DARK : LIGHT;
  const [fullName, setFullName] = useState("");
  const [nationalCode, setNationalCode] = useState("");
  const [mobilePhone, setMobilePhone] = useState("");
  const [accessRoll, setAccessRoll] = useState<AccessRoll | "">("");
  const [accessLevel, setAccessLevel] = useState<AccessLevel | "">("");
  const [password, setPassword] = useState("");

  const [placement, setPlacement] = useState<PlacementForm>(EMPTY_PLACEMENT);
  const [reload, setReload] = useState(0);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const nodes = tree.data?.nodes ?? [];

  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function handleSelect() {
    if (accessRoll && accessLevel) setPreviewTitle(computeTitle(accessRoll, accessLevel));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessRoll || !accessLevel) {
      setError("نوع و سطح دسترسی را انتخاب کنید.");
      return;
    }
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const placementBody = placementPayload(nodes, placement);
      const payload: CreatePersonnelPayload = {
        full_name: fullName,
        // ASCII digits, as the login page sends them: a code stored with Persian digits could never sign in.
        national_code: normalizeNationalCode(nationalCode),
        mobile_phone: normalizeNationalCode(mobilePhone),
        access_roll: accessRoll,
        access_level: accessLevel,
        ...(password ? { password } : {}),
        ...(placementBody ? { placement: placementBody } : {}),
      };
      const created = await apiPost<RegisteredPerson>("/personnel/", payload);

      setSuccess(placedMessage(created.membership?.node_name ?? null));
      onRegistered?.(created);
      setPlacement(EMPTY_PLACEMENT);
      setReload((n) => n + 1);
      setFullName("");
      setNationalCode("");
      setMobilePhone("");
      setPassword("");
      setAccessRoll("");
      setAccessLevel("");
      setPreviewTitle(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت پروفایل پرسنل ممکن نشد.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={t.wrap}>
      {error && (tone === "dark" ? <DarkError message={error} /> : <ErrorBanner message={error} />)}
      {success && (
        <div role="status" className={t.success}>
          {success}
        </div>
      )}

      <div>
        <label className={t.label}>نام و نام خانوادگی</label>
        <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} className={t.input} />
      </div>

      <div>
        <label className={t.label}>کد ملی</label>
        <input type="text" required value={nationalCode} onChange={(e) => setNationalCode(e.target.value)} className={t.input} />
      </div>

      <div>
        <label className={t.label}>تلفن همراه</label>
        <input type="text" required value={mobilePhone} onChange={(e) => setMobilePhone(e.target.value)} className={t.input} />
      </div>

      <div>
        <label className={t.label}>رمز عبور اولیه</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={t.input}
          placeholder="اختیاری"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={t.label}>نوع دسترسی</label>
          <select
            required
            value={accessRoll}
            onChange={(e) => setAccessRoll(e.target.value as AccessRoll)}
            className={t.select}
          >
            <option value="">انتخاب کنید…</option>
            {(Object.keys(ACCESS_ROLL_LABELS) as AccessRoll[]).map((roll) => (
              <option key={roll} value={roll}>
                {ACCESS_ROLL_LABELS[roll]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={t.label}>سطح دسترسی</label>
          <select
            required
            value={accessLevel}
            onChange={(e) => setAccessLevel(e.target.value as AccessLevel)}
            className={t.select}
          >
            <option value="">انتخاب کنید…</option>
            {(Object.keys(ACCESS_LEVEL_LABELS) as AccessLevel[]).map((level) => (
              <option key={level} value={level}>
                {ACCESS_LEVEL_LABELS[level]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <PlacementCascade nodes={nodes} value={placement} onChange={setPlacement} tone={tone} />

      <div className="flex items-center gap-3">
        <button type="button" onClick={handleSelect} className={t.secondaryButton}>
          انتخاب
        </button>
        {previewTitle && (
          <span className={t.hint}>
            سمت: <span className="font-semibold">{previewTitle}</span>
          </span>
        )}
      </div>

      <button type="submit" disabled={saving} className={t.primaryButton}>
        {saving ? "در حال ذخیره..." : "ذخیره"}
      </button>
    </form>
  );
}
