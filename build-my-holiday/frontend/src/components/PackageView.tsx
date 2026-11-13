import { ReactNode } from "react";
import { Clock, Download, Star } from "lucide-react";
import type { Pkg } from "../types";
import { dur, fmtDate } from "../api/format";
import ItineraryTimeline from "./ItineraryTimeline";
import PriceBreakdown from "./PriceBreakdown";
import { Chip } from "./ui";

export function TripHeader({ pkg }: { pkg: Pkg }) {
  const r = pkg.request;
  const kids = r.child_ages.length;
  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <div className="text-xl font-extrabold text-slate-900">{r.name} · {r.country}</div>
        <div className="mt-1 text-sm text-slate-600">
          {r.departure_city} ({r.departure_airport}) · {fmtDate(pkg.trip.start_date, { day: "numeric", month: "short", year: "numeric" })} – {fmtDate(pkg.trip.end_date, { day: "numeric", month: "short", year: "numeric" })} · {pkg.summary.nights} nights
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Chip>{r.adults} adult{r.adults > 1 ? "s" : ""}</Chip>
        {kids > 0 && <Chip>{kids} child{kids > 1 ? "ren" : ""} (age {r.child_ages.join(", ")})</Chip>}
        {pkg.plan.map((p) => <Chip key={p.city} tone="blue">{p.city} · {p.nights}n</Chip>)}
      </div>
    </div>
  );
}

export function PackageStats({ pkg }: { pkg: Pkg }) {
  return (
    <div className="card grid grid-cols-2 gap-3 p-4 text-sm">
      <div><div className="label !mb-0">Travel time</div><div className="mt-0.5 flex items-center gap-1.5 font-bold"><Clock size={14} /> {dur(pkg.summary.travel_minutes)}</div><div className="text-[11px] text-slate-400">flights + city-to-city</div></div>
      <div><div className="label !mb-0">Hotel class</div><div className="mt-0.5 flex items-center gap-1.5 font-bold"><Star size={14} /> {pkg.summary.avg_stars.toFixed(2)} avg stars</div><div className="text-[11px] text-slate-400">weighted by nights</div></div>
    </div>
  );
}

export function ExportButton({ pkg }: { pkg: Pkg }) {
  return (
    <a className="btn-secondary w-full" href={`/api/packages/${pkg.package_id}/export`} download={`trip-${pkg.package_id}.json`}>
      <Download size={15} /> Download JSON export
    </a>
  );
}

export default function PackageView({ pkg, editable, handlers, sidebarExtra }: {
  pkg: Pkg; editable: boolean; sidebarExtra?: ReactNode;
  handlers?: Pick<Parameters<typeof ItineraryTimeline>[0], "onChangeFlight" | "onChangeHotel" | "onRemoveAttraction" | "onAddAttraction" | "busyId">;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2"><ItineraryTimeline pkg={pkg} editable={editable} {...handlers} /></div>
      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <PriceBreakdown s={pkg.summary} />
        <PackageStats pkg={pkg} />
        {pkg.warnings.length > 0 && (
          <div className="card border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <div className="font-bold">Heads-up</div>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs">{pkg.warnings.map((w, i) => <li key={i}><b>{w.item}:</b> {w.message}</li>)}</ul>
          </div>
        )}
        {sidebarExtra}
      </aside>
    </div>
  );
}
