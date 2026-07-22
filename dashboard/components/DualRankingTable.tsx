import { ArrowUp, ArrowDown, Minus, MapPin, Search } from "lucide-react";
import type { DualRanking } from "@/lib/stubs";
import { rankDelta } from "@/lib/stats";

interface DualRankingTableProps {
  data: DualRanking[];
}

function DeltaCell({ delta }: { delta: number }) {
  const { direction, magnitude } = rankDelta(delta);
  if (direction === "none") {
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground/70">
        <Minus className="h-3 w-3" /> No change
      </span>
    );
  }
  if (direction === "up") {
    return (
      <span className="inline-flex items-center gap-1 text-chart-3">
        <ArrowUp className="h-3 w-3" /> Up {magnitude}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-destructive">
      <ArrowDown className="h-3 w-3" /> Down {magnitude}
    </span>
  );
}

export default function DualRankingTable({ data }: DualRankingTableProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <Search className="h-3.5 w-3.5" />
          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-muted-foreground">
            #n
          </span>
          Organic web rank
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <MapPin className="h-3.5 w-3.5" />
          <span className="rounded bg-chart-4/10 px-1.5 py-0.5 font-mono text-chart-4">
            #n
          </span>
          Google Maps Local Pack rank
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th rowSpan={2} className="pb-2 pr-4 align-bottom">
                Keyword
              </th>
              <th colSpan={2} className="pb-1 pr-4">
                Organic
              </th>
              <th colSpan={2} className="pb-1 pr-4 text-chart-4">
                Google Maps Local Pack
              </th>
            </tr>
            <tr className="border-b border-border text-left text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
              <th className="pb-2 pr-4">This week</th>
              <th className="pb-2 pr-4">Change</th>
              <th className="pb-2 pr-4">This week</th>
              <th className="pb-2 pr-4">Change</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={row.keyword}
                className="border-b border-border last:border-0"
              >
                <td className="py-3 pr-4 font-medium text-foreground">
                  {row.keyword}
                </td>
                <td className="py-3 pr-4">
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                    #{row.organicThisWeek}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <DeltaCell delta={row.organicDelta} />
                </td>
                <td className="py-3 pr-4">
                  <span className="rounded bg-chart-4/10 px-1.5 py-0.5 font-mono text-xs text-chart-4">
                    #{row.localPackThisWeek}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <DeltaCell delta={row.localPackDelta} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
