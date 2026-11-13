import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Compass, ShieldCheck, Wallet } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Catalog, TripRequest } from "../types";
import RequestForm from "../components/RequestForm";
import { ErrorBox, Spinner } from "../components/ui";

export default function HomePage() {
  const nav = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [formErr, setFormErr] = useState<string | null>(null);
  const [impossible, setImpossible] = useState<string[] | null>(null);

  useEffect(() => { api.catalog().then(setCatalog).catch((e) => setLoadErr(e.message)); }, []);

  async function submit(req: TripRequest) {
    setBusy(true); setServerErrors({}); setFormErr(null); setImpossible(null);
    try {
      const res = await api.generate(req);
      if (res.status === "IMPOSSIBLE") { setImpossible(res.reasons ?? [res.message]); return; }
      nav(`/package/${res.package!.package_id}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const m: Record<string, string> = {};
        e.errors.forEach((x) => { m[x.field] = x.message; });
        setServerErrors(m);
        setFormErr("Please fix the highlighted fields.");
      } else setFormErr(e instanceof Error ? e.message : "Something went wrong");
    } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-5">
      <section className="lg:col-span-2">
        <h1 className="text-4xl font-extrabold leading-tight text-brand-900">Your whole holiday,<br />built and checked for you.</h1>
        <p className="mt-3 text-slate-600">Tell us where, when and how much. We choose the cities, flights, hotels, airport and city transfers, and attractions — and re-check every rule each time you change something.</p>
        <ul className="mt-6 space-y-3 text-sm text-slate-700">
          <li className="flex gap-3"><Compass className="mt-0.5 text-brand-600" size={18} /> We pick the cities and split your nights.</li>
          <li className="flex gap-3"><ShieldCheck className="mt-0.5 text-brand-600" size={18} /> Every change is validated against rooms, seats, opening hours and transfer timings.</li>
          <li className="flex gap-3"><Wallet className="mt-0.5 text-brand-600" size={18} /> Cheapest, fastest and best-rated options — priced in ₹ against your budget.</li>
        </ul>
      </section>
      <section className="space-y-4 lg:col-span-3">
        {loadErr && <ErrorBox title="Could not load the catalog" message={loadErr} />}
        {!catalog && !loadErr && <Spinner />}
        {catalog && <RequestForm catalog={catalog} busy={busy} serverErrors={serverErrors} onSubmit={submit} />}
        {formErr && <ErrorBox title="Check your request" message={formErr} />}
        {impossible && (
          <div className="card border-amber-300 bg-amber-50 p-5" role="alert" data-testid="impossible">
            <h3 className="text-lg font-extrabold text-amber-900">No holiday package is possible for this request</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">{impossible.map((r, i) => <li key={i}>{r}</li>)}</ul>
            <p className="mt-3 text-sm text-amber-800">Try different dates, fewer nights, another departure city or a smaller group.</p>
          </div>
        )}
      </section>
    </div>
  );
}
