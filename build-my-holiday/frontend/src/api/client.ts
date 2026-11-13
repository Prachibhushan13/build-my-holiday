import type { Catalog, Change, GenerateResult, OptionsResult, Pkg, TripRequest } from "../types";

export class ApiError extends Error {
  status: number;
  errors: { field: string; message: string }[];
  violations: { code: string; message: string }[];
  constructor(status: number, message: string, errors: any[] = [], violations: any[] = []) {
    super(message);
    this.status = status; this.errors = errors; this.violations = violations;
  }
}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (res.ok) return (await res.json()) as T;
  let detail: any = null;
  try { detail = (await res.json()).detail; } catch { /* ignore */ }
  if (typeof detail === "string") throw new ApiError(res.status, detail);
  throw new ApiError(res.status, detail?.message || `Request failed (${res.status})`, detail?.errors, detail?.violations);
}

type Changed = Pkg & { change: Change };

export const api = {
  catalog: () => call<Catalog>("GET", "/api/catalog"),
  generate: (r: TripRequest) => call<GenerateResult>("POST", "/api/packages/generate", r),
  pkg: (id: string) => call<Pkg>("GET", `/api/packages/${id}`),
  options: (id: string) => call<OptionsResult>("GET", `/api/packages/${id}/options`),
  flightAlts: (id: string, direction: string) => call<any>("GET", `/api/packages/${id}/alternatives/flights?direction=${direction}`),
  hotelAlts: (id: string, city: string) => call<any>("GET", `/api/packages/${id}/alternatives/hotels?city=${encodeURIComponent(city)}`),
  attractions: (id: string) => call<{ attractions: any[] }>("GET", `/api/packages/${id}/attractions`),
  cityPlans: (id: string) => call<any>("GET", `/api/packages/${id}/city-plans`),
  changeFlight: (id: string, direction: string, flight_id: string) => call<Changed>("PATCH", `/api/packages/${id}/flight`, { direction, flight_id }),
  changeHotel: (id: string, city: string, hotel_id: string, room_id: string) => call<Changed>("PATCH", `/api/packages/${id}/hotel`, { city, hotel_id, room_id }),
  addAttraction: (id: string, attraction_id: string, date?: string, start?: string) => call<Changed>("POST", `/api/packages/${id}/attractions`, { attraction_id, date, start }),
  removeAttraction: (id: string, attraction_id: string) => call<Changed>("DELETE", `/api/packages/${id}/attractions/${attraction_id}`),
  changeCities: (id: string, plan: { city: string; nights: number }[]) => call<Changed>("POST", `/api/packages/${id}/cities`, { plan }),
  confirm: (id: string, allow_over_budget = false) => call<Pkg>("POST", `/api/packages/${id}/confirm`, { allow_over_budget }),
  reservation: (ref: string) => call<Pkg>("GET", `/api/reservations/${ref}`),
};
