"use client";

import { useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, X } from "lucide-react";
import { ApiError, apiPatch } from "@/lib/api-client";
import { flattenErrorMessages } from "@/lib/api-errors";
import type { Person } from "@/lib/organization";
import { MIN_PASSWORD_LENGTH } from "@/lib/password";
import { PersonPicker } from "@/components/PersonPicker";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, inputClass } from "@/components/ui/Field";
import { IconButton } from "@/components/ui/IconButton";

/**
 * «بازنشانی رمز عبور» (Phase 20): HR picks a person and gives them a temporary password. The server
 * signs that person out everywhere and makes them choose their own at the next sign-in.
 */
export function ResetPasswordCard() {
  const [person, setPerson] = useState<Person | null>(null);
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!person) return;
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز باید دست‌کم ${MIN_PASSWORD_LENGTH.toLocaleString("fa-IR")} نویسه باشد.`);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await apiPatch(`/personnel/${person.id}/`, { password });
      setDone(person.full_name);
      setPerson(null);
      setPassword("");
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.data as Record<string, unknown> | undefined;
        const messages = flattenErrorMessages(body?.password);
        setError(messages.length ? messages.join(" ") : err.message);
      } else {
        setError("بازنشانی انجام نشد.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card aria-label="بازنشانی رمز عبور">
      <CardHeader
        title="بازنشانی رمز عبور"
        description="برای کسی که رمزش را فراموش کرده است. او از همهٔ دستگاه‌ها خارج می‌شود و در ورود بعدی باید رمز خودش را بگذارد."
        icon={<KeyRound />}
      />
      {done && (
        <Alert tone="success" role="status" className="mb-4">
          رمز {done} بازنشانی شد. رمز موقت را به خود او بدهید.
        </Alert>
      )}
      {person ? (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="flex items-center justify-between gap-3 rounded-xl border border-border px-3 py-2 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={person.full_name} size="sm" />
              <span className="min-w-0 truncate font-bold text-foreground">{person.full_name}</span>
              <span className="truncate text-xs text-muted-foreground">{person.title}</span>
            </span>
            <IconButton label="انتخاب شخص دیگر" size="sm" onClick={() => setPerson(null)}>
              <X />
            </IconButton>
          </div>
          <Field label="رمز موقت" htmlFor="reset-password" error={error} required>
            <div className="relative">
              <input
                id="reset-password"
                type={visible ? "text" : "password"}
                autoComplete="new-password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={Boolean(error) || undefined}
                className={`${inputClass} pl-10`}
              />
              <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? "پنهان کردن رمز" : "نمایش رمز"}
                className="absolute inset-y-0 left-2 my-auto flex size-7 items-center justify-center rounded-md text-subtle-foreground hover:text-soft-foreground"
              >
                {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>
          <div className="flex justify-end">
            <Button type="submit" variant="primary" loading={saving} icon={<KeyRound />}>
              بازنشانی رمز
            </Button>
          </div>
        </form>
      ) : (
        <PersonPicker
          id="reset-password-person"
          ariaLabel="جست و جوی شخص برای بازنشانی رمز"
          pickLabel="انتخاب"
          onPick={(picked) => {
            setDone(null);
            setError(null);
            setPerson(picked);
          }}
        />
      )}
    </Card>
  );
}
