export default function App() {
  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-slate-800 bg-slate-950 px-4 py-3">
        <h1 className="text-lg font-bold text-indigo-400">ProFiles Launcher</h1>
      </header>
      <main className="flex-1 p-4">
        <p className="text-slate-400">Loading workstation profiles...</p>
      </main>
    </div>
  );
}
