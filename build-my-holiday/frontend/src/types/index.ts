export interface Catalog {
  departure_cities: { airport: string; city: string }[];
  countries: { code: string; name: string; cities: string[] }[];
  rules: { min_nights: number; max_nights: number; min_nights_per_city: number; data_window: { first_night: string; last_departure: string } };
}
export interface TripRequest {
  name: string; departure_city: string; country: string; start_date: string; nights: number;
  adults: number; child_ages: number[]; budget_inr: number;
}
export interface Summary {
  total_inr: number; budget_inr: number; remaining_inr: number; within_budget: boolean;
  breakdown: { flights: number; hotels: number; transfers: number; attractions: number };
  travel_minutes: number; avg_stars: number; nights: number; cities: string[];
}
export interface TripItem {
  item_id: string; type: "flight" | "hotel" | "transfer" | "attraction"; name: string; city: string; status: string;
  catalog_id: string; room_id: string | null; start: string; end: string | null; quantity: number; price_inr: number;
  booking: { reference: string } | null; sources: string[]; warnings: string[]; meta: Record<string, any>;
}
export interface Trip {
  trip_id: string; traveler: { name: string; home_airport: string; adults: number; children: number; child_ages: number[] };
  start_date: string; end_date: string; country: string; budget_inr: number; total_inr: number; items: TripItem[];
}
export interface DayEvent {
  item_id: string; type: TripItem["type"]; city: string; price_inr: number; time: string; end_time?: string; end_date?: string;
  title: string; subtitle: string; kind?: string; meta: Record<string, any>; warnings: string[]; catalog_id: string;
}
export interface Day { date: string; day_number: number; city: string | null; label: string | null; events: DayEvent[] }
export interface Change { previous_total_inr: number; new_total_inr: number; price_diff_inr: number; notes: string[] }
export interface Pkg {
  package_id: string; group_id: string | null; option: string | null; status: "PLANNED" | "BOOKED"; reference: string | null;
  request: TripRequest & { departure_airport: string }; plan: { city: string; nights: number }[];
  summary: Summary; itinerary: Day[]; trip: Trip; warnings: { item_id: string; item: string; message: string }[];
  confirmed_at?: string; change?: Change;
}
export interface PackageOption {
  option: string; title: string; package_id: string; total_inr: number; travel_minutes: number; avg_stars: number;
  cities: string[]; within_budget: boolean;
}
export interface GenerateResult {
  status: "OK" | "OVER_BUDGET" | "IMPOSSIBLE"; message: string; reasons?: string[]; suggestions?: string[];
  cheapest_total_inr?: number; deficit_inr?: number; options: PackageOption[]; package: Pkg | null;
}
export interface OptionsResult { status: string; options: PackageOption[]; suggestions?: string[]; deficit_inr?: number; cheapest_total_inr?: number }
