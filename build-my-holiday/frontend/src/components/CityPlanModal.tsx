import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { api, ApiError } from "../api/client";
import { inr } from "../api/format";
import type { Pkg } from "../types";
import { Chip, Delta, ErrorBox, Modal, Spinner } from "./ui";

export default function CityPlanModal({ pkgId, onClose, onChanged }: { pkgId: string; onClose: () => void; onChanged: (p: Pkg) => void }) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  useEffect(() => { api.cityPlans(pkgId).then(setData).catch((e) => setErr(e.message)); }, [pkgId]);

  async function pick(i: number, plan: any[]) {
    setBusy(i); setErr(null);
    try { onChanged(await api.changeCities(pkgId, plan)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Change failed"); }
    finally { setBusy(null); }
  }
  const plans: any[] = data?.plans ?? [];
  return (
    <Modal title="Change cities" onClose={onClose}>
      <p className="mb-4 text-sm text-slate-500">Every valid way to split your nights across cities (min. 2 nights each, each city once, linked by a transfer). Choosing one rebuilds hotels, transfers and attractions.</p>
      {err && <div className="mb-3"><ErrorBox title="That plan was refused" message={err} /></div>}
      {!data && !err && <Spinner label="Pricing every city plan…" />}
      <ul className="space-y-2">
        {plans.filter((p) => p.feasible).map((p, i) => (
          <li key={i} className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 ${p.is_current ? "border-brand-500 bg-brand-50" : "border-slate-200"}`}>
            <div className="flex flex-wrap items-center gap-1.5 text-sm font-semibold text-slate-800">
              {p.plan.map((c: any, j: number) => (
                <span key={j} className="flex items-center gap-1.5">{j > 0 && <ArrowRight size={13} className="text-slate-400" />}{c.city} <span className="font-normal text-slate-500">{c.nights}n</span></span>
              ))}
              {p.is_current && <Chip tone="blue">Current</Chip>}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold tabular-nums">{inr(p.total_inr)}</span>
              {!p.is_current && <Delta value={p.diff_inr} />}
              {!p.within_budget && <Chip tone="rose">Over budget</Chip>}
              {!p.is_current && <button className="btn-primary !py-1.5 text-xs" disabled={busy !== null} onClick={() => pick(i, p.plan)}>{busy === i ? "Rebuilding…" : "Use this"}</button>}
            </div>
          </li>
        ))}
      </ul>
      {plans.some((p) => !p.feasible) && <p className="mt-3 text-xs text-slate-400">{plans.filter((p) => !p.feasible).length} other plan(s) are not possible for your dates and group.</p>}
    </Modal>
  );
}
