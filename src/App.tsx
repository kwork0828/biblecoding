import { useEffect, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import { ensureSeeded } from './db/seed';
import HomePage from './pages/HomePage';
import ReviewPage from './pages/ReviewPage';

export default function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    ensureSeeded().then(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center text-ink-soft text-sm">
        불러오는 중…
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/review/:deckId" element={<ReviewPage />} />
    </Routes>
  );
}
