"use client";

import { useRouter } from "next/navigation";
import { LogOut, ShieldAlert } from "lucide-react";
import { apiPost } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/current-user";
import { BrandMark } from "@/components/ui/BrandMark";
import { Button } from "@/components/ui/Button";
import { cardClass } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { cx } from "@/components/ui/cx";
import { ChangePasswordForm } from "./ChangePasswordForm";

/**
 * What the app shows — instead of everything else — to someone whose password HR chose (a new account
 * or a reset; Phase 20). The API refuses every other request until they pick their own, so this is
 * the honest screen rather than a page of errors.
 */
export function ForcedPasswordScreen() {
  const router = useRouter();
  const toast = useToast();
  const { user, replaceUser } = useCurrentUser();

  async function logout() {
    try {
      await apiPost("/auth/logout/");
    } catch {
      // Still leave: the cookies are cleared by the next sign-in anyway.
    } finally {
      router.push("/login");
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <section className={cx(cardClass, "w-full max-w-md p-6 sm:p-8")} aria-labelledby="forced-password-title">
        <div className="mb-6 flex items-center gap-3">
          <BrandMark />
          <div className="min-w-0">
            <h1 id="forced-password-title" className="text-lg font-bold text-slate-900">
              رمز عبور خود را انتخاب کنید
            </h1>
            {user && <p className="truncate text-sm text-slate-500">{user.full_name}</p>}
          </div>
        </div>
        <p className="mb-5 flex gap-2 rounded-xl bg-amber-50/80 px-3 py-2.5 text-sm leading-7 text-amber-900 ring-1 ring-inset ring-amber-600/20">
          <ShieldAlert className="mt-1.5 size-4 shrink-0 text-amber-600" />
          رمز فعلی را شخص دیگری برای شما گذاشته است. پیش از ادامه، رمزی بگذارید که فقط خودتان بدانید.
        </p>
        <ChangePasswordForm
          onChanged={(next) => {
            replaceUser(next);
            toast({ tone: "success", title: "رمز عبور شما تغییر کرد." });
          }}
        />
        <div className="mt-6 border-t border-slate-100 pt-4">
          <Button variant="ghost" size="sm" icon={<LogOut />} onClick={logout}>
            خروج
          </Button>
        </div>
      </section>
    </div>
  );
}
