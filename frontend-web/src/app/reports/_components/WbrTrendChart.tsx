"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type ChartWeek = {
  label: string;
};

type ChartSeries = {
  key: string;
  label: string;
  data: number[];
  color: string;
};

type Props = {
  title: string;
  weeks: ChartWeek[];
  series: ChartSeries[];
  formatValue: (value: number) => string;
  showTotal: boolean;
  onToggleTotal: () => void;
};

type TooltipPayload = {
  color?: string;
  dataKey?: string;
  name?: string;
  value?: number;
};

const CustomTooltip = ({
  active,
  label,
  payload,
  formatValue,
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipPayload[];
  formatValue: (value: number) => string;
}) => {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white/95 px-3 py-2 shadow-[0_20px_50px_rgba(15,23,42,0.18)]">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">{label}</p>
      <div className="mt-2 space-y-1.5">
        {payload.map((entry) => (
          <div key={String(entry.dataKey)} className="flex items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-2 text-[#0f172a]">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color || "#0a6fd6" }} />
              <span>{entry.name}</span>
            </div>
            <span className="font-semibold text-[#0f172a]">{formatValue(Number(entry.value || 0))}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function WbrTrendChart({ title, weeks, series, formatValue, showTotal, onToggleTotal }: Props) {
  const chartData = weeks.map((week, index) => {
    const point: Record<string, string | number> = { label: week.label };
    series.forEach((item) => {
      point[item.key] = item.data[index] ?? 0;
    });
    return point;
  });

  return (
    <div className="rounded-3xl border border-slate-200 bg-white/95 p-4 shadow-[0_30px_80px_rgba(10,59,130,0.12)] backdrop-blur md:p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#4c576f]">Trend</p>
          <h3 className="text-lg font-semibold text-[#0f172a]">{title}</h3>
        </div>
        <button
          type="button"
          onClick={onToggleTotal}
          className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold transition ${
            showTotal
              ? "border-[#0a6fd6] bg-[#0a6fd6] text-white shadow-[0_10px_24px_rgba(10,111,214,0.24)]"
              : "border-[#d5e2f7] bg-[#f7faff] text-[#4c576f] hover:border-[#0a6fd6] hover:text-[#0a6fd6]"
          }`}
          aria-pressed={showTotal}
        >
          Total
        </button>
      </div>
      <div className="h-[260px] w-full">
        {series.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-[#d5e2f7] bg-[#f7faff] px-6 text-center text-sm text-[#4c576f]">
            Select rows from the table to compare trends.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 20, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="#dbe7fb" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#4c576f", fontSize: 12 }}
                axisLine={{ stroke: "#cbd5e1" }}
                tickLine={{ stroke: "#cbd5e1" }}
              />
              <YAxis
                tickFormatter={(value) => formatValue(Number(value))}
                tick={{ fill: "#4c576f", fontSize: 12 }}
                axisLine={{ stroke: "#cbd5e1" }}
                tickLine={{ stroke: "#cbd5e1" }}
                width={64}
              />
              <Tooltip content={<CustomTooltip formatValue={formatValue} />} />
              <Legend wrapperStyle={{ paddingTop: 8 }} />
              {series.map((item) => (
                <Line
                  key={item.key}
                  type="monotone"
                  dataKey={item.key}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={item.key === "total" ? 3 : 2}
                  dot={{ r: item.key === "total" ? 4 : 3 }}
                  activeDot={{ r: item.key === "total" ? 6 : 5 }}
                  animationDuration={300}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
