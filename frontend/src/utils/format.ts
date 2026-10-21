const integerFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

export function formatCount(value: number | null | undefined): string {
  return value == null ? "—" : integerFormatter.format(value);
}

const costFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 3,
});

export function formatCost(value: number | null | undefined): string {
  return value == null ? "—" : costFormatter.format(value);
}
