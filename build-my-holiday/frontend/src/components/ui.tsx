import { ReactNode, useEffect } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { signedInr } from "../api/format";

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4" onClick={onClose}>
      <div className={`card my-8 w-full ${wide ? "max-w-4xl" : "max-w-2xl"}`} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-bold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export const Spinner = ({ label = "Loading…" }: { label?: string }) => (
  <div className="flex items-center justify-center gap-2 py-10 text-slate-500"><Loader2 className="animate-spin" size={18} /> {label}</div>
);

export const ErrorBox = ({ message, title = "Something went wrong" }: { message: string; title?: string }) => (
  <div className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
    <AlertTriangle size={18} className="mt-0.5 shrink-0" />
    <div><div className="font-semibold">{title}</div><div>{message}</div></div>
  </div>
);

export function Delta({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return null;
  const cls = value > 0 ? "bg-rose-50 text-rose-700" : value < 0 ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${cls}`}>{signedInr(value)}</span>;
}

export const Chip = ({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "blue" | "green" | "amber" | "rose" }) => {
  const t = { slate: "bg-slate-100 text-slate-600", blue: "bg-brand-50 text-brand-700", green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", rose: "bg-rose-50 text-rose-700" }[tone];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${t}`}>{children}</span>;
};
