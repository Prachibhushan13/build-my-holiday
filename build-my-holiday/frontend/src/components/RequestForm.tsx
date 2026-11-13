import { FormEvent, useState } from "react";
import { Baby, CalendarDays, Globe2, IndianRupee, MapPin, Moon, Plus, Sparkles, User, Users } from "lucide-react";
import type { Catalog, TripRequest } from "../types";

export const MENON: TripRequest = {
  name: "Menon family", departure_city: "Bengaluru", country: "Japan", start_date: "2027-04-10", nights: 6,
  adults: 2, child_ages: [6], budget_inr: 350000,
};

type Errors = Record<string, string>;

export function validate(f: { [k: string]: any }, cat: Catalog): Errors {
  const e: Errors = {};
  if (!f.departure_city) e.departure_city = "Choose a departure city.";
  if (!f.country) e.country = "Choose a destination country.";
  if (!f.start_date) e.start_date = "Pick the holiday start date.";
  else if (isNaN(Date.parse(f.start_date))) e.start_date = "Enter a valid date.";
  const n = Number(f.nights);
  if (f.nights === "" || !Number.isInteger(n)) e.nights = "Enter a whole number of nights.";
  else if (n < cat.rules.min_nights || n > cat.rules.max_nights) e.nights = `Nights must be between ${cat.rules.min_nights} and ${cat.rules.max_nights}.`;
  const a = Number(f.adults);
  if (f.adults === "" || !Number.isInteger(a) || a < 1) e.adults = "At least 1 adult is required.";
  f.child_ages.forEach((v: string, i: number) => {
    const x = Number(v);
    if (v === "" || !Number.isInteger(x) || x < 0 || x > 17) e[`age${i}`] = "Age 0–17";
  });
  const b = Number(f.budget_inr);
  if (f.budget_inr === "" || !(b > 0)) e.budget_inr = "Enter a budget in INR greater than 0.";
  return e;
}

export default function RequestForm({ catalog, busy, serverErrors, onSubmit }: {
  catalog: Catalog; busy: boolean; serverErrors: Errors; onSubmit: (r: TripRequest) => void;
}) {
  const [f, setF] = useState<any>({ name: "", departure_city: "", country: "", start_date: "", nights: "", adults: 1, child_ages: [] as string[], budget_inr: "" });
  const [touched, setTouched] = useState(false);
  const errors: Errors = { ...(touched ? validate(f, catalog) : {}), ...serverErrors };
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const fill = () => { setF({ ...MENON, child_ages: MENON.child_ages.map(String) }); setTouched(false); };
  const setChildren = (n: number) => setF((p: any) => ({ ...p, child_ages: Array.from({ length: n }, (_, i) => p.child_ages[i] ?? "") }));

  function submit(ev: FormEvent) {
    ev.preventDefault();
    setTouched(true);
    if (Object.keys(validate(f, catalog)).length) return;
    onSubmit({ name: f.name || "Traveler", departure_city: f.departure_city, country: f.country, start_date: f.start_date,
      nights: Number(f.nights), adults: Number(f.adults), child_ages: f.child_ages.map(Number), budget_inr: Number(f.budget_inr) });
  }
  const err = (k: string) => errors[k] && <p className="mt-1 text-xs font-medium text-rose-600">{errors[k]}</p>;
  const cls = (k: string) => `input ${errors[k] ? "input-error" : ""}`;
  const win = catalog.rules.data_window;

  return (
    <form onSubmit={submit} className="card p-6" noValidate>
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-extrabold text-slate-900">Tell us about your trip</h2>
        <button type="button" onClick={fill} className="btn-secondary !px-3 !py-1.5 text-xs"><Sparkles size={14} /> Use the Menon example</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="label flex items-center gap-1.5"><User size={13} /> Traveller name (optional)</label>
          <input className="input" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Menon family" />
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><MapPin size={13} /> Departure city</label>
          <select className={cls("departure_city")} value={f.departure_city} onChange={(e) => set("departure_city", e.target.value)}>
            <option value="">Select…</option>
            {catalog.departure_cities.map((c) => <option key={c.airport} value={c.city}>{c.city} ({c.airport})</option>)}
          </select>{err("departure_city")}
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><Globe2 size={13} /> Destination country</label>
          <select className={cls("country")} value={f.country} onChange={(e) => set("country", e.target.value)}>
            <option value="">Select…</option>
            {catalog.countries.map((c) => <option key={c.code} value={c.name}>{c.name}</option>)}
          </select>{err("country")}
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><CalendarDays size={13} /> Holiday start date</label>
          <input type="date" className={cls("start_date")} value={f.start_date} onChange={(e) => set("start_date", e.target.value)} />
          <p className="mt-1 text-xs text-slate-400">The day you land. Flights &amp; rooms exist {win.first_night} to {win.last_departure}.</p>{err("start_date")}
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><Moon size={13} /> Total nights ({catalog.rules.min_nights}–{catalog.rules.max_nights})</label>
          <input type="number" className={cls("nights")} value={f.nights} onChange={(e) => set("nights", e.target.value)} min={catalog.rules.min_nights} max={catalog.rules.max_nights} />{err("nights")}
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><Users size={13} /> Adults</label>
          <input type="number" className={cls("adults")} value={f.adults} onChange={(e) => set("adults", e.target.value)} min={1} />{err("adults")}
        </div>
        <div>
          <label className="label flex items-center gap-1.5"><Baby size={13} /> Children</label>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-secondary !px-3" onClick={() => setChildren(Math.max(0, f.child_ages.length - 1))} aria-label="Fewer children">−</button>
            <span className="w-8 text-center font-semibold" data-testid="child-count">{f.child_ages.length}</span>
            <button type="button" className="btn-secondary !px-3" onClick={() => setChildren(Math.min(10, f.child_ages.length + 1))} aria-label="More children"><Plus size={14} /></button>
          </div>
          {err("children")}
        </div>
        {f.child_ages.length > 0 && (
          <div className="sm:col-span-2">
            <label className="label">Child ages (0–17)</label>
            <div className="flex flex-wrap gap-3">
              {f.child_ages.map((v: string, i: number) => (
                <div key={i} className="w-24">
                  <input type="number" min={0} max={17} className={cls(`age${i}`)} value={v} placeholder={`Child ${i + 1}`}
                    onChange={(e) => set("child_ages", f.child_ages.map((x: string, j: number) => (j === i ? e.target.value : x)))} />
                  {err(`age${i}`)}
                </div>
              ))}
            </div>
            {err("child_ages")}
          </div>
        )}
        <div className="sm:col-span-2">
          <label className="label flex items-center gap-1.5"><IndianRupee size={13} /> Total budget (INR, everything included)</label>
          <input type="number" className={cls("budget_inr")} value={f.budget_inr} onChange={(e) => set("budget_inr", e.target.value)} placeholder="350000" />{err("budget_inr")}
        </div>
      </div>
      <button className="btn-primary mt-6 w-full !py-3 text-base" disabled={busy}>{busy ? "Building your holiday…" : "Build my holiday"}</button>
    </form>
  );
}
