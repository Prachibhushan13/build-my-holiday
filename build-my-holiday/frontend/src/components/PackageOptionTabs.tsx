import { Clock, IndianRupee, Star } from "lucide-react";
import type { PackageOption } from "../types";
import { dur, inr } from "../api/format";

const ICON: Record<string, typeof Star> = { cheapest: IndianRupee, fastest: Clock, best_rated: Star };
const HINT: Record<string, string> = {
  cheapest: "Lowest total price",
  fastest: "Least flight + city-to-city travel time",
  best_rated: "Highest average hotel stars (within budget)",
};

export default function PackageOptionTabs({ options, currentId, onSelect }: { options: PackageOption[]; currentId: string; onSelect: (id: string) => void }) {
  if (options.length < 2) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-3" role="tablist" aria-label="Package options">
      {options.map((o) => {
        const Icon = ICON[o.option] ?? Star;
        const active = o.package_id === currentId;
        return (
          <button key={o.package_id} role="tab" aria-selected={active} onClick={() => onSelect(o.package_id)}
            className={`rounded-2xl border p-4 text-left transition ${active ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : "border-slate-200 bg-white hover:border-slate-300"}`}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-bold text-slate-900"><Icon size={16} className="text-brand-600" /> {o.title}</span>
              <span className="text-lg font-extrabold tabular-nums">{inr(o.total_inr)}</span>
            </div>
            <div className="mt-1 text-xs text-slate-500">{HINT[o.option]}</div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
              <span><Clock size={11} className="mr-1 inline" />{dur(o.travel_minutes)} travel</span>
              <span><Star size={11} className="mr-1 inline" />{o.avg_stars.toFixed(2)}★ avg</span>
              <span>{o.cities.join(" → ")}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
