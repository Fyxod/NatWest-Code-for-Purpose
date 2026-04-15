import React from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';

interface ChartRendererProps {
  chartType: string;
  data: Array<Record<string, string | number | null>>;
  xKey: string;
  yKeys: string[];
  title?: string;
  height?: number;
}

const COLORS = ['#0EA5E9', '#22C55E', '#F97316', '#A855F7', '#E11D48', '#14B8A6'];

const isNumericSeries = (value: unknown) => typeof value === 'number' && Number.isFinite(value);

const ChartRenderer: React.FC<ChartRendererProps> = ({
  chartType,
  data,
  xKey,
  yKeys,
  title,
  height = 360,
}) => {
  const safeType = (chartType || 'bar').toLowerCase();
  const series = yKeys && yKeys.length > 0 ? yKeys : [];

  if (!data || data.length === 0) {
    return <div className="text-sm text-muted-foreground">No chart data available.</div>;
  }

  const fallbackSeries = series.length > 0 ? series : Object.keys(data[0]).filter((k) => k !== xKey);
  const primarySeries = fallbackSeries[0];

  if (!primarySeries) {
    return <div className="text-sm text-muted-foreground">Unable to infer chart series from data.</div>;
  }

  return (
    <div className="w-full">
      {title && <h3 className="text-base font-semibold mb-3">{title}</h3>}
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          {safeType === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) => (
                <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          ) : safeType === 'area' ? (
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) => (
                <Area key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} fill={COLORS[idx % COLORS.length]} fillOpacity={0.22} />
              ))}
            </AreaChart>
          ) : safeType === 'pie' ? (
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie data={data} dataKey={primarySeries} nameKey={xKey} outerRadius={120}>
                {data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          ) : safeType === 'scatter' ? (
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey={xKey} name={xKey} />
              <YAxis type="number" dataKey={primarySeries} name={primarySeries} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter
                data={data.filter((row) => isNumericSeries(row[xKey]) && isNumericSeries(row[primarySeries]))}
                fill={COLORS[0]}
              />
            </ScatterChart>
          ) : safeType === 'radar' ? (
            <RadarChart data={data}>
              <PolarGrid />
              <PolarAngleAxis dataKey={xKey} />
              <PolarRadiusAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) => (
                <Radar
                  key={key}
                  name={key}
                  dataKey={key}
                  stroke={COLORS[idx % COLORS.length]}
                  fill={COLORS[idx % COLORS.length]}
                  fillOpacity={0.2}
                />
              ))}
            </RadarChart>
          ) : safeType === 'composed' ? (
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) =>
                idx % 2 === 0 ? (
                  <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} />
                ) : (
                  <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2} dot={false} />
                )
              )}
            </ComposedChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) => (
                <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ChartRenderer;
