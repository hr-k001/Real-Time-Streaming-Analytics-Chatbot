import { useEffect, useRef, useState } from 'react';
import { BarChart3 } from 'lucide-react';

interface Props {
  figure: Record<string, unknown>;
}

export function ChartDisplay({ figure }: Props) {
  const divRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!divRef.current || !figure || !figure.data) {
      setError(true);
      return;
    }

    setError(false);

    import('plotly.js-dist-min')
      .then(Plotly => {
        if (!divRef.current) return;
        const layout = {
          ...(figure.layout as object ?? {}),
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { color: 'var(--text-2)', family: 'Inter, sans-serif', size: 12 },
          margin: { t: 36, r: 16, b: 44, l: 52 },
          xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
          yaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
          legend: { bgcolor: 'transparent', borderwidth: 0 },
          colorway: ['#4f8ef7', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#38bdf8'],
        };
        Plotly.newPlot(
          divRef.current,
          figure.data as Plotly.Data[],
          layout as Plotly.Layout,
          { responsive: true, displayModeBar: false },
        );
      })
      .catch(() => setError(true));

    return () => {
      const el = divRef.current;
      if (el) {
        import('plotly.js-dist-min').then(P => { if (el) P.purge(el); });
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [figure]);

  if (error) {
    return (
      <div
        className="mt-3 flex flex-col items-center justify-center gap-2 py-8 rounded-xl border text-center"
        style={{ borderColor: 'var(--border)', color: 'var(--text-3)' }}
      >
        <BarChart3 size={28} strokeWidth={1.5} />
        <p className="text-[13px]">Chart could not be rendered</p>
      </div>
    );
  }

  return (
    <div
      className="mt-3 rounded-xl overflow-hidden border"
      style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
    >
      <div ref={divRef} style={{ minHeight: 280, width: '100%' }} />
    </div>
  );
}
