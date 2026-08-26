import { useEffect } from "react";

const DEST = "http://localhost:5173/observability";

export default function App() {
  useEffect(() => {
    window.location.replace(DEST);
  }, []);

  return (
    <div className="page">
      <h1>Observability moved</h1>
      <p className="lede">
        Open the dashboard at <a href={DEST}>{DEST.replace("http://", "")}</a>
      </p>
    </div>
  );
}
