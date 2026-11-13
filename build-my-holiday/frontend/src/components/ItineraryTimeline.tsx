import { AlertTriangle, BedDouble, Bus, Landmark, MapPin, Plane, Plus, RefreshCw, Trash2 } from "lucide-react";
import type { Day, DayEvent, Pkg } from "../types";
import { fmtDate, inr } from "../api/format";
import { Chip } from "./ui";

const ICON = { flight: Plane, transfer: Bus, hotel: BedDouble, attraction: Landmark } as const;
const TONE = {
  flight: "bg-sky-50 text-sky-700 ring-sky-100",
  transfer: "bg-amber-50 text-amber-700 ring-amber-100",
  hotel: "bg-violet-50 text-violet-700 ring-violet-100",
  attraction: "bg-emerald-50 text-emerald-700 ring-emerald-100",
} as const;
const LABEL = { flight: "Flight", transfer: "Transfer", hotel: "Hotel", attraction: "Attraction" } as const;

interface Props {
  pkg: Pkg;
  editable: boolean;
  onChangeFlight?: (direction: "arrival" | "return") => void;
  onChangeHotel?: (city: string) => void;
  onRemoveAttraction?: (id: string) => void;
  onAddAttraction?: () => void;
  busyId?: string | null;
}

function Event({ ev, props }: { ev: DayEvent; props: Props }) {
  const Icon = ICON[ev.type];
  const isCheckOut = ev.kind === "check-out";
  const img = ev.meta?.image ? `/${ev.meta.image}` : null;
  return (
    <li className="flex gap-3">
      <div className="w-14 shrink-0 pt-1 text-right">
        <div className="text-sm font-bold tabular-nums text-slate-800">{ev.time}</div>
        {ev.end_time && <div className="text-[11px] tabular-nums text-slate-400">→ {ev.end_time}</div>}
      </div>
      <div className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full ring-4 ${TONE[ev.type]}`}><Icon size={16} /></div>
      <div className={`min-w-0 flex-1 rounded-xl border border-slate-200 p-3 ${isCheckOut ? "bg-slate-50" : "bg-white"}`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 gap-3">
            {img && !isCheckOut && <img src={img} alt="" loading="lazy" className="hidden h-14 w-20 shrink-0 rounded-lg object-cover sm:block" />}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={ev.type === "flight" ? "blue" : ev.type === "transfer" ? "amber" : ev.type === "hotel" ? "slate" : "green"}>{LABEL[ev.type]}</Chip>
                <Chip><MapPin size={10} /> {ev.city}</Chip>
                {ev.meta?.role && <Chip tone="blue">{ev.meta.role === "ARRIVAL" ? "Arrival" : "Return"}</Chip>}
              </div>
              <div className="mt-1 font-semibold text-slate-900">{ev.title}</div>
              <div className="text-xs text-slate-500">{ev.subtitle}</div>
            </div>
          </div>
          <div className="text-right">
            {ev.price_inr > 0 && <div className="font-bold tabular-nums text-slate-900">{inr(ev.price_inr)}</div>}
            {props.editable && ev.type === "flight" && (
              <button className="btn-secondary mt-1 !px-2.5 !py-1 text-xs" onClick={() => props.onChangeFlight?.(ev.meta.role === "ARRIVAL" ? "arrival" : "return")}>
                <RefreshCw size={12} /> Change flight
              </button>
            )}
            {props.editable && ev.type === "hotel" && ev.kind === "check-in" && (
              <button className="btn-secondary mt-1 !px-2.5 !py-1 text-xs" onClick={() => props.onChangeHotel?.(ev.city)}>
                <RefreshCw size={12} /> Change hotel
              </button>
            )}
            {props.editable && ev.type === "attraction" && (
              <button className="btn-danger mt-1 !px-2.5 !py-1 text-xs" disabled={props.busyId === ev.catalog_id} onClick={() => props.onRemoveAttraction?.(ev.catalog_id)}>
                <Trash2 size={12} /> Remove
              </button>
            )}
          </div>
        </div>
        {ev.warnings.map((w, i) => (
          <div key={i} className="mt-2 flex gap-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{w}</div>
        ))}
      </div>
    </li>
  );
}

export default function ItineraryTimeline(props: Props) {
  const { pkg } = props;
  return (
    <section aria-label="Day-by-day plan">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-extrabold text-slate-900">Day-by-day plan</h2>
        {props.editable && (
          <button className="btn-primary !py-2" onClick={props.onAddAttraction}><Plus size={15} /> Add attraction</button>
        )}
      </div>
      <div className="space-y-4">
        {pkg.itinerary.map((d: Day) => (
          <div key={d.date} className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <span className="rounded-lg bg-brand-600 px-2.5 py-1 text-xs font-bold text-white">{d.day_number >= 1 ? `Day ${d.day_number}` : "Before"}</span>
                <span className="font-semibold text-slate-800">{fmtDate(d.date, { weekday: "long", day: "numeric", month: "long" })}</span>
              </div>
              <div className="flex items-center gap-2">
                {d.label && <Chip tone={d.label.startsWith("Return") ? "rose" : "blue"}>{d.label}</Chip>}
                {d.city && <Chip><MapPin size={10} /> {d.city}</Chip>}
              </div>
            </div>
            <ul className="space-y-3 p-4">
              {d.events.length === 0 && <li className="text-sm text-slate-400">Nothing planned — free time.</li>}
              {d.events.map((ev, i) => <Event key={ev.item_id + ev.kind + i} ev={ev} props={props} />)}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
