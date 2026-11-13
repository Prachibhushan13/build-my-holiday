import { Link, Route, Routes, useLocation } from "react-router-dom";
import { Plane, Search } from "lucide-react";
import HomePage from "./pages/HomePage";
import PackagePage from "./pages/PackagePage";
import ConfirmationPage from "./pages/ConfirmationPage";
import ReservationLookupPage from "./pages/ReservationLookupPage";

export default function App() {
  const loc = useLocation();
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-extrabold text-brand-900">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white"><Plane size={18} /></span>
            Build My Holiday
          </Link>
          <nav className="flex items-center gap-2 text-sm font-medium">
            <Link to="/" className={`rounded-lg px-3 py-2 ${loc.pathname === "/" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}`}>Plan a trip</Link>
            <Link to="/find" className={`flex items-center gap-1.5 rounded-lg px-3 py-2 ${loc.pathname === "/find" ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}`}>
              <Search size={15} /> Find my reservation
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/package/:id" element={<PackagePage />} />
          <Route path="/reservation/:ref" element={<ConfirmationPage />} />
          <Route path="/find" element={<ReservationLookupPage />} />
          <Route path="*" element={<HomePage />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400">
        All data is synthetic. Photos are real and freely licensed — <a className="underline" href="/images/ATTRIBUTIONS.md" target="_blank" rel="noreferrer">photo credits</a>.
      </footer>
    </div>
  );
}
