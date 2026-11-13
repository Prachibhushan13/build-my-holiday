import { Bus, BedDouble, Landmark, Plane } from "lucide-react";
import type { Summary } from "../types";
import { inr } from "../api/format";

export default function PriceBreakdown({ s }: { s: Summary }) {
  const rows = [
    { key: "flights", label: "Flights", icon: Plane, color: "bg-sky-500" },
    { key: "hotels", label: "Hotels", icon: BedDouble, color: "bg-violet-500" },
    { key: "transfers", label: "Transfers", icon: Bus, color: "bg-amber-500" },
    { key: "attractions", label: "Attractions", icon: Landmark, color: "bg-emerald-500" },
  ] as const;
  const pct = Math.min(100, s.budget_inr > 0 ? (s.total_inr / s.budget_inr) * 100 : 100);
  const over = !s.within_budget;
  return (
    <div className="card p-5" data-testid="price-breakdown">
      <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">Price breakdown</h3>
      <ul className="mt-3 space-y-2.5">
        {rows.map((r) => {
          const v = s.breakdown[r.key];
          const share = s.total_inr ? (v / s.total_inr) * 100 : 0;
          return (
            <li key={r.key}>
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-slate-600"><r.icon size={14} /> {r.label}</span>
                <span className="font-semibold tabular-nums text-slate-900">{inr(v)}</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full ${r.color}`} style={{ width: `${share}%` }} /></div>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex items-end justify-between border-t border-slate-200 pt-3">
        <span className="text-sm font-semibold text-slate-600">Total</span>
        <span className="text-2xl font-extrabold tabular-nums text-slate-900" data-testid="total">{inr(s.total_inr)}</span>
      </div>
      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-xs font-semibold">
          <span className="text-slate-500">Budget {inr(s.budget_inr)}</span>
          <span className={over ? "text-rose-600" : "text-emerald-600"}>
            {over ? `${inr(-s.remaining_inr)} over budget` : `${inr(s.remaining_inr)} left`}
          </span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
          <div className={`h-full rounded-full ${over ? "bg-rose-500" : pct > 90 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}
