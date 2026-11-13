import { useEffect, useState } from "react";
import { Plane } from "lucide-react";
import { api, ApiError } from "../api/client";
import { dur, inr } from "../api/format";
import type { Pkg } from "../types";
import { Chip, Delta, ErrorBox, Modal, Spinner } from "./ui";

export default function ChangeFlightModal({ pkgId, direction, onClose, onChanged }: {
  pkgId: string; direction: "arrival" | "return"; onClose: () => void; onChanged: (p: Pkg) => void;
}) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { api.flightAlts(pkgId, direction).then(setData).catch((e) => setErr(e.message)); }, [pkgId, direction]);

  async function pick(id: string) {
    setBusy(id); setErr(null);
    try { onChanged(await api.changeFlight(pkgId, direction, id)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Change failed"); }
    finally { setBusy(null); }
  }
  return (
    <Modal title={direction === "arrival" ? "Change arrival flight" : "Change return flight"} onClose={onClose}>
      <p className="mb-4 text-sm text-slate-500">Every option is checked against the whole package (airport transfer hours, hotel dates, seats). The price difference is against your current flight.</p>
      {err && <div className="mb-3"><ErrorBox title="That change was refused" message={err} /></div>}
      {!data && !err && <Spinner label="Checking flights…" />}
      <ul className="space-y-3">
        {data?.alternatives.map((f: any) => (
          <li key={f.flight_id} className={`rounded-xl border p-4 ${f.is_current ? "border-brand-500 bg-brand-50" : f.valid ? "border-slate-200" : "border-slate-200 bg-slate-50 opacity-80"}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 font-bold text-slate-900"><Plane size={15} /> {f.airline} {f.flight_number}
                  {f.is_current && <Chip tone="blue">Current</Chip>}
                </div>
                <div className="mt-1 text-sm text-slate-700">{f.from} {f.departure_local.slice(11)} <span className="text-slate-400">({f.departure_local.slice(5, 10)})</span> → {f.to} {f.arrival_local.slice(11)} <span className="text-slate-400">({f.arrival_local.slice(5, 10)})</span></div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                  <Chip>{f.stops === 0 ? "Direct" : "1 stop"}</Chip><Chip>{dur(f.duration_minutes)}</Chip><Chip>{f.seats_left} seats left</Chip>
                </div>
              </div>
              <div className="text-right">
                <div className="font-extrabold tabular-nums text-slate-900">{inr(f.price_inr)}</div>
                <div className="text-xs text-slate-400">{inr(f.price_per_seat)} × seats</div>
                {!f.is_current && f.valid && <div className="mt-1"><Delta value={f.price_diff_inr} /></div>}
                {!f.is_current && f.valid && (
                  <button className="btn-primary mt-2 !py-1.5 text-xs" disabled={!!busy} onClick={() => pick(f.flight_id)}>{busy === f.flight_id ? "Checking…" : "Select"}</button>
                )}
              </div>
            </div>
            {f.valid && f.notes?.length > 0 && <div className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{f.notes.join(" ")}</div>}
            {!f.valid && <div className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">Not possible: {f.reason}</div>}
          </li>
        ))}
        {data && data.alternatives.length === 0 && <li className="text-sm text-slate-500">No other flights are available for this day.</li>}
      </ul>
    </Modal>
  );
}
