export type RGB = [number, number, number];

export const DEFAULT_CLUSTER_COLOR: RGB = [128, 132, 140];

function hslToRgb(h: number, s: number, l: number): RGB {
  const hue = ((h % 360) + 360) % 360;
  const chroma = (1 - Math.abs(2 * l - 1)) * s;
  const segment = hue / 60;
  const x = chroma * (1 - Math.abs((segment % 2) - 1));

  let rPrime = 0;
  let gPrime = 0;
  let bPrime = 0;

  if (segment >= 0 && segment < 1) {
    rPrime = chroma;
    gPrime = x;
  } else if (segment >= 1 && segment < 2) {
    rPrime = x;
    gPrime = chroma;
  } else if (segment >= 2 && segment < 3) {
    gPrime = chroma;
    bPrime = x;
  } else if (segment >= 3 && segment < 4) {
    gPrime = x;
    bPrime = chroma;
  } else if (segment >= 4 && segment < 5) {
    rPrime = x;
    bPrime = chroma;
  } else if (segment >= 5 && segment < 6) {
    rPrime = chroma;
    bPrime = x;
  }

  const match = l - chroma / 2;
  const r = Math.round((rPrime + match) * 255);
  const g = Math.round((gPrime + match) * 255);
  const b = Math.round((bPrime + match) * 255);

  return [r, g, b];
}

export function colorForClusterId(clusterId: number | null | undefined): RGB {
  if (clusterId == null || clusterId < 0 || !Number.isFinite(clusterId)) {
    return DEFAULT_CLUSTER_COLOR;
  }

  const hue = (clusterId * 137.508) % 360;
  const saturation = 0.58;
  const lightness = 0.55;

  return hslToRgb(hue, saturation, lightness);
}

export function rgbToCss(color: RGB, alpha = 1): string {
  const [r, g, b] = color;
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;
}

export function rgbToHex(color: RGB): string {
  const [r, g, b] = color.map((component) =>
    Math.max(0, Math.min(255, Math.round(component))),
  ) as RGB;

  const value = (r << 16) | (g << 8) | b;
  return `#${value.toString(16).padStart(6, "0")}`;
}

export const GREY_CLUSTER_LABEL = "N/A";
