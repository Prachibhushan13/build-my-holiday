import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, SearchX } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Pkg } from "../types";
import PackageView, { ExportButton, TripHeader } from "../components/PackageView";
import { Spinner } from "../components/ui";

export default function ConfirmationPage() {
  const { ref = "" } = useParams();
  const [pkg, setPkg] = useState<Pkg | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setPkg(null); setNotFound(false); setErr(null);
    api.reservation(ref).then(setPkg).catch((e) => (e instanceof ApiError && e.status === 404 ? setNotFound(true) : setErr(e.message)));
  }, [ref]);

  if (notFound) return (
    <div className="card mx-auto max-w-lg p-8 text-center" data-testid="not-found">
      <SearchX className="mx-auto text-slate-400" size={40} />
      <h1 className="mt-3 text-xl font-extrabold">Reservation not found</h1>
      <p className="mt-1 text-sm text-slate-500">We could not find a reservation numbered <span className="font-mono">{ref}</span>. Check the 10 digits and try again.</p>
      <Link to="/find" className="btn-primary mt-5">Try another number</Link>
    </div>
  );
  if (err) return <div className="text-rose-600">{err}</div>;
  if (!pkg) return <Spinner label="Opening your reservation…" />;
  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-4 border-emerald-300 bg-emerald-50 p-5">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="text-emerald-600" size={36} />
          <div>
            <div className="text-sm font-semibold text-emerald-800">Booked · reservation number</div>
            <div className="select-all font-mono text-3xl font-extrabold tracking-widest text-emerald-900" data-testid="reference">{pkg.reference}</div>
          </div>
        </div>
        <div className="w-full sm:w-56"><ExportButton pkg={pkg} /></div>
      </div>
      <TripHeader pkg={pkg} />
      <PackageView pkg={pkg} editable={false} />
    </div>
  );
}
