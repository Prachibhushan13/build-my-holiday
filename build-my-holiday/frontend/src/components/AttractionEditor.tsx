import { useEffect, useState } from "react";
import { Check, Clock, Plus } from "lucide-react";
import { api, ApiError } from "../api/client";
import { fmtDate, inr } from "../api/format";
import type { Pkg } from "../types";
import { Chip, ErrorBox, Modal, Spinner } from "./ui";

export default function AttractionEditor({ pkgId, onClose, onChanged }: { pkgId: string; onClose: () => void; onChanged: (p: Pkg) => void }) {
  const [list, setList] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [city, setCity] = useState<string>("all");
  useEffect(() => { api.attractions(pkgId).then((r) => setList(r.attractions)).catch((e) => setErr(e.message)); }, [pkgId]);

  async function add(a: any) {
    setBusy(a.attraction_id); setErr(null);
    try { onChanged(await api.addAttraction(pkgId, a.attraction_id, a.suggested?.date, a.suggested?.start)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Could not add"); }
    finally { setBusy(null); }
  }
  const cities = Array.from(new Set((list ?? []).map((a) => a.city)));
  const shown = (list ?? []).filter((a) => city === "all" || a.city === city);
  return (
    <Modal title="Add an attraction" onClose={onClose} wide>
      <p className="mb-3 text-sm text-slate-500">Only attractions in the cities where you sleep are listed. We pick the first free time that fits opening hours and does not overlap your other plans.</p>
      {err && <div className="mb-3"><ErrorBox title="Could not add that attraction" message={err} /></div>}
      {cities.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {["all", ...cities].map((c) => (
            <button key={c} onClick={() => setCity(c)} className={`rounded-full px-3 py-1 text-xs font-semibold ${city === c ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}>{c === "all" ? "All cities" : c}</button>
          ))}
        </div>
      )}
      {!list && !err && <Spinner />}
      <ul className="grid gap-3 sm:grid-cols-2">
        {shown.map((a) => (
          <li key={a.attraction_id} className="flex gap-3 rounded-xl border border-slate-200 p-3">
            {a.image && <img src={`/${a.image}`} alt="" loading="lazy" className="h-20 w-24 shrink-0 rounded-lg object-cover" />}
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="font-bold text-slate-900">{a.name}</div>
              <div className="mt-0.5 flex flex-wrap gap-1.5 text-xs">
                <Chip>{a.city}</Chip><Chip><Clock size={10} /> {a.visit_minutes} min</Chip><Chip tone="amber">{inr(a.price_inr)} total</Chip>
              </div>
              <div className="mt-1 text-xs text-slate-500">Open {a.open_from}–{a.open_until}{a.open_days.length < 7 ? ` · ${a.open_days.join(" ")}` : " · daily"}</div>
              <div className="mt-auto pt-2">
                {a.in_package ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600"><Check size={13} /> In your package</span>
                ) : a.can_add ? (
                  <button className="btn-primary !py-1.5 text-xs" disabled={!!busy} onClick={() => add(a)}>
                    <Plus size={13} /> {busy === a.attraction_id ? "Adding…" : `Add · ${fmtDate(a.suggested.date)} ${a.suggested.start}`}
                  </button>
                ) : <span className="text-xs text-rose-600">{a.reason}</span>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
