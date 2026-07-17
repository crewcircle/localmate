export default function DemoBadge({ className }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-chart-2 cursor-help ${className ?? ""}`}
      title="This feature is coming in the next release"
    >
      <span>⚠</span> DEMO
    </span>
  );
}
