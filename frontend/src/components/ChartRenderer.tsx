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

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const shiftColorLightness = (color: string, lightnessDelta: number): string => {
  const parsedColor = new THREE.Color(color);
  const hsl = { h: 0, s: 0, l: 0 };
  parsedColor.getHSL(hsl);

  const adjusted = new THREE.Color();
  adjusted.setHSL(hsl.h, hsl.s, clamp(hsl.l + lightnessDelta, 0, 1));
  return `#${adjusted.getHexString()}`;
};

interface Bar3DShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
}

const BAR_3D_DEPTH_X = 10;
const BAR_3D_DEPTH_Y = 7;

const Bar3DShape: React.FC<Bar3DShapeProps> = ({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  fill = COLORS[0],
}) => {
  const normalizedY = height >= 0 ? y : y + height;
  const normalizedHeight = Math.abs(height);

  if (width <= 0 || normalizedHeight <= 0) {
    return null;
  }

  const depthX = Math.min(BAR_3D_DEPTH_X, Math.max(4, width * 0.22));
  const depthY = Math.min(BAR_3D_DEPTH_Y, Math.max(3, width * 0.16));
  const topFill = shiftColorLightness(fill, 0.12);
  const sideFill = shiftColorLightness(fill, -0.14);
  const highlightFill = shiftColorLightness(fill, 0.24);

  const frontLeft = x;
  const frontTop = normalizedY;
  const frontRight = x + width;
  const frontBottom = normalizedY + normalizedHeight;

  const topPoints = [
    `${frontLeft},${frontTop}`,
    `${frontLeft + depthX},${frontTop - depthY}`,
    `${frontRight + depthX},${frontTop - depthY}`,
    `${frontRight},${frontTop}`,
  ].join(' ');

  const sidePoints = [
    `${frontRight},${frontTop}`,
    `${frontRight + depthX},${frontTop - depthY}`,
    `${frontRight + depthX},${frontBottom - depthY}`,
    `${frontRight},${frontBottom}`,
  ].join(' ');

  return (
    <g>
      <polygon points={sidePoints} fill={sideFill} opacity={0.96} />
      <polygon points={topPoints} fill={topFill} opacity={0.98} />
      <rect x={frontLeft} y={frontTop} width={width} height={normalizedHeight} fill={fill} />
      <rect
        x={frontLeft + 1}
        y={frontTop + 1}
        width={Math.max(2, width * 0.34)}
        height={Math.max(0, normalizedHeight - 2)}
        fill={highlightFill}
        opacity={0.23}
      />
    </g>
  );
};

interface Pie3DSliceDatum {
  name: string;
  value: number;
  fill: string;
}

interface Pie3DGeometrySlice extends Pie3DSliceDatum {
  startAngle: number;
  endAngle: number;
  topPath: string;
  sidePaths: string[];
  sideFill: string;
  percentage: number;
}

interface Pie3DRendererProps {
  data: Pie3DSliceDatum[];
  height: number;
}

interface Point2D {
  x: number;
  y: number;
}

const TAU = Math.PI * 2;
const PIE_3D_TILT = 0.58;
const PIE_3D_ANGLE_STEP = Math.PI / 64;

const ellipsePoint = (cx: number, cy: number, rx: number, ry: number, angle: number): Point2D => ({
  x: cx + rx * Math.cos(angle),
  y: cy + ry * Math.sin(angle),
});

const buildTopSlicePath = (
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  startAngle: number,
  endAngle: number,
): string => {
  const start = ellipsePoint(cx, cy, rx, ry, startAngle);
  const end = ellipsePoint(cx, cy, rx, ry, endAngle);
  const largeArcFlag = Math.abs(endAngle - startAngle) > Math.PI ? 1 : 0;

  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${rx} ${ry} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`,
    'Z',
  ].join(' ');
};

const splitContiguousIndices = (indices: number[]): number[][] => {
  if (!indices.length) {
    return [];
  }

  const groups: number[][] = [[indices[0]]];
  for (let idx = 1; idx < indices.length; idx += 1) {
    const prev = indices[idx - 1];
    const current = indices[idx];

    if (current === prev + 1) {
      groups[groups.length - 1].push(current);
    } else {
      groups.push([current]);
    }
  }

  return groups;
};

const buildFrontSidePaths = (
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  startAngle: number,
  endAngle: number,
  depth: number,
): string[] => {
  const delta = endAngle - startAngle;
  if (delta <= 0) {
    return [];
  }

  const sampleCount = Math.max(2, Math.ceil(delta / PIE_3D_ANGLE_STEP));
  const angles = Array.from({ length: sampleCount + 1 }, (_, idx) => startAngle + (delta * idx) / sampleCount);
  const points = angles.map((angle) => ellipsePoint(cx, cy, rx, ry, angle));

  const frontIndices = points
    .map((point, idx) => (point.y > cy ? idx : -1))
    .filter((idx) => idx >= 0);

  const groups = splitContiguousIndices(frontIndices);

  return groups
    .map((group) => {
      const segment = group.map((pointIndex) => points[pointIndex]);
      if (segment.length < 2) {
        return null;
      }

      const topEdge = segment
        .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
        .join(' ');
      const bottomEdge = [...segment]
        .reverse()
        .map((point) => `L ${point.x} ${point.y + depth}`)
        .join(' ');

      return `${topEdge} ${bottomEdge} Z`;
    })
    .filter((path): path is string => Boolean(path));
};

const Pie3DRenderer: React.FC<Pie3DRendererProps> = ({ data, height }) => {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = React.useState(0);
  const [hoveredIndex, setHoveredIndex] = React.useState<number | null>(null);
  const [tooltip, setTooltip] = React.useState<{
    x: number;
    y: number;
    name: string;
    value: number;
    percentage: number;
  } | null>(null);

  React.useEffect(() => {
    const node = containerRef.current;
    if (!node) {
      return;
    }

    const updateWidth = () => {
      setContainerWidth(Math.max(320, node.clientWidth));
    };

    updateWidth();

    const observer = new ResizeObserver(() => {
      updateWidth();
    });

    observer.observe(node);

    return () => {
      observer.disconnect();
    };
  }, []);

  const chartHeight = Math.max(240, Math.min(560, Math.round(height * 0.74)));
  const legendMaxHeight = Math.max(72, Math.round(height * 0.2));

  const geometry = React.useMemo(() => {
    const width = containerWidth || 640;
    const svgHeight = chartHeight;

    const radius = Math.min(width * 0.28, svgHeight * 0.38);
    const rx = radius;
    const ry = radius * PIE_3D_TILT;
    const depth = Math.max(20, Math.min(36, radius * 0.24));
    const cx = width / 2;
    const cy = clamp(svgHeight * 0.42, ry + 10, svgHeight - (ry + depth + 12));

    const total = data.reduce((sum, datum) => sum + datum.value, 0);
    if (total <= 0) {
      return {
        width,
        svgHeight,
        slices: [] as Pie3DGeometrySlice[],
        sideElements: [] as Array<{ d: string; fill: string; z: number; key: string }>,
      };
    }

    let cursor = -Math.PI / 2;
    const slices: Pie3DGeometrySlice[] = data.map((datum, idx) => {
      const ratio = datum.value / total;
      const sweep = ratio * TAU;
      const startAngle = cursor;
      const endAngle = cursor + sweep;
      cursor = endAngle;

      return {
        ...datum,
        startAngle,
        endAngle,
        topPath: buildTopSlicePath(cx, cy, rx, ry, startAngle, endAngle),
        sidePaths: buildFrontSidePaths(cx, cy, rx, ry, startAngle, endAngle, depth),
        sideFill: shiftColorLightness(datum.fill, -0.24),
        percentage: ratio * 100,
      };
    });

    const sideElements = slices
      .flatMap((slice, sliceIdx) =>
        slice.sidePaths.map((path, segmentIdx) => ({
          d: path,
          fill: slice.sideFill,
          z: Math.sin((slice.startAngle + slice.endAngle) / 2),
          key: `side-${sliceIdx}-${segmentIdx}`,
        }))
      )
      .sort((a, b) => a.z - b.z);

    return { width, svgHeight, slices, sideElements };
  }, [chartHeight, containerWidth, data]);

  const handleSliceHover = (
    event: React.MouseEvent<SVGPathElement>,
    slice: Pie3DGeometrySlice,
    index: number,
  ) => {
    setHoveredIndex(index);

    const bounds = containerRef.current?.getBoundingClientRect();
    if (!bounds) {
      return;
    }

    setTooltip({
      x: event.clientX - bounds.left + 10,
      y: event.clientY - bounds.top - 12,
      name: slice.name,
      value: slice.value,
      percentage: slice.percentage,
    });
  };

  const clearHover = () => {
    setHoveredIndex(null);
    setTooltip(null);
  };

  const currentTooltip = tooltip;

  return (
    <div className="w-full h-full flex flex-col">
      <div ref={containerRef} className="relative w-full" style={{ height: chartHeight }}>
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${geometry.width} ${geometry.svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {geometry.sideElements.map((side) => (
            <path key={side.key} d={side.d} fill={side.fill} opacity={0.97} />
          ))}

          {geometry.slices.map((slice, idx) => (
            <path
              key={`top-${slice.name}-${idx}`}
              d={slice.topPath}
              fill={slice.fill}
              stroke="rgba(255,255,255,0.88)"
              strokeWidth={1.2}
              onMouseEnter={(event) => handleSliceHover(event, slice, idx)}
              onMouseMove={(event) => handleSliceHover(event, slice, idx)}
              onMouseLeave={clearHover}
              style={{
                cursor: 'pointer',
                filter: hoveredIndex === idx ? 'brightness(1.1)' : undefined,
                transform: hoveredIndex === idx ? 'translateY(-1px)' : undefined,
                transformOrigin: 'center',
              }}
            />
          ))}
        </svg>

        {currentTooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border bg-background/95 px-2.5 py-1.5 text-xs shadow-lg"
            style={{ left: currentTooltip.x, top: currentTooltip.y }}
          >
            <div className="font-semibold text-foreground max-w-64 truncate">{currentTooltip.name}</div>
            <div className="text-muted-foreground">
              {currentTooltip.value.toLocaleString()} ({currentTooltip.percentage.toFixed(1)}%)
            </div>
          </div>
        )}
      </div>

      <div
        className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 overflow-y-auto pr-1"
        style={{ maxHeight: legendMaxHeight }}
      >
        {data.map((item, idx) => (
          <div key={`legend-${item.name}-${idx}`} className="flex items-center gap-1.5 text-xs text-foreground/90">
            <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ backgroundColor: item.fill }} />
            <span>{item.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

type ChartCell = string | number | null;
type ChartRow = Record<string, ChartCell>;

interface Scatter3DPoint {
  x: number;
  y: number;
  z: number;
  size: number;
  color: string;
}

interface Scatter3DAxesMeta {
  xAxis: string;
  yAxis: string;
  zAxis: string;
  sizeKey?: string;
  xRange: [number, number];
  yRange: [number, number];
  zRange: [number, number];
  sizeRange?: [number, number];
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

const denormalizeFromRange = (value: number, min: number, max: number) => {
  if (max <= min) {
    return min;
  }
  return min + ((value + 1) / 2) * (max - min);
};

const formatAxisValue = (value: number) => {
  const absValue = Math.abs(value);

  if (absValue >= 1000) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (absValue >= 1) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
};

const buildScatter3DPoints = (
  rows: ChartRow[],
  xKey: string,
  seriesKeys: string[],
): { points: Scatter3DPoint[]; axes: Scatter3DAxesMeta | null } => {
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

  return {
    points,
    axes: {
      xAxis,
      yAxis,
      zAxis,
      sizeKey: sizeKey || undefined,
      xRange: [xMin, xMax],
      yRange: [yMin, yMax],
      zRange: [zMin, zMax],
      sizeRange: sizeKey ? [sizeMin, sizeMax] : undefined,
    },
  };
};

const Scatter3DScene: React.FC<{ points: Scatter3DPoint[]; axes: Scatter3DAxesMeta; height: number }> = ({ points, axes, height }) => {
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
    controls.target.set(0, 0, 0);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.85);
    directionalLight.position.set(2.8, 2.6, 1.9);
    scene.add(directionalLight);

    const grid = new THREE.GridHelper(2.4, 12, 0xcbd5e1, 0xe2e8f0);
    grid.position.y = -1.05;
    scene.add(grid);

    const lineGeometries: THREE.BufferGeometry[] = [];
    const lineMaterials: THREE.Material[] = [];
    const labelTextures: THREE.Texture[] = [];
    const labelMaterials: THREE.Material[] = [];

    const addLine = (start: THREE.Vector3, end: THREE.Vector3, color: string) => {
      const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
      const material = new THREE.LineBasicMaterial({ color: new THREE.Color(color) });
      const line = new THREE.Line(geometry, material);
      scene.add(line);
      lineGeometries.push(geometry);
      lineMaterials.push(material);
    };

    const createTextSprite = (text: string, color = '#0f172a') => {
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      if (!context) {
        return null;
      }

      const fontSize = 46;
      const font = `600 ${fontSize}px "Segoe UI", sans-serif`;
      context.font = font;
      const metrics = context.measureText(text);
      const textWidth = Math.ceil(metrics.width);
      const horizontalPadding = 22;
      const verticalPadding = 14;

      canvas.width = textWidth + horizontalPadding * 2;
      canvas.height = fontSize + verticalPadding * 2;

      context.font = font;
      context.textBaseline = 'middle';
      context.fillStyle = 'rgba(248, 250, 252, 0.95)';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = color;
      context.fillText(text, horizontalPadding, canvas.height / 2);

      const texture = new THREE.CanvasTexture(canvas);
      texture.needsUpdate = true;
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;

      const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      });

      const sprite = new THREE.Sprite(material);
      const spriteWidth = Math.max(0.22, Math.min(0.56, text.length * 0.048));
      sprite.scale.set(spriteWidth, 0.09, 1);

      labelTextures.push(texture);
      labelMaterials.push(material);

      return sprite;
    };

    const addLabel = (text: string, position: THREE.Vector3, color?: string) => {
      const sprite = createTextSprite(text, color);
      if (!sprite) {
        return;
      }
      sprite.position.copy(position);
      scene.add(sprite);
    };

    const axisBase = -1.1;
    const axisTop = 1.1;
    const tickMarks = [-1, 0, 1];

    addLine(
      new THREE.Vector3(axisBase, axisBase, axisBase),
      new THREE.Vector3(axisTop, axisBase, axisBase),
      '#ef4444'
    );
    addLine(
      new THREE.Vector3(axisBase, axisBase, axisBase),
      new THREE.Vector3(axisBase, axisTop, axisBase),
      '#22c55e'
    );
    addLine(
      new THREE.Vector3(axisBase, axisBase, axisBase),
      new THREE.Vector3(axisBase, axisBase, axisTop),
      '#3b82f6'
    );

    tickMarks.forEach((tick) => {
      addLine(
        new THREE.Vector3(tick, axisBase, axisBase),
        new THREE.Vector3(tick, axisBase + 0.05, axisBase),
        '#64748b'
      );
      addLabel(
        formatAxisValue(denormalizeFromRange(tick, axes.xRange[0], axes.xRange[1])),
        new THREE.Vector3(tick, axisBase - 0.08, axisBase),
      );

      addLine(
        new THREE.Vector3(axisBase, tick, axisBase),
        new THREE.Vector3(axisBase + 0.05, tick, axisBase),
        '#64748b'
      );
      addLabel(
        formatAxisValue(denormalizeFromRange(tick, axes.yRange[0], axes.yRange[1])),
        new THREE.Vector3(axisBase - 0.12, tick, axisBase),
      );

      addLine(
        new THREE.Vector3(axisBase, axisBase, tick),
        new THREE.Vector3(axisBase, axisBase + 0.05, tick),
        '#64748b'
      );
      addLabel(
        formatAxisValue(denormalizeFromRange(tick, axes.zRange[0], axes.zRange[1])),
        new THREE.Vector3(axisBase - 0.1, axisBase - 0.1, tick),
      );
    });

    addLabel(axes.xAxis, new THREE.Vector3(axisTop + 0.17, axisBase, axisBase), '#991b1b');
    addLabel(axes.yAxis, new THREE.Vector3(axisBase, axisTop + 0.14, axisBase), '#166534');
    addLabel(axes.zAxis, new THREE.Vector3(axisBase, axisBase, axisTop + 0.16), '#1d4ed8');

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
      lineGeometries.forEach((geometry) => geometry.dispose());
      lineMaterials.forEach((material) => material.dispose());
      labelTextures.forEach((texture) => texture.dispose());
      labelMaterials.forEach((material) => material.dispose());
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [points, axes, height]);

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
  const pie3DData = React.useMemo(() => {
    if (safeType !== 'pie' || !typedData.length || !primarySeries) {
      return [] as Pie3DSliceDatum[];
    }

    return typedData
      .map((row, idx) => {
        const numericValue = toNumber(row[primarySeries]);
        if (numericValue === null || numericValue <= 0) {
          return null;
        }

        const rawName = row[xKey];
        const name = String(rawName ?? `Segment ${idx + 1}`).trim() || `Segment ${idx + 1}`;

        return {
          name,
          value: numericValue,
          fill: COLORS[idx % COLORS.length],
        };
      })
      .filter((item): item is Pie3DSliceDatum => item !== null);
  }, [safeType, typedData, primarySeries, xKey]);

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

    const axes = scatter3D.axes;

    return (
      <div className="w-full">
        {title && <h3 className="text-base font-semibold mb-2">{title}</h3>}
        <p className="text-xs text-muted-foreground mb-2">
          3D axes: x = {axes.xAxis}, y = {axes.yAxis}, z = {axes.zAxis}
          {axes.sizeKey ? `, bubble size = ${axes.sizeKey}` : ''}
        </p>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 mb-2">
          <div className="rounded-md border bg-muted/25 px-2.5 py-2 text-xs">
            <span className="font-medium text-foreground">{axes.xAxis}</span>
            <span className="text-muted-foreground">: {formatAxisValue(axes.xRange[0])} to {formatAxisValue(axes.xRange[1])}</span>
          </div>
          <div className="rounded-md border bg-muted/25 px-2.5 py-2 text-xs">
            <span className="font-medium text-foreground">{axes.yAxis}</span>
            <span className="text-muted-foreground">: {formatAxisValue(axes.yRange[0])} to {formatAxisValue(axes.yRange[1])}</span>
          </div>
          <div className="rounded-md border bg-muted/25 px-2.5 py-2 text-xs">
            <span className="font-medium text-foreground">{axes.zAxis}</span>
            <span className="text-muted-foreground">: {formatAxisValue(axes.zRange[0])} to {formatAxisValue(axes.zRange[1])}</span>
          </div>
        </div>

        <div style={{ width: '100%', height }} className="rounded-md border overflow-hidden">
          <Scatter3DScene points={scatter3D.points} axes={axes} height={height} />
        </div>
        <p className="text-[11px] text-muted-foreground mt-2">
          Axis tick labels in the scene show min, midpoint, and max values. Drag to rotate and inspect.
        </p>
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

  if (safeType === 'pie') {
    if (!pie3DData.length) {
      return <div className="text-sm text-muted-foreground">Pie chart needs positive numeric values.</div>;
    }

    return (
      <div className="w-full">
        {title && <h3 className="text-base font-semibold mb-3">{title}</h3>}
        <Pie3DRenderer data={pie3DData} height={height} />
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
            <ComposedChart data={data} margin={{ top: 20, right: 24, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) =>
                idx % 2 === 0 ? (
                  <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} shape={<Bar3DShape />} />
                ) : (
                  <Line key={key} type="monotone" dataKey={key} stroke={COLORS[idx % COLORS.length]} strokeWidth={2} dot={false} />
                )
              )}
            </ComposedChart>
          ) : (
            <BarChart data={data} margin={{ top: 20, right: 24, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {fallbackSeries.map((key, idx) => (
                <Bar key={key} dataKey={key} fill={COLORS[idx % COLORS.length]} shape={<Bar3DShape />} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ChartRenderer;
