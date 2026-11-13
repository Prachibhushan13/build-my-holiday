import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { inr, stars } from "../api/format";
import type { Pkg } from "../types";
import { Chip, Delta, ErrorBox, Modal, Spinner } from "./ui";

export default function ChangeHotelModal({ pkgId, city, onClose, onChanged }: {
  pkgId: string; city: string; onClose: () => void; onChanged: (p: Pkg) => void;
}) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showInvalid, setShowInvalid] = useState(false);
  useEffect(() => { api.hotelAlts(pkgId, city).then(setData).catch((e) => setErr(e.message)); }, [pkgId, city]);

  async function pick(h: any) {
    setBusy(h.room_id); setErr(null);
    try { onChanged(await api.changeHotel(pkgId, city, h.hotel_id, h.room_id)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Change failed"); }
    finally { setBusy(null); }
  }
  const valid = data?.alternatives.filter((a: any) => a.valid) ?? [];
  const invalid = data?.alternatives.filter((a: any) => !a.valid) ?? [];
  return (
    <Modal title={`Change hotel in ${city}`} onClose={onClose} wide>
      <p className="mb-4 text-sm text-slate-500">One hotel and one room type for all nights in {city}. Room count, availability on every night and the airport-transfer area are re-checked for each option.</p>
      {err && <div className="mb-3"><ErrorBox title="That change was refused" message={err} /></div>}
      {!data && !err && <Spinner label="Checking hotels and rooms…" />}
      <ul className="grid gap-3 sm:grid-cols-2">
        {valid.map((h: any) => (
          <li key={h.room_id} className={`flex flex-col overflow-hidden rounded-xl border ${h.is_current ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white"}`}>
            {h.image && <img src={`/${h.image}`} alt="" loading="lazy" className="h-28 w-full object-cover" />}
            <div className="flex flex-1 flex-col p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-slate-900">{h.name}</div>
                  <div className="text-xs text-amber-500">{stars(h.stars)} <span className="text-slate-500">· guest {h.rating}</span></div>
                </div>
                {h.is_current ? <Chip tone="blue">Current</Chip> : <Delta value={h.price_diff_inr} />}
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                <Chip>{h.area}</Chip><Chip>{h.room_name} × {h.rooms}</Chip>{h.family_friendly && <Chip tone="green">Family friendly</Chip>}
              </div>
              <div className="mt-2 text-xs text-slate-500">{inr(h.price_per_night)} per room per night</div>
              {h.notes?.length > 0 && <div className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">{h.notes.join(" ")}</div>}
              {!h.is_current && (
                <button className="btn-primary mt-auto !py-1.5 text-xs" style={{ marginTop: 12 }} disabled={!!busy} onClick={() => pick(h)}>
                  {busy === h.room_id ? "Checking…" : `Select · total ${inr(h.new_total_inr)}`}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {invalid.length > 0 && (
        <div className="mt-5">
          <button className="text-sm font-semibold text-slate-500 underline" onClick={() => setShowInvalid(!showInvalid)}>
            {showInvalid ? "Hide" : "Show"} {invalid.length} unavailable option{invalid.length > 1 ? "s" : ""} and why
          </button>
          {showInvalid && (
            <ul className="mt-3 space-y-1.5 text-xs text-slate-500">
              {invalid.map((h: any) => <li key={h.room_id}><span className="font-semibold text-slate-700">{h.name} · {h.room_name}</span> — {h.reason}</li>)}
            </ul>
          )}
        </div>
      )}
    </Modal>
  );
}
