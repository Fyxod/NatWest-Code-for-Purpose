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

interface TreemapHierarchyNode {
  name: string;
  value?: number;
  children?: TreemapHierarchyNode[];
  fill?: string;
  pathLabel?: string;
}

interface TreemapModel {
  nodes: TreemapHierarchyNode[];
  hierarchyKeys: string[];
  totalValue: number;
}

interface TreemapContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  value?: number;
  payload?: TreemapHierarchyNode;
}

interface TreemapTooltipPayloadItem {
  value?: number;
  name?: string;
  payload?: TreemapHierarchyNode;
}

interface TreemapTooltipProps {
  active?: boolean;
  payload?: TreemapTooltipPayloadItem[];
  valueKey: string;
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

const TREEMAP_HUES = [212, 148, 26, 283, 352, 188, 48, 116, 8, 236];

const formatCompactNumber = (value: number) => new Intl.NumberFormat(undefined, { notation: 'compact' }).format(value);

const truncateLabel = (value: string, maxChars: number): string => {
  const text = String(value || '').trim();
  if (!text || text.length <= maxChars) {
    return text;
  }
  if (maxChars <= 2) {
    return text.slice(0, Math.max(0, maxChars));
  }
  return `${text.slice(0, maxChars - 1)}…`;
};

const isLikelyNumericColumn = (rows: ChartRow[], key: string): boolean => {
  if (!rows.length) {
    return false;
  }

  const usable = rows
    .map((row) => toNumber(row[key]))
    .filter((value): value is number => value !== null);
  if (!usable.length) {
    return false;
  }

  return usable.length / rows.length >= 0.7;
};

const buildTreemapHierarchy = (rows: ChartRow[], xKey: string, valueKey: string): TreemapModel => {
  if (!rows.length) {
    return { nodes: [], hierarchyKeys: [], totalValue: 0 };
  }

  const sampleKeys = Object.keys(rows[0]);
  const categoricalKeys = sampleKeys.filter((key) => key !== valueKey && !isLikelyNumericColumn(rows, key));

  const hierarchyKeys: string[] = [];
  if (xKey && xKey !== valueKey && sampleKeys.includes(xKey)) {
    hierarchyKeys.push(xKey);
  }

  for (const key of categoricalKeys) {
    if (hierarchyKeys.includes(key)) {
      continue;
    }
    hierarchyKeys.push(key);
    if (hierarchyKeys.length >= 3) {
      break;
    }
  }

  if (!hierarchyKeys.length) {
    const fallbackKey = sampleKeys.find((key) => key !== valueKey) || xKey;
    if (fallbackKey) {
      hierarchyKeys.push(fallbackKey);
    }
  }

  const root: TreemapHierarchyNode = { name: 'root', children: [] };
  let totalValue = 0;

  const upsertChild = (parent: TreemapHierarchyNode, name: string): TreemapHierarchyNode => {
    if (!parent.children) {
      parent.children = [];
    }

    const existing = parent.children.find((child) => child.name === name);
    if (existing) {
      return existing;
    }

    const created: TreemapHierarchyNode = { name, children: [] };
    parent.children.push(created);
    return created;
  };

  rows.forEach((row) => {
    const value = toNumber(row[valueKey]);
    if (value === null || value <= 0) {
      return;
    }

    const path = hierarchyKeys.map((key) => {
      const raw = row[key];
      const text = String(raw ?? '').trim();
      return text || 'Unknown';
    });

    if (!path.length) {
      return;
    }

    totalValue += value;

    let current = root;
    const pathParts: string[] = [];
    path.forEach((segment, idx) => {
      pathParts.push(segment);
      const child = upsertChild(current, segment);
      child.pathLabel = pathParts.join(' > ');

      if (idx === path.length - 1) {
        child.value = (child.value || 0) + value;
      } else {
        current = child;
      }
    });
  });

  if (!root.children || !root.children.length) {
    return { nodes: [], hierarchyKeys, totalValue: 0 };
  }

  const paintNode = (node: TreemapHierarchyNode, hue: number, depth: number) => {
    const saturation = Math.max(42, 76 - depth * 8);
    const lightness = Math.min(70, 44 + depth * 9);
    node.fill = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

    node.children?.forEach((child) => paintNode(child, hue, depth + 1));
  };

  root.children.forEach((child, idx) => {
    paintNode(child, TREEMAP_HUES[idx % TREEMAP_HUES.length], 0);
  });

  return {
    nodes: root.children,
    hierarchyKeys,
    totalValue,
  };
};

const TreemapCellRenderer: React.FC<TreemapContentProps> = ({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  name,
  value,
  payload,
}) => {
  if (width < 2 || height < 2) {
    return null;
  }

  const fill = payload?.fill || '#93c5fd';
  const showName = width >= 86 && height >= 32;
  const showValue = width >= 116 && height >= 52 && typeof value === 'number';
  const maxChars = Math.max(8, Math.floor((Math.min(width - 12, 300)) / 7));
  const label = truncateLabel(String(name || ''), maxChars);

  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#e2e8f0" strokeWidth={1} />
      {showName && (
        <text
          x={x + 8}
          y={y + 18}
          fill="#ffffff"
          stroke="rgba(2, 6, 23, 0.7)"
          strokeWidth={1.25}
          paintOrder="stroke"
          fontSize={12}
          fontWeight={800}
          letterSpacing={0.1}
        >
          {label}
        </text>
      )}
      {showValue && (
        <text
          x={x + 8}
          y={y + 32}
          fill="#ffffff"
          stroke="rgba(2, 6, 23, 0.64)"
          strokeWidth={1}
          paintOrder="stroke"
          fontSize={11}
          fontWeight={700}
          letterSpacing={0.1}
        >
          {formatCompactNumber(value || 0)}
        </text>
      )}
    </g>
  );
};

const TreemapHoverTooltip: React.FC<TreemapTooltipProps> = ({ active, payload, valueKey }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const point = payload[0];
  const item = point.payload;
  const numericValue = typeof point.value === 'number' ? point.value : toNumber(point.value);
  const pathLabel = item?.pathLabel || point.name || 'Segment';

  return (
    <div className="rounded-md border bg-background px-3 py-2 shadow text-xs">
      <div className="font-semibold text-foreground max-w-72 break-words">{pathLabel}</div>
      {numericValue !== null && numericValue !== undefined && (
        <div className="text-muted-foreground mt-1">
          {valueKey}: {numericValue.toLocaleString()}
        </div>
      )}
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
  const firstRow = typedData[0] || {};
  const fallbackSeries = series.length > 0 ? series : Object.keys(firstRow).filter((k) => k !== xKey);
  const primarySeries = fallbackSeries[0] || '';
  const scatter3D = buildScatter3DPoints(typedData, xKey, fallbackSeries);
  const treemapModel = React.useMemo(() => {
    if (safeType !== 'treemap' || !primarySeries || !typedData.length) {
      return { nodes: [], hierarchyKeys: [], totalValue: 0 } as TreemapModel;
    }
    return buildTreemapHierarchy(typedData, xKey, primarySeries);
  }, [safeType, typedData, xKey, primarySeries]);

  if (!typedData.length) {
    return <div className="text-sm text-muted-foreground">No chart data available.</div>;
  }

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

  if (safeType === 'treemap') {
    if (!treemapModel.nodes.length || treemapModel.totalValue <= 0) {
      return <div className="text-sm text-muted-foreground">Treemap needs categorical dimensions with positive numeric values.</div>;
    }

    return (
      <div className="w-full">
        {title && <h3 className="text-base font-semibold mb-2">{title}</h3>}
        <p className="text-xs text-muted-foreground mb-2">
          Hierarchy: {treemapModel.hierarchyKeys.join(' > ')} | Total {primarySeries}: {treemapModel.totalValue.toLocaleString()}
        </p>
        <div style={{ width: '100%', height }}>
          <ResponsiveContainer>
            <Treemap
              data={treemapModel.nodes}
              dataKey="value"
              stroke="#e2e8f0"
              content={<TreemapCellRenderer />}
              aspectRatio={4 / 3}
              isAnimationActive={false}
            >
              <Tooltip content={<TreemapHoverTooltip valueKey={primarySeries} />} />
            </Treemap>
          </ResponsiveContainer>
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
