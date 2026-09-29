"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { BadgeCheck, Building2, Eye, EyeOff, IdCard, KeyRound, Phone, ShieldCheck, UserRound, UserPlus } from "lucide-react";
import {
  ACCESS_LEVEL_LABELS,
  ACCESS_ROLL_LABELS,
  TITLE_MATRIX,
  computeTitle,
  type AccessLevel,
  type AccessRoll,
  type PersonnelWritePayload,
} from "@/lib/types";
import { apiPost, ApiError } from "@/lib/api-client";
import { DarkError } from "@/components/setup/ui";
import { ErrorBanner } from "@/components/StatusBanner";
import { PlacementCascade } from "@/components/personnel/PlacementCascade";
import { normalizeNationalCode } from "@/lib/login";
import type { OrgTreeResponse } from "@/lib/organization";
import {
  EMPTY_PLACEMENT,
  placedMessage,
  placementPayload,
  resolvePlacement,
  type PlacementForm,
  type RegisteredPerson,
} from "@/lib/personnel-org";
import { useApiQuery } from "@/lib/use-api-query";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Spinner } from "@/components/ui/Spinner";
import { cx } from "@/components/ui/cx";

type Tone = "light" | "dark";

const THEME = {
  light: {
    wrap: "overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card",
    section: "border-slate-100",
    stepBadge: "bg-brand-50 text-brand-700 ring-brand-600/15",
    title: "text-slate-900",
    description: "text-slate-500",
    label: "text-slate-700",
    input:
      "h-11 w-full rounded-xl border border-slate-300 bg-white ps-10 pe-3 text-sm text-slate-900 shadow-xs placeholder:text-slate-400 " +
      "transition-[border-color,box-shadow] duration-150 hover:border-slate-400 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15",
    icon: "text-slate-400",
    choice: "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
    choiceOn: "border-brand-500 bg-brand-50/70 ring-4 ring-brand-500/10",
    choiceTitle: "text-slate-900",
    choiceText: "text-slate-500",
    footer: "border-slate-100 bg-slate-50/70",
    submit:
      "bg-brand-700 text-white shadow-[0_1px_2px_rgb(3_105_161/0.3),inset_0_1px_0_rgb(255_255_255/0.12)] hover:bg-brand-800",
    hint: "text-slate-500",
  },
  dark: {
    wrap: "overflow-hidden rounded-2xl border border-line bg-surface",
    section: "border-line",
    stepBadge: "bg-accent/15 text-accent ring-accent/20",
    title: "text-slate-50",
    description: "text-slate-400",
    label: "text-slate-300",
    input:
      "h-11 w-full rounded-xl border border-line bg-surface-raised ps-10 pe-3 text-sm text-slate-100 placeholder:text-slate-500 " +
      "transition-[border-color,box-shadow] duration-150 focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/20",
    icon: "text-slate-500",
    choice: "border-line bg-surface-raised hover:bg-white/5",
    choiceOn: "border-accent bg-accent/10 ring-4 ring-accent/10",
    choiceTitle: "text-slate-100",
    choiceText: "text-slate-400",
    footer: "border-line bg-surface-raised/60",
    submit: "bg-accent text-slate-950 hover:bg-accent-strong",
    hint: "text-slate-400",
  },
} as const;

interface CreatePersonnelPayload extends PersonnelWritePayload {
  placement?: { node: number; is_lead: boolean; position_label: string };
}

/** One numbered part of the form: a badge, a title with its line, and the fields. */
function Section({
  step,
  title,
  description,
  tone,
  children,
}: {
  step: number;
  title: string;
  description?: string;
  tone: Tone;
  children: ReactNode;
}) {
  const t = THEME[tone];
  return (
    <section className={cx("border-t px-5 py-6 first:border-t-0 sm:px-6", t.section)}>
      <div className="mb-4 flex items-start gap-3">
        <span
          className={cx(
            "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ring-1 ring-inset tabular-nums",
            t.stepBadge,
          )}
        >
          {step.toLocaleString("fa-IR")}
        </span>
        <div>
          <h3 className={cx("text-sm font-bold leading-7", t.title)}>{title}</h3>
          {description && <p className={cx("text-xs leading-6", t.description)}>{description}</p>}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

/** A text box with a leading icon inside it. */
function IconInput({
  id,
  label,
  icon,
  tone,
  hint,
  children,
}: {
  id: string;
  label: string;
  icon: ReactNode;
  tone: Tone;
  hint?: string;
  children: ReactNode;
}) {
  const t = THEME[tone];
  return (
    <div>
      <label htmlFor={id} className={cx("mb-1.5 block text-sm", t.label)}>
        {label}
      </label>
      <div className="relative">
        <span className={cx("pointer-events-none absolute inset-y-0 right-3.5 my-auto flex items-center [&_svg]:size-4", t.icon)}>
          {icon}
        </span>
        {children}
      </div>
      {hint && <p className={cx("mt-1.5 text-xs", t.hint)}>{hint}</p>}
    </div>
  );
}

/** A group of selectable cards (a radio group): the chosen one is outlined in the brand colour. */
function ChoiceCards<T extends string>({
  name,
  label,
  options,
  value,
  onChange,
  tone,
}: {
  name: string;
  label: string;
  options: { value: T; title: string; text?: string }[];
  value: T | "";
  onChange: (value: T) => void;
  tone: Tone;
}) {
  const t = THEME[tone];
  return (
    <fieldset>
      <legend className={cx("mb-2 text-sm", t.label)}>{label}</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {options.map((option) => {
          const on = option.value === value;
          return (
            <label
              key={option.value}
              className={cx(
                "relative flex cursor-pointer flex-col gap-0.5 rounded-xl border px-3.5 py-3 transition-[border-color,background-color,box-shadow] duration-150",
                "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500",
                on ? t.choiceOn : t.choice,
              )}
            >
              <input
                type="radio"
                name={name}
                value={option.value}
                checked={on}
                onChange={() => onChange(option.value)}
                className="sr-only"
                required
              />
              <span className={cx("flex items-center justify-between gap-2 text-sm font-bold", t.choiceTitle)}>
                {option.title}
                <BadgeCheck
                  aria-hidden
                  className={cx(
                    "size-4 transition-[opacity,transform] duration-200",
                    on ? "scale-100 text-brand-600 opacity-100" : "scale-50 opacity-0",
                  )}
                />
              </span>
              {option.text && <span className={cx("text-xs leading-5", t.choiceText)}>{option.text}</span>}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * «ساخت پروفایل پرسنل» — register a person, optionally placing them in the org chart in the same
 * request (ADR-010 §B). Used both by `/personnel/register` and by A1's setup-wizard people step
 * (`tone="dark"`, to match `components/setup/ui.tsx`). `onDraft` reports what is typed so far, for a
 * live preview beside the form.
 */
export function PersonnelForm({
  onRegistered,
  onDraft,
  tone = "light",
}: {
  onRegistered?: (person: RegisteredPerson) => void;
  onDraft?: (draft: { fullName: string; title: string; placement: string | null }) => void;
  tone?: Tone;
}) {
  const t = THEME[tone];
  const [fullName, setFullName] = useState("");
  const [nationalCode, setNationalCode] = useState("");
  const [mobilePhone, setMobilePhone] = useState("");
  const [accessRoll, setAccessRoll] = useState<AccessRoll | "">("");
  const [accessLevel, setAccessLevel] = useState<AccessLevel | "">("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [placement, setPlacement] = useState<PlacementForm>(EMPTY_PLACEMENT);
  const [reload, setReload] = useState(0);
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const nodes = tree.data?.nodes ?? [];

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ message: string; name: string; title: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const title = accessRoll && accessLevel ? computeTitle(accessRoll, accessLevel) : "";
  const nameOf = (form: PlacementForm) => {
    const target = resolvePlacement(nodes, form);
    return target ? (nodes.find((node) => node.id === target.node)?.name ?? null) : null;
  };
  const placementName = nameOf(placement);

  function report(next: Partial<{ fullName: string; roll: AccessRoll | ""; level: AccessLevel | ""; placement: PlacementForm }>) {
    if (!onDraft) return;
    const roll = next.roll ?? accessRoll;
    const level = next.level ?? accessLevel;
    const place = next.placement ?? placement;
    onDraft({
      fullName: next.fullName ?? fullName,
      title: roll && level ? computeTitle(roll, level) : "",
      placement: nameOf(place),
    });
  }

  const rollOptions = (Object.keys(ACCESS_ROLL_LABELS) as AccessRoll[]).map((roll) => ({
    value: roll,
    title: ACCESS_ROLL_LABELS[roll],
    text: (Object.keys(ACCESS_LEVEL_LABELS) as AccessLevel[]).map((level) => TITLE_MATRIX[`${roll}:${level}`]).join("، "),
  }));
  const levelOptions = (Object.keys(ACCESS_LEVEL_LABELS) as AccessLevel[]).map((level) => ({
    value: level,
    title: ACCESS_LEVEL_LABELS[level],
    text: accessRoll ? computeTitle(accessRoll, level) : undefined,
  }));

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

      setSuccess({ message: placedMessage(created.membership?.node_name ?? null), name: fullName, title });
      onRegistered?.(created);
      setPlacement(EMPTY_PLACEMENT);
      setReload((n) => n + 1);
      setFullName("");
      setNationalCode("");
      setMobilePhone("");
      setPassword("");
      setAccessRoll("");
      setAccessLevel("");
      onDraft?.({ fullName: "", title: "", placement: null });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "ثبت پروفایل پرسنل ممکن نشد.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={t.wrap}>
      {(error || success) && (
        <div className="space-y-3 px-5 pt-5 sm:px-6">
          {error && (tone === "dark" ? <DarkError message={error} /> : <ErrorBanner message={error} />)}
          {success &&
            (tone === "dark" ? (
              <div role="status" className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-200">
                {success.message}
              </div>
            ) : (
              <Alert tone="success" role="status" title={`${success.name} ثبت شد`}>
                {success.message}
              </Alert>
            ))}
        </div>
      )}

      <Section step={1} title="مشخصات فردی" description="نام، کد ملی و شمارهٔ تماس شخص." tone={tone}>
        <IconInput id="person-name" label="نام و نام خانوادگی" icon={<UserRound />} tone={tone}>
          <input
            id="person-name"
            type="text"
            required
            autoComplete="off"
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              report({ fullName: e.target.value });
            }}
            className={t.input}
          />
        </IconInput>
        <div className="grid gap-4 sm:grid-cols-2">
          <IconInput id="person-code" label="کد ملی" icon={<IdCard />} tone={tone} hint="با همین کد وارد سامانه می‌شود.">
            <input
              id="person-code"
              type="text"
              required
              inputMode="numeric"
              autoComplete="off"
              value={nationalCode}
              onChange={(e) => setNationalCode(e.target.value)}
              className={cx(t.input, "latn text-left")}
            />
          </IconInput>
          <IconInput id="person-phone" label="تلفن همراه" icon={<Phone />} tone={tone}>
            <input
              id="person-phone"
              type="text"
              required
              inputMode="tel"
              autoComplete="off"
              value={mobilePhone}
              onChange={(e) => setMobilePhone(e.target.value)}
              className={cx(t.input, "latn text-left")}
            />
          </IconInput>
        </div>
      </Section>

      <Section step={2} title="دسترسی و سمت" description="سمت از نوع و سطح دسترسی ساخته می‌شود." tone={tone}>
        <ChoiceCards
          name="access-roll"
          label="نوع دسترسی"
          options={rollOptions}
          value={accessRoll}
          onChange={(roll) => {
            setAccessRoll(roll);
            report({ roll });
          }}
          tone={tone}
        />
        <ChoiceCards
          name="access-level"
          label="سطح دسترسی"
          options={levelOptions}
          value={accessLevel}
          onChange={(level) => {
            setAccessLevel(level);
            report({ level });
          }}
          tone={tone}
        />
        {title && (
          <p className={cx("flex items-center gap-2 text-sm animate-fade-in", t.hint)}>
            <ShieldCheck className="size-4 text-emerald-500" />
            سمت: <span className={cx("font-bold", t.title)}>{title}</span>
          </p>
        )}
      </Section>

      <Section
        step={3}
        title="جایگاه در ساختار سازمان"
        description="اختیاری — می‌توانید بعداً هم او را در ساختار قرار دهید."
        tone={tone}
      >
        <PlacementCascade
          nodes={nodes}
          value={placement}
          onChange={(next) => {
            setPlacement(next);
            report({ placement: next });
          }}
          tone={tone}
          bare
        />
        {placementName && (
          <p className={cx("flex items-center gap-2 text-sm animate-fade-in", t.hint)}>
            <Building2 className="size-4 text-brand-500" />
            در <span className={cx("font-bold", t.title)}>{placementName}</span>
          </p>
        )}
      </Section>

      <Section step={4} title="رمز عبور اولیه" description="اختیاری — شخص پس از ورود می‌تواند آن را عوض کند." tone={tone}>
        <IconInput id="person-password" label="رمز عبور" icon={<KeyRound />} tone={tone}>
          <input
            id="person-password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={cx(t.input, "latn pl-11 text-left")}
            placeholder="اختیاری"
          />
          <button
            type="button"
            onClick={() => setShowPassword((shown) => !shown)}
            aria-label={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
            aria-pressed={showPassword}
            title={showPassword ? "پنهان کردن رمز" : "نمایش رمز"}
            className={cx(
              "absolute inset-y-0 left-1.5 my-auto flex size-8 items-center justify-center rounded-lg transition-colors",
              tone === "dark" ? "text-slate-500 hover:bg-white/5 hover:text-slate-200" : "text-slate-400 hover:bg-slate-100 hover:text-slate-700",
            )}
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </IconInput>
      </Section>

      <div className={cx("flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4 sm:px-6", t.footer)}>
        {tone === "light" && fullName ? (
          <span className="flex min-w-0 items-center gap-2 text-sm text-slate-600 animate-fade-in">
            <Avatar name={fullName} size="sm" />
            <span className="truncate">
              {fullName}
              {title && <span className="text-slate-400"> · {title}</span>}
            </span>
          </span>
        ) : (
          <span />
        )}
        <button
          type="submit"
          disabled={saving}
          aria-busy={saving || undefined}
          className={cx(
            "inline-flex h-11 min-w-40 items-center justify-center gap-2 rounded-xl px-6 text-sm font-bold transition-[background-color,transform] duration-150",
            "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100",
            t.submit,
          )}
        >
          {saving ? <Spinner /> : <UserPlus className="size-4" />}
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </button>
      </div>
    </form>
  );
}
