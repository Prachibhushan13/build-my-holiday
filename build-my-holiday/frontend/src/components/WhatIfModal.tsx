import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, X } from "lucide-react";
import { api, ApiError } from "../api/client";
import { inr } from "../api/format";
import type { Pkg } from "../types";
import { Chip, ErrorBox, Modal, Spinner } from "./ui";

type Plan = { plan: { city: string; nights: number }[]; feasible: boolean; total_inr?: number; is_current?: boolean };

const STEP = 5000;
const down = (n: number) => Math.floor(n / STEP) * STEP;
const up = (n: number) => Math.ceil(n / STEP) * STEP;

export default function WhatIfModal({ pkg, onClose, onReplan }: { pkg: Pkg; onClose: () => void; onReplan: (budget: number) => Promise<void> }) {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const budget0 = pkg.summary.budget_inr;
  const [budget, setBudget] = useState(budget0);

  useEffect(() => { api.cityPlans(pkg.package_id).then((d) => setPlans(d.plans)).catch((e) => setErr(e.message)); }, [pkg.package_id]);

  const feasible = useMemo(() => (plans ?? []).filter((p) => p.feasible && p.total_inr != null).sort((a, b) => a.total_inr! - b.total_inr!), [plans]);
  const lo = feasible.length ? Math.min(down(feasible[0].total_inr! * 0.8), down(budget0)) : 0;
  const hi = feasible.length ? Math.max(up(feasible[feasible.length - 1].total_inr! * 1.05), up(budget0)) : 0;
  const fits = feasible.filter((p) => p.total_inr! <= budget);
  const cheapest = feasible[0]?.total_inr;

  async function replan() {
    setBusy(true); setErr(null);
    try { await onReplan(budget); } catch (e) { setErr(e instanceof ApiError ? e.message : (e as Error).message); setBusy(false); }
  }

  return (
    <Modal title="What if my budget changes?" onClose={onClose} wide>
      {err && <div className="mb-3"><ErrorBox title="Could not do that" message={err} /></div>}
      {!plans && !err && <Spinner label="Pricing every city plan…" />}
      {plans && feasible.length === 0 && <p className="text-sm text-slate-500">No city plan is possible for this request, so there is nothing to compare.</p>}
      {feasible.length > 0 && (
        <>
          <p className="mb-4 text-sm text-slate-500">Drag the slider to see which city plans would fit. Prices are the cheapest valid package for each plan, so the numbers are exactly what we would book.</p>
          <div className="rounded-xl bg-slate-50 p-4">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Budget</div>
                <div className="text-3xl font-extrabold tabular-nums text-brand-900" data-testid="whatif-budget">{inr(budget)}</div>
              </div>
              <div className="text-right text-sm">
                <div className={`font-bold ${fits.length ? "text-emerald-600" : "text-rose-600"}`} data-testid="whatif-count">{fits.length} of {feasible.length} plans fit</div>
                {budget !== budget0 && <button className="text-xs text-brand-600 underline" onClick={() => setBudget(budget0)}>Reset to {inr(budget0)}</button>}
              </div>
            </div>
            <input type="range" className="mt-3 w-full accent-brand-600" min={lo} max={hi} step={STEP} value={budget}
              onChange={(e) => setBudget(Number(e.target.value))} aria-label="Budget" />
            <div className="flex justify-between text-[11px] text-slate-400"><span>{inr(lo)}</span><span>{inr(hi)}</span></div>
            {cheapest != null && (
              <p className={`mt-2 text-sm font-medium ${budget >= cheapest ? "text-emerald-700" : "text-rose-700"}`}>
                {budget >= cheapest
                  ? `You have ${inr(budget - cheapest)} to spare over the cheapest plan (${inr(cheapest)}).`
                  : `You are ${inr(cheapest - budget)} short of the cheapest plan (${inr(cheapest)}).`}
              </p>
            )}
          </div>

          <ul className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
            {feasible.map((p, i) => {
              const ok = p.total_inr! <= budget;
              return (
                <li key={i} className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3 text-sm transition-colors ${ok ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white opacity-60"}`}>
                  <div className="flex flex-wrap items-center gap-1.5 font-semibold text-slate-800">
                    {ok ? <Check size={15} className="text-emerald-600" /> : <X size={15} className="text-slate-400" />}
                    {p.plan.map((c, j) => (
                      <span key={j} className="flex items-center gap-1.5">{j > 0 && <ArrowRight size={13} className="text-slate-400" />}{c.city} <span className="font-normal text-slate-500">{c.nights}n</span></span>
                    ))}
                    {p.is_current && <Chip tone="blue">Current</Chip>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold tabular-nums">{inr(p.total_inr!)}</span>
                    {!ok && <span className="text-xs text-rose-600">{inr(p.total_inr! - budget)} over</span>}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex gap-2">
            <button className="btn-secondary" onClick={onClose}>Close</button>
            <button className="btn-primary flex-1" disabled={busy || budget === budget0} onClick={replan}>
              {busy ? "Planning…" : budget === budget0 ? "Move the slider to try another budget" : `Plan again with ${inr(budget)}`}
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
