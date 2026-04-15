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
  Treemap,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

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

type ChartCell = string | number | null;
type ChartRow = Record<string, ChartCell>;

interface Scatter3DPoint {
  x: number;
  y: number;
  z: number;
  size: number;
  color: string;
}

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== 'string') {
    return null;
  }

  const cleaned = value
    .replace(/[,$%]/g, '')
    .trim();
  if (!cleaned) {
    return null;
  }

  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
};

const colorFromScale = (value: number, min: number, max: number): string => {
  if (max <= min) {
    return 'hsl(195, 80%, 58%)';
  }
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const hue = 214 - ratio * 170;
  const lightness = 88 - ratio * 46;
  return `hsl(${hue}, 84%, ${lightness}%)`;
};

const normalizeToRange = (value: number, min: number, max: number, outMin: number, outMax: number) => {
  if (max <= min) {
    return (outMin + outMax) / 2;
  }
  return outMin + ((value - min) / (max - min)) * (outMax - outMin);
};

const buildScatter3DPoints = (
  rows: ChartRow[],
  xKey: string,
  seriesKeys: string[],
): { points: Scatter3DPoint[]; axes: { xAxis: string; yAxis: string; zAxis: string; sizeKey?: string } | null } => {
  if (!rows.length) {
    return { points: [], axes: null };
  }

  const allKeys = Object.keys(rows[0]);
  const numericKeys = allKeys.filter((key) => rows.some((row) => toNumber(row[key]) !== null));

  const xAxis = toNumber(rows[0][xKey]) !== null || rows.some((r) => toNumber(r[xKey]) !== null)
    ? xKey
    : numericKeys[0];
  if (!xAxis) {
    return { points: [], axes: null };
  }

  const candidateSeries = seriesKeys.filter((k) => k !== xAxis);
  const yAxis = candidateSeries[0] || numericKeys.find((k) => k !== xAxis);
  const zAxis = candidateSeries[1] || numericKeys.find((k) => k !== xAxis && k !== yAxis);
  const sizeKey = candidateSeries[2] || numericKeys.find((k) => k !== xAxis && k !== yAxis && k !== zAxis);

  if (!yAxis || !zAxis) {
    return { points: [], axes: null };
  }

  const parsedRows = rows
    .map((row) => {
      const xv = toNumber(row[xAxis]);
      const yv = toNumber(row[yAxis]);
      const zv = toNumber(row[zAxis]);
      const sv = sizeKey ? toNumber(row[sizeKey]) : null;
      if (xv === null || yv === null || zv === null) {
        return null;
      }
      return { xv, yv, zv, sv };
    })
    .filter((row): row is { xv: number; yv: number; zv: number; sv: number | null } => row !== null);

  if (!parsedRows.length) {
    return { points: [], axes: null };
  }

  const xValues = parsedRows.map((r) => r.xv);
  const yValues = parsedRows.map((r) => r.yv);
  const zValues = parsedRows.map((r) => r.zv);
  const sizeValues = parsedRows.map((r) => r.sv).filter((v): v is number => v !== null);

  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const zMin = Math.min(...zValues);
  const zMax = Math.max(...zValues);
  const sizeMin = sizeValues.length ? Math.min(...sizeValues) : 0;
  const sizeMax = sizeValues.length ? Math.max(...sizeValues) : 1;

  const points = parsedRows.map((row) => ({
    x: normalizeToRange(row.xv, xMin, xMax, -1, 1),
    y: normalizeToRange(row.yv, yMin, yMax, -1, 1),
    z: normalizeToRange(row.zv, zMin, zMax, -1, 1),
    size:
      row.sv === null
        ? 0.04
        : normalizeToRange(row.sv, sizeMin, sizeMax, 0.03, 0.09),
    color: colorFromScale(row.zv, zMin, zMax),
  }));

  return { points, axes: { xAxis, yAxis, zAxis, sizeKey: sizeKey || undefined } };
};

const Scatter3DScene: React.FC<{ points: Scatter3DPoint[]; height: number }> = ({ points, height }) => {
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const width = Math.max(container.clientWidth, 320);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#f8fafc');

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(2.5, 2.2, 2.4);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.85);
    directionalLight.position.set(2.8, 2.6, 1.9);
    scene.add(directionalLight);

    const grid = new THREE.GridHelper(2.4, 12, 0xcbd5e1, 0xe2e8f0);
    grid.position.y = -1.05;
    scene.add(grid);
    scene.add(new THREE.AxesHelper(1.4));

    const pointGeometry = new THREE.SphereGeometry(1, 12, 12);
    const pointMeshes: THREE.Mesh[] = [];
    points.forEach((p) => {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(p.color),
        roughness: 0.42,
        metalness: 0.1,
      });
      const mesh = new THREE.Mesh(pointGeometry, material);
      mesh.position.set(p.x, p.y, p.z);
      mesh.scale.setScalar(p.size);
      scene.add(mesh);
      pointMeshes.push(mesh);
    });

    let frameId = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    animate();

    const handleResize = () => {
      if (!containerRef.current) {
        return;
      }
      const nextWidth = Math.max(containerRef.current.clientWidth, 320);
      renderer.setSize(nextWidth, height);
      camera.aspect = nextWidth / height;
      camera.updateProjectionMatrix();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(frameId);
      controls.dispose();
      pointMeshes.forEach((mesh) => {
        scene.remove(mesh);
        if (mesh.material instanceof THREE.Material) {
          mesh.material.dispose();
        }
      });
      pointGeometry.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [points, height]);

  return <div ref={containerRef} style={{ width: '100%', height }} />;
};

const HeatmapRenderer: React.FC<{
  rows: ChartRow[];
  xKey: string;
  seriesKeys: string[];
}> = ({ rows, xKey, seriesKeys }) => {
  const trimmedRows = rows.slice(0, 60);
  const yLabels = seriesKeys.slice(0, 12);

  const values = yLabels
    .flatMap((yLabel) => trimmedRows.map((row) => toNumber(row[yLabel])))
    .filter((v): v is number => v !== null);

  if (!yLabels.length || !trimmedRows.length || !values.length) {
    return <div className="text-sm text-muted-foreground">Heatmap requires numeric series data.</div>;
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const gridMinWidth = Math.max(780, 160 + trimmedRows.length * 70);

  return (
    <div className="space-y-3">
      <div className="text-xs text-muted-foreground">
        Showing first {trimmedRows.length} columns and {yLabels.length} series.
      </div>
      <div className="rounded-md border overflow-auto" style={{ maxHeight: 470 }}>
        <div
          className="text-xs"
          style={{
            minWidth: gridMinWidth,
            display: 'grid',
            gridTemplateColumns: `160px repeat(${trimmedRows.length}, minmax(68px, 1fr))`,
          }}
        >
          <div className="sticky left-0 z-10 bg-background border-b border-r p-2 font-semibold">Series</div>
          {trimmedRows.map((row, idx) => (
            <div key={`h-head-${idx}`} className="border-b border-r p-2 text-[11px] text-muted-foreground">
              {String(row[xKey] ?? `Col ${idx + 1}`)}
            </div>
          ))}

          {yLabels.map((yLabel) => (
            <React.Fragment key={`h-row-${yLabel}`}>
              <div className="sticky left-0 z-10 bg-background border-b border-r p-2 font-medium">{yLabel}</div>
              {trimmedRows.map((row, idx) => {
                const num = toNumber(row[yLabel]);
                const bg = num === null ? '#f1f5f9' : colorFromScale(num, minValue, maxValue);
                return (
                  <div
                    key={`h-cell-${yLabel}-${idx}`}
                    className="border-b border-r p-2 text-center"
                    style={{ backgroundColor: bg }}
                    title={`${String(row[xKey] ?? '')} · ${yLabel}: ${num ?? 'n/a'}`}
                  >
                    {num === null ? '-' : num.toLocaleString()}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="text-xs text-muted-foreground">
        Intensity range: {minValue.toLocaleString()} to {maxValue.toLocaleString()}
      </div>
    </div>
  );
};

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
  const typedData = data as ChartRow[];

  if (!data || data.length === 0) {
    return <div className="text-sm text-muted-foreground">No chart data available.</div>;
  }

  const fallbackSeries = series.length > 0 ? series : Object.keys(data[0]).filter((k) => k !== xKey);
  const primarySeries = fallbackSeries[0];
  const scatter3D = buildScatter3DPoints(typedData, xKey, fallbackSeries);

  if (!primarySeries) {
    return <div className="text-sm text-muted-foreground">Unable to infer chart series from data.</div>;
  }

  if (safeType === 'heatmap') {
    return (
      <div className="w-full">
        {title && <h3 className="text-base font-semibold mb-3">{title}</h3>}
        <HeatmapRenderer rows={typedData} xKey={xKey} seriesKeys={fallbackSeries} />
      </div>
    );
  }

  if (safeType === 'scatter3d') {
    if (!scatter3D.axes || !scatter3D.points.length) {
      return (
        <div className="text-sm text-muted-foreground">
          3D scatter needs three numeric dimensions. Try a different chart type or data selection.
        </div>
      );
    }

    return (
      <div className="w-full">
        {title && <h3 className="text-base font-semibold mb-2">{title}</h3>}
        <p className="text-xs text-muted-foreground mb-2">
          3D axes: x = {scatter3D.axes.xAxis}, y = {scatter3D.axes.yAxis}, z = {scatter3D.axes.zAxis}
          {scatter3D.axes.sizeKey ? `, bubble size = ${scatter3D.axes.sizeKey}` : ''}
        </p>
        <div style={{ width: '100%', height }} className="rounded-md border overflow-hidden">
          <Scatter3DScene points={scatter3D.points} height={height} />
        </div>
      </div>
    );
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
                data={data
                  .map((row) => ({
                    ...row,
                    [xKey]: toNumber(row[xKey]),
                    [primarySeries]: toNumber(row[primarySeries]),
                  }))
                  .filter((row) => isNumericSeries(row[xKey]) && isNumericSeries(row[primarySeries]))}
                fill={COLORS[0]}
              />
            </ScatterChart>
          ) : safeType === 'bubble' ? (
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey={xKey} name={xKey} />
              <YAxis type="number" dataKey={primarySeries} name={primarySeries} />
              {fallbackSeries[1] && <ZAxis type="number" dataKey={fallbackSeries[1]} range={[48, 320]} name={fallbackSeries[1]} />}
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter
                data={data
                  .map((row) => ({
                    ...row,
                    [xKey]: toNumber(row[xKey]),
                    [primarySeries]: toNumber(row[primarySeries]),
                    ...(fallbackSeries[1] ? { [fallbackSeries[1]]: toNumber(row[fallbackSeries[1]]) } : {}),
                  }))
                  .filter((row) => {
                    const hasXY = isNumericSeries(row[xKey]) && isNumericSeries(row[primarySeries]);
                    const hasSize = fallbackSeries[1] ? isNumericSeries(row[fallbackSeries[1]]) : true;
                    return hasXY && hasSize;
                  })}
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
          ) : safeType === 'treemap' ? (
            <Treemap
              data={data
                .map((row) => ({
                  ...row,
                  [primarySeries]: toNumber(row[primarySeries]),
                }))
                .filter((row) => isNumericSeries(row[primarySeries]))}
              dataKey={primarySeries}
              nameKey={xKey}
              stroke="#ffffff"
              fill={COLORS[0]}
              aspectRatio={4 / 3}
            />
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
