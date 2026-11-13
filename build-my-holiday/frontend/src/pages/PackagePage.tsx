import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Copy, Lightbulb, Shuffle, SlidersHorizontal, X } from "lucide-react";
import { api, ApiError } from "../api/client";
import { inr, signedInr } from "../api/format";
import type { OptionsResult, Pkg } from "../types";
import PackageView, { ExportButton, TripHeader } from "../components/PackageView";
import PackageOptionTabs from "../components/PackageOptionTabs";
import ChangeFlightModal from "../components/ChangeFlightModal";
import ChangeHotelModal from "../components/ChangeHotelModal";
import AttractionEditor from "../components/AttractionEditor";
import CityPlanModal from "../components/CityPlanModal";
import WhatIfModal from "../components/WhatIfModal";
import { ErrorBox, Modal, Spinner } from "../components/ui";

type ModalState = null | { t: "flight"; dir: "arrival" | "return" } | { t: "hotel"; city: string } | { t: "attr" } | { t: "cities" } | { t: "whatif" } | { t: "confirm" };

export default function PackagePage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [pkg, setPkg] = useState<Pkg | null>(null);
  const [opts, setOpts] = useState<OptionsResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<Pkg["change"] | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmErr, setConfirmErr] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [booked, setBooked] = useState<Pkg | null>(null);

  const load = useCallback(() => {
    setErr(null);
    api.pkg(id).then((p) => { if (p.status === "BOOKED" && p.reference) nav(`/reservation/${p.reference}`, { replace: true }); else setPkg(p); }).catch((e) => setErr(e.message));
    api.options(id).then(setOpts).catch(() => setOpts(null));
  }, [id, nav]);
  useEffect(() => { setPkg(null); setNotice(null); setActionErr(null); load(); }, [load]);

  const changed = (p: Pkg) => { setPkg(p); setNotice(p.change ?? null); setActionErr(null); setModal(null); api.options(id).then(setOpts).catch(() => undefined); };

  async function removeAttraction(attId: string) {
    setBusyId(attId); setActionErr(null);
    try { changed(await api.removeAttraction(id, attId)); }
    catch (e) { setActionErr(e instanceof ApiError ? e.message : "Could not remove"); }
    finally { setBusyId(null); }
  }

  async function replan(budget: number) {
    if (!pkg) return;
    const r = pkg.request;
    const res = await api.generate({ name: r.name, departure_city: r.departure_city, country: r.country, start_date: r.start_date,
      nights: r.nights, adults: r.adults, child_ages: r.child_ages, budget_inr: budget });
    if (res.status === "IMPOSSIBLE" || !res.package) throw new ApiError(409, (res.reasons ?? [res.message]).join(" "));
    setModal(null);
    nav(`/package/${res.package.package_id}`);
  }

  async function confirm(allowOver = false) {
    setConfirming(true); setConfirmErr(null);
    try { setBooked(await api.confirm(id, allowOver)); }
    catch (e) { setConfirmErr(e instanceof ApiError ? e.message : "Could not confirm"); }
    finally { setConfirming(false); }
  }

  if (err) return <ErrorBox title="Could not load this package" message={err} />;
  if (!pkg) return <Spinner label="Loading your package…" />;
  const over = !pkg.summary.within_budget;
  const overOpts = opts && opts.status === "OVER_BUDGET";

  return (
    <div className="space-y-5">
      <TripHeader pkg={pkg} />
      {opts && <PackageOptionTabs options={opts.options} currentId={pkg.package_id} onSelect={(pid) => nav(`/package/${pid}`)} />}

      {overOpts && (
        <div className="card border-rose-300 bg-rose-50 p-5" role="alert" data-testid="over-budget">
          <h3 className="text-lg font-extrabold text-rose-900">No package fits your budget</h3>
          <p className="mt-1 text-sm text-rose-900">The cheapest valid package costs <b>{inr(opts!.cheapest_total_inr ?? pkg.summary.total_inr)}</b>, which is <b>{inr(opts!.deficit_inr ?? -pkg.summary.remaining_inr)}</b> over your budget of {inr(pkg.summary.budget_inr)}.</p>
          {opts!.suggestions && (
            <ul className="mt-3 space-y-1.5 text-sm text-rose-900">
              {opts!.suggestions.map((s, i) => <li key={i} className="flex gap-2"><Lightbulb size={15} className="mt-0.5 shrink-0" /> {s}</li>)}
            </ul>
          )}
        </div>
      )}

      {notice && (
        <div className="card flex items-start justify-between gap-3 border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900" data-testid="change-notice">
          <div>
            <div className="flex items-center gap-2 font-bold"><CheckCircle2 size={16} /> Package updated and re-checked — {inr(notice.previous_total_inr)} → {inr(notice.new_total_inr)} ({signedInr(notice.price_diff_inr)})</div>
            {notice.notes.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs">{notice.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
          </div>
          <button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={16} /></button>
        </div>
      )}
      {actionErr && <ErrorBox title="That change was refused — your package is unchanged" message={actionErr} />}

      <PackageView
        pkg={pkg}
        editable
        handlers={{
          onChangeFlight: (dir) => setModal({ t: "flight", dir }),
          onChangeHotel: (city) => setModal({ t: "hotel", city }),
          onAddAttraction: () => setModal({ t: "attr" }),
          onRemoveAttraction: removeAttraction,
          busyId,
        }}
        sidebarExtra={
          <div className="space-y-2">
            {pkg.plan.length >= 1 && (
              <button className="btn-secondary w-full" onClick={() => setModal({ t: "cities" })}><Shuffle size={15} /> Change cities</button>
            )}
            <button className="btn-secondary w-full" onClick={() => setModal({ t: "whatif" })}><SlidersHorizontal size={15} /> What if my budget changes?</button>
            <ExportButton pkg={pkg} />
            <button className="btn-primary w-full !py-3 text-base" onClick={() => { setConfirmErr(null); setModal({ t: "confirm" }); }}>Confirm package</button>
            {over && <p className="text-center text-xs text-rose-600">Over budget by {inr(-pkg.summary.remaining_inr)}</p>}
          </div>
        }
      />

      {modal?.t === "flight" && <ChangeFlightModal pkgId={id} direction={modal.dir} onClose={() => setModal(null)} onChanged={changed} />}
      {modal?.t === "hotel" && <ChangeHotelModal pkgId={id} city={modal.city} onClose={() => setModal(null)} onChanged={changed} />}
      {modal?.t === "attr" && <AttractionEditor pkgId={id} onClose={() => setModal(null)} onChanged={changed} />}
      {modal?.t === "whatif" && <WhatIfModal pkg={pkg} onClose={() => setModal(null)} onReplan={replan} />}
      {modal?.t === "cities" && <CityPlanModal pkgId={id} onClose={() => setModal(null)} onChanged={changed} />}
      {modal?.t === "confirm" && !booked && (
        <Modal title="Confirm your holiday" onClose={() => setModal(null)}>
          <p className="text-sm text-slate-600">Confirming re-validates every rule and saves your reservation. There is no payment in this demo.</p>
          <div className="my-4 rounded-xl bg-slate-50 p-4">
            <div className="flex justify-between text-sm"><span>Total</span><b>{inr(pkg.summary.total_inr)}</b></div>
            <div className="flex justify-between text-sm"><span>Budget</span><span>{inr(pkg.summary.budget_inr)}</span></div>
            <div className={`flex justify-between text-sm font-semibold ${over ? "text-rose-600" : "text-emerald-600"}`}><span>{over ? "Over budget" : "Left"}</span><span>{inr(Math.abs(pkg.summary.remaining_inr))}</span></div>
          </div>
          {confirmErr && <div className="mb-3"><ErrorBox title="Could not confirm" message={confirmErr} /></div>}
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => setModal(null)}>Back</button>
            <button className="btn-primary flex-1" disabled={confirming} onClick={() => confirm(false)}>{confirming ? "Confirming…" : "Confirm & get reservation number"}</button>
          </div>
          {over && <button className="btn-secondary mt-2 w-full" disabled={confirming} onClick={() => confirm(true)}>Confirm anyway (over budget)</button>}
        </Modal>
      )}
      {booked && (
        <Modal title="You're booked!" onClose={() => nav(`/reservation/${booked.reference}`)}>
          <div className="text-center">
            <CheckCircle2 className="mx-auto text-emerald-500" size={44} />
            <p className="mt-2 text-sm text-slate-600">Your reservation number</p>
            <div className="my-2 select-all font-mono text-4xl font-extrabold tracking-widest text-brand-900" data-testid="reference">{booked.reference}</div>
            <button className="btn-secondary !py-1.5 text-xs" onClick={() => navigator.clipboard?.writeText(booked.reference ?? "")}><Copy size={13} /> Copy</button>
            <p className="mt-3 text-xs text-slate-500">Use it on “Find my reservation” any time to reopen the full package.</p>
            <button className="btn-primary mt-4 w-full" onClick={() => nav(`/reservation/${booked.reference}`)}>View reservation</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
