type PayloadItem = {
  name?: string;
  value?: number | string | null;
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, unknown>;
};

export function ChartTooltip({
  active,
  payload,
  label,
  valueFormatter = (value) => String(value),
  labelFormatter = (value) => String(value),
}: {
  active?: boolean;
  payload?: PayloadItem[];
  label?: string | number;
  valueFormatter?: (value: number) => string;
  labelFormatter?: (value: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-zinc-500">
        {labelFormatter(String(label ?? ""))}
      </div>
      <div className="space-y-1.5">
        {payload.map((item, index) => {
          const value = typeof item.value === "number" ? item.value : Number(item.value);
          if (!Number.isFinite(value)) return null;
          return (
            <div key={`${item.dataKey}-${index}`} className="flex items-center justify-between gap-6">
              <span className="inline-flex items-center gap-1.5 text-zinc-400">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: item.color ?? "#9ae6a5" }}
                />
                {item.name}
              </span>
              <span className="tabular font-medium text-zinc-100">{valueFormatter(value)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
