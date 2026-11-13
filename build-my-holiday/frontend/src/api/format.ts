export const inr = (n: number) => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
export const signedInr = (n: number) => (n === 0 ? "±₹0" : (n > 0 ? "+" : "-") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN"));
export const dur = (min: number) => `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;
export const fmtDate = (iso: string, opts: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short" }) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-IN", opts);
export const stars = (n: number) => "★".repeat(n) + "☆".repeat(Math.max(0, 5 - n));
