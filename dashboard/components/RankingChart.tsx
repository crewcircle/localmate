import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import type { Ranking } from "@/lib/stubs";

interface RankingChartProps {
  data: Ranking[];
}

export default function RankingChart({ data }: RankingChartProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs font-medium uppercase tracking-wide text-gray-500">
            <th className="pb-2 pr-4">Keyword</th>
            <th className="pb-2 pr-4">Last Week</th>
            <th className="pb-2 pr-4">This Week</th>
            <th className="pb-2 pr-4">Change</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const delta = row.lastWeek - row.thisWeek;
            const improved = delta > 0;
            const worsened = delta < 0;
            return (
              <tr
                key={row.keyword}
                className="border-b last:border-0"
              >
                <td className="py-2 pr-4 font-medium text-gray-900">
                  {row.keyword}
                </td>
                <td className="py-2 pr-4 text-gray-600">{row.lastWeek}</td>
                <td className="py-2 pr-4 text-gray-600">{row.thisWeek}</td>
                <td className="py-2 pr-4">
                  {delta === 0 ? (
                    <span className="inline-flex items-center gap-1 text-gray-400">
                      <Minus className="h-3 w-3" /> No change
                    </span>
                  ) : improved ? (
                    <span className="inline-flex items-center gap-1 text-green-600">
                      <ArrowUp className="h-3 w-3" /> Up {delta}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-red-600">
                      <ArrowDown className="h-3 w-3" /> Down {Math.abs(delta)}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
