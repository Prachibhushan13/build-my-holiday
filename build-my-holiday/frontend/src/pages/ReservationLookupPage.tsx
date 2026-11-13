import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { api, ApiError } from "../api/client";
import { ErrorBox } from "../components/ui";

export default function ReservationLookupPage() {
  const nav = useNavigate();
  const [ref, setRef] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const v = ref.trim();
    if (!/^\d{10}$/.test(v)) { setErr("Enter the 10-digit reservation number."); return; }
    setBusy(true); setErr(null);
    try { await api.reservation(v); nav(`/reservation/${v}`); }
    catch (ex) { setErr(ex instanceof ApiError && ex.status === 404 ? "Reservation not found. Check the number and try again." : (ex as Error).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="mx-auto max-w-lg">
      <form onSubmit={submit} className="card p-6">
        <h1 className="text-xl font-extrabold text-slate-900">Find my reservation</h1>
        <p className="mt-1 text-sm text-slate-500">Enter the 10-digit number you received when you confirmed your package.</p>
        <label className="label mt-5">Reservation number</label>
        <input className="input font-mono text-lg tracking-widest" inputMode="numeric" maxLength={10} value={ref} placeholder="0492817364"
          onChange={(e) => setRef(e.target.value.replace(/\D/g, ""))} aria-label="Reservation number" />
        {err && <div className="mt-3"><ErrorBox title="Not found" message={err} /></div>}
        <button className="btn-primary mt-4 w-full" disabled={busy}><Search size={15} /> {busy ? "Searching…" : "Open reservation"}</button>
      </form>
    </div>
  );
}
